"""
Timer (v2.1) – Remanent

Countdown-Timer mit Minuteneingabe und Start/Stop-Steuerung.
Remanent: Timer-Zustand wird über Reboots hinweg gespeichert.

Eingänge:
- E1: Start/Stop (1 = Start, 0 = Stop/Reset)
- E2: Timer-Dauer in Minuten (z.B. 5 für 5 Minuten)

Ausgänge:
- A1: Timer-Status (1 = läuft, 0 = abgelaufen/gestoppt)
- A2: Restzeit in Sekunden
- A3: Restzeit als HH:MM
"""

import asyncio
import logging
import time

try:
    from ..base import LogicBlock
except ImportError:
    from logic.base import LogicBlock

logger = logging.getLogger(__name__)


class Timer(LogicBlock):
    """Countdown-Timer mit Start/Stop, Minuteneingabe und Remanenz"""

    BLOCK_TYPE = "timer"
    ID = 20043
    NAME = "Timer"
    DESCRIPTION = "Countdown-Timer mit Minuteneingabe, Start/Stop und Remanenz"
    VERSION = "2.1"
    CATEGORY = "Hilfsmittel"
    REMANENT = True

    HELP = """Funktionsweise:
1. Dauer in Minuten an E2 setzen (z.B. 5 für 5 Minuten)
2. E1 auf 1 → Timer startet, A1 = 1
3. Restzeit wird jede Sekunde aktualisiert (A2 in Sekunden, A3 als HH:MM)
4. Timer läuft ab → A1 wechselt auf 0, A2 = 0, A3 = 00:00
5. E1 auf 0 → Timer wird sofort gestoppt

Remanent-Verhalten:
- Bei Shutdown wird der Zielzeitpunkt gespeichert
- Nach Reboot wird die verstrichene Zeit automatisch abgezogen
- War der Timer während des Neustarts abgelaufen → A1 = 0
- War noch Restzeit übrig → Timer läuft automatisch weiter

Versionshistorie:
v2.1 – Neuer Ausgang A3: Restzeit als HH:MM
v2.0 – Remanenz: Timer überlebt Reboots, speichert Zielzeit als Unix-Timestamp
v1.0 – Erstversion: Countdown-Timer mit Start/Stop und Sekunden-Aktualisierung"""

    INPUTS = {
        'E1': {'name': 'Start/Stop (1=Start, 0=Stop)', 'type': 'bool'},
        'E2': {'name': 'Dauer in Minuten', 'type': 'float'},
    }

    OUTPUTS = {
        'A1': {'name': 'Timer-Status (1=läuft, 0=abgelaufen)', 'type': 'bool'},
        'A2': {'name': 'Restzeit in Sekunden', 'type': 'float'},
        'A3': {'name': 'Restzeit (HH:MM)', 'type': 'str'},
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._timer_task = None
        self._timer_running = False
        self._remaining = 0.0
        self._target_time = 0.0  # Unix timestamp when timer expires

    def _set_remaining(self, seconds):
        """Setzt A2 (Sekunden) und A3 (HH:MM) gleichzeitig"""
        seconds = max(0, round(seconds))
        self.set_output('A2', seconds)
        h = seconds // 3600
        m = (seconds % 3600) // 60
        self.set_output('A3', f'{h:02d}:{m:02d}')

    def execute(self, triggered_by=None):
        """Reagiert auf Änderungen an E1 oder E2"""
        start = self.get_input('E1')
        duration_min = self.get_input('E2')

        if start and duration_min is not None and float(duration_min) > 0:
            # Timer starten oder neu starten
            self._stop_timer()
            seconds = float(duration_min) * 60
            self._target_time = time.time() + seconds
            self._remaining = seconds
            self._timer_running = True
            self.set_output('A1', 1)
            self._set_remaining(seconds)
            self._timer_task = asyncio.ensure_future(self._countdown())
            self.debug('Status', f'Läuft – {duration_min} min')
            logger.info(f"{self.instance_id}: Timer gestartet ({duration_min} Minuten)")
        else:
            # Timer stoppen
            self._stop_timer()
            self._timer_running = False
            self._remaining = 0
            self._target_time = 0
            self.set_output('A1', 0)
            self._set_remaining(0)
            self.debug('Status', 'Gestoppt')
            logger.info(f"{self.instance_id}: Timer gestoppt")

    def _stop_timer(self):
        """Stoppt den laufenden Timer-Task"""
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
            self._timer_task = None

    async def _countdown(self):
        """Countdown-Schleife, aktualisiert jede Sekunde"""
        try:
            while True:
                remaining = self._target_time - time.time()
                if remaining <= 0:
                    break
                self._remaining = remaining
                self._set_remaining(remaining)
                h = int(remaining) // 3600
                m = (int(remaining) % 3600) // 60
                s = int(remaining) % 60
                self.debug('Status', f'Läuft – {h:02d}:{m:02d}:{s:02d}')
                await asyncio.sleep(1)

            # Timer abgelaufen
            self._timer_running = False
            self._remaining = 0
            self._target_time = 0
            self.set_output('A1', 0)
            self._set_remaining(0)
            self.debug('Status', 'Abgelaufen')
            logger.info(f"{self.instance_id}: Timer abgelaufen")

        except asyncio.CancelledError:
            logger.debug(f"{self.instance_id}: Timer-Task abgebrochen")

    # ---- Remanenz ----

    def get_remanent_state(self):
        """Speichere Timer-Zustand für Reboot-Persistenz"""
        if not self._timer_running or self._target_time <= 0:
            return {'running': False}
        return {
            'running': True,
            'target_time': self._target_time,
            'saved_at': time.time(),
        }

    def restore_remanent_state(self, state):
        """Stelle Timer nach Reboot wieder her"""
        if not state or not state.get('running'):
            self.debug('Status', 'Gestoppt (wiederhergestellt)')
            return

        target = state.get('target_time', 0)
        now = time.time()
        remaining = target - now

        if remaining <= 0:
            # Timer ist während des Reboots abgelaufen
            self._timer_running = False
            self._remaining = 0
            self._target_time = 0
            self.set_output('A1', 0)
            self._set_remaining(0)
            self.debug('Status', 'Abgelaufen (während Reboot)')
            logger.info(f"{self.instance_id}: Timer war abgelaufen während Reboot")
        else:
            # Timer hat noch Restzeit → weiterlaufen
            self._target_time = target
            self._remaining = remaining
            self._timer_running = True
            self.set_output('A1', 1)
            self._set_remaining(remaining)
            self._timer_task = asyncio.ensure_future(self._countdown())
            h = int(remaining) // 3600
            m = (int(remaining) % 3600) // 60
            self.debug('Status', f'Fortgesetzt – {h:02d}:{m:02d} übrig')
            logger.info(f"{self.instance_id}: Timer fortgesetzt nach Reboot ({int(remaining)}s übrig)")

    def on_start(self):
        super().on_start()
        self.debug('Version', self.VERSION)
        if not self._timer_running:
            self.debug('Status', 'Bereit')

    def on_stop(self):
        """Cleanup: Timer-Task stoppen"""
        self._stop_timer()
        super().on_stop()


# Für EDOMI-Kompatibilität
class_1 = Timer
