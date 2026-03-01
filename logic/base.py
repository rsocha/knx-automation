"""
Base class for Logic Blocks (Logikbausteine)

Similar to EDOMI LBS or Gira HomeServer logic blocks.
Each block has:
- Unique ID number (like EDOMI's 5-digit IDs)
- Inputs (E1-En) and Outputs (A1-An)
- Optional timer/polling support
- HTTP request capabilities

Example block:

class MyLogicBlock(LogicBlock):
    ID = 10001  # Unique block ID
    NAME = "My Block"
    DESCRIPTION = "Does something useful"
    CATEGORY = "Custom"
    
    INPUTS = {
        'E1': {'name': 'Input 1', 'type': 'bool', 'default': False},
        'E2': {'name': 'Input 2', 'type': 'float', 'default': 0.0},
    }
    
    OUTPUTS = {
        'A1': {'name': 'Output 1', 'type': 'bool'},
        'A2': {'name': 'Output 2', 'type': 'float'},
    }
    
    def execute(self, triggered_by=None):
        # Called when any input changes
        if self.get_input('E1'):
            self.set_output('A1', True)
            self.set_output('A2', self.get_input('E2') * 2)
"""

import asyncio
import aiohttp
import logging
import json
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
from datetime import datetime

logger = logging.getLogger(__name__)


