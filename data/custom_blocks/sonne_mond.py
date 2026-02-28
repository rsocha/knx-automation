"""
Sonne & Mond (v1.0)

Berechnet Sonnenaufgang/-untergang, Tageslänge, Mondphase und Mondaufgang/-untergang
basierend auf geografischen Koordinaten.

Eingänge:
- E1: Breitengrad (Latitude, z.B. 48.137 für München)
- E2: Längengrad (Longitude, z.B. 11.576 für München)

Ausgänge:
- A1: Sonnenaufgang (HH:MM)
- A2: Sonnenuntergang (HH:MM)
- A3: Tageslänge (HH:MM)
- A4: Mondphase (Text: Neumond, Zunehmend, Vollmond, Abnehmend)
- A5: Mondaufgang (HH:MM)
- A6: Monduntergang (HH:MM)

Verwendung:
[Latitude 48.137] → E1
[Longitude 11.576] → E2
→ [Sonne & Mond] → A1..A6

Die Werte werden einmal pro Minute aktualisiert.
Benötigt: pip install ephem
"""

import asyncio
import logging
import math
from datetime import datetime, timedelta

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


def _fallback_sun_times(lat, lon, date=None):
    """Vereinfachte Sonnenberechnung ohne ephem-Bibliothek"""
    if date is None:
        date = datetime.now()
    
    day_of_year = date.timetuple().tm_yday
    
    # Vereinfachte Berechnung der Sonnendeklination
    declination = 23.45 * math.sin(math.radians((360 / 365) * (day_of_year - 81)))
    
    lat_rad = math.radians(lat)
    decl_rad = math.radians(declination)
    
    # Stundenwinkel
    cos_hour_angle = (
        math.sin(math.radians(-0.833)) - 
        math.sin(lat_rad) * math.sin(decl_rad)
    ) / (math.cos(lat_rad) * math.cos(decl_rad))
    
    # Polargebiete: Mitternachtssonne oder Polarnacht
    if cos_hour_angle > 1:
        return None, None  # Polarnacht
    elif cos_hour_angle < -1:
        return "00:00", "23:59"  # Mitternachtssonne
    
    hour_angle = math.degrees(math.acos(cos_hour_angle))
    
    # Zeitgleichung (vereinfacht)
    b = math.radians((360 / 365) * (day_of_year - 81))
    eot = 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)
    
    # Sonnenmittag in UTC
    solar_noon = 12 - (lon / 15) - (eot / 60)
    
    sunrise_utc = solar_noon - (hour_angle / 15)
    sunset_utc = solar_noon + (hour_angle / 15)
    
    # In lokale Zeit umrechnen (vereinfacht: UTC+1 für MEZ)
    # In der Praxis sollte die Zeitzone konfigurierbar sein
    import time
    utc_offset = -(time.timezone if time.daylight == 0 else time.altzone) / 3600
    
    sunrise_local = sunrise_utc + utc_offset
    sunset_local = sunset_utc + utc_offset
    
    sunrise_h = int(sunrise_local)
    sunrise_m = int((sunrise_local - sunrise_h) * 60)
    sunset_h = int(sunset_local)
    sunset_m = int((sunset_local - sunset_h) * 60)
    
    return f"{sunrise_h:02d}:{sunrise_m:02d}", f"{sunset_h:02d}:{sunset_m:02d}"


def _moon_phase(date=None):
    """Berechnet die Mondphase (vereinfacht)"""
    if date is None:
        date = datetime.now()
    
    # Referenz-Neumond: 6. Januar 2000
    ref = datetime(2000, 1, 6, 18, 14)
    diff = (date - ref).total_seconds()
    synodic_month = 29.53058867 * 86400  # Sekunden
    
    phase = (diff % synodic_month) / synodic_month
    
    if phase < 0.0625 or phase >= 0.9375:
        return "Neumond"
    elif phase < 0.3125:
        return "Zunehmend"
    elif phase < 0.5625:
        return "Vollmond"
    else:
        return "Abnehmend"


def _fallback_moon_times(lat, lon, date=None):
    """Vereinfachte Mondzeiten-Berechnung"""
    if date is None:
        date = datetime.now()
    
    # Sehr vereinfachte Berechnung
    # Mond geht ca. 50 Minuten später auf als am Vortag
    day_of_year = date.timetuple().tm_yday
    
    # Basis-Aufgang bei Vollmond: ca. Sonnenuntergang
    # Verschiebung: ca. 50 min/Tag relativ zum synodischen Monat
    ref = datetime(2000, 1, 6, 18, 14)
    diff = (date - ref).total_seconds()
    synodic_month = 29.53058867 * 86400
    phase_days = (diff % synodic_month) / 86400
    
    # Mondaufgang verschiebt sich um ca. 50 min pro Tag
    moonrise_hour = (18 + phase_days * (50 / 60)) % 24
    moonset_hour = (moonrise_hour + 12) % 24
    
    rise_h = int(moonrise_hour)
    rise_m = int((moonrise_hour - rise_h) * 60)
    set_h = int(moonset_hour)
    set_m = int((moonset_hour - set_h) * 60)
    
    return f"{rise_h:02d}:{rise_m:02d}", f"{set_h:02d}:{set_m:02d}"


