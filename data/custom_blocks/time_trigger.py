"""
Uhrzeit Trigger (v1.0)

Löst täglich zur eingestellten Uhrzeit einen Puls auf A1 aus.

Eingänge:
- E1: Aktivierung (1 = aktiv, 0 = deaktiviert)
- E2: Uhrzeit im Format HH:MM (z.B. "14:30")

Ausgänge:
- A1: Trigger-Ausgang (Puls: 1 für 100ms, dann 0)

Verwendung:
[Aktivierung] → E1
[Uhrzeit "14:30"] → E2 → [Uhrzeit Trigger] → A1 → [Aktion]

Wenn E1 = 1 und aktuelle Uhrzeit = E2:
- A1 wird auf 1 gesetzt
- Nach 100ms wird A1 auf 0 gesetzt
- Nächster Trigger erfolgt am nächsten Tag
"""

import asyncio
import logging
from datetime import datetime

try:
    from ..base import LogicBlock
except ImportError:
    from logic.base import LogicBlock

logger = logging.getLogger(__name__)


class UhrzeitTrigger(LogicBlock):
    """Löst täglich zur eingestellten Uhrzeit einen Puls aus"""
    
    BLOCK_TYPE = "uhrzeit_trigger"
    ID = 20041
    NAME = "Uhrzeit Trigger"
    DESCRIPTION = "Löst täglich zur eingestellten Uhrzeit einen Puls auf A1 aus"
    CATEGORY = "Hilfsmittel"
    
    INPUTS = {
        'E1': {'name': 'Aktivierung', 'type': 'bool'},
        'E2': {'name': 'Uhrzeit (HH:MM)', 'type': 'str'},
    }
    
    OUTPUTS = {
        'A1': {'name': 'Trigger Output', 'type': 'bool'},
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._check_task = None
        self._triggered_today = False
        self._last_trigger_minute = -1
    
    def execute(self, triggered_by=None):
        """Startet oder stoppt die Zeitüberwachung basierend auf E1"""
        if triggered_by == 'E1':
            active = self.get_input('E1')
            
            if active:
                # Zeitüberwachung starten
                if self._check_task is None or self._check_task.done():
                    logger.debug(f"{self.instance_id}: Zeitüberwachung gestartet")
                    self._check_task = asyncio.create_task(self._time_check_loop())
            else:
                # Zeitüberwachung stoppen
                if self._check_task and not self._check_task.done():
                    self._check_task.cancel()
                    logger.debug(f"{self.instance_id}: Zeitüberwachung gestoppt")
                self.set_output('A1', False)
    
    async def _time_check_loop(self):
        """Prüft jede Sekunde die aktuelle Uhrzeit"""
        try:
            while True:
                target_time = self.get_input('E2')
                active = self.get_input('E1')
                
                if not active:
                    break
                
                if target_time:
                    now = datetime.now()
                    current_time = now.strftime("%H:%M")
                    current_minute = now.hour * 60 + now.minute
                    
                    if current_time == target_time and current_minute != self._last_trigger_minute:
                        # Uhrzeit stimmt überein → Puls senden
                        logger.debug(f"{self.instance_id}: Uhrzeit {target_time} erreicht, sende Puls")
                        self._last_trigger_minute = current_minute
                        await self._send_pulse()
                    elif current_time != target_time:
                        # Minute ist vorbei, Reset für nächsten Tag
                        pass
                
                # Jede Sekunde prüfen
                await asyncio.sleep(1)
                
        except asyncio.CancelledError:
            logger.debug(f"{self.instance_id}: Zeitüberwachung abgebrochen")
            self.set_output('A1', False)
    
    async def _send_pulse(self):
        """Sendet einen kurzen Puls (1 für 100ms, dann 0)"""
        try:
            self.set_output('A1', True)
            logger.debug(f"{self.instance_id}: Puls ON")
            
            await asyncio.sleep(0.1)
            
            self.set_output('A1', False)
            logger.debug(f"{self.instance_id}: Puls OFF")
            
        except asyncio.CancelledError:
            logger.debug(f"{self.instance_id}: Puls abgebrochen")
            self.set_output('A1', False)


# Für EDOMI-Kompatibilität
class_1 = UhrzeitTrigger
