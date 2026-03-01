"""
Min/Max v2.1 – Remanent

Ermittelt den minimalen und maximalen Wert eines Eingangs.

Eingänge:
- E1: Wert (Eingangswert der überwacht wird)
- E2: Reset (bei jeder 1 → alles auf 0 zurücksetzen)

Ausgänge:
- A1: Aktueller Wert
- A2: Minimum
- A3: Maximum
- A4: Zeitstempel Minimum (HH:MM)
- A5: Zeitstempel Maximum (HH:MM)

Versionshistorie:
v2.1 – E1 trigger, E2 Reset auf 0, force_output überall
v2.0 – REMANENT-Framework
v1.0 – Erstversion
"""

import logging
from datetime import datetime, timezone, timedelta

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

try:
    from ..base import LogicBlock
except ImportError:
    from logic.base import LogicBlock

logger = logging.getLogger(__name__)


def _local_now() -> datetime:
    if ZoneInfo:
        try:
            return datetime.now(ZoneInfo("Europe/Vienna"))
        except Exception:
            pass
    return datetime.now(timezone(timedelta(hours=1)))


class MinMax(LogicBlock):
    """Ermittelt Min/Max eines Eingangswertes mit Zeitstempel"""

    ID = 20045
    NAME = "Min/Max"
    VERSION = "2.1"
    DESCRIPTION = "Ermittelt Minimum und Maximum mit Zeitstempel (remanent)"
    CATEGORY = "Hilfsmittel"
    REMANENT = True

    INPUTS = {
        'E1': {'name': 'Wert', 'type': 'float', 'default': 0.0, 'trigger': True},
        'E2': {'name': 'Reset (1=Reset)', 'type': 'bool', 'default': False, 'trigger': True},
    }

    OUTPUTS = {
        'A1': {'name': 'Aktueller Wert', 'type': 'float'},
        'A2': {'name': 'Minimum', 'type': 'float'},
        'A3': {'name': 'Maximum', 'type': 'float'},
        'A4': {'name': 'Min Zeitstempel (HH:MM)', 'type': 'str'},
        'A5': {'name': 'Max Zeitstempel (HH:MM)', 'type': 'str'},
    }

    HELP = """Min/Max v2.1

E1 = Sensorwert → wird überwacht
E2 = Reset → bei jeder 1 alles auf 0 setzen

A1 = Aktueller Wert
A2 = Minimum  |  A4 = Zeitstempel Min
A3 = Maximum  |  A5 = Zeitstempel Max

Remanent: Werte überleben Neustart.
"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._min_val = None
        self._max_val = None
        self._min_time = ""
        self._max_time = ""

    def on_start(self):
        super().on_start()
        if self._min_val is not None:
            self._send_all()
            logger.info(f"{self.instance_id}: Start min={self._min_val} max={self._max_val}")

    # ── Output immer senden ─────────────────────

    def _out(self, key, value):
        """Ausgang setzen und IMMER senden"""
        self._output_values[key] = value
        if self._output_callback:
            self._output_callback(self.instance_id, key, value)

    def _send_all(self):
        """Alle Ausgänge senden"""
        self._out('A1', self._min_val if self._min_val is not None else 0.0)
        self._out('A2', self._min_val if self._min_val is not None else 0.0)
        self._out('A3', self._max_val if self._max_val is not None else 0.0)
        self._out('A4', self._min_time)
        self._out('A5', self._max_time)

    # ── Remanent ────────────────────────────────

    def get_remanent_state(self):
        if self._min_val is None:
            return None
        return {
            'min': self._min_val,
            'max': self._max_val,
            'min_t': self._min_time,
            'max_t': self._max_time,
        }

    def restore_remanent_state(self, state):
        if not state:
            return
        self._min_val = state.get('min')
        self._max_val = state.get('max')
        self._min_time = state.get('min_t', "")
        self._max_time = state.get('max_t', "")

    # ── Execute ─────────────────────────────────

    def execute(self, triggered_by=None):
        # Reset: jede 1 auf E2 → alles auf 0
        if self.get_input('E2'):
            self._min_val = None
            self._max_val = None
            self._min_time = ""
            self._max_time = ""
            self._out('A1', 0.0)
            self._out('A2', 0.0)
            self._out('A3', 0.0)
            self._out('A4', "")
            self._out('A5', "")
            # E2 intern zurücksetzen damit nächste 1 wieder triggert
            self._input_values['E2'] = False
            logger.info(f"{self.instance_id}: Reset → alles auf 0")
            return

        # Wert verarbeiten
        raw = self.get_input('E1')
        if raw is None:
            return

        try:
            value = float(raw)
        except (ValueError, TypeError):
            return

        now = _local_now().strftime("%H:%M")

        # Aktuellen Wert immer senden
        self._out('A1', value)
        self.debug('E1_raw', str(raw))
        self.debug('Wert', str(value))

        # Erst-Initialisierung
        if self._min_val is None:
            self._min_val = value
            self._max_val = value
            self._min_time = now
            self._max_time = now
            self._out('A2', value)
            self._out('A3', value)
            self._out('A4', now)
            self._out('A5', now)
            logger.info(f"{self.instance_id}: Init {value}")
            return

        # Min prüfen
        if value < self._min_val:
            self._min_val = value
            self._min_time = now
            self._out('A2', value)
            self._out('A4', now)
            logger.debug(f"{self.instance_id}: Neues Min {value}")
            self.debug("Min", str(value))

        # Max prüfen
        if value > self._max_val:
            self._max_val = value
            self._max_time = now
            self._out('A3', value)
            self._out('A5', now)
            logger.debug(f"{self.instance_id}: Neues Max {value}")
            self.debug("Max", str(value))


class_1 = MinMax
