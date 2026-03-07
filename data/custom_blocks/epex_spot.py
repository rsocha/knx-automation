"""
EPEX Spot Preis Baustein für KNX Automation
Unterstützt: aWATTar AT, smartENERGY
"""
import json
import logging
import asyncio
import aiohttp
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any

from logic.base import LogicBlock

logger = logging.getLogger(__name__)


class EPEXSpotPrice(LogicBlock):
    """EPEX Spot Preis - Strompreise von aWATTar und smartENERGY"""
    
    ID = 20035
    NAME = "EPEX Spot Preis"
    DESCRIPTION = "Strompreise von aWATTar AT / smartENERGY mit Min/Max/Avg"
    CATEGORY = "Energie"
    
    INPUTS = {
        'E1': {'name': 'Start/Stop (1/0)', 'type': 'bool', 'default': True},
        'E2': {'name': 'Poll Intervall (Sek)', 'type': 'int', 'default': 300},
        'E3': {'name': 'Provider (0=aWATTar, 1=smartENERGY)', 'type': 'int', 'default': 0},
        'E4': {'name': 'Preisaufschlag ct/kWh', 'type': 'float', 'default': 0.0},
        'E5': {'name': 'Debug (0/1)', 'type': 'bool', 'default': False},
    }
    
    OUTPUTS = {
        'A1': {'name': 'Status (1=OK, 0=ERR)', 'type': 'int', 'default': 0},
        'A2': {'name': 'Error Message', 'type': 'str', 'default': ''},
        'A3': {'name': 'Provider Name', 'type': 'str', 'default': ''},
        'A4': {'name': 'Unit', 'type': 'str', 'default': 'ct/kWh'},
        'A5': {'name': 'Interval (min)', 'type': 'int', 'default': 0},
        'A6': {'name': 'Current Start (Unix)', 'type': 'int', 'default': 0},
        'A7': {'name': 'Current Price raw (ct/kWh)', 'type': 'float', 'default': 0.0},
        'A8': {'name': 'Current Price inkl. Aufschlag', 'type': 'float', 'default': 0.0},
        'A9': {'name': 'Next Start (Unix)', 'type': 'int', 'default': 0},
        'A10': {'name': 'Next Price inkl. Aufschlag', 'type': 'float', 'default': 0.0},
        'A11': {'name': 'Min 24h Start (Unix)', 'type': 'int', 'default': 0},
        'A12': {'name': 'Min 24h Price inkl. Aufschlag', 'type': 'float', 'default': 0.0},
        'A13': {'name': 'Max 24h Start (Unix)', 'type': 'int', 'default': 0},
        'A14': {'name': 'Max 24h Price inkl. Aufschlag', 'type': 'float', 'default': 0.0},
        'A15': {'name': 'Avg 24h Price inkl. Aufschlag', 'type': 'float', 'default': 0.0},
        'A16': {'name': 'JSON Next 24h', 'type': 'str', 'default': '[]'},
        'A17': {'name': 'JSON Heute 0-24h', 'type': 'str', 'default': '[]'},
        'A18': {'name': 'JSON Morgen 0-24h', 'type': 'str', 'default': '[]'},
    }
    
    AWATTAR_URL = "https://api.awattar.at/v1/marketdata"
    SMARTENERGY_URL = "https://apis.smartenergy.at/market/v1/price"
    
    def on_start(self):
        """Block gestartet"""
        logger.info(f"[{self.ID}] EPEX Spot Preis starting...")
        
        self._slots: List[Dict] = []
        self._last_fetch = 0
        self._poll_task: Optional[asyncio.Task] = None
        
        self._debug_values['Status'] = 'Init'
        self._debug_values['Provider'] = ''
        self._debug_values['Slots'] = '0'
        self._debug_values['Last Update'] = '-'
        
        # Start polling
        if self.get_input('E1'):
            self._start_polling()
    
    def on_stop(self):
        """Block gestoppt"""
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
        logger.info(f"[{self.ID}] EPEX Spot Preis stopped")
    
    def _start_polling(self):
        """Start the polling loop"""
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
        self._poll_task = asyncio.create_task(self._poll_loop())
    
    async def _poll_loop(self):
        """Main polling loop"""
        while True:
            try:
                if not self.get_input('E1'):
                    self._debug_values['Status'] = 'Gestoppt'
                    self.set_output('A1', 0)
                    self.set_output('A2', 'Stopped')
                    await asyncio.sleep(5)
                    continue
                
                await self._fetch_prices()
                
                interval = self.get_input('E2') or 300
                if interval < 30:
                    interval = 30
                
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{self.ID}] Poll loop error: {e}")
                self._debug_values['Status'] = f'Fehler: {str(e)[:30]}'
                await asyncio.sleep(60)
    
    async def _fetch_prices(self):
        """Fetch prices from provider"""
        provider = self.get_input('E3') or 0
        surcharge = self.get_input('E4') or 0.0
        debug = self.get_input('E5')
        
        try:
            if provider == 0:
                await self._fetch_awattar(surcharge, debug)
            else:
                await self._fetch_smartenergy(surcharge, debug)
                
        except Exception as e:
            logger.error(f"[{self.ID}] Fetch error: {e}")
            self.set_output('A1', 0)
            self.set_output('A2', str(e)[:100])
            self._debug_values['Status'] = f'Fehler: {str(e)[:30]}'
    
    async def _fetch_awattar(self, surcharge: float, debug: bool):
        """Fetch from aWATTar AT"""
        provider_name = "aWATTar AT"
        self._debug_values['Provider'] = provider_name
        
        # Build URL: from today midnight to day after tomorrow
        now = datetime.now()
        today_midnight = datetime(now.year, now.month, now.day).timestamp() * 1000
        day_after_tomorrow = (datetime(now.year, now.month, now.day).timestamp() + 2 * 86400) * 1000
        
        url = f"{self.AWATTAR_URL}?start={int(today_midnight)}&end={int(day_after_tomorrow)}"
        
        if debug:
            logger.info(f"[{self.ID}] GET {url}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=25)) as response:
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}")
                
                data = await response.json()
        
        if not data or 'data' not in data:
            raise Exception("Keine Daten in Response")
        
        # Parse slots
        self._slots = []
        for d in data['data']:
            if not isinstance(d, dict):
                continue
            start = d.get('start_timestamp', 0) // 1000
            end = d.get('end_timestamp', 0) // 1000
            price = d.get('marketprice')
            
            if start > 0 and end > 0 and price is not None:
                # Convert EUR/MWh to ct/kWh (multiply by 0.1)
                price_ct = float(price) * 0.1
                self._slots.append({'start': start, 'end': end, 'price': price_ct})
        
        self._slots.sort(key=lambda x: x['start'])
        
        if debug:
            logger.info(f"[{self.ID}] Parsed {len(self._slots)} slots")
        
        self._process_slots(provider_name, 60, surcharge)
    
    async def _fetch_smartenergy(self, surcharge: float, debug: bool):
        """Fetch from smartENERGY"""
        provider_name = "smartENERGY"
        self._debug_values['Provider'] = provider_name
        
        if debug:
            logger.info(f"[{self.ID}] GET {self.SMARTENERGY_URL}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(self.SMARTENERGY_URL, timeout=aiohttp.ClientTimeout(total=25)) as response:
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}")
                
                data = await response.json()
        
        if not data or 'data' not in data:
            raise Exception("Keine Daten in Response")
        
        interval_min = data.get('interval', 15)
        if interval_min <= 0:
            interval_min = 15
        slot_sec = interval_min * 60
        
        # Parse slots
        self._slots = []
        for d in data['data']:
            if not isinstance(d, dict):
                continue
            date_str = d.get('date', '')
            value = d.get('value')
            
            if date_str and value is not None:
                try:
                    # Parse ISO date - compatible with Python 3.7+
                    # smartENERGY format: "2026-02-10T00:00:00+01:00"
                    # Strip timezone offset and parse as naive local time
                    dt_str = date_str[:19]  # "2026-02-10T00:00:00"
                    dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
                    start = int(dt.timestamp())
                    end = start + slot_sec
                    # smartENERGY liefert Brutto (inkl. 20% MwSt) -> Netto
                    price_ct = float(value) / 1.2
                    self._slots.append({'start': start, 'end': end, 'price': price_ct})
                except Exception as e:
                    if debug:
                        logger.warning(f"[{self.ID}] Parse error for '{date_str}': {e}")
        
        self._slots.sort(key=lambda x: x['start'])
        
        if debug:
            logger.info(f"[{self.ID}] Parsed {len(self._slots)} slots")
        
        self._process_slots(provider_name, interval_min, surcharge)
    
    def _process_slots(self, provider_name: str, interval_min: int, surcharge: float):
        """Process slots and set outputs"""
        now = int(datetime.now().timestamp())
        
        if len(self._slots) == 0:
            self.set_output('A1', 0)
            self.set_output('A2', 'Keine Preis-Slots gefunden')
            return
        
        # Find current and next slot
        current_slot = None
        next_slot = None
        
        for s in self._slots:
            if s['start'] <= now < s['end']:
                current_slot = s
                break
        
        if current_slot:
            for s in self._slots:
                if s['start'] >= current_slot['end']:
                    next_slot = s
                    break
        else:
            # Fallback: first future slot as next
            for s in self._slots:
                if s['start'] > now:
                    next_slot = s
                    break
        
        # Calculate stats for next 24h
        end_window = now + 24 * 3600
        min_slot = None
        max_slot = None
        sum_price = 0.0
        count = 0
        json_24h = []
        
        for s in self._slots:
            if s['start'] >= now and s['start'] <= end_window:
                p_incl = s['price'] + surcharge
                
                if min_slot is None or p_incl < min_slot['p']:
                    min_slot = {'t': s['start'], 'p': p_incl}
                if max_slot is None or p_incl > max_slot['p']:
                    max_slot = {'t': s['start'], 'p': p_incl}
                
                sum_price += p_incl
                count += 1
                json_24h.append({'t': s['start'], 'p': round(p_incl, 4)})
        
        avg_price = sum_price / count if count > 0 else 0.0
        
        # JSON for today (0:00 - 23:59 local)
        today_start = int(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
        today_end = today_start + 86400 - 1
        
        json_today = []
        for s in self._slots:
            if today_start <= s['start'] <= today_end:
                json_today.append({'t': s['start'], 'p': round(s['price'] + surcharge, 4)})
        
        # JSON for tomorrow
        tomorrow_start = today_start + 86400
        tomorrow_end = tomorrow_start + 86400 - 1
        
        json_tomorrow = []
        for s in self._slots:
            if tomorrow_start <= s['start'] <= tomorrow_end:
                json_tomorrow.append({'t': s['start'], 'p': round(s['price'] + surcharge, 4)})
        
        # Set outputs
        self.set_output('A1', 1)
        self.set_output('A2', 'OK')
        self.set_output('A3', provider_name)
        self.set_output('A4', 'ct/kWh')
        self.set_output('A5', interval_min)
        
        if current_slot:
            self.set_output('A6', current_slot['start'])
            self.set_output('A7', round(current_slot['price'], 4))
            self.set_output('A8', round(current_slot['price'] + surcharge, 4))
        else:
            self.set_output('A6', 0)
            self.set_output('A7', 0.0)
            self.set_output('A8', 0.0)
        
        if next_slot:
            self.set_output('A9', next_slot['start'])
            self.set_output('A10', round(next_slot['price'] + surcharge, 4))
        else:
            self.set_output('A9', 0)
            self.set_output('A10', 0.0)
        
        self.set_output('A11', min_slot['t'] if min_slot else 0)
        self.set_output('A12', round(min_slot['p'], 4) if min_slot else 0.0)
        self.set_output('A13', max_slot['t'] if max_slot else 0)
        self.set_output('A14', round(max_slot['p'], 4) if max_slot else 0.0)
        self.set_output('A15', round(avg_price, 4))
        
        self.set_output('A16', json.dumps(json_24h))
        self.set_output('A17', json.dumps(json_today))
        self.set_output('A18', json.dumps(json_tomorrow))
        
        # Update debug
        self._debug_values['Status'] = 'OK'
        self._debug_values['Slots'] = str(len(self._slots))
        self._debug_values['Last Update'] = datetime.now().strftime('%H:%M:%S')
        self._debug_values['Current'] = f"{round(current_slot['price'] + surcharge, 2)} ct" if current_slot else '-'
        
        logger.info(f"[{self.ID}] Updated: {len(self._slots)} slots, current={self._debug_values['Current']}")
    
    def on_input_change(self, key, value, old_value):
        """Input changed"""
        logger.info(f"[{self.ID}] Input {key} changed: {value}")
        
        if key == 'E1':
            if value:
                self._debug_values['Status'] = 'Gestartet'
                self._start_polling()
            else:
                self._debug_values['Status'] = 'Gestoppt'
                if self._poll_task and not self._poll_task.done():
                    self._poll_task.cancel()
    
    def execute(self, triggered_by: str = None):
        """Execute - handled by polling loop"""
        pass