class SonneMond(LogicBlock):
    """Berechnet Sonnen-/Monddaten basierend auf Koordinaten"""
    
    BLOCK_TYPE = "sonne_mond"
    ID = 20042
    NAME = "Sonne & Mond"
    DESCRIPTION = "Berechnet Sonnenaufgang/-untergang, Tageslänge, Mondphase und Mondzeiten"
    CATEGORY = "Hilfsmittel"
    
    INPUTS = {
        'E1': {'name': 'Breitengrad (Latitude)', 'type': 'float'},
        'E2': {'name': 'Längengrad (Longitude)', 'type': 'float'},
    }
    
    OUTPUTS = {
        'A1': {'name': 'Sonnenaufgang (HH:MM)', 'type': 'str'},
        'A2': {'name': 'Sonnenuntergang (HH:MM)', 'type': 'str'},
        'A3': {'name': 'Tageslänge (HH:MM)', 'type': 'str'},
        'A4': {'name': 'Mondphase', 'type': 'str'},
        'A5': {'name': 'Mondaufgang (HH:MM)', 'type': 'str'},
        'A6': {'name': 'Monduntergang (HH:MM)', 'type': 'str'},
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._update_task = None
        self._last_update_minute = -1
    
    def execute(self, triggered_by=None):
        """Startet die Berechnung wenn Koordinaten gesetzt werden"""
        lat = self.get_input('E1')
        lon = self.get_input('E2')
        
        if lat is not None and lon is not None:
            # Sofort berechnen
            self._calculate(lat, lon)
            
            # Periodische Aktualisierung starten
            if self._update_task is None or self._update_task.done():
                self._update_task = asyncio.create_task(self._update_loop())
    
    def _calculate(self, lat, lon):
        """Führt die Berechnung der Sonnen-/Monddaten durch"""
        try:
            now = datetime.now()
            
            if HAS_EPHEM:
                self._calculate_with_ephem(lat, lon, now)
            else:
                self._calculate_fallback(lat, lon, now)
                
            logger.debug(f"{self.instance_id}: Daten aktualisiert")
            
        except Exception as e:
            logger.error(f"{self.instance_id}: Berechnungsfehler: {e}")
    
    def _calculate_with_ephem(self, lat, lon, now):
        """Berechnung mit der ephem-Bibliothek (genau)"""
        observer = ephem.Observer()
        observer.lat = str(lat)
        observer.lon = str(lon)
        observer.date = now.strftime('%Y/%m/%d %H:%M:%S')
        observer.elevation = 0
        
        sun = ephem.Sun()
        moon = ephem.Moon()
        
        # Sonnenaufgang/-untergang
        try:
            sunrise = ephem.localtime(observer.next_rising(sun))
            sunset = ephem.localtime(observer.next_setting(sun))
            
            # Falls Untergang vor Aufgang → vorherigen Aufgang nehmen
            if sunset < sunrise:
                sunrise = ephem.localtime(observer.previous_rising(sun))
            
            self.set_output('A1', sunrise.strftime('%H:%M'))
            self.set_output('A2', sunset.strftime('%H:%M'))
            
            # Tageslänge
            day_length = sunset - sunrise
            hours = int(day_length.total_seconds() // 3600)
            minutes = int((day_length.total_seconds() % 3600) // 60)
            self.set_output('A3', f"{hours:02d}:{minutes:02d}")
            
        except (ephem.AlwaysUpError, ephem.NeverUpError):
            self.set_output('A1', '--:--')
            self.set_output('A2', '--:--')
            self.set_output('A3', '--:--')
        
        # Mondphase
        moon.compute(observer)
        phase_pct = moon.phase  # 0-100
        if phase_pct < 6.25:
            phase_name = "Neumond"
        elif phase_pct < 43.75:
            phase_name = "Zunehmend"
        elif phase_pct < 56.25:
            phase_name = "Vollmond"
        else:
            phase_name = "Abnehmend"
        self.set_output('A4', phase_name)
        
        # Mondaufgang/-untergang
        try:
            moonrise = ephem.localtime(observer.next_rising(moon))
            moonset = ephem.localtime(observer.next_setting(moon))
            self.set_output('A5', moonrise.strftime('%H:%M'))
            self.set_output('A6', moonset.strftime('%H:%M'))
        except (ephem.AlwaysUpError, ephem.NeverUpError):
            self.set_output('A5', '--:--')
            self.set_output('A6', '--:--')
    
    def _calculate_fallback(self, lat, lon, now):
        """Berechnung ohne ephem (vereinfacht)"""
        logger.info(f"{self.instance_id}: ephem nicht verfügbar, verwende Fallback")
        
        sunrise, sunset = _fallback_sun_times(lat, lon, now)
        
        if sunrise and sunset:
            self.set_output('A1', sunrise)
            self.set_output('A2', sunset)
            
            # Tageslänge berechnen
            sr_parts = sunrise.split(':')
            ss_parts = sunset.split(':')
            sr_min = int(sr_parts[0]) * 60 + int(sr_parts[1])
            ss_min = int(ss_parts[0]) * 60 + int(ss_parts[1])
            diff = ss_min - sr_min
            if diff < 0:
                diff += 1440
            self.set_output('A3', f"{diff // 60:02d}:{diff % 60:02d}")
        else:
            self.set_output('A1', '--:--')
            self.set_output('A2', '--:--')
            self.set_output('A3', '--:--')
        
        self.set_output('A4', _moon_phase(now))
        
        moonrise, moonset = _fallback_moon_times(lat, lon, now)
        self.set_output('A5', moonrise)
        self.set_output('A6', moonset)
    
    async def _update_loop(self):
        """Aktualisiert die Daten einmal pro Minute"""
        try:
            while True:
                await asyncio.sleep(60)
                
                lat = self.get_input('E1')
                lon = self.get_input('E2')
                
                if lat is not None and lon is not None:
                    self._calculate(lat, lon)
                else:
                    break
                    
        except asyncio.CancelledError:
            logger.debug(f"{self.instance_id}: Aktualisierung gestoppt")


# Für EDOMI-Kompatibilität
class_1 = SonneMond
