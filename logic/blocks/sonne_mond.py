"""
Sonne & Mond (v2.0) – Remanent

Berechnet Sonnenaufgang/-untergang, Tageslänge, Mondphase und Mondzeiten
basierend auf geografischen Koordinaten.

Eingänge:
- E1: Breitengrad (Latitude, z.B. 47.93 für Zurndorf)
- E2: Längengrad (Longitude, z.B. 16.97 für Zurndorf)
- E3: Trigger (1 = Sofort neu berechnen)
- E4: Update-Intervall in Minuten (Standard: 60)

Ausgänge:
- A1: Sonnenaufgang (HH:MM)
- A2: Sonnenuntergang (HH:MM)
- A3: Tageslänge (HH:MM)
- A4: Mondphase (Text)
- A5: Mondbeleuchtung (%)
- A6: Mondaufgang (HH:MM)
- A7: Monduntergang (HH:MM)
- A8: Dämmerung Beginn (HH:MM) – Bürgerliche Dämmerung morgens
- A9: Dämmerung Ende (HH:MM) – Bürgerliche Dämmerung abends
- A10: Tag/Nacht (1 = Tag, 0 = Nacht)
- A11: Debug / Status

Berechnung:
- Präzise Berechnung mit der ephem-Bibliothek (falls installiert)
- Fallback: Eigene Berechnung ohne externe Abhängigkeiten
- MESZ/MEZ wird automatisch erkannt

Remanent: Letzte Werte bleiben nach Reboot erhalten bis zum nächsten Update.
"""

import asyncio
import logging
import math
from datetime import datetime, timedelta, date, timezone

try:
    import ephem
    HAS_EPHEM = True
except ImportError:
    HAS_EPHEM = False

try:
    from ..base import LogicBlock
except ImportError:
    from logic.base import LogicBlock

logger = logging.getLogger(__name__)


# ============================================================================
# MESZ / MEZ Bestimmung
# ============================================================================

def _utc_offset_hours(dt=None):
    """Gibt UTC-Offset zurück: 2 für MESZ, 1 für MEZ"""
    if dt is None:
        dt = datetime.now()
    year = dt.year
    # Letzter Sonntag im März 02:00 UTC → MESZ Start
    march_last = datetime(year, 3, 31)
    mesz_start = march_last - timedelta(days=(march_last.weekday() + 1) % 7)
    mesz_start = mesz_start.replace(hour=2)
    # Letzter Sonntag im Oktober 03:00 UTC → MEZ Start
    oct_last = datetime(year, 10, 31)
    mesz_end = oct_last - timedelta(days=(oct_last.weekday() + 1) % 7)
    mesz_end = mesz_end.replace(hour=3)
    return 2 if mesz_start <= dt < mesz_end else 1


# ============================================================================
# FALLBACK: Sonnenberechnung ohne ephem
# ============================================================================

def _sun_times_fallback(lat, lon, dt=None):
    """Sonnenaufgang/-untergang ohne externe Bibliothek.
    Gibt (sunrise_hhmm, sunset_hhmm, dawn_hhmm, dusk_hhmm) zurück."""
    if dt is None:
        dt = datetime.now()

    day_of_year = dt.timetuple().tm_yday
    b_rad = math.radians((360 / 365) * (day_of_year - 81))

    # Sonnendeklination
    declination = 23.45 * math.sin(b_rad)
    lat_rad = math.radians(lat)
    decl_rad = math.radians(declination)

    # Zeitgleichung (Minuten)
    eot = 9.87 * math.sin(2 * b_rad) - 7.53 * math.cos(b_rad) - 1.5 * math.sin(b_rad)
    solar_noon_utc = 12 - (lon / 15) - (eot / 60)

    utc_off = _utc_offset_hours(dt)
    results = {}

    for label, zenith_angle in [('sun', -0.833), ('civil', -6.0)]:
        cos_ha = (
            math.sin(math.radians(zenith_angle)) -
            math.sin(lat_rad) * math.sin(decl_rad)
        ) / (math.cos(lat_rad) * math.cos(decl_rad))

        if cos_ha > 1:
            results[label] = (None, None)  # Polarnacht
        elif cos_ha < -1:
            results[label] = ("00:00", "23:59")  # Mitternachtssonne
        else:
            ha = math.degrees(math.acos(cos_ha))
            rise_utc = solar_noon_utc - (ha / 15)
            set_utc = solar_noon_utc + (ha / 15)
            rise_local = rise_utc + utc_off
            set_local = set_utc + utc_off

            def fmt(h):
                h = h % 24
                return f"{int(h):02d}:{int((h - int(h)) * 60):02d}"

            results[label] = (fmt(rise_local), fmt(set_local))

    sunrise, sunset = results.get('sun', (None, None))
    dawn, dusk = results.get('civil', (None, None))
    return sunrise, sunset, dawn, dusk


