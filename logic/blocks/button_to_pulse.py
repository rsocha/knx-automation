"""
Button to Pulse Converter (v1.0)

Konvertiert einen Button-Klick (konstante 1) in einen kurzen Puls (1→0).

Eingänge:
- E1: Button Input (bei 1 wird Puls ausgelöst)

Ausgänge:
- A1: Puls Output (1 für 100ms, dann 0)

Verwendung:
[Button] → E1 → [Button-to-Pulse] → A1 → [Sonos E4 Play]

Wenn Button = 1:
- A1 wird auf 1 gesetzt
- Nach 100ms wird A1 auf 0 gesetzt
- Beim nächsten Klick funktioniert es wieder
"""

import asyncio
import logging

try:
    from ..base import LogicBlock
except ImportError:
    from logic.base import LogicBlock

logger = logging.getLogger(__name__)


class ButtonToPulse(LogicBlock):
    """Konvertiert Button-Klicks in Pulse"""
    
    BLOCK_TYPE = "button_to_pulse"
    ID = 19001  # Unique ID for custom blocks
    NAME = "Button → Puls"
    DESCRIPTION = "Konvertiert Button-Klicks (konstante 1) in Pulse (1→0→1)"
    CATEGORY = "Hilfsmittel"
    
    INPUTS = {
        'E1': {'name': 'Button Input', 'type': 'bool'},
    }
    
    OUTPUTS = {
        'A1': {'name': 'Pulse Output', 'type': 'bool'},
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pulse_task = None
    
    def execute(self, triggered_by=None):
        # Nur bei E1 und nur bei steigender Flanke (0→1)
        if triggered_by == 'E1':
            button_state = self.get_input('E1')
            
            if button_state:
                # Button wurde gedrückt → Puls senden
                logger.debug(f"{self.instance_id}: Button gedrückt, sende Puls")
                
                # Falls ein alter Puls noch läuft, abbrechen
                if self._pulse_task and not self._pulse_task.done():
                    self._pulse_task.cancel()
                
                # Neuen Puls starten
                self._pulse_task = asyncio.create_task(self._send_pulse())
    
    async def _send_pulse(self):
        """Sendet einen kurzen Puls (1 für 100ms, dann 0)"""
        try:
            # Puls auf 1 setzen
            self.set_output('A1', True)
            logger.debug(f"{self.instance_id}: Puls ON")
            
            # 100ms warten
            await asyncio.sleep(0.1)
            
            # Puls auf 0 zurücksetzen
            self.set_output('A1', False)
            logger.debug(f"{self.instance_id}: Puls OFF")
            
        except asyncio.CancelledError:
            logger.debug(f"{self.instance_id}: Puls abgebrochen")
            self.set_output('A1', False)


# Für EDOMI-Kompatibilität
class_1 = ButtonToPulse