class LogicBlock(ABC):
    """Base class for all logic blocks"""
    
    # Override in subclass - UNIQUE ID NUMBER
    ID: int = 0  # Unique block ID like EDOMI (e.g. 20027)
    NAME: str = "Unnamed Block"
    DESCRIPTION: str = ""
    VERSION: str = "1.0"
    AUTHOR: str = ""
    CATEGORY: str = "Allgemein"  # Category for grouping
    
    # Define inputs and outputs in subclass
    # Format: {'E1': {'name': 'Input Name', 'type': 'bool|int|float|str', 'default': value}}
    INPUTS: Dict[str, Dict] = {}
    OUTPUTS: Dict[str, Dict] = {}

    # Remanent blocks persist custom state across reboots
    REMANENT: bool = False

    # Help text: documentation, usage notes, version history (displayed in help dialog)
    # Use plain text or simple markdown. Example:
    # HELP = """
    # Funktionsweise:
    # 1. E1 auf 1 setzen → Block startet
    # 2. Wert an E2 → wird verdoppelt an A1 ausgegeben
    #
    # Versionshistorie:
    # v1.1 – Neuer Eingang E3
    # v1.0 – Erstversion
    # """
    HELP: str = ""
    
    def __init__(self, instance_id: str):
        self.instance_id = instance_id
        self._input_values: Dict[str, Any] = {}
        self._output_values: Dict[str, Any] = {}
        self._input_bindings: Dict[str, str] = {}  # E1 -> "1/2/3" or "INT/0/1"
        self._output_bindings: Dict[str, str] = {}  # A1 -> "1/2/4" or "INT/0/2"
        self._enabled = True
        self._last_executed: Optional[datetime] = None
        self._output_callback = None
        self._timer_task: Optional[asyncio.Task] = None
        self._timer_interval: float = 0  # Seconds, 0 = disabled
        self._running = False
        self._debug_values: Dict[str, str] = {}
        
        # Initialize with defaults
        for key, config in self.INPUTS.items():
            self._input_values[key] = config.get('default')
        for key, config in self.OUTPUTS.items():
            self._output_values[key] = config.get('default')
    
    # ============ INPUT/OUTPUT METHODS ============
    
    def get_input(self, key: str) -> Any:
        """Get current value of an input"""
        return self._input_values.get(key)
    
    def set_input(self, key: str, value: Any, force_trigger: bool = False) -> bool:
        """Set input value (called by manager when bound address changes)
        
        Args:
            key: Input key (e.g. 'E1')
            value: New value to set
            force_trigger: If True, always trigger execute even if value unchanged
        """
        if key not in self.INPUTS:
            logger.warning(f"Unknown input {key} for block {self.instance_id}")
            return False
        
        # Type conversion based on config
        input_config = self.INPUTS[key]
        input_type = input_config.get('type', 'str')
        is_trigger = input_config.get('trigger', False)  # Trigger inputs always execute on True
        
        try:
            if input_type == 'bool':
                if isinstance(value, str):
                    value = value.lower() in ('1', 'true', 'on', 'ein')
                else:
                    value = bool(value)
            elif input_type == 'int':
                value = int(float(value)) if value is not None else 0
            elif input_type == 'float':
                value = float(value) if value is not None else 0.0
            else:
                value = str(value) if value is not None else ''
        except (ValueError, TypeError):
            logger.warning(f"Could not convert value {value} to {input_type}")
            return False
        
        old_value = self._input_values.get(key)
        self._input_values[key] = value
        
        # Trigger execution if:
        # - Value changed, OR
        # - force_trigger is True, OR
        # - Input is marked as 'trigger' and value is True/1
        should_trigger = (old_value != value) or force_trigger or (is_trigger and value)
        
        if should_trigger and self._enabled:
            self._trigger_execute(key)
        
        return True
    
    def get_output(self, key: str) -> Any:
        """Get current value of an output"""
        return self._output_values.get(key)
    
    def set_output(self, key: str, value: Any):
        """Set output value (called from execute())"""
        if key not in self.OUTPUTS:
            logger.warning(f"Unknown output {key} for block {self.instance_id}")
            return
        
        # Type conversion
        output_type = self.OUTPUTS[key].get('type', 'str')
        try:
            if output_type == 'bool':
                value = bool(value)
            elif output_type == 'int':
                value = int(float(value)) if value is not None else 0
            elif output_type == 'float':
                value = float(value) if value is not None else 0.0
            else:
                value = str(value) if value is not None else ''
        except (ValueError, TypeError):
            pass
        
        old_value = self._output_values.get(key)
        self._output_values[key] = value
        
        # Notify manager about output change
        if old_value != value and self._output_callback:
            self._output_callback(self.instance_id, key, value)
    
    # ============ BINDING METHODS ============
    
    def bind_input(self, input_key: str, address: str):
        """Bind an input to a KNX or internal address"""
        if input_key not in self.INPUTS:
            logger.warning(f"{self.instance_id}: Binding unknown input '{input_key}' (known: {list(self.INPUTS.keys())})")
        self._input_bindings[input_key] = address
    
    def bind_output(self, output_key: str, address: str):
        """Bind an output to a KNX or internal address"""
        if output_key not in self.OUTPUTS:
            logger.warning(f"{self.instance_id}: Binding unknown output '{output_key}' (known: {list(self.OUTPUTS.keys())})")
        self._output_bindings[output_key] = address
    
    def get_input_binding(self, input_key: str) -> Optional[str]:
        return self._input_bindings.get(input_key)
    
    def get_output_binding(self, output_key: str) -> Optional[str]:
        return self._output_bindings.get(output_key)
    
    # ============ TIMER METHODS ============
    
    def set_timer(self, interval_seconds: float):
        """Set a recurring timer that calls on_timer()"""
        self._timer_interval = interval_seconds
        if self._running and interval_seconds > 0:
            self._start_timer()
    
    def _start_timer(self):
        """Start the timer task"""
        if self._timer_task:
            self._timer_task.cancel()
        if self._timer_interval > 0:
            self._timer_task = asyncio.create_task(self._timer_loop())
    
    async def _timer_loop(self):
        """Timer loop - calls on_timer periodically"""
        # Run immediately on start
        if self._running and self._enabled:
            try:
                logger.info(f"Timer starting for {self.instance_id}, running first poll...")
                await self.on_timer()
            except Exception as e:
                logger.error(f"Error in initial on_timer for {self.instance_id}: {e}")
        
        # Then continue with interval
        while self._running and self._timer_interval > 0:
            await asyncio.sleep(self._timer_interval)
            if self._running and self._enabled:
                try:
                    await self.on_timer()
                except Exception as e:
                    logger.error(f"Error in on_timer for {self.instance_id}: {e}")
    
    async def on_timer(self):
        """Override this for periodic tasks (polling, etc.)"""
        pass
    
    # ============ HTTP METHODS ============
    
    async def http_get(self, url: str, timeout: float = 10) -> Optional[str]:
        """Make HTTP GET request"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                    return await response.text()
        except Exception as e:
            logger.error(f"HTTP GET error for {url}: {e}")
            return None
    
    async def http_get_json(self, url: str, timeout: float = 10) -> Optional[Dict]:
        """Make HTTP GET request and parse JSON"""
        try:
            logger.info(f"HTTP GET JSON: {url}")
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                    text = await response.text()
                    logger.debug(f"HTTP Response ({response.status}): {text[:200]}")
                    if response.status == 200:
                        import json
                        return json.loads(text)
                    else:
                        logger.error(f"HTTP GET failed with status {response.status}")
                        return None
        except Exception as e:
            logger.error(f"HTTP GET JSON error for {url}: {e}")
            self.debug("HTTP Error", str(e))
            return None
    
    async def http_post(self, url: str, data: Dict = None, json_data: Dict = None, timeout: float = 10) -> Optional[str]:
        """Make HTTP POST request"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data, json=json_data, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                    return await response.text()
        except Exception as e:
            logger.error(f"HTTP POST error for {url}: {e}")
            return None
    
    # ============ DEBUG METHODS ============
    
    def debug(self, key: str, value: Any):
        """Set a debug value (visible in dashboard)"""
        self._debug_values[key] = str(value)
    
    # ============ UTILITY METHODS ============
    
    def clean_float(self, value: Any, default: float = 0.0) -> float:
        """Safely convert value to float, removing units"""
        if value is None:
            return default
        try:
            s_val = str(value)
            for unit in ['%', '°C', 'C', 'm/s', 'mm/h', 'mm/Hr', 'mm', 'Klux', 'W/m²', 'hPa', 'kPa', 'W', 'kW', 'kWh', 'V', 'A']:
                s_val = s_val.replace(unit, '')
            return float(s_val.strip())
        except:
            return default
    
    # ============ EXECUTION ============
    
    def _trigger_execute(self, changed_input: str = None):
        """Execute the logic block"""
        try:
            self._last_executed = datetime.now()
            
            # Call on_input_change if the block has it (used by async blocks)
            if hasattr(self, 'on_input_change') and changed_input:
                old_value = None  # We don't track old value here
                new_value = self._input_values.get(changed_input)
                logger.debug(f"Calling on_input_change for {self.instance_id}: {changed_input} = {new_value}")
                self.on_input_change(changed_input, new_value, old_value)
            
            # Also call execute
            self.execute(changed_input)
        except Exception as e:
            logger.error(f"Error executing block {self.instance_id}: {e}")
    
    @abstractmethod
    def execute(self, triggered_by: str = None):
        """
        Main logic - override in subclass.
        Called when any input value changes.
        
        Args:
            triggered_by: The input key that triggered this execution (e.g. 'E1')
        """
        pass
    
    def on_start(self):
        """Called when block is started/loaded. Override for initialization."""
        self._running = True
        if self._timer_interval > 0:
            self._start_timer()
    
    def on_stop(self):
        """Called when block is stopped/unloaded. Override for cleanup."""
        self._running = False
        if self._timer_task:
            self._timer_task.cancel()
            self._timer_task = None

    def get_remanent_state(self) -> Optional[Dict]:
        """Override: Return custom state dict to persist across reboots.
        Only called if REMANENT = True. Return None to skip saving."""
        return None

    def restore_remanent_state(self, state: Dict) -> None:
        """Override: Restore block from previously saved remanent state.
        Called during startup before on_start() if saved state exists."""
        pass

    def to_dict(self) -> Dict:
        """Serialize block state"""
        return {
            'instance_id': self.instance_id,
            'block_id': self.ID,
            'block_type': self.__class__.__name__,
            'name': self.NAME,
            'description': self.DESCRIPTION,
            'category': self.CATEGORY,
            'remanent': self.REMANENT,
            'enabled': self._enabled,
            'timer_interval': self._timer_interval,
            'page_id': getattr(self, '_page_id', None),
            'inputs': {
                k: {
                    'config': v,
                    'value': self._input_values.get(k),
                    'binding': self._input_bindings.get(k)
                }
                for k, v in self.INPUTS.items()
            },
            'outputs': {
                k: {
                    'config': v,
                    'value': self._output_values.get(k),
                    'binding': self._output_bindings.get(k)
                }
                for k, v in self.OUTPUTS.items()
            },
            'input_bindings': dict(self._input_bindings),
            'output_bindings': dict(self._output_bindings),
            'input_values': dict(self._input_values),
            'output_values': dict(self._output_values),
            'debug': self._debug_values,
            'last_executed': self._last_executed.isoformat() if self._last_executed else None
        }