# ============================================================================
# FALLBACK: Mondberechnung ohne ephem
# ============================================================================

def _moon_phase_fallback(dt=None):
    """Mondphase und Beleuchtungsgrad (vereinfacht)"""
    if dt is None:
        dt = datetime.now()
    ref = datetime(2000, 1, 6, 18, 14)
    diff = (dt - ref).total_seconds()
    synodic = 29.53058867 * 86400
    phase = (diff % synodic) / synodic  # 0..1

    illumination = round((1 - math.cos(2 * math.pi * phase)) / 2 * 100)

    if phase < 0.0625 or phase >= 0.9375:
        name = "Neumond 🌑"
    elif phase < 0.25:
        name = "Zunehmende Sichel 🌒"
    elif phase < 0.3125:
        name = "Erstes Viertel 🌓"
    elif phase < 0.4375:
        name = "Zunehmender Mond 🌔"
    elif phase < 0.5625:
        name = "Vollmond 🌕"
    elif phase < 0.6875:
        name = "Abnehmender Mond 🌖"
    elif phase < 0.75:
        name = "Letztes Viertel 🌗"
    else:
        name = "Abnehmende Sichel 🌘"

    return name, illumination


def _moon_times_fallback(lat, lon, dt=None):
    """Mondauf-/untergang (grobe Annäherung)"""
    if dt is None:
        dt = datetime.now()
    ref = datetime(2000, 1, 6, 18, 14)
    diff = (dt - ref).total_seconds()
    synodic = 29.53058867 * 86400
    phase_days = (diff % synodic) / 86400

    utc_off = _utc_offset_hours(dt)
    moonrise_h = (18 + phase_days * (50 / 60) + utc_off - 1) % 24
    moonset_h = (moonrise_h + 12.4) % 24

    def fmt(h):
        return f"{int(h):02d}:{int((h - int(h)) * 60):02d}"

    return fmt(moonrise_h), fmt(moonset_h)


# ============================================================================
# BLOCK
# ============================================================================

