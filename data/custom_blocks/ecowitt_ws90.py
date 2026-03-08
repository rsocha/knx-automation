# coding: UTF-8
"""
Ecowitt WS90 Weather Station (v2.0) – Remanent

Liest Wetterdaten von Ecowitt GW1200/GW2000 Gateway via HTTP API.

============================================================
VORAUSSETZUNG:
  pip install aiohttp

FUNKTION:
  Pollt zyklisch http://<IP>/get_livedata_info und parst das JSON.
  Alle Sensordaten werden auf Ausgänge gemappt.

NEUE AUSGÄNGE (v2.0):
  A9:  Windrichtung in Grad (0-360°)
  A12: Windrichtung als Text (N, NO, O, SO, S, SW, W, NW)
  A13: Luftdruck relativ (hPa)
  A14: Taupunkt (°C)
  A17: Max. Tageswind (m/s)
  A18: Regen Woche (mm)
  A19: Regen Monat (mm)
============================================================

Eingänge:
- E1: IP-Adresse des Gateways (z.B. 192.168.0.16)
- E2: Poll-Intervall in Sekunden (Standard: 60, min. 10)
- E3: Trigger (1 = sofort abfragen)

Ausgänge:
- A1:  Temperatur (°C)
- A2:  Luftfeuchte (%)
- A3:  Wind (m/s)
- A4:  Windböe (m/s)
- A5:  Solar (kLux)
- A6:  Regenrate (mm/h)
- A7:  Regen Tag (mm)
- A8:  UV Index
- A9:  Windrichtung (°)
- A10: Innentemperatur (°C)
- A11: Innenfeuchte (%)
- A12: Windrichtung Text (N/NO/O/SO/S/SW/W/NW)
- A13: Luftdruck relativ (hPa)
- A14: Taupunkt (°C)
- A15: Letztes Update (HH:MM:SS)
- A16: Status Text
- A17: Max. Tageswind (m/s)
- A18: Regen Woche (mm)
- A19: Regen Monat (mm)

Versionshistorie:
v2.0 – Windrichtung (°+Text), Luftdruck, Taupunkt, Max-Tageswind,
       Regen Woche/Monat, Remanent, execute(triggered_by) Fix
v1.7 – Basis-Version (Temp, Wind, Solar, Regen, UV, Innen)
"""

import json
import logging
import asyncio
import aiohttp
import re
from datetime import datetime
from typing import Optional, Dict, Any

try:
    from logic.base import LogicBlock
except ImportError:
    try:
        from ..base import LogicBlock
    except (ImportError, ValueError):
        import sys, os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from base import LogicBlock

logger = logging.getLogger(__name__)

# Wind direction to German compass text
WIND_DIRS = [
    (22.5,  "N"),
    (67.5,  "NO"),
    (112.5, "O"),
    (157.5, "SO"),
    (202.5, "S"),
    (247.5, "SW"),
    (292.5, "W"),
    (337.5, "NW"),
    (360.1, "N"),
]

def deg_to_compass(deg: float) -> str:
    """Convert degrees (0-360) to compass direction text"""
    for limit, name in WIND_DIRS:
        if deg < limit:
            return name
    return "N"


