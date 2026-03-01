"""
Logic Manager - Handles loading, executing and managing logic blocks

Similar to EDOMI's logic engine or Gira HomeServer's logic module system.
"""

import os
import sys
import json
import asyncio
import logging
import importlib.util
from typing import Dict, List, Optional, Any, Type
from datetime import datetime
from pathlib import Path

from .base import LogicBlock, BUILTIN_BLOCKS

# Import extra blocks
try:
    from .blocks import EXTRA_BLOCKS
except ImportError:
    EXTRA_BLOCKS = {}

# Combine all blocks
ALL_BUILTIN_BLOCKS = {**BUILTIN_BLOCKS, **EXTRA_BLOCKS}

logger = logging.getLogger(__name__)


class LogicManager:
    """Manages logic blocks and their execution"""
    
    def __init__(self):
        self._blocks: Dict[str, LogicBlock] = {}  # instance_id -> block
        self._custom_block_classes: Dict[str, Type[LogicBlock]] = {}  # class_name -> class
        self._address_to_blocks: Dict[str, List[tuple]] = {}  # address -> [(block_id, input_key)]
        self._pages: Dict[str, Dict] = {}  # page_id -> page config
        self._db_manager = None
        self._knx_manager = None
        self._running = False
        self._custom_blocks_path = Path(__file__).parent.parent / "data" / "custom_blocks"
    
    async def initialize(self, db_manager, knx_manager):
        """Initialize the logic manager"""
        self._db_manager = db_manager
        self._knx_manager = knx_manager
        
        # Create directories
        self._custom_blocks_path.mkdir(parents=True, exist_ok=True)
        data_dir = self._custom_blocks_path.parent
        data_dir.mkdir(parents=True, exist_ok=True)
        
        # Preserve raw config for blocks that couldn't be loaded (missing .py, import error, etc.)
        # These will be re-saved so they aren't lost permanently
        self._unloaded_block_configs: list = []
        
        logger.info(f"Data directory: {data_dir}")
        logger.info(f"Custom blocks path: {self._custom_blocks_path}")
        logger.info(f"Available builtin blocks: {list(ALL_BUILTIN_BLOCKS.keys())}")
        
        # Load custom blocks from disk
        await self._load_custom_blocks()
        
        # Load block instances and pages from database
        await self._load_from_db()
        
        self._running = True
        logger.info(f"Logic manager initialized with {len(self._blocks)} blocks")

        # Start periodic auto-save for remanent blocks
        self._autosave_task = asyncio.create_task(self._autosave_loop())
    
    async def _load_custom_blocks(self):
        """Load custom block classes from Python files"""
        logger.info(f"Loading custom blocks from: {self._custom_blocks_path}")
        logger.info(f"Path exists: {self._custom_blocks_path.exists()}")
        
        if not self._custom_blocks_path.exists():
            logger.warning(f"Custom blocks path does not exist, creating it...")
            self._custom_blocks_path.mkdir(parents=True, exist_ok=True)
            return
        
        # List all files in directory
        all_files = list(self._custom_blocks_path.iterdir())
        logger.info(f"Files in custom_blocks directory: {[f.name for f in all_files]}")
        
        py_files = list(self._custom_blocks_path.glob("*.py"))
        logger.info(f"Found {len(py_files)} .py files: {[f.name for f in py_files]}")
        
        for file in py_files:
            try:
                logger.info(f"Loading block file: {file}")
                result = await self._load_block_file(file)
                if result:
                    logger.info(f"Successfully loaded: {result}")
                else:
                    logger.warning(f"No LogicBlock classes found in {file}")
            except Exception as e:
                logger.error(f"Error loading custom block {file}: {e}", exc_info=True)
        
        logger.info(f"Custom block classes loaded: {list(self._custom_block_classes.keys())}")
    
    async def _load_block_file(self, file_path: Path) -> Optional[str]:
        """Load a single block file and register its classes"""
        try:
            spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
            if not spec or not spec.loader:
                return None
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[file_path.stem] = module
            spec.loader.exec_module(module)
            
            # Find all LogicBlock subclasses in the module
            loaded = []
            for name in dir(module):
                obj = getattr(module, name)
                if (isinstance(obj, type) and 
                    issubclass(obj, LogicBlock) and 
                    obj is not LogicBlock):
                    self._custom_block_classes[name] = obj
                    loaded.append(name)
                    logger.info(f"Loaded custom block: {name}")
            
            return ", ".join(loaded) if loaded else None
            
        except Exception as e:
            logger.error(f"Error loading block file {file_path}: {e}")
            raise
    
    async def upload_block_file(self, filename: str, content: bytes) -> Dict:
        """Upload and register a new custom block file, auto-restart running instances"""
        # Sanitize filename
        safe_name = "".join(c for c in filename if c.isalnum() or c in "._-").rstrip()
        if not safe_name.endswith('.py'):
            safe_name += '.py'
        
        # Ensure directory exists
        self._custom_blocks_path.mkdir(parents=True, exist_ok=True)
        
        file_path = self._custom_blocks_path / safe_name
        
        # Write file
        with open(file_path, 'wb') as f:
            f.write(content)
        
        # Try to load it
        try:
            loaded = await self._load_block_file(file_path)
            if loaded:
                # Auto-restart running instances of updated block types
                loaded_classes = [c.strip() for c in loaded.split(",")]
                restarted = await self._restart_instances_of_types(loaded_classes)
                result = {"status": "success", "file": safe_name, "loaded_classes": loaded_classes}
                if restarted:
                    result["restarted"] = restarted
                    logger.info(f"Auto-restarted {len(restarted)} block instances: {restarted}")
                return result
            else:
                return {"status": "warning", "file": safe_name, "message": "No LogicBlock classes found"}
        except Exception as e:
            # Remove file if it failed to load
            file_path.unlink(missing_ok=True)
            raise ValueError(f"Invalid block file: {e}")
    
    async def _restart_instances_of_types(self, class_names: list) -> list:
        """Restart all running instances whose block_type matches one of the class_names.
        Preserves bindings, page_id and input values."""
        restarted = []
        for instance_id, block in list(self._blocks.items()):
            block_type = type(block).__name__
            if block_type not in class_names:
                continue
            
            logger.info(f"Auto-restarting {instance_id} (type: {block_type})")
            
            # Save state
            saved_input_bindings = dict(block._input_bindings)
            saved_output_bindings = dict(block._output_bindings)
            saved_input_values = dict(block._input_values)
            saved_page_id = getattr(block, '_page_id', None)
            
            # Stop old instance
            try:
                result = block.on_stop()
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.warning(f"Error stopping {instance_id}: {e}")
            
            # Remove from address mappings
            for addr, bindings in list(self._address_to_blocks.items()):
                self._address_to_blocks[addr] = [(bid, key) for bid, key in bindings if bid != instance_id]
                if not self._address_to_blocks[addr]:
                    del self._address_to_blocks[addr]
            
            # Create new instance with updated class
            cls = self._custom_block_classes.get(block_type)
            if not cls:
                logger.error(f"Class {block_type} not found after reload, skipping {instance_id}")
                continue
            
            new_block = cls(instance_id)
            new_block._output_callback = self._on_block_output
            new_block._page_id = saved_page_id
            
            # Restore bindings
            new_block._input_bindings = saved_input_bindings
            new_block._output_bindings = saved_output_bindings
            
            # Restore address mappings
            for input_key, addr in saved_input_bindings.items():
                if addr not in self._address_to_blocks:
                    self._address_to_blocks[addr] = []
                self._address_to_blocks[addr].append((instance_id, input_key))
            
            # Replace in blocks dict
            self._blocks[instance_id] = new_block
            
            # Start new instance
            try:
                result = new_block.on_start()
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Error starting {instance_id}: {e}")
            
            # Restore input values (triggers execute for each)
            for key, val in saved_input_values.items():
                try:
                    new_block.set_input(key, val)
                except Exception:
                    pass
            
            restarted.append(instance_id)
            logger.info(f"Restarted {instance_id} with new {block_type} class")
        
        return restarted
    
    def get_available_blocks(self) -> List[Dict]:
        """Get list of all available block types (builtin + custom)"""
        blocks = []
        
        # Built-in blocks
        for name, cls in ALL_BUILTIN_BLOCKS.items():
            blocks.append({
                'type': name,
                'id': getattr(cls, 'ID', 0),
                'name': cls.NAME,
                'description': cls.DESCRIPTION,
                'category': getattr(cls, 'CATEGORY', 'Allgemein'),
                'version': getattr(cls, 'VERSION', '1.0'),
                'author': getattr(cls, 'AUTHOR', ''),
                'remanent': getattr(cls, 'REMANENT', False),
                'builtin': True,
                'inputs': cls.INPUTS,
                'outputs': cls.OUTPUTS,
                'help': getattr(cls, 'HELP', ''),
            })
        
        # Custom blocks
        for name, cls in self._custom_block_classes.items():
            blocks.append({
                'type': name,
                'id': getattr(cls, 'ID', 0),
                'name': getattr(cls, 'NAME', name),
                'description': getattr(cls, 'DESCRIPTION', ''),
                'category': getattr(cls, 'CATEGORY', 'Custom'),
                'version': getattr(cls, 'VERSION', '1.0'),
                'author': getattr(cls, 'AUTHOR', ''),
                'remanent': getattr(cls, 'REMANENT', False),
                'builtin': False,
                'inputs': getattr(cls, 'INPUTS', {}),
                'outputs': getattr(cls, 'OUTPUTS', {}),
                'help': getattr(cls, 'HELP', ''),
            })
        
        # Sort by ID
        blocks.sort(key=lambda b: b['id'])
        
        return blocks
    
    def get_custom_block_files(self) -> List[Dict]:
        """Get list of uploaded custom block files"""
        files = []
        if self._custom_blocks_path.exists():
            for f in self._custom_blocks_path.glob("*.py"):
                files.append({
                    'filename': f.name,
                    'size': f.stat().st_size,
                    'modified': datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                })
        return files
    
    async def delete_block_file(self, filename: str) -> bool:
        """Delete a custom block file"""
        file_path = self._custom_blocks_path / filename
        if file_path.exists():
            # Remove classes from registry
            # (instances using these classes will fail on next restart)
            file_path.unlink()
            return True
        return False
    
    async def create_block_async(self, block_type: str, instance_id: str = None, page_id: str = None) -> Optional[LogicBlock]:
        """Create a new block instance (async version)"""
        block = self.create_block(block_type, instance_id, page_id)
        if block:
            # Give the event loop time, then trigger initial poll if available
            await asyncio.sleep(0.1)
            if hasattr(block, 'poll_data'):
                try:
                    logger.info(f"Running initial poll for {block.instance_id}")
                    await block.poll_data()
                except Exception as e:
                    logger.error(f"Error in initial poll for {block.instance_id}: {e}")
        return block
    
    def create_block(self, block_type: str, instance_id: str = None, page_id: str = None, skip_on_start: bool = False) -> Optional[LogicBlock]:
        """Create a new block instance"""
        # Find the class
        if block_type in ALL_BUILTIN_BLOCKS:
            cls = ALL_BUILTIN_BLOCKS[block_type]
        elif block_type in self._custom_block_classes:
            cls = self._custom_block_classes[block_type]
        else:
            logger.error(f"Unknown block type: {block_type}")
            return None
        
        # Generate ID if not provided - include block ID number
        if not instance_id:
            block_id = getattr(cls, 'ID', 0)
            instance_id = f"{block_id}_{block_type}_{len(self._blocks)}_{datetime.now().strftime('%H%M%S')}"
        
        # Create instance
        block = cls(instance_id)
        block._output_callback = self._on_block_output
        block._page_id = page_id
        
        # Register
        self._blocks[instance_id] = block
        
        # Call on_start (handle both sync and async) - unless loading from DB
        if not skip_on_start:
            try:
                result = block.on_start()
                if asyncio.iscoroutine(result):
                    asyncio.create_task(result)
            except Exception as e:
                logger.error(f"Error in on_start for {instance_id}: {e}")
        
        logger.info(f"Created block {instance_id} of type {block_type}")
        return block
    
    def get_block(self, instance_id: str) -> Optional[LogicBlock]:
        """Get a block by its instance ID"""
        return self._blocks.get(instance_id)
    
    def get_all_blocks(self) -> List[Dict]:
        """Get all block instances as dicts"""
        return [b.to_dict() for b in self._blocks.values()]
    
    def delete_block(self, instance_id: str) -> bool:
        """Delete a block instance"""
        if instance_id not in self._blocks:
            return False
        
        block = self._blocks[instance_id]
        
        # Call on_stop (handle both sync and async)
        try:
            result = block.on_stop()
            # If it's a coroutine, run it
            if asyncio.iscoroutine(result):
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(result)
                    else:
                        loop.run_until_complete(result)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Error in on_stop for {instance_id}: {e}")
        
        # Remove from address mappings
        for addr, bindings in list(self._address_to_blocks.items()):
            self._address_to_blocks[addr] = [(bid, key) for bid, key in bindings if bid != instance_id]
            if not self._address_to_blocks[addr]:
                del self._address_to_blocks[addr]
        
        del self._blocks[instance_id]
        logger.info(f"Deleted block {instance_id}")
        return True
    
    def bind_input(self, instance_id: str, input_key: str, address: str):
        """Bind a block input to an address"""
        block = self._blocks.get(instance_id)
        if not block:
            return False
        
        # Remove old binding
        old_addr = block.get_input_binding(input_key)
        if old_addr and old_addr in self._address_to_blocks:
            self._address_to_blocks[old_addr] = [
                (bid, key) for bid, key in self._address_to_blocks[old_addr]
                if not (bid == instance_id and key == input_key)
            ]
        
        # Set new binding
        block.bind_input(input_key, address)
        
        # Register in address map
        if address not in self._address_to_blocks:
            self._address_to_blocks[address] = []
        self._address_to_blocks[address].append((instance_id, input_key))
        
        logger.debug(f"Bound {instance_id}.{input_key} to {address}")
        
        # Schedule initial value sync
        asyncio.create_task(self._sync_input_value(instance_id, input_key, address))
        
        return True
    
    async def _sync_input_value(self, instance_id: str, input_key: str, address: str):
        """Sync input value from bound address"""
        try:
            if self._db_manager:
                addr_obj = await self._db_manager.get_group_address(address)
                if addr_obj and addr_obj.last_value is not None:
                    block = self._blocks.get(instance_id)
                    if block:
                        logger.info(f"Syncing {address}={addr_obj.last_value} -> {instance_id}.{input_key}")
                        block.set_input(input_key, addr_obj.last_value)
        except Exception as e:
            logger.error(f"Error syncing input value: {e}")
    
    def bind_output(self, instance_id: str, output_key: str, address: str):
        """Bind a block output to an address"""
        block = self._blocks.get(instance_id)
        if not block:
            return False
        
        block.bind_output(output_key, address)
        logger.debug(f"Bound {instance_id}.{output_key} -> {address}")
        
        # Write current value to address immediately
        current_value = block._output_values.get(output_key)
        if current_value is not None:
            asyncio.create_task(self._write_output(address, current_value))
            logger.info(f"Initial write {address} = {current_value}")
        
        return True
    
    def unbind_address(self, address: str) -> int:
        """Remove all bindings to a specific address (when KO is deleted)
        
        Returns the number of bindings removed.
        """
        removed_count = 0
        
        # Remove from input bindings
        if address in self._address_to_blocks:
            for instance_id, input_key in self._address_to_blocks[address]:
                block = self._blocks.get(instance_id)
                if block:
                    block._input_bindings.pop(input_key, None)
                    removed_count += 1
                    logger.info(f"Unbound input {instance_id}.{input_key} from deleted address {address}")
            del self._address_to_blocks[address]
        
        # Remove from output bindings
        for instance_id, block in self._blocks.items():
            for output_key, bound_addr in list(block._output_bindings.items()):
                if bound_addr == address:
                    del block._output_bindings[output_key]
                    removed_count += 1
                    logger.info(f"Unbound output {instance_id}.{output_key} from deleted address {address}")
        
        if removed_count > 0:
            # Save changes to DB
            asyncio.create_task(self.save_to_db())
        
        return removed_count

    def unbind_input(self, instance_id: str, input_key: str) -> bool:
        """Remove a single input binding from a block"""
        block = self._blocks.get(instance_id)
        if not block:
            return False

        old_addr = block.get_input_binding(input_key)
        if not old_addr:
            logger.warning(f"No binding found for {instance_id}.{input_key}")
            return False

        # Remove from address_to_blocks map
        if old_addr in self._address_to_blocks:
            self._address_to_blocks[old_addr] = [
                (bid, key) for bid, key in self._address_to_blocks[old_addr]
                if not (bid == instance_id and key == input_key)
            ]
            if not self._address_to_blocks[old_addr]:
                del self._address_to_blocks[old_addr]

        # Remove from block
        block._input_bindings.pop(input_key, None)
        logger.info(f"Unbound input {instance_id}.{input_key} from {old_addr}")
        return True

    def unbind_output(self, instance_id: str, output_key: str) -> bool:
        """Remove a single output binding from a block"""
        block = self._blocks.get(instance_id)
        if not block:
            return False

        old_addr = block.get_output_binding(output_key)
        if not old_addr:
            logger.warning(f"No output binding found for {instance_id}.{output_key}")
            return False

        block._output_bindings.pop(output_key, None)
        logger.info(f"Unbound output {instance_id}.{output_key} from {old_addr}")
        return True

    async def on_address_changed(self, address: str, value: Any):
        """Called when a KNX or internal address value changes"""
        if not self._running:
            return
        
        # Coerce string values to proper types (API sends strings from query params)
        if isinstance(value, str):
            v = value.strip()
            if v.lower() in ('true', 'on'):
                value = True
            elif v.lower() in ('false', 'off'):
                value = False
            else:
                try:
                    iv = int(v)
                    # Keep as int if it round-trips cleanly
                    if str(iv) == v:
                        value = iv
                except ValueError:
                    try:
                        value = float(v)
                    except ValueError:
                        pass  # keep as string
        
        bindings = self._address_to_blocks.get(address, [])
        if bindings:
            logger.info(f"on_address_changed {address}={value} ({type(value).__name__}) -> {len(bindings)} bindings")
        for instance_id, input_key in bindings:
            block = self._blocks.get(instance_id)
            if block and block._enabled:
                try:
                    # Use force_trigger=True so repeated same-value sends still trigger
                    # (important for Play/Pause/Stop buttons that always send 1)
                    block.set_input(input_key, value, force_trigger=True)
                except TypeError:
                    # Fallback for blocks that don't accept force_trigger
                    logger.warning(f"Block {instance_id} set_input doesn't accept force_trigger, using positional")
                    block.set_input(input_key, value)
                except Exception as e:
                    logger.error(f"Error setting input {input_key} on {instance_id}: {e}")
    
    def _on_block_output(self, instance_id: str, output_key: str, value: Any):
        """Called when a block sets an output value"""
        block = self._blocks.get(instance_id)
        if not block:
            return
        
        address = block.get_output_binding(output_key)
        if not address:
            return
        
        # Schedule async write
        asyncio.create_task(self._write_output(address, value))
    
    async def _write_output(self, address: str, value: Any):
        """Write output value to address and trigger all bound inputs"""
        try:
            # Detect internal by prefix or DB flag
            is_internal = address.upper().startswith("IKO:")
            
            if not is_internal and self._db_manager:
                addr_obj = await self._db_manager.get_group_address(address)
                is_internal = addr_obj is not None and addr_obj.is_internal
            
            if is_internal:
                if self._db_manager:
                    # Auto-create IKO if not in DB
                    existing = await self._db_manager.get_group_address(address)
                    if not existing:
                        try:
                            from models.group_address import GroupAddressCreate
                            ga = GroupAddressCreate(
                                address=address, name=f"Auto: {address}",
                                is_internal=True, function="IKO"
                            )
                            await self._db_manager.create_group_address(ga)
                        except Exception:
                            pass
                    # Update DB value
                    await self._db_manager.update_group_address_value(address, str(value))
            elif self._knx_manager:
                # Send to KNX bus
                await self._knx_manager.send_telegram(address, value)

            # ALWAYS route to bound inputs (triggers execute on downstream blocks)
            # For IKO: this is the only way values reach other blocks
            # For KNX: the bus echo is unreliable, so trigger directly too
            await self.on_address_changed(address, value)

        except Exception as e:
            logger.error(f"Error writing output to {address}: {e}")
    
    # ============ PAGES ============
    
    def create_page(self, page_id: str, name: str, description: str = "", room: str = "") -> Dict:
        """Create a new logic page"""
        if page_id in self._pages:
            raise ValueError(f"Page {page_id} already exists")
        
        self._pages[page_id] = {
            'id': page_id,
            'name': name,
            'description': description,
            'room': room,
            'blocks': [],
            'created_at': datetime.now().isoformat()
        }
        return self._pages[page_id]
    
    def update_page(self, page_id: str, name: str = None, description: str = None, room: str = None) -> Optional[Dict]:
        """Update a logic page's name, description, or room"""
        page = self._pages.get(page_id)
        if not page:
            return None
        if name is not None:
            page['name'] = name
        if description is not None:
            page['description'] = description
        if room is not None:
            page['room'] = room
        return page
    
    def get_page(self, page_id: str) -> Optional[Dict]:
        return self._pages.get(page_id)
    
    def get_all_pages(self) -> List[Dict]:
        return list(self._pages.values())
    
    def delete_page(self, page_id: str) -> bool:
        """Delete a page and all its blocks"""
        if page_id not in self._pages:
            return False
        
        # Delete all blocks on this page
        for block in list(self._blocks.values()):
            if getattr(block, '_page_id', None) == page_id:
                self.delete_block(block.instance_id)
        
        del self._pages[page_id]
        return True
    
    # ============ PERSISTENCE ============
    
    async def _load_from_db(self):
        """Load pages and blocks from database"""
        if not self._db_manager:
            logger.warning("No DB manager, skipping config load")
            return
        
        try:
            # Load from JSON file for now (simpler than new DB tables)
            config_file = self._custom_blocks_path.parent / "logic_config.json"
            logger.info(f"Looking for config file: {config_file}")
            
            if config_file.exists():
                logger.info(f"Config file found, loading...")
                with open(config_file, 'r') as f:
                    data = json.load(f)
                
                logger.info(f"Config data: {len(data.get('pages', []))} pages, {len(data.get('blocks', []))} blocks")
                
                # Restore pages
                for page_data in data.get('pages', []):
                    self._pages[page_data['id']] = page_data
                    logger.info(f"Loaded page: {page_data['id']}")
                
                # Restore blocks
                for block_data in data.get('blocks', []):
                    block_type = block_data['block_type']
                    instance_id = block_data['instance_id']
                    
                    logger.info(f"Loading block: {instance_id} (type: {block_type})")
                    
                    # Check if block type exists
                    if block_type not in ALL_BUILTIN_BLOCKS and block_type not in self._custom_block_classes:
                        logger.warning(f"Block type '{block_type}' not available, preserving config for later. "
                                      f"Available: {list(ALL_BUILTIN_BLOCKS.keys())} + {list(self._custom_block_classes.keys())}")
                        # PRESERVE the raw config so it's not lost on next save_to_db()
                        self._unloaded_block_configs.append(block_data)
                        continue
                    
                    block = self.create_block(
                        block_type,
                        instance_id,
                        block_data.get('page_id'),
                        skip_on_start=True  # Don't call on_start yet!
                    )
                    if block:
                        block._enabled = block_data.get('enabled', True)
                        logger.info(f"Created block: {instance_id}")
                        
                        # Restore input values first (before bindings)
                        saved_values = block_data.get('input_values', {})
                        if saved_values:
                            for key, value in saved_values.items():
                                if key in block.INPUTS:
                                    block._input_values[key] = value
                                    logger.debug(f"Restored input value {key} = {value}")

                        # Restore output values
                        saved_outputs = block_data.get('output_values', {})
                        if saved_outputs:
                            for key, value in saved_outputs.items():
                                if key in block.OUTPUTS:
                                    block._output_values[key] = value

                        # Restore remanent state (before bindings/on_start)
                        if getattr(block, 'REMANENT', False) and 'remanent_state' in block_data:
                            try:
                                block.restore_remanent_state(block_data['remanent_state'])
                                logger.info(f"Restored remanent state for {instance_id}")
                            except Exception as e:
                                logger.warning(f"Error restoring remanent state for {instance_id}: {e}")
                        
                        # Restore bindings
                        for key, binding in block_data.get('input_bindings', {}).items():
                            self.bind_input(block.instance_id, key, binding)
                            logger.debug(f"Bound input {key} -> {binding}")
                        for key, binding in block_data.get('output_bindings', {}).items():
                            self.bind_output(block.instance_id, key, binding)
                            logger.debug(f"Bound output {key} -> {binding}")

                        # NOW call on_start (after remanent + bindings are restored)
                        try:
                            result = block.on_start()
                            if asyncio.iscoroutine(result):
                                asyncio.create_task(result)
                        except Exception as e:
                            logger.error(f"Error in on_start for {instance_id}: {e}")
                    else:
                        logger.error(f"Failed to create block: {instance_id}")
                
                logger.info(f"Loaded {len(self._pages)} pages and {len(self._blocks)} blocks from config")
                
                # Run initial polls for all blocks with poll_data method
                await asyncio.sleep(1)  # Give system time to settle
                for block in self._blocks.values():
                    if hasattr(block, 'poll_data') and block._enabled:
                        try:
                            logger.info(f"Running initial poll for {block.instance_id}")
                            await block.poll_data()
                        except Exception as e:
                            logger.error(f"Error in initial poll for {block.instance_id}: {e}")
            else:
                logger.info(f"No config file found at {config_file}, starting fresh")
                            
        except Exception as e:
            logger.error(f"Error loading logic config: {e}", exc_info=True)
    
    async def save_to_db(self):
        """Save pages and blocks to database (with lock to prevent concurrent writes)"""
        if not hasattr(self, '_save_lock'):
            self._save_lock = asyncio.Lock()
        async with self._save_lock:
            try:
                config_file = self._custom_blocks_path.parent / "logic_config.json"
                config_file.parent.mkdir(parents=True, exist_ok=True)
                
                # Active blocks
                active_blocks = []
                for b in self._blocks.values():
                    block_data = {
                        'instance_id': b.instance_id,
                        'block_type': b.__class__.__name__,
                        'page_id': getattr(b, '_page_id', None),
                        'enabled': b._enabled,
                        'input_bindings': b._input_bindings,
                        'output_bindings': b._output_bindings,
                        'input_values': b._input_values,
                        'output_values': dict(b._output_values),
                    }
                    # Save remanent state if block supports it
                    if getattr(b, 'REMANENT', False):
                        try:
                            rem_state = b.get_remanent_state()
                            if rem_state is not None:
                                block_data['remanent_state'] = rem_state
                        except Exception as e:
                            logger.warning(f"Error getting remanent state for {b.instance_id}: {e}")
                    active_blocks.append(block_data)
                
                # Include unloaded blocks so they aren't lost!
                # Filter out any that were since loaded (by instance_id)
                active_ids = {b.instance_id for b in self._blocks.values()}
                preserved = [cfg for cfg in self._unloaded_block_configs if cfg.get('instance_id') not in active_ids]
                
                if preserved:
                    logger.info(f"Preserving {len(preserved)} unloaded block configs: {[c.get('instance_id') for c in preserved]}")
                
                data = {
                    'pages': list(self._pages.values()),
                    'blocks': active_blocks + preserved,
                }
                
                # Atomic write: write to temp file then rename
                tmp_file = config_file.with_suffix('.json.tmp')
                with open(tmp_file, 'w') as f:
                    json.dump(data, f, indent=2)
                tmp_file.replace(config_file)
                
                logger.info(f"Saved logic config: {len(active_blocks)} active + {len(preserved)} preserved blocks, {len(data['pages'])} pages")
            except Exception as e:
                logger.error(f"Error saving logic config: {e}", exc_info=True)
    
    def get_block_file_code(self, filename: str) -> str:
        """Get source code of a custom block file"""
        file_path = self._custom_blocks_path / filename
        if not file_path.exists():
            raise FileNotFoundError(f"File {filename} not found")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()

    def get_block_source_by_type(self, block_type: str) -> dict:
        """Get source code and file info for a block type (builtin or custom)"""
        import inspect
        # Check custom blocks first
        if block_type in self._custom_block_classes:
            cls = self._custom_block_classes[block_type]
            # Find the source file
            for py_file in self._custom_blocks_path.glob("*.py"):
                try:
                    code = py_file.read_text(encoding='utf-8')
                    if f'class {block_type}' in code:
                        return {'code': code, 'filename': py_file.name, 'editable': True}
                except Exception:
                    pass
        # Check builtins
        if block_type in ALL_BUILTIN_BLOCKS:
            cls = ALL_BUILTIN_BLOCKS[block_type]
            try:
                src_file = Path(inspect.getfile(cls))
                code = src_file.read_text(encoding='utf-8')
                # Also check custom_blocks for an editable copy
                custom_copy = self._custom_blocks_path / src_file.name
                return {
                    'code': code,
                    'filename': src_file.name,
                    'editable': custom_copy.exists(),
                }
            except Exception:
                pass
        raise FileNotFoundError(f"Source for {block_type} not found")
    
    async def update_block_file_code(self, filename: str, code: str) -> dict:
        """Update source code of a custom block file"""
        file_path = self._custom_blocks_path / filename
        if not file_path.exists():
            raise FileNotFoundError(f"File {filename} not found")
        
        # Try to compile the code to check for syntax errors
        try:
            compile(code, filename, 'exec')
        except SyntaxError as e:
            raise ValueError(f"Syntax error in code: {e}")
        
        # Write the code
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code)
        
        # Reload the block
        try:
            await self.upload_block_file(filename, code.encode('utf-8'))
        except Exception as e:
            logger.warning(f"Could not reload block after code update: {e}")
        
        return {"status": "saved", "filename": filename}
    
    async def _autosave_loop(self):
        """Periodically save config (important for remanent blocks)"""
        try:
            while self._running:
                await asyncio.sleep(60)
                if self._running:
                    # Only save if any remanent blocks exist
                    has_remanent = any(getattr(b, 'REMANENT', False) for b in self._blocks.values())
                    if has_remanent:
                        await self.save_to_db()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Autosave error: {e}")

    async def shutdown(self):
        """Shutdown the logic manager"""
        self._running = False
        
        # Cancel autosave
        if hasattr(self, '_autosave_task') and self._autosave_task:
            self._autosave_task.cancel()
        
        # Call on_stop for all blocks
        for block in self._blocks.values():
            try:
                block.on_stop()
            except Exception:
                pass
        
        # Save config (captures final remanent state)
        await self.save_to_db()
        
        logger.info("Logic manager shutdown")


# Singleton instance
logic_manager = LogicManager()
