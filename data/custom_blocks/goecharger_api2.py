# coding: UTF-8
"""
go-eCharger API v2 Logikbaustein für KNX / EDOMI-Automation
Unterstützt: Status-Polling, Steuerung, PV-Überschuss-Laden

API Dokumentation: https://github.com/goecharger/go-eCharger-API-v2/blob/main/apikeys-en.md

Author: Reinhard
Version: 1.0
"""
import json
import logging
import asyncio
import aiohttp
from datetime import datetime
from typing import Optional, Any

from logic.base import LogicBlock

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Hilfsmapping: Car-State-Code → lesbarer Text
# ---------------------------------------------------------------------------
CAR_STATE_TEXT = {
    0: 'Unbekannt',
    1: 'Bereit (kein Auto)',
    2: 'Lädt',
    3: 'Wartet auf Auto',
    4: 'Laden abgeschlossen',
    5: 'Fehler',
}

# ---------------------------------------------------------------------------
# Hilfsmapping: modelStatus-Code → lesbarer Text
# ---------------------------------------------------------------------------
MODEL_STATUS_TEXT = {
    0:  'NotChargingBecauseNoChargeCtrlData',
    1:  'NotChargingBecauseOvertemperature',
    2:  'NotChargingBecauseAccessControlWait',
    3:  'ChargingBecauseForceStateOn',
    4:  'NotChargingBecauseForceStateOff',
    5:  'NotChargingBecauseScheduler',
    6:  'NotChargingBecauseEnergyLimit',
    7:  'ChargingBecauseAwattarPriceLow',
    8:  'ChargingBecauseAutomaticStopTestLadung',
    9:  'ChargingBecauseAutomaticStopNotEnoughTime',
    10: 'ChargingBecauseAutomaticStop',
    11: 'ChargingBecauseAutomaticStopNoClock',
    12: 'ChargingBecausePvSurplus',
    13: 'ChargingBecauseFallbackGoEDefault',
    14: 'ChargingBecauseFallbackGoEScheduler',
    15: 'ChargingBecauseFallbackDefault',
    16: 'NotChargingBecauseFallbackGoEAwattar',
    17: 'NotChargingBecauseFallbackAwattar',
    18: 'NotChargingBecauseFallbackAutomaticStop',
    19: 'ChargingBecauseCarCompatibilityKeepAlive',
    20: 'ChargingBecauseChargePauseNotAllowed',
    22: 'NotChargingBecauseSimulateUnplugging',
    23: 'NotChargingBecausePhaseSwitch',
    24: 'NotChargingBecauseMinPauseDuration',
}