class EcowittWS90(LogicBlock):
    """Ecowitt WS90 Wetterstation – GW1200/GW2000 HTTP API"""

    ID = 20027
    NAME = "Ecowitt WS90"
    DESCRIPTION = "Liest Wetterdaten von Ecowitt GW1200/GW2000 Gateway via HTTP API"
    CATEGORY = "Wetter"
    VERSION = "2.0"
    AUTHOR = "Reinhard"
    REMANENT = True

    HELP = """
Ecowitt WS90 Wetterstation

VORAUSSETZUNG:
  pip install aiohttp

KONFIGURATION:
  E1 = IP-Adresse des Gateways (z.B. 192.168.0.16)
  E2 = Poll-Intervall in Sekunden (Standard: 60)
  E3 = 1 → sofort abfragen

AUSGÄNGE:
  A1  = Außentemperatur (°C)
  A2  = Luftfeuchte (%)
  A3  = Windgeschwindigkeit (m/s)
  A4  = Windböe (m/s)
  A5  = Solar (kLux)
  A6  = Regenrate (mm/h)
  A7  = Regen heute (mm)
  A8  = UV Index
  A9  = Windrichtung (0-360°)
  A10 = Innentemperatur (°C)
  A11 = Innenfeuchte (%)
  A12 = Windrichtung Text (N/NO/O/SO/S/SW/W/NW)
  A13 = Luftdruck relativ (hPa)
  A14 = Taupunkt (°C)
  A15 = Letztes Update
  A16 = Status
  A17 = Max. Tageswind (m/s)
  A18 = Regen Woche (mm)
  A19 = Regen Monat (mm)

ECOWITT API IDs:
  0x02=Temp, 0x03=Taupunkt, 0x07=Feuchte, 0x08=Druck abs,
  0x09=Druck rel, 0x0A=Windrichtung, 0x0B=Wind, 0x0C=Böe,
  0x0D=Regen Event, 0x0E=Regenrate, 0x10=Regen Tag,
  0x11=Regen Woche, 0x12=Regen Monat, 0x15=Solar,
  0x17=UV Index, 0x19=Max Tageswind
"""

    INPUTS = {
        'E1': {'name': 'IP-Adresse', 'type': 'str', 'default': '192.168.0.16'},
        'E2': {'name': 'Poll-Intervall (s)', 'type': 'int', 'default': 60},
        'E3': {'name': 'Trigger', 'type': 'bool', 'default': False},
    }

    OUTPUTS = {
        'A1':  {'name': 'Temperatur °C',        'type': 'float', 'default': 0.0},
        'A2':  {'name': 'Luftfeuchte %',         'type': 'float', 'default': 0.0},
        'A3':  {'name': 'Wind m/s',              'type': 'float', 'default': 0.0},
        'A4':  {'name': 'Windböe m/s',           'type': 'float', 'default': 0.0},
        'A5':  {'name': 'Solar kLux',            'type': 'float', 'default': 0.0},
        'A6':  {'name': 'Regenrate mm/h',        'type': 'float', 'default': 0.0},
        'A7':  {'name': 'Regen Tag mm',          'type': 'float', 'default': 0.0},
        'A8':  {'name': 'UV Index',              'type': 'int',   'default': 0},
        'A9':  {'name': 'Windrichtung °',        'type': 'float', 'default': 0.0},
        'A10': {'name': 'Innentemp °C',          'type': 'float', 'default': 0.0},
        'A11': {'name': 'Innenfeuchte %',        'type': 'float', 'default': 0.0},
        'A12': {'name': 'Windrichtung Text',     'type': 'str',   'default': ''},
        'A13': {'name': 'Luftdruck hPa',         'type': 'float', 'default': 0.0},
        'A14': {'name': 'Taupunkt °C',           'type': 'float', 'default': 0.0},
        'A15': {'name': 'Letztes Update',        'type': 'str',   'default': ''},
        'A16': {'name': 'Status',                'type': 'str',   'default': 'Init'},
        'A17': {'name': 'Max. Tageswind m/s',    'type': 'float', 'default': 0.0},
        'A18': {'name': 'Regen Woche mm',        'type': 'float', 'default': 0.0},
        'A19': {'name': 'Regen Monat mm',        'type': 'float', 'default': 0.0},
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._poll_task: Optional[asyncio.Task] = None

    def on_start(self):
        super().on_start()
        self.debug("Version", self.VERSION)
        if self._poll_task is None or self._poll_task.done():
            self._poll_task = asyncio.ensure_future(self._loop())

    def on_stop(self):
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            self._poll_task = None
        super().on_stop()

    def execute(self, triggered_by=None):
        if triggered_by == 'E3':
            val = self.get_input('E3')
            if val and (val is True or str(val) == "1" or str(val).lower() == "true"):
                asyncio.ensure_future(self._poll_data())

    async def _loop(self):
        """Background polling loop"""
        await asyncio.sleep(5)  # Startup delay
        while self._running:
            try:
                await self._poll_data()
            except Exception as e:
                logger.error(f"[{self.ID}] Poll error: {e}")
                self.set_output('A16', f"Fehler: {str(e)[:50]}")
            interval = max(10, self.get_input('E2') or 60)
            try:
                interval = int(interval)
            except (ValueError, TypeError):
                interval = 60
            await asyncio.sleep(interval)

    def clean_float(self, value: Any) -> float:
        """Extract number from strings like '8.4 C' or '80%' or '1012.4 hPa'"""
        if value is None:
            return 0.0
        try:
            if isinstance(value, (int, float)):
                return float(value)
            s = str(value).strip()
            # Remove units: split on space, take first part
            parts = s.split(' ')
            num_str = parts[0]
            # Remove any remaining non-numeric chars except . and -
            clean_val = re.sub(r'[^0-9.\-]', '', num_str)
            return float(clean_val) if clean_val else 0.0
        except Exception:
            return 0.0

    async def _poll_data(self):
        """HTTP request to gateway"""
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
                        self.set_output('A16', "JSON Fehler")
                        return

                    self._parse_data(data)
                    self.set_output('A15', datetime.now().strftime("%H:%M:%S"))
                    self.set_output('A16', "OK")

        except asyncio.TimeoutError:
            self.set_output('A16', "Timeout")
        except aiohttp.ClientError as e:
            self.set_output('A16', f"Verbindungsfehler")
            logger.error(f"[{self.ID}] Connection error: {e}")
        except Exception as e:
            self.set_output('A16', f"Fehler")
            logger.exception(f"[{self.ID}] Poll error")

    def _parse_data(self, data: Dict[str, Any]):
        """Map JSON fields to outputs"""

        # ── common_list: outdoor sensors ──
        if "common_list" in data:
            for item in data["common_list"]:
                idx = item.get("id")
                val = item.get("val")
                if val is None:
                    continue

                if idx == "0x02":    # Outdoor Temperature
                    self.set_output('A1', self.clean_float(val))
                elif idx == "0x03":  # Dew Point
                    self.set_output('A14', self.clean_float(val))
                elif idx == "0x07":  # Outdoor Humidity
                    self.set_output('A2', self.clean_float(val))
                elif idx == "0x09":  # Relative Barometric Pressure
                    self.set_output('A13', self.clean_float(val))
                elif idx == "0x08":  # Absolute Barometric (fallback if no 0x09)
                    if not self._output_values.get('A13'):
                        self.set_output('A13', self.clean_float(val))
                elif idx == "0x0A":  # Wind Direction (degrees)
                    deg = self.clean_float(val)
                    self.set_output('A9', deg)
                    self.set_output('A12', deg_to_compass(deg))
                elif idx == "0x0B":  # Wind Speed
                    self.set_output('A3', self.clean_float(val))
                elif idx == "0x0C":  # Gust Speed
                    self.set_output('A4', self.clean_float(val))
                elif idx == "0x15":  # Solar radiation (W/m² → kLux approx)
                    self.set_output('A5', self.clean_float(val))
                elif idx == "0x17":  # UV Index
                    self.set_output('A8', int(self.clean_float(val)))
                elif idx == "0x19":  # Day max wind
                    self.set_output('A17', self.clean_float(val))

        # ── piezoRain or rain: rainfall sensors ──
        rain_section = data.get("piezoRain") or data.get("rain") or []
        for item in rain_section:
            idx = item.get("id")
            val = item.get("val")
            if val is None:
                continue

            if idx == "0x0E":    # Rain Rate
                self.set_output('A6', self.clean_float(val))
            elif idx == "0x0D":  # Rain Event
                pass  # not mapped separately
            elif idx == "0x10":  # Rain Day
                self.set_output('A7', self.clean_float(val))
            elif idx == "0x11":  # Rain Week
                self.set_output('A18', self.clean_float(val))
            elif idx == "0x12":  # Rain Month
                self.set_output('A19', self.clean_float(val))

        # ── wh25: indoor sensor ──
        if "wh25" in data and len(data["wh25"]) > 0:
            inner = data["wh25"][0]
            if "intemp" in inner:
                self.set_output('A10', self.clean_float(inner["intemp"]))
            if "inhumi" in inner:
                self.set_output('A11', self.clean_float(inner["inhumi"]))
            # Pressure from wh25 as fallback
            if "rel" in inner and not self._output_values.get('A13'):
                self.set_output('A13', self.clean_float(inner["rel"]))

    # ─── Remanent ───────────────────────────────────────────────────────

    def get_remanent_state(self) -> dict:
        return {"outputs": dict(self._output_values)}

    def restore_remanent_state(self, state: dict):
        if state and "outputs" in state:
            for k, v in state["outputs"].items():
                self._output_values[k] = v
