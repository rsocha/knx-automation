# coding: UTF-8
"""
Ecowitt WS90 Weather Station Controller
Block ID: 20027
"""
import json
import logging
import asyncio
import aiohttp
import re
from datetime import datetime
from typing import Optional, Dict, Any

try:
    from ..base import LogicBlock
except (ImportError, ValueError):
    try:
        from logic.base import LogicBlock
    except ImportError:
        import sys
        import os

        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from base import LogicBlock

logger = logging.getLogger(__name__)


class EcowittWS90(LogicBlock):
    """Ecowitt WS90 Wetterstation Controller"""

    ID = 20027
    NAME = "Ecowitt WS90"
    DESCRIPTION = "Liest Wetterdaten von Ecowitt GW1200 Gateway via HTTP API"
    CATEGORY = "Wetter"
    VERSION = "1.7"
    AUTHOR = "Reinhard"

    INPUTS = {
        'E1': {'name': 'IP-Adresse', 'type': 'str', 'default': '192.168.0.16'},
        'E2': {'name': 'Poll-Intervall (s)', 'type': 'int', 'default': 60},
        'E3': {'name': 'Trigger (Manuell)', 'type': 'bool', 'default': False},
    }

    OUTPUTS = {
        'A1': {'name': 'Temperatur C', 'type': 'float', 'default': 0.0},
        'A2': {'name': 'Luftfeuchte %', 'type': 'float', 'default': 0.0},
        'A3': {'name': 'Wind m/s', 'type': 'float', 'default': 0.0},
        'A4': {'name': 'Windboee m/s', 'type': 'float', 'default': 0.0},
        'A5': {'name': 'Solar (Klux)', 'type': 'float', 'default': 0.0},
        'A6': {'name': 'Regenrate mm/h', 'type': 'float', 'default': 0.0},
        'A7': {'name': 'Regen Tag mm', 'type': 'float', 'default': 0.0},
        'A8': {'name': 'UV Index', 'type': 'int', 'default': 0},
        'A10': {'name': 'Innentemp C', 'type': 'float', 'default': 0.0},
        'A11': {'name': 'Innenfeuchte %', 'type': 'float', 'default': 0.0},
        'A15': {'name': 'Letztes Update', 'type': 'str', 'default': ''},
        'A16': {'name': 'Status Text', 'type': 'str', 'default': 'Initialisierung'}
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._poll_task: Optional[asyncio.Task] = None

    async def on_start(self):
        """Wird beim Laden des Bausteins aufgerufen"""
        logger.info(f"[{self.ID}] Starte Ecowitt Poll Task...")
        self._poll_task = asyncio.create_task(self._loop())

    async def on_stop(self):
        """Wird beim Beenden aufgerufen"""
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass

    def execute(self):
        """Wird zyklisch vom System gerufen"""
        if self.get_input('E3') is True:
            asyncio.create_task(self._poll_data())

    async def _loop(self):
        """Hintergrund-Schleife fuer automatisches Polling"""
        while True:
            try:
                await self._poll_data()
            except Exception as e:
                logger.error(f"[{self.ID}] Poll error: {e}")
            interval = max(10, self.get_input('E2') or 60)
            await asyncio.sleep(interval)

    def clean_float(self, value: Any) -> float:
        """Extrahiert Zahlen aus Strings wie '8.4 C' oder '80%'"""
        if value is None: return 0.0
        try:
            if isinstance(value, (int, float)):
                return float(value)
            s = str(value).split(' ')[0]
            clean_val = re.sub(r'[^0-9.\-]', '', s)
            return float(clean_val) if clean_val else 0.0
        except Exception:
            return 0.0

    async def _poll_data(self):
        """Fuehrt die eigentliche HTTP-Abfrage durch"""
        ip = self.get_input('E1') or '192.168.0.16'
        url = f"http://{ip}/get_livedata_info"

        try:
            timeout = aiohttp.ClientTimeout(total=10)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:

                    if response.status != 200:
                        self.set_output('A16', f"HTTP {response.status}")
                        return

                    payload = await response.text()

                    try:
                        data = json.loads(payload)
                    except Exception:
                        logger.error(f"[{self.ID}] JSON Fehler")
                        self.set_output('A16', "JSON Fehler")
                        return

                    logger.debug(f"[{self.ID}] JSON empfangen")
                    self._parse_json_data(data)

                    self.set_output('A15', datetime.now().strftime("%H:%M:%S"))
                    self.set_output('A16', "OK")

        except asyncio.TimeoutError:
            logger.warning(f"[{self.ID}] Timeout")
            self.set_output('A16', "Timeout")
        except aiohttp.ClientError as e:
            logger.error(f"[{self.ID}] Verbindungsfehler: {e}")
            self.set_output('A16', "Verbindungsfehler")
        except Exception as e:
            logger.exception(f"[{self.ID}] Fehler")
            self.set_output('A16', f"Fehler")

    def _parse_json_data(self, data: Dict[str, Any]):
        """Mappt die JSON-Felder auf die Ausgaenge"""
        if "common_list" in data:
            for item in data["common_list"]:
                idx = item.get("id")
                val = item.get("val")
                if val is None: continue

                if idx == "0x02":
                    self.set_output('A1', self.clean_float(val))
                elif idx == "0x07":
                    self.set_output('A2', self.clean_float(val))
                elif idx == "0x0B":
                    self.set_output('A3', self.clean_float(val))
                elif idx == "0x0C":
                    self.set_output('A4', self.clean_float(val))
                elif idx == "0x15":
                    self.set_output('A5', self.clean_float(val))
                elif idx == "0x17":
                    self.set_output('A8', int(self.clean_float(val)))

        if "piezoRain" in data:
            for item in data["piezoRain"]:
                idx = item.get("id")
                val = item.get("val")
                if idx == "0x0E":
                    self.set_output('A6', self.clean_float(val))
                elif idx == "0x0D":
                    self.set_output('A7', self.clean_float(val))

        if "wh25" in data and len(data["wh25"]) > 0:
            inner = data["wh25"][0]
            self.set_output('A10', self.clean_float(inner.get("intemp")))
            self.set_output('A11', self.clean_float(inner.get("inhumi")))
