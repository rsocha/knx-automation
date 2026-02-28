"""
iCal-Termine (20044) – Kalender-Abfrage mit 5 Suchslots
=========================================================
Portierung des Gira HSL Bausteins 14490 für KNX-Automation.

Liest eine iCal-URL aus, sucht nach bis zu 5 verschiedenen Terminnamen
und gibt pro Slot den nächsten Termin, Wochentag, Tage bis zum Termin
und eine Vorwarnung aus.

Eingänge:
  E1  - iCal-URL (string)
  E2  - Trigger (bool, TRIGGER_ALWAYS)
  E3  - Suchbegriff Slot 1 (string)
  E4  - Suchbegriff Slot 2 (string)
  E5  - Suchbegriff Slot 3 (string)
  E6  - Suchbegriff Slot 4 (string)
  E7  - Suchbegriff Slot 5 (string)
  E8  - Vorwarnzeit Slot 1 in Tagen (int, default 1)
  E9  - Vorwarnzeit Slot 2 in Tagen (int, default 1)
  E10 - Vorwarnzeit Slot 3 in Tagen (int, default 1)
  E11 - Vorwarnzeit Slot 4 in Tagen (int, default 1)
  E12 - Vorwarnzeit Slot 5 in Tagen (int, default 1)
  E13 - Auto-Trigger Uhrzeit "HH:MM" (string)
  E14 - Auto-Trigger Ein/Aus (bool, default 0)

Ausgänge:
  A1  - Summe aller Vorwarnungen (int)
  A2  - Text Slot 1 (string)     A3  - Vorwarnung 1 (int 0/1)
  A4  - Nächster Termin 1 (string DD.MM.YYYY)
  A5  - Wochentag 1 (string)     A6  - Tage bis Termin 1 (int)
  A7  - Text Slot 2              A8  - Vorwarnung 2
  A9  - Nächster Termin 2        A10 - Wochentag 2      A11 - Tage 2
  A12 - Text Slot 3              A13 - Vorwarnung 3
  A14 - Nächster Termin 3        A15 - Wochentag 3      A16 - Tage 3
  A17 - Text Slot 4              A18 - Vorwarnung 4
  A19 - Nächster Termin 4        A20 - Wochentag 4      A21 - Tage 4
  A22 - Text Slot 5              A23 - Vorwarnung 5
  A24 - Nächster Termin 5        A25 - Wochentag 5      A26 - Tage 5
  A27 - Debug / Status (string)
"""

from logic.base import LogicBlock
import aiohttp
import asyncio
import logging
from datetime import datetime, date, time as dtime, timedelta
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)

# Deutsche Wochentage
WOCHENTAGE = ("Montag", "Dienstag", "Mittwoch", "Donnerstag",
              "Freitag", "Samstag", "Sonntag")