class SonneMond(LogicBlock):
    """Berechnet Sonnen-/Monddaten basierend auf Koordinaten"""

    BLOCK_TYPE = "sonne_mond"
    ID = 20042
    NAME = "Sonne & Mond"
    DESCRIPTION = "Sonnenaufgang/-untergang, Tageslänge, Dämmerung, Mondphase und Mondzeiten"
    VERSION = "2.0"
    CATEGORY = "Hilfsmittel"
    REMANENT = True

    HELP = """Funktionsweise:
Berechnet Sonnen- und Monddaten für die eingestellten Koordinaten.
Die Daten werden beim Start und dann im konfigurierten Intervall
(Standard: 60 Minuten) automatisch aktualisiert.

Berechnung:
- Präzise Berechnung mit der ephem-Bibliothek (falls installiert: pip install ephem)
- Fallback: Eigene Berechnung ohne externe Abhängigkeiten
- MESZ/MEZ wird automatisch erkannt
- A10 (Tag/Nacht) wechselt bei Sonnenaufgang auf 1, bei Sonnenuntergang auf 0

Remanent:
Letzte Werte bleiben nach Reboot sichtbar bis zum nächsten Update.

Versionshistorie:
v2.0 – Trigger-Eingang, Auto-Update, Dämmerung, Tag/Nacht-Ausgang, Mondbeleuchtung %, Remanenz, HELP
v1.0 – Erstversion mit ephem + Fallback"""

    INPUTS = {
        'E1': {'name': 'Breitengrad (Latitude)', 'type': 'float', 'default': 47.93},
        'E2': {'name': 'Längengrad (Longitude)', 'type': 'float', 'default': 16.97},
        'E3': {'name': 'Trigger', 'type': 'bool', 'default': False},
        'E4': {'name': 'Update-Intervall (min)', 'type': 'int', 'default': 60},
    }

    OUTPUTS = {
        'A1':  {'name': 'Sonnenaufgang', 'type': 'str'},
        'A2':  {'name': 'Sonnenuntergang', 'type': 'str'},
        'A3':  {'name': 'Tageslänge', 'type': 'str'},
        'A4':  {'name': 'Mondphase', 'type': 'str'},
        'A5':  {'name': 'Mondbeleuchtung (%)', 'type': 'int'},
        'A6':  {'name': 'Mondaufgang', 'type': 'str'},
        'A7':  {'name': 'Monduntergang', 'type': 'str'},
        'A8':  {'name': 'Dämmerung Beginn', 'type': 'str'},
        'A9':  {'name': 'Dämmerung Ende', 'type': 'str'},
        'A10': {'name': 'Tag/Nacht (1/0)', 'type': 'int'},
        'A11': {'name': 'Debug / Status', 'type': 'str'},
    }

    TRIGGER_ALWAYS_INPUTS = ['E3']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._update_task = None

    def set_input(self, key, value, force_trigger=False):
        """E3 (Trigger) löst immer aus"""
        if key in self.TRIGGER_ALWAYS_INPUTS:
            self._input_values[key] = bool(value) if value else False
            if self._enabled:
                self._trigger_execute(key)
            return True
        return super().set_input(key, value, force_trigger)

    def on_start(self):
        super().on_start()
        self.debug('Version', self.VERSION)
        self.debug('ephem', 'Ja' if HAS_EPHEM else 'Nein (Fallback)')

        # Sofort berechnen beim Start
        self._do_calculate()

        # Auto-Update-Loop starten
        if self._update_task is None or self._update_task.done():
            self._update_task = asyncio.ensure_future(self._update_loop())

    def on_stop(self):
        if self._update_task and not self._update_task.done():
            self._update_task.cancel()
            self._update_task = None
        super().on_stop()

    def execute(self, triggered_by=None):
        """Koordinaten-Änderung oder Trigger → sofort berechnen"""
        if triggered_by in ('E1', 'E2', 'E3'):
            self._do_calculate()
        elif triggered_by == 'E4':
            # Intervall geändert → Loop neu starten
            if self._update_task and not self._update_task.done():
                self._update_task.cancel()
            self._update_task = asyncio.ensure_future(self._update_loop())

    def _do_calculate(self):
        """Berechnung durchführen"""
        lat = self.get_input('E1')
        lon = self.get_input('E2')
        if lat is None or lon is None:
            self.set_output('A11', 'Fehler: Koordinaten fehlen')
            self.debug('Status', 'Keine Koordinaten')
            return

        try:
            lat = float(lat)
            lon = float(lon)
        except (ValueError, TypeError):
            self.set_output('A11', 'Fehler: Ungültige Koordinaten')
            return

        now = datetime.now()

        if HAS_EPHEM:
            self._calc_ephem(lat, lon, now)
        else:
            self._calc_fallback(lat, lon, now)

        self.set_output('A11', f'OK – {now.strftime("%H:%M:%S")}')
        self.debug('Status', f'Aktualisiert {now.strftime("%H:%M:%S")}')
        self.debug('Koordinaten', f'{lat:.4f}, {lon:.4f}')

    # ----------------------------------------------------------------
    # ephem-Berechnung (präzise)
    # ----------------------------------------------------------------

    def _calc_ephem(self, lat, lon, now):
        """Berechnung mit pyephem"""
        obs = ephem.Observer()
        obs.lat = str(lat)
        obs.lon = str(lon)
        obs.date = now.strftime('%Y/%m/%d %H:%M:%S')
        obs.elevation = 0

        sun = ephem.Sun()
        moon = ephem.Moon()

        # --- Sonne ---
        try:
            sunrise = ephem.localtime(obs.next_rising(sun))
            sunset = ephem.localtime(obs.next_setting(sun))
            if sunset < sunrise:
                sunrise = ephem.localtime(obs.previous_rising(sun))

            sr_str = sunrise.strftime('%H:%M')
            ss_str = sunset.strftime('%H:%M')
            self.set_output('A1', sr_str)
            self.set_output('A2', ss_str)

            day_len = sunset - sunrise
            h = int(day_len.total_seconds() // 3600)
            m = int((day_len.total_seconds() % 3600) // 60)
            self.set_output('A3', f'{h:02d}:{m:02d}')

            # Tag/Nacht
            is_day = 1 if sunrise <= now <= sunset else 0
            self.set_output('A10', is_day)

        except (ephem.AlwaysUpError, ephem.NeverUpError) as e:
            is_always_up = isinstance(e, ephem.AlwaysUpError)
            self.set_output('A1', '--:--')
            self.set_output('A2', '--:--')
            self.set_output('A3', '24:00' if is_always_up else '00:00')
            self.set_output('A10', 1 if is_always_up else 0)

        # --- Bürgerliche Dämmerung ---
        try:
            obs.horizon = '-6'
            dawn = ephem.localtime(obs.next_rising(sun, use_center=True))
            dusk = ephem.localtime(obs.next_setting(sun, use_center=True))
            if dusk < dawn:
                dawn = ephem.localtime(obs.previous_rising(sun, use_center=True))
            self.set_output('A8', dawn.strftime('%H:%M'))
            self.set_output('A9', dusk.strftime('%H:%M'))
            obs.horizon = '0'  # Reset
        except (ephem.AlwaysUpError, ephem.NeverUpError):
            self.set_output('A8', '--:--')
            self.set_output('A9', '--:--')

        # --- Mond ---
        moon.compute(obs)
        illumination = round(moon.phase)  # 0-100
        self.set_output('A5', illumination)

        # Mondphase als Text
        phase_pct = moon.phase
        if phase_pct < 6.25:
            phase_name = "Neumond 🌑"
        elif phase_pct < 25:
            phase_name = "Zunehmende Sichel 🌒"
        elif phase_pct < 37.5:
            phase_name = "Erstes Viertel 🌓"
        elif phase_pct < 50:
            phase_name = "Zunehmender Mond 🌔"
        elif phase_pct < 56.25:
            phase_name = "Vollmond 🌕"
        elif phase_pct < 68.75:
            phase_name = "Abnehmender Mond 🌖"
        elif phase_pct < 75:
            phase_name = "Letztes Viertel 🌗"
        else:
            phase_name = "Abnehmende Sichel 🌘"
        self.set_output('A4', phase_name)

        try:
            moonrise = ephem.localtime(obs.next_rising(moon))
            moonset = ephem.localtime(obs.next_setting(moon))
            self.set_output('A6', moonrise.strftime('%H:%M'))
            self.set_output('A7', moonset.strftime('%H:%M'))
        except (ephem.AlwaysUpError, ephem.NeverUpError):
            self.set_output('A6', '--:--')
            self.set_output('A7', '--:--')

    # ----------------------------------------------------------------
    # Fallback-Berechnung (ohne ephem)
    # ----------------------------------------------------------------

    def _calc_fallback(self, lat, lon, now):
        """Berechnung ohne externe Bibliothek"""
        sunrise, sunset, dawn, dusk = _sun_times_fallback(lat, lon, now)

        self.set_output('A1', sunrise or '--:--')
        self.set_output('A2', sunset or '--:--')

        if sunrise and sunset:
            sr_parts = sunrise.split(':')
            ss_parts = sunset.split(':')
            sr_min = int(sr_parts[0]) * 60 + int(sr_parts[1])
            ss_min = int(ss_parts[0]) * 60 + int(ss_parts[1])
            diff = ss_min - sr_min
            if diff < 0:
                diff += 1440
            self.set_output('A3', f'{diff // 60:02d}:{diff % 60:02d}')

            # Tag/Nacht
            now_min = now.hour * 60 + now.minute
            self.set_output('A10', 1 if sr_min <= now_min <= ss_min else 0)
        else:
            self.set_output('A3', '--:--')
            self.set_output('A10', 0)

        self.set_output('A8', dawn or '--:--')
        self.set_output('A9', dusk or '--:--')

        phase_name, illumination = _moon_phase_fallback(now)
        self.set_output('A4', phase_name)
        self.set_output('A5', illumination)

        moonrise, moonset = _moon_times_fallback(lat, lon, now)
        self.set_output('A6', moonrise)
        self.set_output('A7', moonset)

    # ----------------------------------------------------------------
    # Auto-Update Loop
    # ----------------------------------------------------------------

    async def _update_loop(self):
        """Periodische Aktualisierung"""
        try:
            while self._running:
                interval = self.get_input('E4')
                try:
                    interval = max(1, int(interval or 60))
                except (ValueError, TypeError):
                    interval = 60

                await asyncio.sleep(interval * 60)

                if self._running:
                    self._do_calculate()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[SonneMond] update loop error: {e}")

    # ----------------------------------------------------------------
    # Remanenz
    # ----------------------------------------------------------------

    def get_remanent_state(self):
        """Letzte Werte speichern"""
        return {'outputs': dict(self._output_values)}

    def restore_remanent_state(self, state):
        """Werte wiederherstellen bis zum nächsten Update"""
        if not state:
            return
        for key, val in state.get('outputs', {}).items():
            if key in self.OUTPUTS:
                self._output_values[key] = val
        self.debug('Status', 'Wiederhergestellt – wartet auf Update')


# Für EDOMI-Kompatibilität
class_1 = SonneMond