class GoEChargerAPI2(LogicBlock):
    """
    go-eCharger API v2 Logikbaustein
    Pollt den Lader per HTTP, liest Status aus und ermöglicht Steuerung.
    Unterstützt PV-Überschuss-Laden (pgrid/ppv/pakku alle 5 s senden).
    """

    ID          = 20040
    NAME        = "go-eCharger API v2"
    DESCRIPTION = "Steuerung & Status-Polling für go-eCharger Wallbox via lokaler HTTP API v2"
    CATEGORY    = "Energie"
    VERSION     = "1.0"
    AUTHOR      = "Reinhard"

    # ------------------------------------------------------------------
    # Eingänge
    # ------------------------------------------------------------------
    INPUTS = {
        # Betrieb
        'E1':  {'name': 'Start/Stop (1/0)',                'type': 'bool',  'default': True},
        'E2':  {'name': 'IP-Adresse Wallbox',              'type': 'str',   'default': '192.168.1.100'},
        'E3':  {'name': 'Status-Abfrageintervall (Sek)',   'type': 'int',   'default': 5},
        'E4':  {'name': 'Manuell Refresh',                 'type': 'bool',  'default': False},

        # Steuerung Laden
        'E5':  {'name': 'Laden erlauben (alw)',            'type': 'bool',  'default': True},
        'E6':  {'name': 'Force-State (0=Neutral/1=Aus/2=Ein)', 'type': 'int', 'default': 0},
        'E7':  {'name': 'Ladestrom in Ampere (amp, 6-32)', 'type': 'int',   'default': 16},
        'E8':  {'name': 'Phasenmodus (1=1Ph / 2=3Ph)',    'type': 'int',   'default': 0},

        # PV-Überschuss
        'E9':  {'name': 'PV-Senden aktivieren',            'type': 'bool',  'default': False},
        'E10': {'name': 'Netzleistung pgrid (W, +Bezug/-Einspeisung)', 'type': 'float', 'default': 0.0},
        'E11': {'name': 'PV-Leistung ppv (W, positiv)',   'type': 'float', 'default': 0.0},
        'E12': {'name': 'Akku-Leistung pakku (W, +Entladen/-Laden)', 'type': 'float', 'default': 0.0},
    }

    # ------------------------------------------------------------------
    # Ausgänge
    # ------------------------------------------------------------------
    OUTPUTS = {
        # Verbindung & Status
        'A1':  {'name': 'Online (1=OK)',                   'type': 'int',   'default': 0},
        'A2':  {'name': 'Letzter Fehler',                  'type': 'str',   'default': ''},
        'A3':  {'name': 'Seriennummer',                    'type': 'str',   'default': ''},

        # Auto & Laden
        'A4':  {'name': 'Auto-Status (0-5)',               'type': 'int',   'default': 0},
        'A5':  {'name': 'Auto-Status Text',                'type': 'str',   'default': ''},
        'A6':  {'name': 'Modell-Status Code',              'type': 'int',   'default': 0},
        'A6b': {'name': 'Modell-Status Text',              'type': 'str',   'default': ''},
        'A7':  {'name': 'Laden erlaubt (alw)',             'type': 'bool',  'default': False},
        'A8':  {'name': 'Force-State (frc)',               'type': 'int',   'default': 0},
        'A9':  {'name': 'Ladestrom gesetzt (amp, A)',      'type': 'int',   'default': 0},
        'A10': {'name': 'Effektiver Ladestrom (acu, A)',   'type': 'int',   'default': 0},
        'A11': {'name': 'Phasenmodus (psm)',               'type': 'int',   'default': 0},

        # Leistung & Energie
        'A12': {'name': 'Gesamtleistung (W)',              'type': 'float', 'default': 0.0},
        'A13': {'name': 'Leistung L1 (W)',                 'type': 'float', 'default': 0.0},
        'A14': {'name': 'Leistung L2 (W)',                 'type': 'float', 'default': 0.0},
        'A15': {'name': 'Leistung L3 (W)',                 'type': 'float', 'default': 0.0},
        'A16': {'name': 'Spannung L1 (V)',                 'type': 'float', 'default': 0.0},
        'A17': {'name': 'Spannung L2 (V)',                 'type': 'float', 'default': 0.0},
        'A18': {'name': 'Spannung L3 (V)',                 'type': 'float', 'default': 0.0},
        'A19': {'name': 'Strom L1 (A)',                   'type': 'float', 'default': 0.0},
        'A20': {'name': 'Strom L2 (A)',                   'type': 'float', 'default': 0.0},
        'A21': {'name': 'Strom L3 (A)',                   'type': 'float', 'default': 0.0},
        'A22': {'name': 'Energie Session (Wh)',            'type': 'float', 'default': 0.0},
        'A23': {'name': 'Energie gesamt (kWh)',            'type': 'float', 'default': 0.0},

        # Temperatur & Fehler
        'A24': {'name': 'Temperatur 1 (°C)',               'type': 'float', 'default': 0.0},
        'A25': {'name': 'Temperatur 2 (°C)',               'type': 'float', 'default': 0.0},
        'A26': {'name': 'Fehlercode (err)',                'type': 'int',   'default': 0},

        # PV-Überschuss Feedback
        'A27': {'name': 'PV pgrid zuletzt gesendet (W)',  'type': 'float', 'default': 0.0},
        'A28': {'name': 'PV ppv zuletzt gesendet (W)',    'type': 'float', 'default': 0.0},
        'A29': {'name': 'PV pakku zuletzt gesendet (W)',  'type': 'float', 'default': 0.0},
    }

    # API-Filter: nur die wichtigsten Keys abfragen (reduziert Traffic)
    _STATUS_FILTER = 'car,alw,amp,acu,err,frc,psm,nrg,wh,eto,tma,modelStatus,sse,pgrid,ppv,pakku'

    # Wieviele Sekunden vor dem nächsten Status-Poll
    _PV_INTERVAL   = 4.5   # PV-Daten fast jede 5 s schicken
    _SET_TIMEOUT   = 5     # HTTP-Timeout für SET-Aufrufe

    def on_start(self):
        """Block gestartet"""
        self._running      = False
        self._daemon_task: Optional[asyncio.Task] = None
        self._set_queue    = {}      # {api_key: value} – ausstehende SET-Befehle
        self._next_status_ts  = 0   # wann nächste Status-Abfrage fällig
        self._next_pv_ts      = 0   # wann nächste PV-Daten-Sendung fällig
        self._last_ip         = ''

        self._debug_values['Status']   = 'Init'
        self._debug_values['Version']  = self.VERSION
        self._debug_values['Wallbox']  = '-'
        self._debug_values['Auto']     = '-'
        self._debug_values['Leistung'] = '-'

        logger.info("[{}] go-eCharger API v2 v{} starting...".format(self.ID, self.VERSION))

        if self.get_input('E1'):
            self._start_daemon()

    def on_stop(self):
        """Block gestoppt"""
        self._stop_daemon()
        logger.info("[{}] go-eCharger API v2 stopped".format(self.ID))

    # ------------------------------------------------------------------
    # Daemon-Steuerung
    # ------------------------------------------------------------------
    def _start_daemon(self):
        if self._daemon_task and not self._daemon_task.done():
            self._daemon_task.cancel()
        self._running     = True
        self._next_status_ts = 0   # sofort pollen
        self._next_pv_ts     = 0
        self._daemon_task = asyncio.create_task(self._daemon_loop())
        logger.info("[{}] Daemon gestartet".format(self.ID))

    def _stop_daemon(self):
        self._running = False
        if self._daemon_task and not self._daemon_task.done():
            self._daemon_task.cancel()
        self.set_output('A1', 0)
        self.set_output('A2', 'Gestoppt')
        self._debug_values['Status'] = 'Gestoppt'
        logger.info("[{}] Daemon gestoppt".format(self.ID))

    # ------------------------------------------------------------------
    # Input-Handling
    # ------------------------------------------------------------------
    def on_input_change(self, key: str, value: Any, old_value: Any):
        logger.info("[{}] Input {} geändert: {} -> {}".format(self.ID, key, old_value, value))

        if key == 'E1':
            if value:
                self._start_daemon()
            else:
                self._stop_daemon()
            return

        if key == 'E4' and value:
            # Manuell Refresh
            self._next_status_ts = 0
            if not self._running:
                self._start_daemon()
            return

        if key == 'E2':
            # IP geändert → sofort neu verbinden
            self._next_status_ts = 0
            return

        if key == 'E3':
            # Intervall geändert → gilt beim nächsten Zyklus automatisch
            return

        # --- Steuer-Eingänge → SET-Queue befüllen ---
        if key == 'E5':
            # Laden erlauben/verbieten (alw)
            self._queue_set('alw', 'true' if value else 'false')

        elif key == 'E6':
            # Force-State (frc): 0=Neutral, 1=Aus, 2=Ein
            frc = int(value) if value in (0, 1, 2) else 0
            self._queue_set('frc', str(frc))

        elif key == 'E7':
            # Ladestrom (amp): 6-32 A
            amp = max(6, min(32, int(value or 6)))
            self._queue_set('amp', str(amp))

        elif key == 'E8':
            # Phasenmodus (psm): 0=Auto, 1=1-Phase, 2=3-Phasen
            psm = int(value) if value in (0, 1, 2) else 0
            self._queue_set('psm', str(psm))

        # PV-Werte → nächste Sendung sofort fällig
        elif key in ('E9', 'E10', 'E11', 'E12'):
            self._next_pv_ts = 0

    def _queue_set(self, api_key: str, api_value: str):
        """Schreibt einen SET-Befehl in die Queue (Daemon sendet ihn beim nächsten Durchlauf)"""
        self._set_queue[api_key] = api_value
        logger.debug("[{}] SET queued: {}={}".format(self.ID, api_key, api_value))

    def execute(self, triggered_by: str = None):
        """Wird von EDOMI getriggert – Hauptlogik läuft im Daemon"""
        pass

    # ------------------------------------------------------------------
    # Daemon-Loop
    # ------------------------------------------------------------------
    async def _daemon_loop(self):
        logger.info("[{}] Daemon-Loop gestartet".format(self.ID))

        while self._running:
            try:
                if not self.get_input('E1'):
                    await asyncio.sleep(1)
                    continue

                ip = (self.get_input('E2') or '').strip()
                if not ip:
                    self.set_output('A1', 0)
                    self.set_output('A2', 'Keine IP konfiguriert')
                    await asyncio.sleep(2)
                    continue

                now = datetime.now().timestamp()

                # 1) Ausstehende SET-Befehle senden
                if self._set_queue:
                    await self._send_set(ip, dict(self._set_queue))
                    self._set_queue.clear()

                # 2) PV-Daten senden (wenn aktiviert und fällig)
                if self.get_input('E9') and now >= self._next_pv_ts:
                    await self._send_pv_data(ip)
                    self._next_pv_ts = now + self._PV_INTERVAL

                # 3) Status pollen (wenn fällig)
                if now >= self._next_status_ts:
                    await self._poll_status(ip)
                    interval = max(1, int(self.get_input('E3') or 5))
                    self._next_status_ts = datetime.now().timestamp() + interval

                # Schlaf bis zur nächsten Aktion
                now2 = datetime.now().timestamp()
                next_wakeup = min(self._next_status_ts, self._next_pv_ts if self.get_input('E9') else self._next_status_ts)
                sleep_secs  = max(0.2, next_wakeup - now2)
                await asyncio.sleep(min(sleep_secs, 1.0))   # max. 1 s schlafen

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("[{}] Daemon-Fehler: {}".format(self.ID, e))
                self._debug_values['Status'] = 'Fehler: {}'.format(str(e)[:40])
                await asyncio.sleep(5)

        logger.info("[{}] Daemon-Loop beendet".format(self.ID))

    # ------------------------------------------------------------------
    # HTTP: Status lesen
    # ------------------------------------------------------------------
    async def _poll_status(self, ip: str):
        url = 'http://{}/api/status?filter={}'.format(ip, self._STATUS_FILTER)
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        self._set_offline('HTTP {}'.format(resp.status))
                        return
                    data = await resp.json(content_type=None)
            self._parse_status(data)
        except asyncio.TimeoutError:
            self._set_offline('Timeout')
        except Exception as e:
            self._set_offline(str(e)[:80])

    def _parse_status(self, d: dict):
        """JSON-Antwort auswerten und Ausgänge setzen"""

        # --- Online ---
        self.set_output('A1', 1)
        self.set_output('A2', '')

        # Seriennummer
        sse = d.get('sse', '')
        self.set_output('A3', str(sse) if sse else '')

        # --- Auto-Status ---
        car = int(d.get('car', 0) or 0)
        self.set_output('A4', car)
        self.set_output('A5', CAR_STATE_TEXT.get(car, 'Unbekannt'))

        # Modell-Status
        ms = int(d.get('modelStatus', 0) or 0)
        self.set_output('A6',  ms)
        self.set_output('A6b', MODEL_STATUS_TEXT.get(ms, 'Status {}'.format(ms)))

        # Laden erlaubt
        alw = d.get('alw', False)
        self.set_output('A7', bool(alw))

        # Force-State
        frc = int(d.get('frc', 0) or 0)
        self.set_output('A8', frc)

        # Ladestrom
        amp = int(d.get('amp', 0) or 0)
        self.set_output('A9', amp)
        acu = int(d.get('acu', 0) or 0)
        self.set_output('A10', acu)

        # Phasenmodus
        psm = int(d.get('psm', 0) or 0)
        self.set_output('A11', psm)

        # --- nrg-Array auswerten ---
        # Offizielles Layout (16 Elemente, APIv2):
        # [0] U1  [1] U2  [2] U3  [3] UN   → Volt (direkt)
        # [4] I1  [5] I2  [6] I3            → 0,1 A  (÷10 → A)
        # [7] P1  [8] P2  [9] P3  [10] PN  → W (direkt, KEIN Faktor!)
        # [11] Pges                          → 0,01 kW (×10 → W)
        # [12] PF1 [13] PF2 [14] PF3 [15] PFN → % (Leistungsfaktor)
        nrg = d.get('nrg') or []
        if isinstance(nrg, list) and len(nrg) >= 12:
            u1  = float(nrg[0]  or 0)           # V direkt
            u2  = float(nrg[1]  or 0)
            u3  = float(nrg[2]  or 0)
            i1  = float(nrg[4]  or 0)           # A direkt (APIv2 liefert float!)
            i2  = float(nrg[5]  or 0)
            i3  = float(nrg[6]  or 0)
            p1  = float(nrg[7]  or 0)           # W direkt
            p2  = float(nrg[8]  or 0)
            p3  = float(nrg[9]  or 0)
            pges= float(nrg[11] or 0)           # W direkt (kein Skalierungsfaktor!)

            self.set_output('A12', round(pges, 1))
            self.set_output('A13', round(p1,   1))
            self.set_output('A14', round(p2,   1))
            self.set_output('A15', round(p3,   1))
            self.set_output('A16', round(u1,   1))
            self.set_output('A17', round(u2,   1))
            self.set_output('A18', round(u3,   1))
            self.set_output('A19', round(i1,   2))
            self.set_output('A20', round(i2,   2))
            self.set_output('A21', round(i3,   2))
        else:
            # nrg fehlt oder ungültig → Nullen
            for out in ('A12','A13','A14','A15','A16','A17','A18','A19','A20','A21'):
                self.set_output(out, 0.0)

        # --- Energie ---
        wh  = float(d.get('wh',  0) or 0)       # Wh dieser Session
        eto = float(d.get('eto', 0) or 0) / 10.0  # 0.1 Wh → kWh
        self.set_output('A22', round(wh,    1))
        self.set_output('A23', round(eto, 3))

        # --- Temperaturen ---
        tma = d.get('tma') or []
        t1 = float(tma[0]) if len(tma) > 0 else 0.0
        t2 = float(tma[1]) if len(tma) > 1 else 0.0
        self.set_output('A24', round(t1, 1))
        self.set_output('A25', round(t2, 1))

        # --- Fehlercode ---
        err = int(d.get('err', 0) or 0)
        self.set_output('A26', err)

        # --- Debug ---
        self._debug_values['Status']   = 'Online'
        self._debug_values['Wallbox']  = 'S/N: {}'.format(sse or '-')
        self._debug_values['Auto']     = CAR_STATE_TEXT.get(car, '?')
        self._debug_values['Leistung'] = '{}W | {}A'.format(
            round(pges, 0) if nrg else 0,
            amp
        )

        logger.debug("[{}] Status: car={} amp={}A P={}W".format(
            self.ID, car, amp, self._debug_values['Leistung']))

    def _set_offline(self, reason: str):
        self.set_output('A1', 0)
        self.set_output('A2', reason)
        self._debug_values['Status'] = 'Offline: {}'.format(reason)
        logger.warning("[{}] Offline: {}".format(self.ID, reason))

    # ------------------------------------------------------------------
    # HTTP: Wert setzen  →  GET /api/set?key=value
    # ------------------------------------------------------------------
    async def _send_set(self, ip: str, params: dict):
        """
        Sendet SET-Kommandos an die Wallbox.
        go-eCharger APIv2 akzeptiert: GET /api/set?key=value&key2=value2
        """
        if not params:
            return

        query = '&'.join('{}={}'.format(k, v) for k, v in params.items())
        url = 'http://{}/api/set?{}'.format(ip, query)
        logger.info("[{}] SET: {}".format(self.ID, url))

        try:
            timeout = aiohttp.ClientTimeout(total=self._SET_TIMEOUT)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    text = await resp.text()
                    if resp.status != 200:
                        logger.error("[{}] SET HTTP {}: {}".format(self.ID, resp.status, text[:100]))
                        self.set_output('A2', 'SET Fehler: HTTP {}'.format(resp.status))
                    else:
                        logger.debug("[{}] SET OK: {}".format(self.ID, text[:80]))
                        # Kurz danach neu pollen
                        self._next_status_ts = 0
        except Exception as e:
            logger.error("[{}] SET Exception: {}".format(self.ID, e))
            self.set_output('A2', 'SET Fehler: {}'.format(str(e)[:60]))

    # ------------------------------------------------------------------
    # HTTP: PV-Überschussdaten senden  →  GET /api/set?pgrid=x&ppv=y&pakku=z
    # ------------------------------------------------------------------
    async def _send_pv_data(self, ip: str):
        """
        Sendet PV-Überschussdaten an die Wallbox.
        WICHTIG: go-eCharger verwirft Werte nach 5 Sekunden!
        Muss also spätestens alle 5 s aufgerufen werden.
        """
        pgrid = float(self.get_input('E10') or 0)
        ppv   = float(self.get_input('E11') or 0)
        pakku = float(self.get_input('E12') or 0)

        # Werte auf 1 Dezimale runden
        pgrid_s = str(round(pgrid, 1))
        ppv_s   = str(round(ppv,   1))
        pakku_s = str(round(pakku, 1))

        url = 'http://{}/api/set?pgrid={}&ppv={}&pakku={}'.format(
            ip, pgrid_s, ppv_s, pakku_s)

        logger.debug("[{}] PV senden: pgrid={} ppv={} pakku={}".format(
            self.ID, pgrid_s, ppv_s, pakku_s))

        try:
            timeout = aiohttp.ClientTimeout(total=self._SET_TIMEOUT)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        self.set_output('A27', pgrid)
                        self.set_output('A28', ppv)
                        self.set_output('A29', pakku)
                        self._debug_values['PV'] = 'pgrid={}W ppv={}W'.format(pgrid_s, ppv_s)
                    else:
                        text = await resp.text()
                        logger.warning("[{}] PV-Senden HTTP {}: {}".format(
                            self.ID, resp.status, text[:60]))
        except Exception as e:
            logger.error("[{}] PV-Senden Fehler: {}".format(self.ID, e))
