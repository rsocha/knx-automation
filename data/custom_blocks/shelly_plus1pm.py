"""
Shelly Plus 1 PM LogicBlock (v1.0)

Steuert und überwacht einen Shelly Plus 1 PM über die lokale HTTP RPC-API (Gen2).

Funktionen:
- Schalten (Ein/Aus/Toggle) mit optionalem Timer
- Leistungsmessung (W, V, A)
- Energiezähler (Wh gesamt + Session)
- Temperaturüberwachung (Gerät + bis zu 3 externe DS18B20 via Add-On)
- Input-Status, WLAN-RSSI, Online-Status

API-Endpunkte:
- Status: http://IP/rpc/Shelly.GetStatus
- Schalten: http://IP/rpc/Switch.Set?id=0&on=true/false
- Toggle: http://IP/rpc/Switch.Toggle?id=0
"""

import asyncio
import logging
from datetime import datetime

try:
    from ..base import LogicBlock
except ImportError:
    from logic.base import LogicBlock

logger = logging.getLogger(__name__)


class ShellyPlus1PM(LogicBlock):
    """Shelly Plus 1 PM Controller via lokale RPC-API"""

    ID = 20033
    NAME = "Shelly Plus 1 PM"
    DESCRIPTION = "Steuert und überwacht Shelly Plus 1 PM über lokale HTTP RPC-API (Gen2)"
    VERSION = "1.2"
    AUTHOR = "Reinhard Socha"
    CATEGORY = "Aktoren"

    INPUTS = {
        'E1': {'name': 'Start/Stop', 'type': 'bool', 'default': True},
        'E2': {'name': 'IP-Adresse', 'type': 'str', 'default': ''},
        'E3': {'name': 'Intervall (s)', 'type': 'int', 'default': 30},
        'E4': {'name': 'Schalten (0/1)', 'type': 'int', 'default': -1},
        'E5': {'name': 'Toggle', 'type': 'bool', 'default': False},
        'E6': {'name': 'Timer (s)', 'type': 'int', 'default': 0},
        'E7': {'name': 'Debug (0/1)', 'type': 'bool', 'default': False},
    }

    OUTPUTS = {
        'A1':  {'name': 'Schaltzustand', 'type': 'bool'},
        'A2':  {'name': 'Leistung (W)', 'type': 'float'},
        'A3':  {'name': 'Spannung (V)', 'type': 'float'},
        'A4':  {'name': 'Strom (A)', 'type': 'float'},
        'A5':  {'name': 'Energie gesamt (Wh)', 'type': 'float'},
        'A6':  {'name': 'Energie Session (Wh)', 'type': 'float'},
        'A7':  {'name': 'Gerätetemperatur (°C)', 'type': 'float'},
        'A8':  {'name': 'Input-Status', 'type': 'bool'},
        'A9':  {'name': 'WLAN-RSSI (dBm)', 'type': 'int'},
        'A10': {'name': 'Online-Status', 'type': 'bool'},
        'A11': {'name': 'Letzter Abruf', 'type': 'str'},
        'A12': {'name': 'Letzter Fehler', 'type': 'str'},
        'A13': {'name': 'Quelle letzte Schaltung', 'type': 'str'},
        'A14': {'name': 'Ext. Temperatur 1 (°C)', 'type': 'float'},
        'A15': {'name': 'Ext. Temperatur 2 (°C)', 'type': 'float'},
        'A16': {'name': 'Ext. Temperatur 3 (°C)', 'type': 'float'},
    }

    def on_start(self):
        super().on_start()
        self._pending_action = None  # 'on', 'off', 'toggle'
        interval = self.get_input('E3') or 30
        if interval < 5:
            interval = 30
        self.set_timer(interval)
        logger.info("[{}] Shelly Plus 1 PM gestartet, Intervall: {}s".format(self.ID, interval))

    def execute(self, triggered_by=None):
        if not self.get_input('E1'):
            return

        if triggered_by == 'E3':
            interval = self.get_input('E3') or 30
            if interval < 5:
                interval = 30
            self.set_timer(interval)
            return

        if triggered_by == 'E4':
            val = self.get_input('E4')
            if val is not None and val >= 0:
                self._pending_action = 'on' if val else 'off'
                asyncio.create_task(self._send_command_and_poll())
            return

        if triggered_by == 'E5':
            if self.get_input('E5'):
                self._pending_action = 'toggle'
                asyncio.create_task(self._send_command_and_poll())
            return

    async def on_timer(self):
        if not self.get_input('E1'):
            return
        await self._poll_status()

    async def _send_command_and_poll(self):
        """Schaltbefehl senden, dann Status abrufen"""
        ip = (self.get_input('E2') or '').strip()
        action = self._pending_action
        self._pending_action = None
        debug = self.get_input('E7')

        if not ip:
            self.set_output('A12', 'Keine IP-Adresse')
            self.set_output('A10', False)
            return

        timer_s = self.get_input('E6') or 0
        url = None

        if action == 'on':
            url = "http://{}/rpc/Switch.Set?id=0&on=true".format(ip)
            if timer_s > 0:
                url += "&toggle_after={}".format(timer_s)
        elif action == 'off':
            url = "http://{}/rpc/Switch.Set?id=0&on=false".format(ip)
            if timer_s > 0:
                url += "&toggle_after={}".format(timer_s)
        elif action == 'toggle':
            url = "http://{}/rpc/Switch.Toggle?id=0".format(ip)

        if url:
            if debug:
                logger.info("[{}] CMD: {}".format(self.ID, url))
                self.debug("Last CMD", url)

            result = await self.http_get_json(url, timeout=5)
            if result is None:
                self.set_output('A12', 'Schaltfehler')
                return

            # Kurz warten, damit Shelly den neuen Status hat
            await asyncio.sleep(0.3)

        # Danach Status abrufen
        await self._poll_status()

    async def _poll_status(self):
        """Status vom Shelly abrufen und Ausgänge setzen"""
        ip = (self.get_input('E2') or '').strip()
        debug = self.get_input('E7')

        if not ip:
            self.set_output('A12', 'Keine IP-Adresse')
            self.set_output('A10', False)
            return

        url = "http://{}/rpc/Shelly.GetStatus".format(ip)
        if debug:
            logger.info("[{}] Status: {}".format(self.ID, url))

        data = await self.http_get_json(url, timeout=8)

        if not data or not isinstance(data, dict):
            self.set_output('A12', 'Verbindung fehlgeschlagen')
            self.set_output('A10', False)
            return

        # --- Switch-Daten ---
        sw = data.get('switch:0', {})
        if sw:
            if 'output' in sw:
                self.set_output('A1', bool(sw['output']))
            if 'apower' in sw:
                self.set_output('A2', round(sw['apower'], 1))
            if 'voltage' in sw:
                self.set_output('A3', round(sw['voltage'], 1))
            if 'current' in sw:
                self.set_output('A4', round(sw['current'], 3))

            aenergy = sw.get('aenergy', {})
            if 'total' in aenergy:
                self.set_output('A5', round(aenergy['total'], 1))
            by_minute = aenergy.get('by_minute', [])
            if by_minute:
                self.set_output('A6', round(by_minute[0], 3))

            temp = sw.get('temperature', {})
            if 'tC' in temp:
                self.set_output('A7', round(temp['tC'], 1))

            if 'source' in sw:
                self.set_output('A13', sw['source'])

        # --- Input-Status ---
        inp = data.get('input:0', {})
        if 'state' in inp:
            self.set_output('A8', bool(inp['state']))

        # --- WLAN ---
        wifi = data.get('wifi', {})
        if 'rssi' in wifi:
            self.set_output('A9', wifi['rssi'])

        # --- Externe Temperaturfühler (Add-On DS18B20) ---
        for idx, output_key in enumerate(['A14', 'A15', 'A16'], start=100):
            sensor_key = 'temperature:{}'.format(idx)
            sensor = data.get(sensor_key, {})
            if 'tC' in sensor:
                self.set_output(output_key, round(sensor['tC'], 1))

        # --- Erfolg ---
        self.set_output('A10', True)
        self.set_output('A11', datetime.now().strftime('%d.%m.%Y %H:%M:%S'))
        self.set_output('A12', '')

        if debug:
            logger.info("[{}] Status OK".format(self.ID))
            self.debug("Last Poll", datetime.now().strftime('%H:%M:%S'))
