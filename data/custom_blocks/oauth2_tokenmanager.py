# coding: UTF-8
"""
OAuth2 TokenManager für KNX Automation
Unterstützt: Netatmo und andere OAuth2 APIs
Mit Auth Code Flow und Auto-Refresh

Author: Reinhard
Version: 1.1
"""
import json
import logging
import asyncio
import aiohttp
import os
from datetime import datetime
from urllib.parse import urlencode
from typing import Optional, Dict, Any

from logic.base import LogicBlock  # or: from ..base import LogicBlock (if in subpackage)

logger = logging.getLogger(__name__)


class OAuth2TokenManager(LogicBlock):
    """OAuth2 Token Manager - AuthCode Flow + Auto-Refresh"""
    
    ID = 20031
    NAME = "OAuth2 TokenManager"
    DESCRIPTION = "OAuth2 Token Management mit AuthCode Flow + Auto-Refresh (Netatmo, etc.)"
    CATEGORY = "Netzwerk"
    VERSION = "1.1"
    AUTHOR = "Reinhard"
    
    INPUTS = {
        'E1': {'name': 'Start/Stop (1/0)', 'type': 'bool', 'default': True},
        'E2': {'name': 'Manuell Refresh', 'type': 'bool', 'default': False},
        'E3': {'name': 'Client ID', 'type': 'str', 'default': ''},
        'E4': {'name': 'Client Secret', 'type': 'str', 'default': ''},
        'E5': {'name': 'Refresh Token (nur bei Änderung)', 'type': 'str', 'default': ''},
        'E6': {'name': 'Token URL', 'type': 'str', 'default': 'https://api.netatmo.com/oauth2/token'},
        'E7': {'name': 'Scope', 'type': 'str', 'default': 'read_station'},
        'E8': {'name': 'Auth Code (vom Redirect)', 'type': 'str', 'default': ''},
        'E9': {'name': 'Redirect URI', 'type': 'str', 'default': 'http://localhost'},
        'E10': {'name': 'State (optional)', 'type': 'str', 'default': 'knx_automation'},
        'E11': {'name': 'Auth Base URL', 'type': 'str', 'default': 'https://api.netatmo.com/oauth2/authorize'},
    }
    
    OUTPUTS = {
        'A1': {'name': 'Access Token', 'type': 'str', 'default': ''},
        'A2': {'name': 'Expires In (Sek)', 'type': 'int', 'default': 0},
        'A3': {'name': 'Status (1=OK, 0=ERR)', 'type': 'int', 'default': 0},
        'A4': {'name': 'Fehlermeldung', 'type': 'str', 'default': ''},
        'A5': {'name': 'Ready (1=Token gültig)', 'type': 'int', 'default': 0},
        'A6': {'name': 'Next Refresh (Unix)', 'type': 'int', 'default': 0},
        'A7': {'name': 'Auth URL', 'type': 'str', 'default': ''},
        'A8': {'name': 'Token Quelle', 'type': 'str', 'default': ''},
        'A9': {'name': 'Last Refresh (Unix)', 'type': 'int', 'default': 0},
        'A10': {'name': 'Neuer Refresh Token', 'type': 'str', 'default': ''},
    }
    
    REFRESH_BUFFER = 300  # 5 Minuten vor Ablauf refreshen
    TOKEN_FILE = "oauth2_tokens_{instance_id}.json"  # Persistenz-Datei
    
    def on_start(self):
        """Block gestartet"""
        self._running = True
        logger.info("[{}] OAuth2 TokenManager v{} starting...".format(self.ID, self.VERSION))
        
        # Interne Variablen für Token-Speicherung
        self._rem_access_token = ''
        self._rem_refresh_token = ''
        self._rem_expires_at = 0.0
        self._last_auth_code = ''
        self._last_input_rt = ''
        
        # Daemon Task
        self._daemon_task: Optional[asyncio.Task] = None
        self._next_action_ts = 0  # 0 = sofort
        
        # Debug
        self._debug_values['Status'] = 'Init'
        self._debug_values['Token Source'] = '-'
        self._debug_values['Expires'] = '-'
        self._debug_values['Version'] = self.VERSION
        
        # Tokens aus Datei laden
        self._load_tokens()
        
        # Auth URL setzen
        self._update_auth_url()
        
        # Initial Output
        self._set_outputs('', 0, 0, 'Init', 0, 0, '', '-', 0, '')
        
        # Bei gültigem Token: sofort publishen
        now = int(datetime.now().timestamp())
        remaining = max(0, int(self._rem_expires_at - now)) if self._rem_expires_at > 0 else 0
        if self._rem_access_token and remaining > 60:
            logger.info("[{}] Restored token from file, {}s remaining".format(self.ID, remaining))
            next_refresh = int(self._rem_expires_at) - self.REFRESH_BUFFER
            if next_refresh < now + 60:
                next_refresh = now + 60
            self._set_outputs(
                self._rem_access_token, remaining, 1, 'OK', 1, 
                next_refresh, '', 'File', 0, self._rem_refresh_token
            )
            self._next_action_ts = next_refresh
        
        # Start daemon if enabled
        if self.get_input('E1'):
            self._start_daemon()
    
    def on_stop(self):
        """Block gestoppt"""
        self._running = False
        if self._daemon_task and not self._daemon_task.done():
            self._daemon_task.cancel()
        logger.info("[{}] OAuth2 TokenManager stopped".format(self.ID))
    
    def _get_token_file_path(self) -> str:
        """Pfad zur Token-Datei"""
        filename = self.TOKEN_FILE.format(instance_id=self.instance_id)
        # Im gleichen Verzeichnis wie das Skript speichern
        script_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(script_dir, filename)
    
    def _load_tokens(self):
        """Tokens aus JSON-Datei laden"""
        try:
            filepath = self._get_token_file_path()
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    data = json.load(f)
                self._rem_access_token = data.get('access_token', '')
                self._rem_refresh_token = data.get('refresh_token', '')
                self._rem_expires_at = float(data.get('expires_at', 0))
                self._last_auth_code = data.get('last_auth_code', '')
                self._last_input_rt = data.get('last_input_rt', '')
                logger.info("[{}] Loaded tokens from {}".format(self.ID, filepath))
        except Exception as e:
            logger.warning("[{}] Could not load tokens: {}".format(self.ID, e))
    
    def _save_tokens(self):
        """Tokens in JSON-Datei speichern"""
        try:
            filepath = self._get_token_file_path()
            data = {
                'access_token': self._rem_access_token,
                'refresh_token': self._rem_refresh_token,
                'expires_at': self._rem_expires_at,
                'last_auth_code': self._last_auth_code,
                'last_input_rt': self._last_input_rt,
                'saved_at': datetime.now().isoformat()
            }
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug("[{}] Saved tokens to {}".format(self.ID, filepath))
        except Exception as e:
            logger.error("[{}] Could not save tokens: {}".format(self.ID, e))
    
    def _update_auth_url(self):
        """Build OAuth2 Authorization URL"""
        client_id = self.get_input('E3') or ''
        redirect_uri = self.get_input('E9') or 'http://localhost'
        scope = self.get_input('E7') or ''
        state = self.get_input('E10') or 'knx_automation'
        auth_base = self.get_input('E11') or 'https://api.netatmo.com/oauth2/authorize'
        
        if not client_id or not redirect_uri or not auth_base:
            self.set_output('A7', '')
            return ''
        
        # Clean up scope
        scope = ' '.join(scope.replace(',', ' ').replace('+', ' ').split())
        
        params = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'scope': scope,
            'state': state,
            'response_type': 'code',
        }
        
        auth_url = auth_base.rstrip('?') + '?' + urlencode(params)
        self.set_output('A7', auth_url)
        return auth_url
    
    def _set_outputs(self, access: str, expires_in: int, status: int, error: str, 
                     ready: int, next_refresh: int, auth_url: str, source: str, 
                     last_ref: int, new_rt: str = ''):
        """Set all outputs at once"""
        self.set_output('A1', access if access else '')
        self.set_output('A2', expires_in)
        self.set_output('A3', status)
        self.set_output('A4', error if error else 'OK')
        self.set_output('A5', ready)
        self.set_output('A6', next_refresh)
        if auth_url:
            self.set_output('A7', auth_url)
        self.set_output('A8', source if source else '')
        self.set_output('A9', last_ref)
        self.set_output('A10', new_rt if new_rt else '')
        
        # Debug update
        self._debug_values['Status'] = error if error else 'OK'
        self._debug_values['Token Source'] = source
        self._debug_values['Expires'] = '{}s'.format(expires_in) if expires_in > 0 else '-'
    
    def _start_daemon(self):
        """Start the daemon loop"""
        if self._daemon_task and not self._daemon_task.done():
            self._daemon_task.cancel()
        self._running = True
        self._daemon_task = asyncio.create_task(self._daemon_loop())
        logger.info("[{}] Daemon started".format(self.ID))
    
    def _stop_daemon(self):
        """Stop the daemon"""
        self._running = False
        if self._daemon_task and not self._daemon_task.done():
            self._daemon_task.cancel()
        self._set_outputs('', 0, 0, 'Stopped', 0, 0, '', '', 0, '')
        logger.info("[{}] Daemon stopped".format(self.ID))
    
    async def _daemon_loop(self):
        """Main daemon loop - mirrors EDOMI EXEC block logic"""
        logger.info("[{}] Daemon loop started".format(self.ID))
        
        while self._running:
            try:
                # Check if stopped
                if not self.get_input('E1'):
                    self._set_outputs('', 0, 0, 'Stopped', 0, 0, '', '', 0, '')
                    self._debug_values['Status'] = 'Gestoppt'
                    await asyncio.sleep(2)
                    continue
                
                await self._process_tokens()
                
                # Responsive sleep like EDOMI
                now = int(datetime.now().timestamp())
                sleep_time = self._next_action_ts - now
                if sleep_time <= 0:
                    await asyncio.sleep(0.2)  # 200ms like EDOMI
                else:
                    await asyncio.sleep(min(5, sleep_time))
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("[{}] Daemon error: {}".format(self.ID, e))
                self._debug_values['Status'] = 'Fehler: {}'.format(str(e)[:30])
                await asyncio.sleep(5)
        
        logger.info("[{}] Daemon loop ended".format(self.ID))
    
    async def _process_tokens(self):
        """Process token logic - mirrors EDOMI EXEC while-loop"""
        now = int(datetime.now().timestamp())
        
        # Get inputs
        client_id = (self.get_input('E3') or '').strip()
        client_secret = (self.get_input('E4') or '').strip()
        input_rt = (self.get_input('E5') or '').strip()
        token_url = (self.get_input('E6') or '').strip()
        scope = (self.get_input('E7') or '').strip()
        auth_code = (self.get_input('E8') or '').strip()
        redirect_uri = (self.get_input('E9') or 'http://localhost').strip()
        
        # Token state
        rem_access = self._rem_access_token
        rem_rt = self._rem_refresh_token
        rem_exp_at = int(self._rem_expires_at)
        
        # Token remaining
        remaining = max(0, rem_exp_at - now) if rem_exp_at > 0 else 0
        token_valid = rem_access != '' and remaining > 60
        
        # Build Auth URL if token not valid
        auth_url = ''
        if not token_valid:
            auth_url = self._update_auth_url()
        
        # 1) AUTH CODE FLOW: wenn neuer Code gesetzt wurde
        if auth_code and auth_code != self._last_auth_code:
            logger.info("[{}] New AuthCode detected (len={})".format(self.ID, len(auth_code)))
            self._last_auth_code = auth_code
            self._save_tokens()
            
            if not all([client_id, client_secret, token_url, redirect_uri]):
                self._set_outputs('', 0, 0, 'Missing client/secret/url/redirect', 0, 0, auth_url, 'AuthCode', 0, '')
                return
            
            success = await self._exchange_auth_code(
                auth_code, client_id, client_secret, token_url, redirect_uri, scope
            )
            if not success:
                await asyncio.sleep(5)
            return
        
        # 2) INPUT REFRESH TOKEN: nur bei Änderung übernehmen
        if input_rt and input_rt != self._last_input_rt:
            logger.info("[{}] Input RT changed -> store + refresh".format(self.ID))
            self._last_input_rt = input_rt
            self._rem_refresh_token = input_rt
            self._save_tokens()
            self._next_action_ts = now  # sofort refresh
            token_valid = False
            rem_rt = input_rt
        
        # 3) TOKEN VALID: publish + refresh planen
        if token_valid:
            refresh_at = rem_exp_at - self.REFRESH_BUFFER
            
            # Zeit zum Refresh? (5 Min vor Ablauf)
            if now >= refresh_at:
                logger.info("[{}] Token expiring soon ({}s left), refreshing...".format(self.ID, remaining))
                await self._do_refresh(client_id, client_secret, token_url, scope)
                return
            
            # Noch nicht fällig - publish und warten
            self._set_outputs(rem_access, remaining, 1, 'OK', 1, refresh_at, '', 'File', 0, rem_rt)
            self._next_action_ts = refresh_at
            return
        
        # 4) KEIN GÜLTIGER TOKEN: Refresh mit gespeichertem RT (wenn vorhanden)
        rem_rt = (rem_rt or '').strip()
        if not rem_rt:
            self._set_outputs('', 0, 0, 'No refresh token (warte auf AuthCode/RT)', 0, 0, auth_url, 'File', 0, '')
            await asyncio.sleep(2)
            return
        
        # Warten auf next_action_ts?
        if self._next_action_ts > now:
            return
        
        # Missing params?
        if not all([client_id, client_secret, token_url]):
            self._set_outputs('', 0, 0, 'Missing client/secret/url', 0, 0, auth_url, 'File', 0, '')
            await asyncio.sleep(2)
            return
        
        # Do refresh
        await self._do_refresh(client_id, client_secret, token_url, scope)
    
    async def _exchange_auth_code(self, code: str, client_id: str, client_secret: str,
                                   token_url: str, redirect_uri: str, scope: str) -> bool:
        """Exchange authorization code for tokens"""
        now = int(datetime.now().timestamp())
        self._debug_values['Status'] = 'AuthCode Exchange...'
        
        try:
            data = {
                'grant_type': 'authorization_code',
                'client_id': client_id,
                'client_secret': client_secret,
                'code': code,
                'redirect_uri': redirect_uri,
            }
            if scope:
                data['scope'] = scope
            
            logger.info("[{}] POST grant=authorization_code to {}".format(self.ID, token_url))
            
            async with aiohttp.ClientSession() as session:
                async with session.post(token_url, data=data,
                                        timeout=aiohttp.ClientTimeout(total=25)) as response:
                    text = await response.text()
                    logger.info("[{}] HTTP {}, body={}".format(self.ID, response.status, text[:200]))
                    
                    if response.status != 200:
                        auth_url = self._update_auth_url()
                        self._set_outputs('', 0, 0, 'HTTP {}: {}'.format(response.status, text[:100]), 0, 0, auth_url, 'AuthCode', 0, '')
                        return False
                    
                    result = json.loads(text)
                    
                    access_token = result.get('access_token', '')
                    refresh_token = result.get('refresh_token', '')
                    expires_in = int(result.get('expires_in', 0) or 0)
                    
                    if not access_token:
                        auth_url = self._update_auth_url()
                        self._set_outputs('', 0, 0, 'No access_token in response', 0, 0, auth_url, 'AuthCode', 0, '')
                        return False
                    
                    if not refresh_token:
                        auth_url = self._update_auth_url()
                        self._set_outputs('', 0, 0, 'No refresh_token returned', 0, 0, auth_url, 'AuthCode', 0, '')
                        return False
                    
                    # Save tokens
                    exp_at = now + max(60, expires_in)
                    self._rem_access_token = access_token
                    self._rem_refresh_token = refresh_token
                    self._rem_expires_at = exp_at
                    self._save_tokens()
                    
                    # Next refresh
                    next_refresh = exp_at - self.REFRESH_BUFFER
                    if next_refresh < now + 60:
                        next_refresh = now + 60
                    self._next_action_ts = next_refresh
                    
                    self._set_outputs(access_token, expires_in, 1, 'OK', 1, next_refresh, '', 'AuthCode', now, refresh_token)
                    logger.info("[{}] AuthCode exchange successful, expires in {}s".format(self.ID, expires_in))
                    return True
                    
        except Exception as e:
            logger.error("[{}] AuthCode exchange error: {}".format(self.ID, e))
            auth_url = self._update_auth_url()
            self._set_outputs('', 0, 0, str(e)[:80], 0, 0, auth_url, 'AuthCode', 0, '')
            return False
    
    async def _do_refresh(self, client_id: str, client_secret: str, token_url: str, scope: str) -> bool:
        """Refresh access token using refresh token"""
        now = int(datetime.now().timestamp())
        refresh_token = self._rem_refresh_token
        
        if not all([client_id, client_secret, token_url, refresh_token]):
            auth_url = self._update_auth_url()
            self._set_outputs('', 0, 0, 'Missing params for refresh', 0, 0, auth_url, 'File', 0, '')
            return False
        
        self._debug_values['Status'] = 'Refreshing...'
        
        try:
            data = {
                'grant_type': 'refresh_token',
                'client_id': client_id,
                'client_secret': client_secret,
                'refresh_token': refresh_token,
            }
            if scope:
                data['scope'] = scope
            
            logger.info("[{}] POST grant=refresh_token to {}".format(self.ID, token_url))
            
            async with aiohttp.ClientSession() as session:
                async with session.post(token_url, data=data,
                                        timeout=aiohttp.ClientTimeout(total=25)) as response:
                    text = await response.text()
                    logger.info("[{}] HTTP {}, body={}".format(self.ID, response.status, text[:200]))
                    
                    if response.status != 200:
                        auth_url = self._update_auth_url()
                        self._set_outputs('', 0, 0, 'HTTP {}: {}'.format(response.status, text[:100]), 0, 0, auth_url, 'File', 0, '')
                        
                        # Bei 400/401: Tokens löschen, Auth URL zeigen
                        if response.status in [400, 401]:
                            self._rem_access_token = ''
                            self._rem_refresh_token = ''
                            self._rem_expires_at = 0
                            self._save_tokens()
                        return False
                    
                    result = json.loads(text)
                    
                    access_token = result.get('access_token', '')
                    new_refresh_token = result.get('refresh_token', refresh_token) or refresh_token
                    expires_in = int(result.get('expires_in', 0) or 0)
                    
                    if not access_token:
                        auth_url = self._update_auth_url()
                        self._set_outputs('', 0, 0, 'No access_token in response', 0, 0, auth_url, 'File', 0, '')
                        return False
                    
                    # Save tokens
                    exp_at = now + max(60, expires_in)
                    self._rem_access_token = access_token
                    self._rem_refresh_token = new_refresh_token
                    self._rem_expires_at = exp_at
                    self._save_tokens()
                    
                    # Next refresh
                    next_refresh = exp_at - self.REFRESH_BUFFER
                    if next_refresh < now + 60:
                        next_refresh = now + 60
                    self._next_action_ts = next_refresh
                    
                    self._set_outputs(access_token, expires_in, 1, 'OK', 1, next_refresh, '', 'Refresh', now, new_refresh_token)
                    logger.info("[{}] Token refresh successful, expires in {}s".format(self.ID, expires_in))
                    return True
                    
        except Exception as e:
            logger.error("[{}] Refresh error: {}".format(self.ID, e))
            auth_url = self._update_auth_url()
            self._set_outputs('', 0, 0, str(e)[:80], 0, 0, auth_url, 'File', 0, '')
            return False
    
    def on_input_change(self, key: str, value: Any, old_value: Any):
        """Input changed"""
        logger.info("[{}] Input {} changed: {} -> {}".format(self.ID, key, old_value, value))
        
        # E1: Start/Stop
        if key == 'E1':
            if value:
                self._debug_values['Status'] = 'Gestartet'
                self._start_daemon()
            else:
                self._stop_daemon()
        
        # E2: Manuell Refresh
        elif key == 'E2' and value:
            logger.info("[{}] Manual refresh triggered".format(self.ID))
            self._next_action_ts = 0  # sofort
            if not self._running:
                self._start_daemon()
        
        # E5: Refresh Token Input - nur bei Änderung
        elif key == 'E5':
            new_rt = (value or '').strip()
            if new_rt and new_rt != self._last_input_rt:
                logger.info("[{}] New RT from input detected".format(self.ID))
                self._next_action_ts = 0  # sofort
                if not self._running:
                    self._start_daemon()
        
        # E8: Auth Code - nur bei Änderung
        elif key == 'E8':
            new_code = (value or '').strip()
            old_code = (old_value or '').strip() if old_value else ''
            if new_code and new_code != old_code and new_code != self._last_auth_code:
                logger.info("[{}] New Auth Code detected".format(self.ID))
                self._next_action_ts = 0  # sofort
                if not self._running:
                    self._start_daemon()
        
        # Auth URL relevante Inputs
        elif key in ('E3', 'E7', 'E9', 'E10', 'E11'):
            self._update_auth_url()
    
    def execute(self, triggered_by: str = None):
        """Execute - handled by daemon loop"""
        pass
    
    def get_access_token(self) -> str:
        """Public method for other blocks to get token"""
        if self._rem_access_token and self._rem_expires_at > datetime.now().timestamp() + 30:
            return self._rem_access_token
        return ''