class ICalTermine(LogicBlock):
    ID = 20044
    NAME = "iCal-Termine"
    DESCRIPTION = "iCal-Kalender abfragen – 5 Suchslots mit Vorwarnung und Auto-Trigger"
    VERSION = "2.0"
    AUTHOR = "r.socha"
    CATEGORY = "Kalender"

    INPUTS = {
        'E1':  {'name': 'iCal-URL',                   'type': 'str', 'default': ''},
        'E2':  {'name': 'Trigger',                     'type': 'bool', 'default': False},
        'E3':  {'name': 'Name 1',                      'type': 'str', 'default': ''},
        'E4':  {'name': 'Name 2',                      'type': 'str', 'default': ''},
        'E5':  {'name': 'Name 3',                      'type': 'str', 'default': ''},
        'E6':  {'name': 'Name 4',                      'type': 'str', 'default': ''},
        'E7':  {'name': 'Name 5',                      'type': 'str', 'default': ''},
        'E8':  {'name': 'Vorwarnzeit 1 (Tage)',        'type': 'int', 'default': 1},
        'E9':  {'name': 'Vorwarnzeit 2 (Tage)',        'type': 'int', 'default': 1},
        'E10': {'name': 'Vorwarnzeit 3 (Tage)',        'type': 'int', 'default': 1},
        'E11': {'name': 'Vorwarnzeit 4 (Tage)',        'type': 'int', 'default': 1},
        'E12': {'name': 'Vorwarnzeit 5 (Tage)',        'type': 'int', 'default': 1},
        'E13': {'name': 'Auto-Trigger Uhrzeit (HH:MM)', 'type': 'str', 'default': ''},
        'E14': {'name': 'Auto-Trigger Ein/Aus',        'type': 'bool', 'default': False},
    }

    # 5 Slots × 5 Ausgänge + SumWarn + Debug = 27
    OUTPUTS = {
        'A1':  {'name': 'Summe Vorwarnungen', 'type': 'int', 'default': 0},
        # Slot 1
        'A2':  {'name': 'Text Tonne 1',       'type': 'str', 'default': ''},
        'A3':  {'name': 'Vorwarnung 1',        'type': 'int', 'default': 0},
        'A4':  {'name': 'Nächster Termin 1',   'type': 'str', 'default': ''},
        'A5':  {'name': 'Wochentag 1',         'type': 'str', 'default': ''},
        'A6':  {'name': 'Tage bis Termin 1',   'type': 'int', 'default': 0},
        # Slot 2
        'A7':  {'name': 'Text Tonne 2',       'type': 'str', 'default': ''},
        'A8':  {'name': 'Vorwarnung 2',        'type': 'int', 'default': 0},
        'A9':  {'name': 'Nächster Termin 2',   'type': 'str', 'default': ''},
        'A10': {'name': 'Wochentag 2',         'type': 'str', 'default': ''},
        'A11': {'name': 'Tage bis Termin 2',   'type': 'int', 'default': 0},
        # Slot 3
        'A12': {'name': 'Text Tonne 3',       'type': 'str', 'default': ''},
        'A13': {'name': 'Vorwarnung 3',        'type': 'int', 'default': 0},
        'A14': {'name': 'Nächster Termin 3',   'type': 'str', 'default': ''},
        'A15': {'name': 'Wochentag 3',         'type': 'str', 'default': ''},
        'A16': {'name': 'Tage bis Termin 3',   'type': 'int', 'default': 0},
        # Slot 4
        'A17': {'name': 'Text Tonne 4',       'type': 'str', 'default': ''},
        'A18': {'name': 'Vorwarnung 4',        'type': 'int', 'default': 0},
        'A19': {'name': 'Nächster Termin 4',   'type': 'str', 'default': ''},
        'A20': {'name': 'Wochentag 4',         'type': 'str', 'default': ''},
        'A21': {'name': 'Tage bis Termin 4',   'type': 'int', 'default': 0},
        # Slot 5
        'A22': {'name': 'Text Tonne 5',       'type': 'str', 'default': ''},
        'A23': {'name': 'Vorwarnung 5',        'type': 'int', 'default': 0},
        'A24': {'name': 'Nächster Termin 5',   'type': 'str', 'default': ''},
        'A25': {'name': 'Wochentag 5',         'type': 'str', 'default': ''},
        'A26': {'name': 'Tage bis Termin 5',   'type': 'int', 'default': 0},
        # Debug
        'A27': {'name': 'Debug / Status',      'type': 'str', 'default': ''},
    }

    TRIGGER_ALWAYS_INPUTS = ['E2']

    # Slot-Layout:  (search_input, vwz_input, out_summary, out_warn, out_date, out_wotag, out_days)
    SLOTS = [
        ('E3',  'E8',  'A2',  'A3',  'A4',  'A5',  'A6'),
        ('E4',  'E9',  'A7',  'A8',  'A9',  'A10', 'A11'),
        ('E5',  'E10', 'A12', 'A13', 'A14', 'A15', 'A16'),
        ('E6',  'E11', 'A17', 'A18', 'A19', 'A20', 'A21'),
        ('E7',  'E12', 'A22', 'A23', 'A24', 'A25', 'A26'),
    ]

    # ------------------------------------------------------------------ lifecycle
    def on_start(self):
        self._last_auto_key: Optional[str] = None
        self._auto_task: Optional[asyncio.Task] = None
        self._sbc_cache: dict = {}  # send-by-change cache
        self._running_flag = True

        self.debug('Version', self.VERSION)
        self.debug('Status', 'Initialisiert')
        self.debug('Auto-Trigger', '(nicht konfiguriert)')

        # Start auto-trigger check loop
        self._auto_task = asyncio.ensure_future(self._auto_loop())

    def on_stop(self):
        self._running_flag = False
        if self._auto_task and not self._auto_task.done():
            self._auto_task.cancel()

    # ------------------------------------------------------------------ input handling
    def set_input(self, key, value, force_trigger=False):
        """Override: E2 (Trigger) löst IMMER aus, auch bei gleichem Wert."""
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

    def execute(self, triggered_by=None):
        """Sync entry point – dispatches async work."""
        if triggered_by == 'E2':
            task = asyncio.ensure_future(self._safe_fetch())

    async def _safe_fetch(self):
        """Wrapper with error logging for the async fetch task."""
        try:
            await self._fetch_and_process()
        except Exception as e:
            logger.error(f"[ICalTermine] fetch error: {e}")
            self._set_sbc('A27', f'Fehler: {e}')
            self.debug('Status', f'Fehler: {e}')

    # ------------------------------------------------------------------ auto-trigger loop
    async def _auto_loop(self):
        """Check every 30 s whether Auto-Trigger time has been reached."""
        try:
            while self._running_flag:
                await asyncio.sleep(30)
                if not self._running_flag:
                    break

                enabled = self.get_input('E14')
                if not enabled:
                    continue

                target = self._parse_time(self.get_input('E13'))
                if target is None:
                    continue

                now = datetime.now()
                if now.hour == target[0] and now.minute == target[1]:
                    key = now.strftime('%Y%m%d_%H%M')
                    if key != self._last_auto_key:
                        self._last_auto_key = key
                        self.debug('Last Auto-Trigger', now.strftime('%d.%m.%Y %H:%M:%S'))
                        await self._fetch_and_process()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[ICalTermine] auto_loop error: {e}")

    # ------------------------------------------------------------------ core
    async def _fetch_and_process(self):
        """Download iCal, parse events, fill outputs."""
        url = str(self.get_input('E1') or '').strip()
        if not url:
            self._set_sbc('A27', 'Keine URL konfiguriert')
            self.debug('Status', 'Fehler – keine URL')
            return

        self.debug('Status', 'Daten abrufen…')
        self.debug('URL', url[:80])

        # 1) Download
        try:
            ical_text = await self._download(url)
        except Exception as e:
            self._set_sbc('A27', f'Download-Fehler: {e}')
            self.debug('Status', f'Fehler: {e}')
            return

        # 2) Parse
        try:
            events = self._parse_ical(ical_text)
        except Exception as e:
            self._set_sbc('A27', f'Parse-Fehler: {e}')
            self.debug('Status', f'Parse-Fehler: {e}')
            return

        # 3) Filter future events (today counts as future!), sort by date
        today = date.today()
        future: List[Tuple[str, datetime]] = []
        for summary, dtstart in events:
            event_date = dtstart.date() if isinstance(dtstart, datetime) else dtstart
            if event_date >= today:
                future.append((summary, dtstart))
        future.sort(key=lambda x: x[1])

        self.debug('Events gesamt', str(len(events)))
        self.debug('Zukünftige Events', str(len(future)))
        self._set_sbc('A27', f'VEVENT future: {len(future)}')

        # 4) Reset all slot outputs
        for slot in self.SLOTS:
            _, _, o_sum, o_warn, o_date, o_wotag, o_days = slot
            self._set_sbc(o_sum, '')
            self._set_sbc(o_warn, 0)
            self._set_sbc(o_date, '')
            self._set_sbc(o_wotag, '')
            self._set_sbc(o_days, 0)

        # 5) Match events to slots
        today = date.today()
        warnings_sum = 0

        for slot in self.SLOTS:
            search_key, vwz_key, o_sum, o_warn, o_date, o_wotag, o_days = slot
            search_text = str(self.get_input(search_key) or '').strip()
            if not search_text:
                continue

            vwz = self._to_int(self.get_input(vwz_key), 1)

            # Find first matching future event
            for summary, dtstart in future:
                if summary == search_text:
                    event_date = dtstart.date() if isinstance(dtstart, datetime) else dtstart
                    diff_days = (event_date - today).days
                    wochentag = WOCHENTAGE[event_date.weekday()]
                    date_str = event_date.strftime('%d.%m.%Y')
                    warn = 1 if diff_days == vwz else 0

                    self._set_sbc(o_sum, search_text)
                    self._set_sbc(o_warn, warn)
                    self._set_sbc(o_date, date_str)
                    self._set_sbc(o_wotag, wochentag)
                    self._set_sbc(o_days, diff_days)
                    warnings_sum += warn
                    break  # Only first match per slot

        self._set_sbc('A1', warnings_sum)
        self.debug('Status', f'OK – {len(future)} Termine')
        self.debug('Last Update', datetime.now().strftime('%d.%m.%Y %H:%M:%S'))

    # ------------------------------------------------------------------ helpers
    async def _download(self, url: str, timeout: int = 15) -> str:
        """Download iCal data via HTTP(S) or read from local file."""
        # Support file:// paths and plain filesystem paths
        if url.startswith('file://'):
            path = url[7:]  # strip file://
            try:
                with open(path, 'rb') as f:
                    raw = f.read()
            except Exception as e:
                raise RuntimeError(f"Datei nicht lesbar: {path} – {e}")
        elif url.startswith('/'):
            # Plain file path
            try:
                with open(url, 'rb') as f:
                    raw = f.read()
            except Exception as e:
                raise RuntimeError(f"Datei nicht lesbar: {url} – {e}")
        else:
            # HTTP(S) download
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout),
                                       ssl=False) as resp:
                    if resp.status != 200:
                        raise RuntimeError(f"HTTP {resp.status} von {url}")
                    raw = await resp.read()

        # Decode: try UTF-8 first, then ISO-8859-15
        for enc in ('utf-8', 'iso-8859-15', 'latin-1'):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw.decode('utf-8', errors='replace')

    def _parse_ical(self, text: str) -> List[Tuple[str, datetime]]:
        """
        Minimal iCal parser – returns list of (summary, dtstart).
        Does NOT require the ``icalendar`` package.
        Handles line folding (RFC 5545 §3.1).
        """
        events: List[Tuple[str, datetime]] = []
        in_event = False
        summary = ''
        dtstart: Optional[datetime] = None

        # Unfold continuation lines (RFC 5545: line starting with space/tab)
        unfolded = text.replace('\r\n ', '').replace('\r\n\t', '')

        for line in unfolded.splitlines():
            line = line.strip()
            if line == 'BEGIN:VEVENT':
                in_event = True
                summary = ''
                dtstart = None
            elif line == 'END:VEVENT':
                if in_event and summary and dtstart is not None:
                    events.append((summary, dtstart))
                in_event = False
            elif in_event:
                if line.upper().startswith('SUMMARY'):
                    # SUMMARY:text  or  SUMMARY;LANGUAGE=de:text
                    summary = line.split(':', 1)[-1].strip()
                elif line.upper().startswith('DTSTART'):
                    dtstart = self._parse_dt(line)

        return events

    def _parse_dt(self, line: str) -> Optional[datetime]:
        """Parse DTSTART line → datetime (naive, local)."""
        # Examples:
        #   DTSTART:20250301T080000Z
        #   DTSTART;VALUE=DATE:20250301
        #   DTSTART;TZID=Europe/Berlin:20250301T080000
        val = line.split(':', 1)[-1].strip()
        val = val.replace('Z', '')  # Ignore timezone marker for naive comparison

        for fmt in ('%Y%m%dT%H%M%S', '%Y%m%d'):
            try:
                return datetime.strptime(val, fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _parse_time(val) -> Optional[tuple]:
        """Parse 'HH:MM' → (hour, minute) or None."""
        if not val:
            return None
        try:
            s = str(val).strip()
            if ':' in s:
                parts = s.split(':')
                h, m = int(parts[0]), int(parts[1])
                if 0 <= h <= 23 and 0 <= m <= 59:
                    return (h, m)
        except (ValueError, IndexError):
            pass
        return None

    @staticmethod
    def _to_int(val, default: int = 0) -> int:
        try:
            return int(val)
        except (TypeError, ValueError):
            return default

    def _set_sbc(self, key: str, value):
        """Set output only on change (Send-By-Change)."""
        if self._sbc_cache.get(key) == value:
            return
        self._sbc_cache[key] = value
        self.set_output(key, value)
