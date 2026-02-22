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
        
        logger.info(f"Data directory: {data_dir}")
        logger.info(f"Custom blocks path: {self._custom_blocks_path}")
        logger.info(f"Available builtin blocks: {list(ALL_BUILTIN_BLOCKS.keys())}")
        
        # Load custom blocks from disk
        await self._load_custom_blocks()
        
        # Load block instances and pages from database
        await self._load_from_db()
        
        self._running = True
        logger.info(f"Logic manager initialized with {len(self._blocks)} blocks")
    
    async def _load_custom_blocks(self):
        """Load custom block classes from Python files"""
        if not self._custom_blocks_path.exists():
            return
        
        for file in self._custom_blocks_path.glob("*.py"):
            try:
                await self._load_block_file(file)
            except Exception as e:
                logger.error(f"Error loading custom block {file}: {e}")
    
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
        """Upload and register a new custom block file"""
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
                return {"status": "success", "file": safe_name, "blocks": loaded}
            else:
                return {"status": "warning", "file": safe_name, "message": "No LogicBlock classes found"}
        except Exception as e:
            # Remove file if it failed to load
            file_path.unlink(missing_ok=True)
            raise ValueError(f"Invalid block file: {e}")
    
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
                'builtin': True,
                'inputs': cls.INPUTS,
                'outputs': cls.OUTPUTS,
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
                'builtin': False,
                'inputs': getattr(cls, 'INPUTS', {}),
                'outputs': getattr(cls, 'OUTPUTS', {}),
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
    
    def create_block(self, block_type: str, instance_id: str = None, page_id: str = None) -> Optional[LogicBlock]:
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
        
        # Call on_start (handle both sync and async)
        try:
            result = block.on_start()
            # If it's a coroutine, schedule it
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
    
    async def on_address_changed(self, address: str, value: Any):
        """Called when a KNX or internal address value changes"""
        if not self._running:
            return
        
        bindings = self._address_to_blocks.get(address, [])
        for instance_id, input_key in bindings:
            block = self._blocks.get(instance_id)
            if block and block._enabled:
                block.set_input(input_key, value)
    
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
        """Write output value to address and route to bound inputs"""
        try:
            if self._db_manager:
                # Check if internal address
                addr_obj = await self._db_manager.get_group_address(address)
                if addr_obj and addr_obj.is_internal:
                    # Update DB
                    await self._db_manager.update_group_address_value(address, str(value))
                    # Route to all blocks with inputs bound to this address
                    self._route_value_to_inputs(address, value)
                elif self._knx_manager:
                    # Send to KNX bus
                    await self._knx_manager.send_telegram(address, value)
        except Exception as e:
            logger.error(f"Error writing output to {address}: {e}")
    
    def _route_value_to_inputs(self, address: str, value: Any):
        """Route a value from an address to all blocks with inputs bound to it"""
        for block in self._blocks.values():
            for input_key, bound_addr in block._input_bindings.items():
                if bound_addr == address:
                    logger.debug(f"Routing {address}={value} to {block.instance_id}.{input_key}")
                    old_value = block._input_values.get(input_key)
                    block._input_values[input_key] = value
                    
                    # Trigger input change handler
                    if hasattr(block, 'on_input_change') and old_value != value:
                        try:
                            block.on_input_change(input_key, value, old_value)
                        except Exception as e:
                            logger.error(f"Error in on_input_change for {block.instance_id}: {e}")
    
    # ============ PAGES ============
    
    def create_page(self, page_id: str, name: str, description: str = "") -> Dict:
        """Create a new logic page"""
        if page_id in self._pages:
            raise ValueError(f"Page {page_id} already exists")
        
        self._pages[page_id] = {
            'id': page_id,
            'name': name,
            'description': description,
            'blocks': [],
            'created_at': datetime.now().isoformat()
        }
        return self._pages[page_id]
    
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
                        logger.error(f"Unknown block type: {block_type}. Available: {list(ALL_BUILTIN_BLOCKS.keys())} + {list(self._custom_block_classes.keys())}")
                        continue
                    
                    block = self.create_block(
                        block_type,
                        instance_id,
                        block_data.get('page_id')
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
                        
                        # Restore bindings
                        for key, binding in block_data.get('input_bindings', {}).items():
                            self.bind_input(block.instance_id, key, binding)
                            logger.debug(f"Bound input {key} -> {binding}")
                        for key, binding in block_data.get('output_bindings', {}).items():
                            self.bind_output(block.instance_id, key, binding)
                            logger.debug(f"Bound output {key} -> {binding}")
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
        """Save pages and blocks to database"""
        try:
            config_file = self._custom_blocks_path.parent / "logic_config.json"
            
            # Ensure parent directory exists
            config_file.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'pages': list(self._pages.values()),
                'blocks': [
                    {
                        'instance_id': b.instance_id,
                        'block_type': b.__class__.__name__,
                        'page_id': getattr(b, '_page_id', None),
                        'enabled': b._enabled,
                        'input_bindings': b._input_bindings,
                        'output_bindings': b._output_bindings,
                        'input_values': b._input_values,  # Save input values!
                    }
                    for b in self._blocks.values()
                ]
            }
            
            logger.info(f"Saving config to {config_file}: {len(data['pages'])} pages, {len(data['blocks'])} blocks")
            
            with open(config_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Saved logic config successfully")
        except Exception as e:
            logger.error(f"Error saving logic config: {e}", exc_info=True)
    
    def get_block_file_code(self, filename: str) -> str:
        """Get source code of a custom block file"""
        file_path = self._custom_blocks_path / filename
        if not file_path.exists():
            raise FileNotFoundError(f"File {filename} not found")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    
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
    
    async def shutdown(self):
        """Shutdown the logic manager"""
        self._running = False
        
        # Call on_stop for all blocks
        for block in self._blocks.values():
            try:
                block.on_stop()
            except:
                pass
        
        # Save config
        await self.save_to_db()
        
        logger.info("Logic manager shutdown")


# Singleton instance
logic_manager = LogicManager()
