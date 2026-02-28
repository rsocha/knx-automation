"""
FRITZ!DECT 200/210 Controller LogicBlock (v1.0)

Steuert und überwacht eine AVM FRITZ!DECT 200/210 Steckdose über die
FRITZ!Box AHA-HTTP-Schnittstelle (homeautoswitch.lua).

Funktionen:
- Ein/Aus/Toggle
- Leistungsmessung (W, mW)
- Energiemessung (Wh, kWh)
- Kostenberechnung
- Temperaturmessung
- Verbindungsstatus
- Session-Management mit automatischer Erneuerung

Basiert auf der AVM AHA-HTTP-Interface Spezifikation.
"""

import asyncio
import aiohttp
import hashlib
import logging
import re
import time
from typing import Optional

try:
    from ..base import LogicBlock
except ImportError:
    from logic.base import LogicBlock

logger = logging.getLogger(__name__)


class FritzDect200(LogicBlock):
    """FRITZ!DECT 200/210 Controller über AHA-HTTP-API"""

    ID = 19028
    NAME = "FRITZ!DECT 200"
    DESCRIPTION = "Steuert FRITZ!DECT 200/210 Steckdosen über FRITZ!Box AHA-API"
    VERSION = "1.0"
    AUTHOR = "Reinhard Socha"
    CATEGORY = "Energie"

    INPUTS = {
        'E1':  {'name': 'Start/Stop', 'type': 'bool', 'default': True},
        'E2':  {'name': 'Intervall (s)', 'type': 'int', 'default': 30},
        'E3':  {'name': 'FritzBox IP', 'type': 'str', 'default': '192.168.178.1'},
        'E4':  {'name': 'Benutzer', 'type': 'str', 'default': ''},
        'E5':  {'name': 'Passwort', 'type': 'str', 'default': ''},
        'E6':  {'name': 'AIN (ohne Leerzeichen)', 'type': 'str', 'default': ''},
        'E7':  {'name': 'On/Off', 'type': 'bool', 'default': False},
        'E8':  {'name': 'Toggle', 'type': 'bool', 'default': False},
        'E9':  {'name': 'Kosten/kWh (€)', 'type': 'float', 'default': 0.25},
        'E10': {'name': 'Debug', 'type': 'bool', 'default': False},
    }

    OUTPUTS = {
        'A1':  {'name': 'Gerätename', 'type': 'str'},
        'A2':  {'name': 'Verbindungsstatus', 'type': 'int'},
        'A3':  {'name': 'Schaltstatus', 'type': 'int'},
        'A4':  {'name': 'Leistung (W)', 'type': 'float'},
        'A5':  {'name': 'Leistung (mW)', 'type': 'int'},
        'A6':  {'name': 'Energie (Wh)', 'type': 'int'},
        'A7':  {'name': 'Energie (kWh)', 'type': 'float'},
        'A8':  {'name': 'Kosten gesamt (€)', 'type': 'float'},
        'A9':  {'name': 'Temperatur (°C)', 'type': 'float'},
        'A10': {'name': 'Letzter Fehler', 'type': 'str'},
    }

    # E7/E8 sollen IMMER triggern (auch bei gleichem Wert)
    TRIGGER_ALWAYS_INPUTS = {'E7', 'E8'}

    # Session timeout: 10 Minuten (AVM Standard), wir erneuern nach 8
    SID_REFRESH_INTERVAL = 480

    def set_input(self, key, value, force_trigger=False):
        """Override: E7/E8 triggern immer"""
        if key in self.TRIGGER_ALWAYS_INPUTS:
            input_type = self.INPUTS.get(key, {}).get('type', 'str')
            try:
                if input_type == 'bool':
                    if isinstance(value, str):
                        value = value.lower() in ('1', 'true', 'on', 'ein')
                    else:
                        value = bool(value)
            except (ValueError, TypeError):
                pass
            self._input_values[key] = value
            if self._enabled:
                self._trigger_execute(key)
            return True
        return super().set_input(key, value, force_trigger)

    def on_start(self):
        super().on_start()
        self._sid = None
        self._sid_ts = 0
        self._is_online = False
        self._consecutive_errors = 0

        interval = self.get_input('E2') or 30
        if interval < 10:
            interval = 10
        self.set_timer(interval)
        logger.info("[{}] FRITZ!DECT Controller gestartet, Intervall: {}s".format(
            self.ID, interval))

    def execute(self, triggered_by=None):
        if not self.get_input('E1'):
            return

        if triggered_by == 'E2':
            interval = self.get_input('E2') or 30
            if interval < 10:
                interval = 10
            self.set_timer(interval)
            return

        if triggered_by == 'E7':
            # On/Off Befehl
            asyncio.create_task(self._cmd_switch())

        elif triggered_by == 'E8':
            # Toggle
            asyncio.create_task(self._cmd_toggle())

    async def on_timer(self):
        if not self.get_input('E1'):
            return

        ip = (self.get_input('E3') or '').strip()
        ain = (self.get_input('E6') or '').strip().replace(' ', '')

        if not ip or not ain:
            self.set_output('A10', 'IP oder AIN fehlt')
            self.set_output('A2', 0)
            return

        debug = self.get_input('E10')

        # Session prüfen/erneuern
        if not await self._ensure_session():
            self._is_online = False
            self.set_output('A2', 0)
            return

        try:
            # Gerätename (nur beim ersten Mal oder selten)
            if not self.get_output('A1'):
                name = await self._aha_command('getswitchname')
                if name:
                    self.set_output('A1', name.strip())

            # Verbindungsstatus
            present = await self._aha_command('getswitchpresent')
            if present is None:
                self._consecutive_errors += 1
                if self._consecutive_errors > 3:
                    self._sid = None  # Session vermutlich abgelaufen
                self.set_output('A2', 0)
                self.set_output('A10', 'Keine Antwort')
                return

            is_present = present.strip() == '1'
            self.set_output('A2', 1 if is_present else 0)
            self._is_online = is_present
            self._consecutive_errors = 0

            if not is_present:
                self.set_output('A10', 'Gerät nicht erreichbar')
                return

            # Schaltstatus
            state = await self._aha_command('getswitchstate')
            if state is not None:
                s = state.strip()
                if s in ('0', '1'):
                    self.set_output('A3', int(s))

            # Leistung (mW → W)
            power_mw = await self._aha_command('getswitchpower')
            if power_mw is not None:
                try:
                    mw = int(power_mw.strip())
                    self.set_output('A5', mw)
                    self.set_output('A4', round(mw / 1000.0, 2))
                except ValueError:
                    pass

            # Energie (Wh → kWh)
            energy_wh = await self._aha_command('getswitchenergy')
            if energy_wh is not None:
                try:
                    wh = int(energy_wh.strip())
                    kwh = round(wh / 1000.0, 3)
                    self.set_output('A6', wh)
                    self.set_output('A7', kwh)

                    # Kosten
                    cost_per_kwh = self.get_input('E9') or 0.25
                    self.set_output('A8', round(kwh * cost_per_kwh, 2))
                except ValueError:
                    pass

            # Temperatur (0.1°C Einheiten)
            temp = await self._aha_command('gettemperature')
            if temp is not None:
                try:
                    t = int(temp.strip())
                    self.set_output('A9', round(t / 10.0, 1))
                except ValueError:
                    pass

            self.set_output('A10', '')

            if debug:
                logger.info("[{}] Poll OK: present={}, state={}, power={}mW, "
                            "energy={}Wh, temp={}".format(
                    self.ID, present.strip(), 
                    state.strip() if state else '?',
                    power_mw.strip() if power_mw else '?',
                    energy_wh.strip() if energy_wh else '?',
                    temp.strip() if temp else '?'))

        except Exception as e:
            logger.error("[{}] Poll error: {}".format(self.ID, e))
            self.set_output('A10', str(e)[:100])

    # ============ BEFEHLE ============

    async def _cmd_switch(self):
        """Ein oder Ausschalten basierend auf E7"""
        on = self.get_input('E7')
        debug = self.get_input('E10')

        if not await self._ensure_session():
            self.set_output('A10', 'Keine Session')
            return

        cmd = 'setswitchon' if on else 'setswitchoff'
        result = await self._aha_command(cmd)

        if debug:
            logger.info("[{}] Switch {}: result={}".format(
                self.ID, 'ON' if on else 'OFF', result))

        if result is not None:
            s = result.strip()
            if s in ('0', '1'):
                self.set_output('A3', int(s))
            self.set_output('A10', '')
        else:
            self.set_output('A10', 'Schaltbefehl fehlgeschlagen')

    async def _cmd_toggle(self):
        """Toggle"""
        debug = self.get_input('E10')

        if not await self._ensure_session():
            self.set_output('A10', 'Keine Session')
            return

        result = await self._aha_command('setswitchtoggle')

        if debug:
            logger.info("[{}] Toggle: result={}".format(self.ID, result))

        if result is not None:
            s = result.strip()
            if s in ('0', '1'):
                self.set_output('A3', int(s))
            self.set_output('A10', '')
        else:
            self.set_output('A10', 'Toggle fehlgeschlagen')

    # ============ AHA API ============

    async def _aha_command(self, switchcmd: str) -> Optional[str]:
        """Führt einen AHA-HTTP-Befehl aus"""
        ip = (self.get_input('E3') or '').strip()
        ain = (self.get_input('E6') or '').strip().replace(' ', '')

        if not self._sid or not ip or not ain:
            return None

        url = "http://{}//webservices/homeautoswitch.lua".format(ip)
        params = {
            'ain': ain,
            'switchcmd': switchcmd,
            'sid': self._sid,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, params=params,
                    timeout=aiohttp.ClientTimeout(total=8)
                ) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        # Check for invalid session
                        if '0000000000000000' in text or 'login' in text.lower():
                            self._sid = None
                            return None
                        return text
                    elif resp.status == 403:
                        self._sid = None
                        return None
                    else:
                        logger.warning("[{}] AHA {} status: {}".format(
                            self.ID, switchcmd, resp.status))
                        return None
        except Exception as e:
            logger.error("[{}] AHA {} error: {}".format(self.ID, switchcmd, e))
            return None

    # ============ SESSION MANAGEMENT ============

    async def _ensure_session(self) -> bool:
        """Stellt sicher dass eine gültige SID vorhanden ist"""
        now = time.time()

        # SID noch gültig?
        if self._sid and (now - self._sid_ts) < self.SID_REFRESH_INTERVAL:
            return True

        # Neue SID anfordern
        ip = (self.get_input('E3') or '').strip()
        user = (self.get_input('E4') or '').strip()
        password = (self.get_input('E5') or '').strip()

        if not ip:
            return False

        debug = self.get_input('E10')

        try:
            sid = await self._login(ip, user, password)
            if sid and sid != '0000000000000000':
                self._sid = sid
                self._sid_ts = now
                if debug:
                    logger.info("[{}] Login OK, SID: {}...".format(
                        self.ID, sid[:8]))
                return True
            else:
                self._sid = None
                self.set_output('A10', 'Login fehlgeschlagen')
                if debug:
                    logger.warning("[{}] Login fehlgeschlagen".format(self.ID))
                return False
        except Exception as e:
            self._sid = None
            self.set_output('A10', 'Login: {}'.format(str(e)[:80]))
            return False

    async def _login(self, ip: str, user: str, password: str) -> Optional[str]:
        """
        FRITZ!Box Login mit MD5 Challenge-Response.
        
        1. GET /login_sid.lua → Challenge auslesen
        2. Response berechnen: challenge + "-" + MD5(challenge + "-" + password als UTF-16LE)
        3. GET /login_sid.lua?username=X&response=Y → SID auslesen
        """
        login_url = "http://{}/login_sid.lua".format(ip)

        async with aiohttp.ClientSession() as session:
            # Schritt 1: Challenge holen
            async with session.get(
                login_url,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status != 200:
                    return None
                xml = await resp.text()

            # Prüfen ob bereits eingeloggt (SID != 0000...)
            sid_match = re.search(r'<SID>([0-9a-fA-F]+)</SID>', xml)
            if sid_match:
                sid = sid_match.group(1)
                if sid != '0000000000000000':
                    return sid

            # Challenge extrahieren
            challenge_match = re.search(r'<Challenge>([^<]+)</Challenge>', xml)
            if not challenge_match:
                logger.error("[{}] Kein Challenge in Login-Antwort".format(self.ID))
                return None

            challenge = challenge_match.group(1)

            # Schritt 2: PBKDF2 oder MD5 Response berechnen
            # Prüfen ob PBKDF2 Challenge (Format: 2$iter$salt$...)
            if challenge.startswith('2$'):
                response = self._pbkdf2_response(challenge, password)
            else:
                # Klassische MD5 Response
                response = self._md5_response(challenge, password)

            # Schritt 3: Login mit Response
            params = {}
            if user:
                params['username'] = user
            params['response'] = response

            async with session.get(
                login_url, params=params,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status != 200:
                    return None
                xml = await resp.text()

            sid_match = re.search(r'<SID>([0-9a-fA-F]+)</SID>', xml)
            if sid_match:
                return sid_match.group(1)

            return None

    @staticmethod
    def _md5_response(challenge: str, password: str) -> str:
        """
        Klassische MD5 Challenge-Response (FRITZ!OS < 7.24)
        Response = challenge + "-" + MD5(challenge + "-" + password als UTF-16LE)
        """
        to_hash = "{}-{}".format(challenge, password)
        # In UTF-16LE kodieren (wie AVM spezifiziert)
        encoded = to_hash.encode('utf-16-le')
        md5_hash = hashlib.md5(encoded).hexdigest()
        return "{}-{}".format(challenge, md5_hash)

    @staticmethod
    def _pbkdf2_response(challenge: str, password: str) -> str:
        """
        PBKDF2 Challenge-Response (FRITZ!OS >= 7.24)
        Challenge-Format: 2$<iter1>$<salt1>$<iter2>$<salt2>
        Response: 2$<iter2>$<salt2>$PBKDF2(PBKDF2(password, salt1, iter1), salt2, iter2)
        """
        parts = challenge.split('$')
        if len(parts) < 5:
            # Fallback auf MD5 wenn Format nicht stimmt
            return FritzDect200._md5_response(challenge, password)

        iter1 = int(parts[1])
        salt1 = bytes.fromhex(parts[2])
        iter2 = int(parts[3])
        salt2 = bytes.fromhex(parts[4])

        # Erster PBKDF2 Durchlauf
        hash1 = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'),
                                     salt1, iter1, dklen=32)
        # Zweiter PBKDF2 Durchlauf
        hash2 = hashlib.pbkdf2_hmac('sha256', hash1, salt2, iter2, dklen=32)

        return "2${}${}${}".format(iter2, parts[4], hash2.hex())


# Für Kompatibilität
class_1 = FritzDect200