# ============ BUILT-IN BLOCKS ============

class AndGate(LogicBlock):
    """Logical AND - Output is true only if all inputs are true"""
    ID = 10001
    NAME = "AND Gatter"
    DESCRIPTION = "Ausgang ist 1 wenn alle Eingänge 1 sind"
    CATEGORY = "Logik"
    
    INPUTS = {
        'E1': {'name': 'Eingang 1', 'type': 'bool', 'default': False},
        'E2': {'name': 'Eingang 2', 'type': 'bool', 'default': False},
    }
    OUTPUTS = {
        'A1': {'name': 'Ausgang', 'type': 'bool'},
    }
    
    def execute(self, triggered_by=None):
        result = self.get_input('E1') and self.get_input('E2')
        self.set_output('A1', result)


class OrGate(LogicBlock):
    """Logical OR - Output is true if any input is true"""
    ID = 10002
    NAME = "OR Gatter"
    DESCRIPTION = "Ausgang ist 1 wenn mindestens ein Eingang 1 ist"
    CATEGORY = "Logik"
    
    INPUTS = {
        'E1': {'name': 'Eingang 1', 'type': 'bool', 'default': False},
        'E2': {'name': 'Eingang 2', 'type': 'bool', 'default': False},
    }
    OUTPUTS = {
        'A1': {'name': 'Ausgang', 'type': 'bool'},
    }
    
    def execute(self, triggered_by=None):
        result = self.get_input('E1') or self.get_input('E2')
        self.set_output('A1', result)


