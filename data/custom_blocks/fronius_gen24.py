"""
Fronius Gen24 Solar API LogicBlock (ID 20030)

Liest Daten vom Fronius Gen24 Plus Wechselrichter via lokaler Solar API.
Unterstützt SmartMeter TS 65A-3 und Fronius Reserva Batterie.

Version: 1.6
Author: r.socha
"""

import asyncio
import aiohttp
import logging
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any

try:
    from ..base import LogicBlock
except ImportError:
    from logic.base import LogicBlock

logger = logging.getLogger(__name__)


class FroniusGen24(LogicBlock):
    """Fronius Gen24 Solar API - Wechselrichter Daten"""
    
    ID = 20030
    NAME = "Fronius Gen24 Solar API"
    DESCRIPTION = "Liest PV, Batterie und Grid-Daten vom Fronius Gen24 Plus Wechselrichter"
    VERSION = "1.5"
    AUTHOR = "r.socha"
    CATEGORY = "Energie"
    
    # Persistenz-Datei für Peak-Werte (remanent)
    PEAK_FILE = "fronius_peaks_{instance_id}.json"
    
    # Inverter Status Codes
    INVERTER_STATUS = {
        0: 'Startup',
        1: 'Running',
        2: 'Standby',
        3: 'Bootloader',
        4: 'Error',
        5: 'Idle',
        6: 'Ready',
        7: 'Running',
        8: 'Running MPP',
        9: 'Running Master',
        10: 'Running Slave'
    }
    
    # Batterie Status Codes
    BATTERY_STATUS = {
        0: 'Normal',
        1: 'Full Backup',
        2: 'Hold',
        3: 'Charge Boost',
        4: 'Discharge Boost',
        5: 'Standby',
        6: 'Service',
        7: 'Charge',
        8: 'Discharge'
    }
    
    INPUTS = {
        'E1': {'name': 'Trigger (1=Start, 0=Stop)', 'type': 'bool', 'default': True},
        'E2': {'name': 'Fronius IP-Adresse', 'type': 'str', 'default': '192.168.1.100'},
        'E3': {'name': 'Poll Intervall (Sek)', 'type': 'int', 'default': 10},
        'E4': {'name': 'Peak Reset Uhrzeit (HH:MM)', 'type': 'str', 'default': '00:00'},
        'E5': {'name': 'Debug (0/1)', 'type': 'bool', 'default': False},
    }
    
    OUTPUTS = {
        # Status
        'A1': {'name': 'Status (1=OK, 0=ERR)', 'type': 'bool'},
        'A2': {'name': 'Error Message', 'type': 'str'},
        'A3': {'name': 'Timestamp (HH:MM:SS)', 'type': 'str'},
        
        # PV
        'A4': {'name': 'PV Leistung (W)', 'type': 'float'},
        'A5': {'name': 'PV Energie heute (Wh)', 'type': 'float'},
        'A6': {'name': 'PV Energie gesamt (Wh)', 'type': 'float'},
        
        # Batterie
        'A7': {'name': 'Batterie Leistung (W)', 'type': 'float'},
        'A8': {'name': 'Batterie SOC (%)', 'type': 'float'},
        'A9': {'name': 'Batterie Kapazität (Wh)', 'type': 'float'},
        
        # Grid
        'A10': {'name': 'Grid Bezug (W)', 'type': 'float'},
        'A11': {'name': 'Grid Einspeisung (W)', 'type': 'float'},
        'A12': {'name': 'Grid Bezug heute (Wh)', 'type': 'float'},
        'A13': {'name': 'Grid Einspeisung heute (Wh)', 'type': 'float'},
        
        # Verbrauch
        'A14': {'name': 'Hausverbrauch (W)', 'type': 'float'},
        'A15': {'name': 'Eigenverbrauch (%)', 'type': 'float'},
        
        # Peak Werte
        'A16': {'name': 'PV Peak heute (W)', 'type': 'float'},
        'A17': {'name': 'PV Peak Zeit (HH:MM)', 'type': 'str'},
        'A18': {'name': 'Grid Bezug Peak heute (W)', 'type': 'float'},
        'A19': {'name': 'Grid Bezug Peak Zeit (HH:MM)', 'type': 'str'},
        'A20': {'name': 'Grid Einspeisung Peak heute (W)', 'type': 'float'},
        'A21': {'name': 'Grid Einspeisung Peak Zeit (HH:MM)', 'type': 'str'},
        'A22': {'name': 'Batterie Laden Peak heute (W)', 'type': 'float'},
        'A23': {'name': 'Batterie Laden Peak Zeit (HH:MM)', 'type': 'str'},
        'A24': {'name': 'Batterie Entladen Peak heute (W)', 'type': 'float'},
        'A25': {'name': 'Batterie Entladen Peak Zeit (HH:MM)', 'type': 'str'},
        'A26': {'name': 'Hausverbrauch Peak heute (W)', 'type': 'float'},
        'A27': {'name': 'Hausverbrauch Peak Zeit (HH:MM)', 'type': 'str'},
        
        # Status
        'A28': {'name': 'Inverter Status', 'type': 'str'},
        'A29': {'name': 'Batterie Status', 'type': 'str'},
    }
    
    def __init__(self, instance_id: str):
        super().__init__(instance_id)
        
        # Peak-Werte (remanent)
        self._pv_peak_w = 0.0
        self._pv_peak_time = ''
        self._grid_import_peak_w = 0.0
        self._grid_import_peak_time = ''
        self._grid_export_peak_w = 0.0
        self._grid_export_peak_time = ''
        self._bat_charge_peak_w = 0.0
        self._bat_charge_peak_time = ''
        self._bat_discharge_peak_w = 0.0
        self._bat_discharge_peak_time = ''
        self._load_peak_w = 0.0
        self._load_peak_time = ''
        
        # Mitternachts-Referenzwerte
        self._grid_import_midnight = 0.0
        self._grid_export_midnight = 0.0
        self._pv_total_midnight = 0.0
        self._last_reset_date = ''
        
        # Peak-Datei-Pfad
        self._peak_file = self.PEAK_FILE.format(instance_id=instance_id)
    
    def on_start(self):
        """Block gestartet - lade persistierte Peak-Werte und starte Timer"""
        super().on_start()
        self._load_peaks()
        
        # Setze Timer basierend auf Poll-Intervall
        interval = self.get_input('E3') or 10
        self.set_timer(max(5, interval))
        
        self.debug("Status", "Gestartet")
        self.set_output('A2', 'Init')
    
    def execute(self, triggered_by: str = None):
        """Ausführung bei Input-Änderung"""
        if triggered_by == 'E1':
            # Start/Stop Trigger
            if self.get_input('E1'):
                self.debug("Status", "Daemon gestartet")
                # Starte sofortigen Poll
                asyncio.create_task(self._poll_fronius())
            else:
                self.debug("Status", "Daemon gestoppt")
                self.set_output('A1', False)
                self.set_output('A2', 'Stopped')
        
        elif triggered_by == 'E3':
            # Poll-Intervall geändert
            interval = self.get_input('E3') or 10
            self.set_timer(max(5, interval))
    
    async def on_timer(self):
        """Timer-basiertes Polling"""
        if not self.get_input('E1'):
            return  # Daemon nicht aktiv
        
        await self._poll_fronius()
    
    async def _poll_fronius(self):
        """Fronius API abfragen"""
        ip = self.get_input('E2') or '192.168.1.100'
        reset_time = self.get_input('E4') or '00:00'
        debug = self.get_input('E5')
        
        base_url = "http://{}/solar_api/v1".format(ip)
        
        if debug:
            logger.info("Polling Fronius at {}".format(ip))
        
        try:
            # Parallele API-Aufrufe
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                # 1. PowerFlow Realtime Data
                powerflow_url = "{}/GetPowerFlowRealtimeData.fcgi".format(base_url)
                storage_url = "{}/GetStorageRealtimeData.cgi?Scope=System".format(base_url)
                meter_url = "{}/GetMeterRealtimeData.cgi?Scope=System".format(base_url)
                
                # Parallele Requests
                tasks = [
                    self._fetch_json(session, powerflow_url),
                    self._fetch_json(session, storage_url),
                    self._fetch_json(session, meter_url),
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                powerflow_data = results[0] if not isinstance(results[0], Exception) else None
                storage_data = results[1] if not isinstance(results[1], Exception) else None
                meter_data = results[2] if not isinstance(results[2], Exception) else None
                
                if powerflow_data is None:
                    raise Exception("PowerFlow API nicht erreichbar")
                
                # Parse Daten
                await self._process_data(powerflow_data, storage_data, meter_data, reset_time, debug)
                
        except Exception as e:
            error_msg = str(e)
            logger.error("Fronius Poll Error: {}".format(error_msg))
            self.set_output('A1', False)
            self.set_output('A2', error_msg)
            self.debug("Error", error_msg)
    
    async def _fetch_json(self, session: aiohttp.ClientSession, url: str) -> Optional[Dict]:
        """HTTP GET und JSON parsen"""
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.warning("HTTP {} for {}".format(response.status, url))
                    return None
        except Exception as e:
            logger.debug("Fetch error for {}: {}".format(url, e))
            return None
    
    async def _process_data(self, powerflow: Dict, storage: Optional[Dict], 
                           meter: Optional[Dict], reset_time: str, debug: bool):
        """Daten verarbeiten und Outputs setzen"""
        
        # ============== POWERFLOW DATA ==============
        site = self._get_nested(powerflow, 'Body.Data.Site', {})
        inverters = self._get_nested(powerflow, 'Body.Data.Inverters', {})
        
        # PV Leistung
        pv_power = max(0, float(site.get('P_PV') or 0))
        pv_energy_day = float(site.get('E_Day') or 0)
        pv_energy_total = float(site.get('E_Total') or 0)
        
        # Batterie Leistung (positiv=Laden, negativ=Entladen)
        bat_power = float(site.get('P_Akku') or 0)
        
        # Grid Leistung (positiv=Bezug, negativ=Einspeisung)
        grid_power = float(site.get('P_Grid') or 0)
        
        # Hausverbrauch (negativ = Verbrauch)
        load_power = abs(float(site.get('P_Load') or 0))
        
        # Eigenverbrauch
        self_consumption = float(site.get('rel_SelfConsumption') or 0)
        
        # ============== BATTERIE DETAILS ==============
        bat_soc = 0.0
        bat_capacity = 0.0
        bat_status = 'Unknown'
        
        if storage:
            storage_body = self._get_nested(storage, 'Body.Data', {})
            for storage_id, stor in storage_body.items():
                if 'Controller' in stor:
                    ctrl = stor['Controller']
                    bat_soc = float(ctrl.get('StateOfCharge_Relative') or 0)
                    bat_capacity = float(ctrl.get('Capacity_Maximum') or 0)
                    state_code = int(ctrl.get('StatusBatteryCell') or 0)
                    bat_status = self.BATTERY_STATUS.get(state_code, "Code {}".format(state_code))
                    break
        
        # ============== METER DATA ==============
        grid_import_total = 0.0
        grid_export_total = 0.0
        
        if meter:
            meter_body = self._get_nested(meter, 'Body.Data', {})
            for meter_id, m in meter_body.items():
                imported = float(m.get('EnergyReal_WAC_Sum_Consumed') or 
                               m.get('SMARTMETER_ENERGYACTIVE_CONSUMED_SUM_F64') or 0)
                exported = float(m.get('EnergyReal_WAC_Sum_Produced') or 
                               m.get('SMARTMETER_ENERGYACTIVE_PRODUCED_SUM_F64') or 0)
                grid_import_total = imported
                grid_export_total = exported
                break
        
        # ============== PEAK RESET CHECK ==============
        self._check_peak_reset(reset_time, grid_import_total, grid_export_total, pv_energy_total, debug)
        
        # ============== TAGESWERTE ==============
        # Initialisiere Mitternachtswerte falls nötig
        if self._grid_import_midnight <= 0 and grid_import_total > 0:
            self._grid_import_midnight = grid_import_total
        if self._grid_export_midnight <= 0 and grid_export_total > 0:
            self._grid_export_midnight = grid_export_total
        if self._pv_total_midnight <= 0 and pv_energy_total > 0:
            self._pv_total_midnight = pv_energy_total
        
        grid_import_today = self._get_daily_value(grid_import_total, self._grid_import_midnight)
        grid_export_today = self._get_daily_value(grid_export_total, self._grid_export_midnight)
        pv_energy_day_calc = self._get_daily_value(pv_energy_total, self._pv_total_midnight)
        
        # Falls E_Day nicht verfügbar, benutze berechneten Wert
        if pv_energy_day <= 0:
            pv_energy_day = pv_energy_day_calc
        
        # ============== INVERTER STATUS ==============
        inverter_status = 'Unknown'
        for inv_id, inv in inverters.items():
            status_code = int(inv.get('StatusCode', -1))
            inverter_status = self.INVERTER_STATUS.get(status_code, "Code {}".format(status_code))
            break
        
        # ============== UPDATE PEAKS ==============
        now_time = datetime.now().strftime('%H:%M')
        
        if pv_power > 0:
            self._update_peak('pv', pv_power, now_time)
        if grid_power > 0:  # Bezug
            self._update_peak('grid_import', grid_power, now_time)
        if grid_power < 0:  # Einspeisung
            self._update_peak('grid_export', abs(grid_power), now_time)
        if bat_power > 0:  # Laden
            self._update_peak('bat_charge', bat_power, now_time)
        if bat_power < 0:  # Entladen
            self._update_peak('bat_discharge', abs(bat_power), now_time)
        if load_power > 0:
            self._update_peak('load', load_power, now_time)
        
        # Speichere Peak-Werte
        self._save_peaks()
        
        # ============== GRID IMPORT/EXPORT ==============
        grid_import = grid_power if grid_power > 0 else 0
        grid_export = abs(grid_power) if grid_power < 0 else 0
        
        # ============== SET OUTPUTS ==============
        now_timestamp = datetime.now().strftime('%H:%M:%S')
        
        self.set_output('A1', True)  # Status OK
        self.set_output('A2', 'OK')
        self.set_output('A3', now_timestamp)
        
        # PV
        self.set_output('A4', round(pv_power, 1))
        self.set_output('A5', round(pv_energy_day, 1))
        self.set_output('A6', round(pv_energy_total, 1))
        
        # Batterie
        self.set_output('A7', round(bat_power, 1))
        self.set_output('A8', round(bat_soc, 1))
        self.set_output('A9', round(bat_capacity, 1))
        
        # Grid
        self.set_output('A10', round(grid_import, 1))
        self.set_output('A11', round(grid_export, 1))
        self.set_output('A12', round(grid_import_today, 1))
        self.set_output('A13', round(grid_export_today, 1))
        
        # Verbrauch
        self.set_output('A14', round(load_power, 1))
        self.set_output('A15', round(self_consumption, 1))
        
        # Peak Werte
        self.set_output('A16', round(self._pv_peak_w, 1))
        self.set_output('A17', self._pv_peak_time)
        self.set_output('A18', round(self._grid_import_peak_w, 1))
        self.set_output('A19', self._grid_import_peak_time)
        self.set_output('A20', round(self._grid_export_peak_w, 1))
        self.set_output('A21', self._grid_export_peak_time)
        self.set_output('A22', round(self._bat_charge_peak_w, 1))
        self.set_output('A23', self._bat_charge_peak_time)
        self.set_output('A24', round(self._bat_discharge_peak_w, 1))
        self.set_output('A25', self._bat_discharge_peak_time)
        self.set_output('A26', round(self._load_peak_w, 1))
        self.set_output('A27', self._load_peak_time)
        
        # Status
        self.set_output('A28', inverter_status)
        self.set_output('A29', bat_status)
        
        if debug:
            logger.info("PV={}W, Bat={}W(SOC:{}%), Import={}W, Export={}W, Load={}W".format(
                pv_power, bat_power, bat_soc, grid_import, grid_export, load_power
            ))
            self.debug("PV", "{}W".format(pv_power))
            self.debug("SOC", "{}%".format(bat_soc))
    
    def _get_nested(self, data: Dict, path: str, default=None):
        """Verschachtelte Werte aus Dict holen"""
        keys = path.split('.')
        val = data
        for k in keys:
            if not isinstance(val, dict) or k not in val:
                return default
            val = val[k]
        return val
    
    def _get_daily_value(self, current_total: float, midnight_value: float) -> float:
        """Tageswert berechnen (aktuell - Mitternacht)"""
        if midnight_value <= 0:
            return 0
        daily = current_total - midnight_value
        return daily if daily > 0 else 0
    
    def _update_peak(self, peak_type: str, value: float, time_str: str):
        """Peak-Wert aktualisieren falls neuer Wert höher"""
        attr_w = '_{}_peak_w'.format(peak_type)
        attr_time = '_{}_peak_time'.format(peak_type)
        
        current_peak = getattr(self, attr_w, 0)
        if value > current_peak:
            setattr(self, attr_w, value)
            setattr(self, attr_time, time_str)
    
    def _check_peak_reset(self, reset_time: str, grid_import: float, 
                         grid_export: float, pv_total: float, debug: bool):
        """Peak-Reset zur konfigurierten Uhrzeit"""
        now = datetime.now().strftime('%H:%M')
        today = datetime.now().strftime('%Y-%m-%d')
        
        if now >= reset_time and self._last_reset_date != today:
            if debug:
                logger.info("Peak reset triggered at {} (config: {})".format(now, reset_time))
            
            # Reset alle Peak-Werte
            self._pv_peak_w = 0.0
            self._pv_peak_time = ''
            self._grid_import_peak_w = 0.0
            self._grid_import_peak_time = ''
            self._grid_export_peak_w = 0.0
            self._grid_export_peak_time = ''
            self._bat_charge_peak_w = 0.0
            self._bat_charge_peak_time = ''
            self._bat_discharge_peak_w = 0.0
            self._bat_discharge_peak_time = ''
            self._load_peak_w = 0.0
            self._load_peak_time = ''
            
            # Speichere Mitternachts-Referenzwerte
            self._grid_import_midnight = grid_import
            self._grid_export_midnight = grid_export
            self._pv_total_midnight = pv_total
            self._last_reset_date = today
            
            self._save_peaks()
    
    def _load_peaks(self):
        """Lade persistierte Peak-Werte aus Datei"""
        try:
            if os.path.exists(self._peak_file):
                with open(self._peak_file, 'r') as f:
                    data = json.load(f)
                
                self._pv_peak_w = data.get('pv_peak_w', 0)
                self._pv_peak_time = data.get('pv_peak_time', '')
                self._grid_import_peak_w = data.get('grid_import_peak_w', 0)
                self._grid_import_peak_time = data.get('grid_import_peak_time', '')
                self._grid_export_peak_w = data.get('grid_export_peak_w', 0)
                self._grid_export_peak_time = data.get('grid_export_peak_time', '')
                self._bat_charge_peak_w = data.get('bat_charge_peak_w', 0)
                self._bat_charge_peak_time = data.get('bat_charge_peak_time', '')
                self._bat_discharge_peak_w = data.get('bat_discharge_peak_w', 0)
                self._bat_discharge_peak_time = data.get('bat_discharge_peak_time', '')
                self._load_peak_w = data.get('load_peak_w', 0)
                self._load_peak_time = data.get('load_peak_time', '')
                
                # Mitternachtswerte
                self._grid_import_midnight = data.get('grid_import_midnight', 0)
                self._grid_export_midnight = data.get('grid_export_midnight', 0)
                self._pv_total_midnight = data.get('pv_total_midnight', 0)
                self._last_reset_date = data.get('last_reset_date', '')
                
                logger.info("Peak values loaded from {}".format(self._peak_file))
        except Exception as e:
            logger.warning("Could not load peaks: {}".format(e))
    
    def _save_peaks(self):
        """Speichere Peak-Werte in Datei (remanent)"""
        try:
            data = {
                'pv_peak_w': self._pv_peak_w,
                'pv_peak_time': self._pv_peak_time,
                'grid_import_peak_w': self._grid_import_peak_w,
                'grid_import_peak_time': self._grid_import_peak_time,
                'grid_export_peak_w': self._grid_export_peak_w,
                'grid_export_peak_time': self._grid_export_peak_time,
                'bat_charge_peak_w': self._bat_charge_peak_w,
                'bat_charge_peak_time': self._bat_charge_peak_time,
                'bat_discharge_peak_w': self._bat_discharge_peak_w,
                'bat_discharge_peak_time': self._bat_discharge_peak_time,
                'load_peak_w': self._load_peak_w,
                'load_peak_time': self._load_peak_time,
                'grid_import_midnight': self._grid_import_midnight,
                'grid_export_midnight': self._grid_export_midnight,
                'pv_total_midnight': self._pv_total_midnight,
                'last_reset_date': self._last_reset_date,
            }
            
            with open(self._peak_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning("Could not save peaks: {}".format(e))
