"""
Netatmo Healthy Home Coach (Aircare) für KNX Automation
Basiert auf EDOMI Logikbaustein 19000502
Holt Luftqualitätsdaten von Netatmo API
"""
import json
import logging
import asyncio
import aiohttp
from datetime import datetime
from typing import Optional, Dict, Any

from logic.base import LogicBlock

logger = logging.getLogger(__name__)


class NetatmoHomecoach(LogicBlock):
    """Netatmo Healthy Home Coach - Luftqualitätssensor"""
    
    ID = 20032
    NAME = "Netatmo Homecoach"
    DESCRIPTION = "Netatmo Healthy Home Coach (Aircare) - Temperatur, Luftfeuchtigkeit, CO2, Lärm"
    CATEGORY = "Sensoren"
    
    API_URL = "https://api.netatmo.com/api/gethomecoachsdata"
    
    INPUTS = {
        'E1': {'name': 'Start/Stop (1/0)', 'type': 'bool', 'default': True},
        'E2': {'name': 'Poll Intervall (Sek)', 'type': 'int', 'default': 300, 'min': 60},
        'E3': {'name': 'Access Token', 'type': 'str', 'default': ''},
        'E4': {'name': 'Device ID (MAC)', 'type': 'str', 'default': ''},
        'E5': {'name': 'Debug logging', 'type': 'bool', 'default': False},
    }
    
    OUTPUTS = {
        'A1': {'name': 'Status (1=OK, 0=ERR)', 'type': 'int', 'default': 0},
        'A2': {'name': 'Fehlermeldung', 'type': 'str', 'default': ''},
        'A3': {'name': 'Station Name', 'type': 'str', 'default': ''},
        'A4': {'name': 'Device ID', 'type': 'str', 'default': ''},
        'A5': {'name': 'Temperatur (°C)', 'type': 'float', 'default': 0.0},
        'A6': {'name': 'Luftfeuchtigkeit (%)', 'type': 'int', 'default': 0},
        'A7': {'name': 'CO2 (ppm)', 'type': 'int', 'default': 0},
        'A8': {'name': 'Lärm (dB)', 'type': 'int', 'default': 0},
        'A9': {'name': 'Luftdruck (mbar)', 'type': 'float', 'default': 0.0},
        'A10': {'name': 'Health Index (0-4)', 'type': 'int', 'default': 0},
        'A11': {'name': 'Letzte Messung (Unix)', 'type': 'int', 'default': 0},
        'A12': {'name': 'WiFi Status', 'type': 'str', 'default': ''},
        'A13': {'name': 'Min Temp 24h (°C)', 'type': 'float', 'default': 0.0},
        'A14': {'name': 'Max Temp 24h (°C)', 'type': 'float', 'default': 0.0},
        'A15': {'name': 'Abs. Luftdruck (mbar)', 'type': 'float', 'default': 0.0},
        'A16': {'name': 'Letzte Messung (ISO)', 'type': 'str', 'default': ''},
        'A17': {'name': 'Health Text', 'type': 'str', 'default': ''},
    }
    
    HEALTH_INDEX = ['Gesund', 'Gut', 'Mittel', 'Schlecht', 'Ungesund']
    
    def on_start(self):
        """Block gestartet"""
        logger.info(f"[{self.ID}] Netatmo Homecoach starting...")
        
        self._poll_task: Optional[asyncio.Task] = None
        self._last_device_id = ''
        
        self._debug_values['Status'] = 'Init'
        self._debug_values['Station'] = '-'
        self._debug_values['Last Update'] = '-'
        
        if self.get_input('E1'):
            self._start_polling()
    
    def on_stop(self):
        """Block gestoppt"""
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
        logger.info(f"[{self.ID}] Netatmo Homecoach stopped")
    
    def _start_polling(self):
        """Start polling loop"""
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
        self._poll_task = asyncio.create_task(self._poll_loop())
    
    async def _poll_loop(self):
        """Main polling loop"""
        logger.info(f"[{self.ID}] Poll loop started")
        
        while True:
            try:
                if not self.get_input('E1'):
                    self.set_output('A1', 0)
                    self.set_output('A2', 'Gestoppt')
                    self._debug_values['Status'] = 'Gestoppt'
                    await asyncio.sleep(5)
                    continue
                
                await self._fetch_data()
                
                interval = max(60, self.get_input('E2') or 300)
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{self.ID}] Poll error: {e}")
                self.set_output('A1', 0)
                self.set_output('A2', str(e)[:80])
                self._debug_values['Status'] = f'Fehler: {str(e)[:30]}'
                await asyncio.sleep(60)
    
    async def _fetch_data(self):
        """Fetch data from Netatmo API"""
        token = self.get_input('E3') or ''
        device_id = self.get_input('E4') or self._last_device_id
        debug = self.get_input('E5')
        
        if not token:
            self.set_output('A1', 0)
            self.set_output('A2', 'Kein Access Token')
            self._debug_values['Status'] = 'Kein Token'
            return
        
        # Build URL
        url = self.API_URL
        if device_id:
            url += f"?device_id={device_id}"
        
        if debug:
            logger.info(f"[{self.ID}] Fetching: {url}")
        
        self._debug_values['Status'] = 'Polling...'
        
        try:
            headers = {
                'Authorization': f'Bearer {token}',
                'Accept': 'application/json'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, 
                                       timeout=aiohttp.ClientTimeout(total=25)) as response:
                    
                    if response.status == 401 or response.status == 403:
                        self.set_output('A1', 0)
                        self.set_output('A2', 'Token ungültig/abgelaufen')
                        self._debug_values['Status'] = 'Token ungültig'
                        return
                    
                    if response.status != 200:
                        self.set_output('A1', 0)
                        self.set_output('A2', f'HTTP {response.status}')
                        self._debug_values['Status'] = f'HTTP {response.status}'
                        return
                    
                    data = await response.json()
            
            if debug:
                logger.info(f"[{self.ID}] Response: {json.dumps(data)[:500]}")
            
            # Check status
            if data.get('status') != 'ok':
                error_msg = data.get('error', {}).get('message', 'API Fehler')
                self.set_output('A1', 0)
                self.set_output('A2', error_msg)
                self._debug_values['Status'] = error_msg[:30]
                return
            
            # Parse device data
            devices = data.get('body', {}).get('devices', [])
            if not devices:
                # Try alternative structure
                if isinstance(data.get('body'), dict) and 'dashboard_data' in data.get('body', {}):
                    devices = [data['body']]
                else:
                    self.set_output('A1', 0)
                    self.set_output('A2', 'Keine Geräte gefunden')
                    self._debug_values['Status'] = 'Keine Geräte'
                    return
            
            device = devices[0]
            dashboard = device.get('dashboard_data', {})
            
            # Extract values
            eff_device_id = device.get('_id', device_id)
            if eff_device_id:
                self._last_device_id = eff_device_id
            
            station_name = device.get('station_name') or device.get('name') or device.get('module_name', '')
            
            temp = float(dashboard.get('Temperature', 0))
            humidity = int(dashboard.get('Humidity', 0))
            co2 = int(dashboard.get('CO2', 0))
            noise = int(dashboard.get('Noise', 0))
            pressure = float(dashboard.get('Pressure', 0))
            health_idx = int(dashboard.get('health_idx', 0))
            min_temp = float(dashboard.get('min_temp', 0))
            max_temp = float(dashboard.get('max_temp', 0))
            abs_pressure = float(dashboard.get('AbsolutePressure', 0))
            time_utc = int(dashboard.get('time_utc', 0))
            wifi_status = str(device.get('wifi_status', ''))
            
            iso_time = ''
            if time_utc > 0:
                iso_time = datetime.utcfromtimestamp(time_utc).strftime('%Y-%m-%d %H:%M:%S')
            
            health_text = self.HEALTH_INDEX[health_idx] if 0 <= health_idx < len(self.HEALTH_INDEX) else f'Index {health_idx}'
            
            # Set outputs
            self.set_output('A1', 1)
            self.set_output('A2', 'OK')
            self.set_output('A3', station_name)
            self.set_output('A4', eff_device_id)
            self.set_output('A5', round(temp, 1))
            self.set_output('A6', humidity)
            self.set_output('A7', co2)
            self.set_output('A8', noise)
            self.set_output('A9', round(pressure, 1))
            self.set_output('A10', health_idx)
            self.set_output('A11', time_utc)
            self.set_output('A12', wifi_status)
            self.set_output('A13', round(min_temp, 1))
            self.set_output('A14', round(max_temp, 1))
            self.set_output('A15', round(abs_pressure, 1))
            self.set_output('A16', iso_time)
            self.set_output('A17', health_text)
            
            # Debug info
            self._debug_values['Status'] = 'OK'
            self._debug_values['Station'] = station_name
            self._debug_values['Temp'] = f'{temp}°C'
            self._debug_values['CO2'] = f'{co2} ppm'
            self._debug_values['Health'] = health_text
            self._debug_values['Last Update'] = datetime.now().strftime('%H:%M:%S')
            
            if debug:
                logger.info(f"[{self.ID}] Data: T={temp}°C, H={humidity}%, CO2={co2}ppm, Health={health_text}")
            
        except aiohttp.ClientError as e:
            logger.error(f"[{self.ID}] HTTP error: {e}")
            self.set_output('A1', 0)
            self.set_output('A2', f'HTTP Fehler: {str(e)[:60]}')
            self._debug_values['Status'] = 'HTTP Fehler'
        except Exception as e:
            logger.error(f"[{self.ID}] Fetch error: {e}")
            self.set_output('A1', 0)
            self.set_output('A2', str(e)[:80])
            self._debug_values['Status'] = f'Fehler: {str(e)[:30]}'
    
    def on_input_change(self, key, value, old_value):
        """Input changed"""
        if key == 'E1':
            if value:
                self._start_polling()
            else:
                if self._poll_task and not self._poll_task.done():
                    self._poll_task.cancel()
        elif key == 'E3' and value:
            # Token changed - trigger immediate poll
            if self._poll_task and not self._poll_task.done():
                self._poll_task.cancel()
            self._start_polling()
    
    def execute(self, triggered_by: str = None):
        """Execute - handled by poll loop"""
        pass