class NotGate(LogicBlock):
    """Logical NOT - Inverts the input"""
    ID = 10003
    NAME = "NOT Gatter"
    DESCRIPTION = "Invertiert den Eingang"
    CATEGORY = "Logik"
    
    INPUTS = {
        'E1': {'name': 'Eingang', 'type': 'bool', 'default': False},
    }
    OUTPUTS = {
        'A1': {'name': 'Ausgang', 'type': 'bool'},
    }
    
    def execute(self, triggered_by=None):
        self.set_output('A1', not self.get_input('E1'))


class Threshold(LogicBlock):
    """Threshold comparator - Output true if input >= threshold"""
    ID = 10010
    NAME = "Schwellwert"
    DESCRIPTION = "Ausgang ist 1 wenn Eingang >= Schwellwert"
    CATEGORY = "Vergleich"
    
    INPUTS = {
        'E1': {'name': 'Wert', 'type': 'float', 'default': 0.0},
        'E2': {'name': 'Schwellwert', 'type': 'float', 'default': 50.0},
    }
    OUTPUTS = {
        'A1': {'name': 'Über Schwellwert', 'type': 'bool'},
    }
    
    def execute(self, triggered_by=None):
        value = self.get_input('E1') or 0
        threshold = self.get_input('E2') or 0
        self.set_output('A1', value >= threshold)


class Multiply(LogicBlock):
    """Multiply input by factor"""
    ID = 10020
    NAME = "Multiplikation"
    DESCRIPTION = "Multipliziert Eingang mit Faktor"
    CATEGORY = "Rechnen"
    
    INPUTS = {
        'E1': {'name': 'Wert', 'type': 'float', 'default': 0.0},
        'E2': {'name': 'Faktor', 'type': 'float', 'default': 1.0},
    }
    OUTPUTS = {
        'A1': {'name': 'Ergebnis', 'type': 'float'},
    }
    
    def execute(self, triggered_by=None):
        value = self.get_input('E1') or 0
        factor = self.get_input('E2') or 1
        self.set_output('A1', value * factor)


class Add(LogicBlock):
    """Add two values"""
    ID = 10021
    NAME = "Addition"
    DESCRIPTION = "Addiert zwei Werte"
    CATEGORY = "Rechnen"
    
    INPUTS = {
        'E1': {'name': 'Wert 1', 'type': 'float', 'default': 0.0},
        'E2': {'name': 'Wert 2', 'type': 'float', 'default': 0.0},
    }
    OUTPUTS = {
        'A1': {'name': 'Summe', 'type': 'float'},
    }
    
    def execute(self, triggered_by=None):
        self.set_output('A1', (self.get_input('E1') or 0) + (self.get_input('E2') or 0))


class Switch(LogicBlock):
    """Switch/Selector - Routes input to output based on selector"""
    ID = 10040
    NAME = "Umschalter"
    DESCRIPTION = "Schaltet zwischen zwei Eingängen"
    CATEGORY = "Logik"
    
    INPUTS = {
        'E1': {'name': 'Eingang A', 'type': 'float', 'default': 0.0},
        'E2': {'name': 'Eingang B', 'type': 'float', 'default': 0.0},
        'E3': {'name': 'Auswahl (0=A, 1=B)', 'type': 'bool', 'default': False},
    }
    OUTPUTS = {
        'A1': {'name': 'Ausgang', 'type': 'float'},
    }
    
    def execute(self, triggered_by=None):
        if self.get_input('E3'):
            self.set_output('A1', self.get_input('E2'))
        else:
            self.set_output('A1', self.get_input('E1'))


class Hysteresis(LogicBlock):
    """Hysteresis switch - On above high, off below low"""
    ID = 10050
    NAME = "Hysterese"
    DESCRIPTION = "Schaltet ein über Obergrenze, aus unter Untergrenze"
    CATEGORY = "Vergleich"
    
    INPUTS = {
        'E1': {'name': 'Wert', 'type': 'float', 'default': 0.0},
        'E2': {'name': 'Untergrenze', 'type': 'float', 'default': 20.0},
        'E3': {'name': 'Obergrenze', 'type': 'float', 'default': 25.0},
    }
    OUTPUTS = {
        'A1': {'name': 'Ausgang', 'type': 'bool'},
    }
    
    def on_start(self):
        super().on_start()
        self._state = False
    
    def execute(self, triggered_by=None):
        value = self.get_input('E1') or 0
        low = self.get_input('E2') or 0
        high = self.get_input('E3') or 0
        
        if value >= high:
            self._state = True
        elif value <= low:
            self._state = False
        
        self.set_output('A1', self._state)


# Registry of built-in blocks
BUILTIN_BLOCKS = {
    'AndGate': AndGate,
    'OrGate': OrGate,
    'NotGate': NotGate,
    'Threshold': Threshold,
    'Multiply': Multiply,
    'Add': Add,
    'Switch': Switch,
    'Hysteresis': Hysteresis,
}
