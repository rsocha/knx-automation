from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect, Query, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from models import GroupAddressCreate, GroupAddressUpdate, GroupAddressResponse
from knx import knx_manager
from utils import db_manager
from logic import logic_manager
from logic.manager import ALL_BUILTIN_BLOCKS

logger = logging.getLogger(__name__)

# Single source of truth for version — update HERE only
APP_VERSION = "3.6.3"
router = APIRouter()

# ============ Global WebSocket broadcast for telegram log ============
_ws_telegram_clients: list = []  # Active WebSocket connections for /ws/telegrams

async def _broadcast_telegram(data: dict):
    """Broadcast a telegram/IKO event to all connected WebSocket clients"""
    dead = []
    for ws in _ws_telegram_clients:
        try:
            await ws.send_json(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_telegram_clients.remove(ws)



# ============ LOGIC MODELS ============

class BlockCreate(BaseModel):
    block_type: str
    page_id: Optional[str] = None

class BindingCreate(BaseModel):
    input_key: Optional[str] = None
    output_key: Optional[str] = None
    address: str = ""

class PageCreate(BaseModel):
    name: str
    page_id: Optional[str] = None
    description: Optional[str] = None
    room: Optional[str] = None

class PageUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    room: Optional[str] = None

@router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat(), "version": APP_VERSION}

@router.post("/system/fix-permissions")
async def fix_permissions():
    """Fix file permissions for data directory"""
    import os
    import subprocess
    
    data_dir = Path("data")
    fixed = []
    errors = []
    
    try:
        # Fix data directory
        data_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(str(data_dir), 0o755)
        fixed.append("data/")
        
        # Fix all JSON files
        for f in data_dir.glob("*.json"):
            try:
                os.chmod(str(f), 0o666)
                fixed.append(str(f.name))
            except Exception as e:
                errors.append(f"{f.name}: {e}")
        
        # Fix database
        db_file = data_dir / "knx.db"
        if db_file.exists():
            try:
                os.chmod(str(db_file), 0o666)
                fixed.append("knx.db")
            except Exception as e:
                errors.append(f"knx.db: {e}")
        
        # Fix custom_blocks
        custom_dir = data_dir / "custom_blocks"
        if custom_dir.exists():
            try:
                os.chmod(str(custom_dir), 0o755)
                for f in custom_dir.glob("*.py"):
                    os.chmod(str(f), 0o666)
                fixed.append("custom_blocks/")
            except Exception as e:
                errors.append(f"custom_blocks: {e}")
        
        return {
            "status": "success" if not errors else "partial",
            "fixed": fixed,
            "errors": errors
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============ LICENSE SYSTEM ============
LICENSE_FILE = Path("data/license.json")
# Secret for license validation (change this for your deployment!)
LICENSE_SECRET = "KNX-AUTO-2024-SECRET"

def generate_license_key(email: str, valid_days: int = 365) -> dict:
    """Generate a license key for an email"""
    import hashlib
    import base64
    
    created = datetime.now().isoformat()
    expires = (datetime.now() + timedelta(days=valid_days)).isoformat()
    
    # Create signature
    data = f"{email}:{created}:{expires}:{LICENSE_SECRET}"
    signature = hashlib.sha256(data.encode()).hexdigest()[:16].upper()
    
    # Format: KNX-XXXX-XXXX-XXXX
    key = f"KNX-{signature[:4]}-{signature[4:8]}-{signature[8:12]}"
    
    return {
        "key": key,
        "email": email,
        "created": created,
        "expires": expires,
        "signature": signature
    }

def validate_license_key(key: str, email: str) -> tuple[bool, str]:
    """Validate a license key"""
    import hashlib
    
    if not key or not email:
        return False, "Lizenzschlüssel und E-Mail erforderlich"
    
    # Check format
    if not key.startswith("KNX-") or len(key) != 17:
        return False, "Ungültiges Schlüsselformat"
    
    # Load stored license
    try:
        if LICENSE_FILE.exists():
            with open(LICENSE_FILE, 'r') as f:
                stored = json.load(f)
                
            if stored.get("key") == key and stored.get("email") == email:
                # Check expiry
                expires = datetime.fromisoformat(stored["expires"])
                if datetime.now() > expires:
                    return False, "Lizenz abgelaufen"
                return True, "Lizenz gültig"
    except Exception as e:
        logger.error(f"License validation error: {e}")
    
    return False, "Lizenzschlüssel nicht gefunden oder ungültig"

@router.get("/license/status")
async def get_license_status():
    """Get current license status"""
    try:
        if LICENSE_FILE.exists():
            with open(LICENSE_FILE, 'r') as f:
                stored = json.load(f)
            
            expires = datetime.fromisoformat(stored["expires"])
            is_valid = datetime.now() < expires
            days_left = (expires - datetime.now()).days if is_valid else 0
            
            return {
                "licensed": is_valid,
                "email": stored.get("email", ""),
                "expires": stored.get("expires"),
                "days_left": days_left,
                "key_preview": stored.get("key", "")[:8] + "..." if stored.get("key") else None
            }
        return {"licensed": False, "email": None, "expires": None, "days_left": 0}
    except Exception as e:
        logger.error(f"License status error: {e}")
        return {"licensed": False, "error": str(e)}

@router.post("/license/activate")
async def activate_license(key: str = Query(...), email: str = Query(...)):
    """Activate a license key"""
    try:
        import hashlib
        
        # Validate key format
        if not key.startswith("KNX-") or len(key) != 17:
            raise HTTPException(status_code=400, detail="Ungültiges Schlüsselformat (KNX-XXXX-XXXX-XXXX)")
        
        # Extract signature from key
        key_sig = key.replace("KNX-", "").replace("-", "").upper()
        
        # Try to validate with different expiry dates (allow keys created for this email)
        valid = False
        for days_offset in range(0, 400):  # Check last 400 days of possible creation dates
            for validity in [365, 730, 1095]:  # 1, 2, 3 year licenses
                test_date = datetime.now() - timedelta(days=days_offset)
                test_expires = test_date + timedelta(days=validity)
                
                data = f"{email}:{test_date.isoformat()}:{test_expires.isoformat()}:{LICENSE_SECRET}"
                expected_sig = hashlib.sha256(data.encode()).hexdigest()[:12].upper()
                
                if key_sig == expected_sig:
                    valid = True
                    # Save license
                    LICENSE_FILE.parent.mkdir(parents=True, exist_ok=True)
                    license_data = {
                        "key": key,
                        "email": email,
                        "created": test_date.isoformat(),
                        "expires": test_expires.isoformat(),
                        "activated": datetime.now().isoformat()
                    }
                    with open(LICENSE_FILE, 'w') as f:
                        json.dump(license_data, f, indent=2)
                    
                    days_left = (test_expires - datetime.now()).days
                    logger.info(f"License activated for {email}, expires in {days_left} days")
                    return {
                        "status": "activated",
                        "email": email,
                        "expires": test_expires.isoformat(),
                        "days_left": days_left
                    }
        
        if not valid:
            raise HTTPException(status_code=400, detail="Lizenzschlüssel ungültig für diese E-Mail-Adresse")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"License activation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/license/generate")
async def generate_license(email: str = Query(...), days: int = Query(default=365)):
    """Generate a new license key (admin only - protect this endpoint!)"""
    try:
        license_data = generate_license_key(email, days)
        logger.info(f"Generated license for {email}: {license_data['key']}")
        return license_data
    except Exception as e:
        logger.error(f"License generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============ VISU CONFIG ============
VISU_CONFIG_FILE = Path("data/visu_config.json")
VISU_ROOMS_FILE = Path("data/visu_rooms.json")
VSE_DIR = Path("data/vse")

def ensure_data_writable():
    """Ensure data directory and files are writable"""
    data_dir = Path("data")
    data_dir.mkdir(parents=True, exist_ok=True)
    try:
        import os
        os.chmod(str(data_dir), 0o755)
        for f in data_dir.glob("*.json"):
            os.chmod(str(f), 0o666)
        db_file = data_dir / "knx.db"
        if db_file.exists():
            os.chmod(str(db_file), 0o666)
    except Exception as e:
        logger.warning(f"Could not set permissions: {e}")

@router.get("/visu/rooms")
async def get_visu_rooms():
    """Get visualization rooms with widgets - auto-saved on server"""
    try:
        ensure_data_writable()
        if VISU_ROOMS_FILE.exists():
            with open(VISU_ROOMS_FILE, 'r', encoding='utf-8') as f:
                rooms = json.load(f)
                logger.info(f"Loaded {len(rooms)} visu rooms from server")
                return rooms
        return []
    except Exception as e:
        logger.error(f"Error loading visu rooms: {e}")
        return []

@router.post("/visu/rooms")
async def save_visu_rooms(rooms: list = Body(...)):
    """Save visualization rooms with widgets - with backup"""
    try:
        ensure_data_writable()
        VISU_ROOMS_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Create backup before saving
        if VISU_ROOMS_FILE.exists():
            backup_file = VISU_ROOMS_FILE.with_suffix('.json.bak')
            try:
                import shutil
                shutil.copy(VISU_ROOMS_FILE, backup_file)
                logger.info(f"Created backup: {backup_file}")
            except Exception as e:
                logger.warning(f"Backup failed: {e}")
        
        # Save new data
        with open(VISU_ROOMS_FILE, 'w', encoding='utf-8') as f:
            json.dump(rooms, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved {len(rooms)} visu rooms to server")
        return {"status": "saved", "count": len(rooms)}
    except PermissionError as e:
        logger.error(f"Permission error saving visu rooms: {e}")
        raise HTTPException(status_code=500, detail=f"Keine Schreibrechte: {e}. Bitte 'chmod 666 /opt/knx-automation/data/visu_rooms.json' ausführen.")
    except Exception as e:
        logger.error(f"Error saving visu rooms: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/visu/rooms/restore-backup")
async def restore_visu_backup():
    """Restore visu rooms from backup"""
    backup_file = VISU_ROOMS_FILE.with_suffix('.json.bak')
    if not backup_file.exists():
        raise HTTPException(status_code=404, detail="Kein Backup vorhanden")
    try:
        import shutil
        shutil.copy(backup_file, VISU_ROOMS_FILE)
        logger.info("Restored visu rooms from backup")
        return {"status": "restored"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/visu/export")
async def export_visu_config():
    """Export complete visu configuration as downloadable JSON"""
    try:
        export_data = {
            "version": APP_VERSION,
            "exported_at": datetime.now().isoformat(),
            "rooms": [],
            "config": {}
        }
        
        if VISU_ROOMS_FILE.exists():
            with open(VISU_ROOMS_FILE, 'r', encoding='utf-8') as f:
                export_data["rooms"] = json.load(f)
        
        if VISU_CONFIG_FILE.exists():
            with open(VISU_CONFIG_FILE, 'r', encoding='utf-8') as f:
                export_data["config"] = json.load(f)
        
        return StreamingResponse(
            iter([json.dumps(export_data, ensure_ascii=False, indent=2)]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=visu-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"}
        )
    except Exception as e:
        logger.error(f"Error exporting visu: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/visu/import")
async def import_visu_config(file: UploadFile = File(...)):
    """Import visu configuration from JSON file"""
    try:
        content = await file.read()
        data = json.loads(content.decode('utf-8'))
        
        VISU_ROOMS_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Import rooms
        if "rooms" in data:
            with open(VISU_ROOMS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data["rooms"], f, ensure_ascii=False, indent=2)
        
        # Import config
        if "config" in data:
            with open(VISU_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data["config"], f, ensure_ascii=False, indent=2)
        
        room_count = len(data.get("rooms", []))
        logger.info(f"Imported visu config with {room_count} rooms")
        return {"status": "imported", "rooms": room_count}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Ungültige JSON-Datei")
    except Exception as e:
        logger.error(f"Error importing visu: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============ VSE TEMPLATE MANAGEMENT ============
VSE_DIR = Path("static/vse")

@router.get("/vse/templates")
async def list_vse_templates():
    """List all available VSE templates"""
    try:
        templates = []
        if VSE_DIR.exists():
            for f in VSE_DIR.glob("*.vse.json"):
                try:
                    with open(f, 'r', encoding='utf-8') as file:
                        data = json.load(file)
                        templates.append({
                            "id": data.get("id", f.stem),
                            "name": data.get("name", f.stem),
                            "description": data.get("description", ""),
                            "category": data.get("category", ""),
                            "filename": f.name
                        })
                except Exception:
                    pass
            # Also check for .json files that aren't .vse.json
            for f in VSE_DIR.glob("*.json"):
                if not f.name.endswith('.vse.json'):
                    try:
                        with open(f, 'r', encoding='utf-8') as file:
                            data = json.load(file)
                            if "render" in data:  # It's a VSE template
                                templates.append({
                                    "id": data.get("id", f.stem),
                                    "name": data.get("name", f.stem),
                                    "description": data.get("description", ""),
                                    "category": data.get("category", ""),
                                    "filename": f.name
                                })
                    except Exception:
                        pass
        return {"templates": templates}
    except Exception as e:
        logger.error(f"Error listing VSE templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/vse/upload")
async def upload_vse_template(file: UploadFile = File(...)):
    """Upload a VSE template"""
    try:
        content = await file.read()
        data = json.loads(content.decode('utf-8'))
        
        # Validate template structure
        if "render" not in data:
            raise HTTPException(status_code=400, detail="Ungültiges Template: 'render' fehlt")
        if "id" not in data:
            raise HTTPException(status_code=400, detail="Ungültiges Template: 'id' fehlt")
        
        VSE_DIR.mkdir(parents=True, exist_ok=True)
        
        # Save with .vse.json extension
        filename = f"{data['id']}.vse.json"
        filepath = VSE_DIR / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Uploaded VSE template: {filename}")
        return {"status": "uploaded", "name": data.get("name", data["id"]), "filename": filename}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Ungültige JSON-Datei")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading VSE template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/vse/download")
async def download_vse_templates():
    """Download all VSE templates as ZIP"""
    import io
    import zipfile
    
    try:
        if not VSE_DIR.exists():
            raise HTTPException(status_code=404, detail="Keine Templates gefunden")
        
        # Create ZIP in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for f in VSE_DIR.glob("*.json"):
                zf.write(f, f.name)
        
        zip_buffer.seek(0)
        
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=vse-templates-{datetime.now().strftime('%Y%m%d')}.zip"}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading VSE templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/vse/{template_id}")
async def delete_vse_template(template_id: str):
    """Delete a VSE template"""
    try:
        filepath = VSE_DIR / f"{template_id}.vse.json"
        if not filepath.exists():
            filepath = VSE_DIR / f"{template_id}.json"
        
        if not filepath.exists():
            raise HTTPException(status_code=404, detail="Template nicht gefunden")
        
        filepath.unlink()
        logger.info(f"Deleted VSE template: {template_id}")
        return {"status": "deleted", "id": template_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting VSE template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/visu/config")
async def get_visu_config():
    """Get visualization configuration"""
    try:
        VISU_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        if VISU_CONFIG_FILE.exists():
            with open(VISU_CONFIG_FILE, 'r') as f:
                return json.load(f)
        return {"default": {"id": "default", "name": "Standard", "size": "full", "bgColor": "#1a1a2e", "widgets": []}}
    except Exception as e:
        logger.error(f"Error loading visu config: {e}")
        return {"default": {"id": "default", "name": "Standard", "size": "full", "bgColor": "#1a1a2e", "widgets": []}}

@router.post("/visu/config")
async def save_visu_config(config: dict):
    """Save visualization configuration"""
    try:
        VISU_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(VISU_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return {"status": "saved"}
    except Exception as e:
        logger.error(f"Error saving visu config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============ VSE (Visual Elements) ============
@router.get("/visu/vse")
async def list_vse_elements():
    """List all available VSE elements (PHP and JSON)"""
    try:
        VSE_DIR.mkdir(parents=True, exist_ok=True)
        elements = []
        
        # Load PHP VSE files
        for filepath in VSE_DIR.glob('*_vse.php'):
            try:
                with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                
                import re
                def_match = re.search(r'###\[DEF\]###(.*?)###\[/DEF\]###', content, re.DOTALL)
                if def_match:
                    def_content = def_match.group(1)
                    name = 'Unknown'
                    xsize = 100
                    ysize = 50
                    text = ''
                    category = 'other'
                    
                    for line in def_content.split('\n'):
                        if '[name' in line:
                            name = line.split('=')[1].strip().rstrip(']')
                        elif '[xsize' in line:
                            xsize = int(line.split('=')[1].strip().rstrip(']'))
                        elif '[ysize' in line:
                            ysize = int(line.split('=')[1].strip().rstrip(']'))
                        elif '[text' in line and 'flagText' not in line:
                            text = line.split('=')[1].strip().rstrip(']')
                    
                    # Detect category from name
                    name_lower = name.lower()
                    if 'sensor' in name_lower or 'temp' in name_lower:
                        category = 'sensor'
                    elif 'switch' in name_lower or 'taster' in name_lower:
                        category = 'switch'
                    elif 'slider' in name_lower or 'dimm' in name_lower:
                        category = 'slider'
                    elif 'gauge' in name_lower or 'meter' in name_lower:
                        category = 'gauge'
                    
                    elements.append({
                        'id': filepath.stem.split('_')[0],
                        'filename': filepath.name,
                        'name': name,
                        'xsize': xsize,
                        'ysize': ysize,
                        'text': text,
                        'category': category,
                        'format': 'php',
                        'converted': False
                    })
            except Exception as e:
                logger.error(f"Error parsing VSE {filepath}: {e}")
        
        # Load JSON VSE files
        for filepath in VSE_DIR.glob('*.vse.json'):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    data['filename'] = filepath.name
                    data['format'] = 'json'
                    data['converted'] = True
                    elements.append(data)
            except Exception as e:
                logger.error(f"Error loading JSON VSE {filepath}: {e}")
        
        return sorted(elements, key=lambda x: x.get('id', ''))
    except Exception as e:
        logger.error(f"Error listing VSE: {e}")
        return []

@router.post("/visu/vse")
async def save_vse_element(vse: dict = Body(...)):
    """Create or update a VSE element in JSON format"""
    try:
        vse_id = vse.get('id')
        if not vse_id:
            raise HTTPException(status_code=400, detail="ID ist erforderlich")
        
        VSE_DIR.mkdir(parents=True, exist_ok=True)
        
        # Save as JSON
        filepath = VSE_DIR / f"{vse_id}.vse.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(vse, f, ensure_ascii=False, indent=2)
        
        return {"status": "saved", "id": vse_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving VSE: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/visu/vse/{element_id}/convert")
async def convert_vse_to_json(element_id: str):
    """Convert a PHP VSE to JSON format"""
    try:
        import re
        
        # Find PHP file
        php_files = list(VSE_DIR.glob(f'{element_id}_vse.php'))
        if not php_files:
            raise HTTPException(status_code=404, detail="PHP VSE nicht gefunden")
        
        filepath = php_files[0]
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        
        # Parse PHP to JSON
        result = {
            'id': element_id,
            'name': 'Unknown',
            'category': 'other',
            'xsize': 100,
            'ysize': 60,
            'vars': {},
            'html': '',
            'css': '',
            'format': 'json',
            'converted': True
        }
        
        # Parse DEF section
        def_match = re.search(r'###\[DEF\]###(.*?)###\[/DEF\]###', content, re.DOTALL)
        if def_match:
            def_content = def_match.group(1)
            for line in def_content.split('\n'):
                line = line.strip()
                if not line or not line.startswith('['):
                    continue
                match = re.match(r'\[(\w+)\s*=\s*(.+)\]', line)
                if match:
                    key, value = match.groups()
                    if key == 'name':
                        result['name'] = value
                    elif key == 'xsize':
                        result['xsize'] = int(value)
                    elif key == 'ysize':
                        result['ysize'] = int(value)
                    elif key.startswith('var'):
                        # Parse variable definition
                        result['vars'][key] = {'name': key, 'default': value}
        
        # Try to extract HTML/rendering part
        visu_match = re.search(r'###\[VISU\]###(.*?)###\[/VISU\]###', content, re.DOTALL)
        if visu_match:
            visu_content = visu_match.group(1)
            # Extract HTML-like parts (simplified)
            result['html'] = f'<!-- Converted from PHP -->\n<div class="vse-{element_id}">\n  {result["name"]}\n  <span class="value">{{{{value}}}}</span>\n</div>'
            result['css'] = f'.vse-{element_id} {{ padding: 10px; background: #1a1a2e; border-radius: 8px; }}\n.vse-{element_id} .value {{ font-size: 20px; font-weight: bold; color: #58a6ff; }}'
        
        # Save JSON
        json_path = VSE_DIR / f"{element_id}.vse.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        return {"status": "converted", "id": element_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error converting VSE {element_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/visu/vse/{element_id}")
async def get_vse_element(element_id: str):
    """Get a specific VSE element with full details"""
    try:
        import re
        for filepath in VSE_DIR.glob(f'{element_id}_vse.php'):
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            result = {
                'id': element_id,
                'filename': filepath.name,
                'def': {},
                'properties': [],
                'editor_js': '',
                'visu_js': '',
                'shared_js': '',
                'help': ''
            }
            
            # Parse DEF
            def_match = re.search(r'###\[DEF\]###(.*?)###\[/DEF\]###', content, re.DOTALL)
            if def_match:
                def_content = def_match.group(1)
                result['def']['vars'] = {}
                for line in def_content.split('\n'):
                    line = line.strip()
                    if not line or not line.startswith('['):
                        continue
                    match = re.match(r'\[(\w+)\s*=\s*(.+)\]', line)
                    if match:
                        key, value = match.group(1), match.group(2).strip()
                        if key == 'name':
                            result['def']['name'] = value
                        elif key == 'xsize':
                            result['def']['xsize'] = int(value)
                        elif key == 'ysize':
                            result['def']['ysize'] = int(value)
                        elif key == 'text':
                            result['def']['text'] = value
                        elif key.startswith('var'):
                            result['def']['vars'][key] = value
                        elif key.startswith('flag'):
                            result['def'][key] = value == '1'
                        elif key.startswith('caption'):
                            result['def'][key] = value
            
            # Parse PROPERTIES
            props_match = re.search(r'###\[PROPERTIES\]###(.*?)###\[/PROPERTIES\]###', content, re.DOTALL)
            if props_match:
                props_content = props_match.group(1)
                current_row = ''
                for line in props_content.split('\n'):
                    line = line.strip()
                    if line.startswith('[row'):
                        row_match = re.match(r'\[row(?:=(.+))?\]', line)
                        current_row = row_match.group(1) if row_match and row_match.group(1) else ''
                    elif line.startswith('[var'):
                        var_match = re.match(r'\[(var\d+)\s*=\s*(.+)\]', line)
                        if var_match:
                            var_name = var_match.group(1)
                            var_def = var_match.group(2)
                            # Simple parse: type,span,'label','default'
                            parts = re.findall(r"'[^']*'|[^,]+", var_def)
                            parts = [p.strip().strip("'") for p in parts]
                            if len(parts) >= 4:
                                result['properties'].append({
                                    'var': var_name,
                                    'type': parts[0],
                                    'span': int(parts[1]) if parts[1].isdigit() else 1,
                                    'label': parts[2],
                                    'default': parts[3],
                                    'row': current_row
                                })
            
            # Parse JS sections
            for section, key in [('EDITOR.JS', 'editor_js'), ('VISU.JS', 'visu_js'), ('SHARED.JS', 'shared_js'), ('HELP', 'help')]:
                match = re.search(rf'###\[{section}\]###(.*?)###\[/{section}\]###', content, re.DOTALL)
                if match:
                    result[key] = match.group(1).strip()
            
            return result
        
        raise HTTPException(status_code=404, detail="VSE element not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting VSE {element_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/visu/vse/upload")
async def upload_vse(file: UploadFile = File(...)):
    """Upload a VSE file (PHP, JSON, or YAML)"""
    try:
        import re
        
        filename = file.filename
        ext = filename.split('.')[-1].lower()
        
        VSE_DIR.mkdir(parents=True, exist_ok=True)
        content = await file.read()
        
        if ext == 'php':
            # Save PHP file
            filepath = VSE_DIR / filename
            with open(filepath, 'wb') as f:
                f.write(content)
            
            # Auto-convert to JSON
            try:
                content_str = content.decode('utf-8', errors='replace')
                element_id = filename.split('_')[0]
                
                result = {
                    'id': element_id,
                    'name': 'Unknown',
                    'category': 'other',
                    'xsize': 100,
                    'ysize': 60,
                    'vars': {},
                    'html': '',
                    'css': '',
                    'format': 'json',
                    'converted': True
                }
                
                def_match = re.search(r'###\[DEF\]###(.*?)###\[/DEF\]###', content_str, re.DOTALL)
                if def_match:
                    for line in def_match.group(1).split('\n'):
                        line = line.strip()
                        if not line.startswith('['):
                            continue
                        match = re.match(r'\[(\w+)\s*=\s*(.+)\]', line)
                        if match:
                            key, value = match.groups()
                            if key == 'name':
                                result['name'] = value
                            elif key == 'xsize':
                                result['xsize'] = int(value)
                            elif key == 'ysize':
                                result['ysize'] = int(value)
                            elif key.startswith('var'):
                                result['vars'][key] = {'name': key, 'default': value}
                
                # Basic HTML template
                result['html'] = f'<div class="vse-{element_id}">\n  <span class="label">{result["name"]}</span>\n  <span class="value">{{{{value}}}}</span>\n</div>'
                result['css'] = f'.vse-{element_id} {{ padding: 12px; background: #1a1a2e; border-radius: 8px; }}\n.vse-{element_id} .value {{ font-size: 20px; font-weight: bold; color: #58a6ff; }}'
                
                json_path = VSE_DIR / f"{element_id}.vse.json"
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                
                return {"status": "uploaded", "message": f"PHP hochgeladen und nach JSON konvertiert", "filename": filename}
            except Exception as e:
                logger.warning(f"Auto-convert failed: {e}")
                return {"status": "uploaded", "message": "PHP hochgeladen (Konvertierung später möglich)", "filename": filename}
        
        elif ext == 'json':
            # Validate and save JSON
            try:
                data = json.loads(content.decode('utf-8'))
                vse_id = data.get('id') or filename.replace('.vse.json', '').replace('.json', '')
                data['id'] = vse_id
                data['format'] = 'json'
                data['converted'] = True
                
                filepath = VSE_DIR / f"{vse_id}.vse.json"
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                return {"status": "uploaded", "message": "JSON VSE gespeichert", "filename": filepath.name}
            except json.JSONDecodeError as e:
                raise HTTPException(status_code=400, detail=f"Ungültiges JSON: {e}")
        
        elif ext in ['yaml', 'yml']:
            # Convert YAML to JSON
            try:
                import yaml
            except ImportError:
                raise HTTPException(status_code=400, detail="YAML support nicht installiert. Bitte PyYAML installieren: pip install pyyaml")
            try:
                data = yaml.safe_load(content.decode('utf-8'))
                vse_id = data.get('id') or filename.replace('.vse.yaml', '').replace('.vse.yml', '').replace('.yaml', '').replace('.yml', '')
                data['id'] = vse_id
                data['format'] = 'json'
                data['converted'] = True
                
                filepath = VSE_DIR / f"{vse_id}.vse.json"
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                return {"status": "uploaded", "message": "YAML konvertiert und gespeichert", "filename": filepath.name}
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"YAML Fehler: {e}")
        
        else:
            raise HTTPException(status_code=400, detail="Unterstützte Formate: .php, .json, .yaml, .yml")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading VSE: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/visu/vse/{filename}")
async def delete_vse(filename: str):
    """Delete a VSE file (tries both PHP and JSON)"""
    try:
        deleted = False
        
        # Try exact filename
        filepath = VSE_DIR / filename
        if filepath.exists():
            filepath.unlink()
            deleted = True
        
        # Try JSON version
        if not filename.endswith('.json'):
            json_path = VSE_DIR / f"{filename.split('_')[0]}.vse.json"
            if json_path.exists():
                json_path.unlink()
                deleted = True
        
        # Try PHP version
        if not filename.endswith('.php'):
            php_paths = list(VSE_DIR.glob(f"{filename}*_vse.php"))
            for p in php_paths:
                p.unlink()
                deleted = True
        
        if deleted:
            return {"status": "deleted"}
        raise HTTPException(status_code=404, detail="VSE not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting VSE: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/routes")
async def list_routes():
    """List all available routes for debugging"""
    routes = []
    for route in router.routes:
        if hasattr(route, 'methods') and hasattr(route, 'path'):
            routes.append({"path": route.path, "methods": list(route.methods)})
    return {"routes": routes}

@router.get("/status")
async def get_status():
    try:
        return {
            "knx_connected": knx_manager.is_connected,
            "gateway_ip": knx_manager._gateway_ip,
            "connection_type": knx_manager._connection_type,
            "group_address_count": await db_manager.get_group_address_count(),
            "timestamp": datetime.now().isoformat(),
            "version": APP_VERSION
        }
    except Exception as e:
        logger.error(f"Status error: {e}")
        return {"knx_connected": False, "error": str(e)}

@router.get("/group-addresses", response_model=List[GroupAddressResponse])
async def get_group_addresses(room: Optional[str] = None, function: Optional[str] = None, internal: Optional[bool] = None):
    try:
        return await db_manager.get_all_group_addresses(room, function, internal_only=internal)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/internal-addresses", response_model=List[GroupAddressResponse])
async def get_internal_addresses():
    """Get only internal addresses (not on KNX bus)"""
    try:
        return await db_manager.get_all_group_addresses(internal_only=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/group-addresses/{address}", response_model=GroupAddressResponse)
async def get_group_address(address: str):
    result = await db_manager.get_group_address(address)
    if not result:
        raise HTTPException(status_code=404, detail="Not found")
    return result

@router.post("/group-addresses", response_model=GroupAddressResponse)
async def create_group_address(address: GroupAddressCreate):
    try:
        return await db_manager.create_group_address(address)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/group-addresses/ensure")
async def ensure_group_address(address: GroupAddressCreate):
    """Create IKO/address if it doesn't exist, return existing if it does. Idempotent."""
    existing = await db_manager.get_group_address(address.address)
    if existing:
        return {"address": existing.address, "name": existing.name, "created": False, "status": "exists"}
    try:
        created = await db_manager.create_group_address(address)
        return {"address": created.address, "name": created.name, "created": True, "status": "created"}
    except ValueError:
        # Race condition — someone else created it
        existing = await db_manager.get_group_address(address.address)
        return {"address": existing.address if existing else address.address, "created": False, "status": "exists"}

@router.put("/group-addresses/{address:path}")
async def update_group_address(address: str, data: GroupAddressCreate):
    """Update an existing group address"""
    from urllib.parse import unquote
    address = unquote(address)
    logger.info(f"UPDATE address: {address} -> {data}")
    
    # Get existing address
    existing = await db_manager.get_group_address(address)
    if not existing:
        raise HTTPException(status_code=404, detail="Address not found")
    
    # Update fields
    try:
        updated = await db_manager.update_group_address(address, data)
        if updated:
            return updated
        raise HTTPException(status_code=500, detail="Update failed")
    except Exception as e:
        logger.error(f"Update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/group-addresses/{address:path}")
async def delete_group_address(address: str):
    """Delete a group address (supports internal IKO: addresses)
    
    Also removes any bindings to this address in logic blocks.
    """
    from urllib.parse import unquote
    address = unquote(address)
    logger.info(f"DELETE address: {address}")
    
    # First, unbind from any logic blocks
    removed_bindings = logic_manager.unbind_address(address)
    if removed_bindings > 0:
        logger.info(f"Removed {removed_bindings} binding(s) for deleted address {address}")
    
    # Then delete the address
    if await db_manager.delete_group_address(address):
        return {"status": "deleted", "bindings_removed": removed_bindings}
    raise HTTPException(status_code=404, detail="Not found")

async def _import_csv_content(content: bytes) -> dict:
    """Helper to import CSV content"""
    try:
        text = content.decode('utf-8')
    except Exception:
        text = content.decode('latin-1')
    
    lines = text.strip().split('\n')
    
    created = 0
    updated = 0
    errors = 0
    
    # Skip header
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        
        # Handle quoted CSV
        if '"' in line:
            import csv
            import io
            reader = csv.reader(io.StringIO(line))
            parts = list(reader)[0]
        else:
            parts = line.split(',')
        
        if len(parts) >= 2:
            try:
                ga_data = GroupAddressCreate(
                    address=parts[0].strip().strip('"'),
                    name=parts[1].strip().strip('"'),
                    dpt=parts[2].strip().strip('"') if len(parts) > 2 and parts[2].strip() else None,
                    room=parts[3].strip().strip('"') if len(parts) > 3 and parts[3].strip() else None,
                    function=parts[4].strip().strip('"') if len(parts) > 4 and parts[4].strip() else None
                )
                _, was_created = await db_manager.upsert_group_address(ga_data)
                if was_created:
                    created += 1
                else:
                    updated += 1
            except Exception as e:
                logger.warning(f"CSV import line error: {e}")
                errors += 1
    
    return {
        "status": "success",
        "message": f"CSV Import: {created} neu, {updated} aktualisiert",
        "created": created,
        "updated": updated,
        "errors": errors,
        "total_found": created + updated + errors
    }

@router.post("/import/esf")
async def import_esf(file: UploadFile = File(...), password: Optional[str] = None):
    """Import group addresses from ESF, knxproj or CSV file"""
    import tempfile
    import os
    
    try:
        filename = getattr(file, 'filename', 'upload.esf') or 'upload.esf'
        logger.info(f"")
        logger.info(f"========== IMPORT START ==========")
        logger.info(f"File: {filename}")
        logger.info(f"Password received: {repr(password)}")
        logger.info(f"Password length: {len(password) if password else 0}")
        
        # Check file type
        lower_name = filename.lower()
        if not lower_name.endswith(('.esf', '.knxproj', '.csv')):
            raise HTTPException(status_code=400, detail="Nur .esf, .knxproj oder .csv Dateien erlaubt")
        
        # Handle CSV separately
        if lower_name.endswith('.csv'):
            content = await file.read()
            return await _import_csv_content(content)
        
        # Save uploaded file for ESF/knxproj
        suffix = '.knxproj' if lower_name.endswith('.knxproj') else '.esf'
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
            logger.info(f"Saved to: {tmp_path}, size: {len(content)} bytes")
        
        try:
            from utils.esf_parser import ESFParser
            # Pass password - strip whitespace but keep content
            actual_password = password.strip() if password else None
            logger.info(f"Passing to parser: password={repr(actual_password)}")
            parser = ESFParser(tmp_path, password=actual_password)
            addresses = parser.parse()
            
            created = 0
            updated = 0
            errors = 0
            
            for ga in addresses:
                try:
                    _, was_created = await db_manager.upsert_group_address(ga)
                    if was_created:
                        created += 1
                    else:
                        updated += 1
                except Exception as e:
                    logger.warning(f"Error importing {ga.address}: {e}")
                    errors += 1
            
            return {
                "status": "success", 
                "message": f"Import abgeschlossen: {created} neu, {updated} aktualisiert",
                "created": created,
                "updated": updated,
                "errors": errors,
                "total_found": len(addresses), 
                "project_info": parser.project_info
            }
        finally:
            os.unlink(tmp_path)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Import error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/import/csv")
async def import_csv(file: UploadFile = File(...)):
    try:
        content = await file.read()
        lines = content.decode('utf-8').strip().split('\n')
        
        imported = 0
        for line in lines[1:]:
            parts = line.strip().split(',')
            if len(parts) >= 2:
                try:
                    await db_manager.create_group_address(GroupAddressCreate(
                        address=parts[0].strip(),
                        name=parts[1].strip(),
                        dpt=parts[2].strip() if len(parts) > 2 else None
                    ))
                    imported += 1
                except Exception:
                    pass
        
        return {"status": "success", "count": imported}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/export/csv")
async def export_csv():
    addresses = await db_manager.get_all_group_addresses()
    csv = "address,name,dpt,room,function,last_value\n"
    for a in addresses:
        csv += f"{a.address},{a.name},{a.dpt or ''},{a.room or ''},{a.function or ''},{a.last_value or ''}\n"
    
    return StreamingResponse(
        iter([csv]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=knx_addresses.csv"}
    )

@router.post("/knx/send")
async def send_telegram(group_address: str = Query(...), value: str = Query(...)):
    try:
        logger.info(f"/knx/send: address={group_address}, value={value}")
        
        # Detect internal address by prefix OR DB flag
        is_internal = group_address.upper().startswith("IKO:")
        addr = await db_manager.get_group_address(group_address)
        
        if not is_internal and addr and addr.is_internal:
            is_internal = True
        
        logger.info(f"/knx/send: is_internal={is_internal}, in_db={addr is not None}")
        
        if is_internal:
            # Auto-create IKO in DB if it doesn't exist
            if not addr:
                try:
                    from models.group_address import GroupAddressCreate
                    ga = GroupAddressCreate(
                        address=group_address,
                        name=f"Auto: {group_address}",
                        is_internal=True,
                        function="IKO"
                    )
                    await db_manager.create_group_address(ga)
                    logger.info(f"Auto-created IKO address: {group_address}")
                except Exception as e:
                    logger.debug(f"IKO auto-create {group_address}: {e}")
            
            # Update value in DB
            await db_manager.update_group_address_value(group_address, value)
            
            # Forward to logic manager so blocks receive the value
            try:
                await logic_manager.on_address_changed(group_address, value)
            except Exception as e:
                logger.warning(f"Logic forward for IKO {group_address}: {e}")
            
            # Broadcast to WebSocket log (so Log page shows IKO changes)
            from datetime import datetime
            await _broadcast_telegram({
                "type": "telegram",
                "timestamp": datetime.now().isoformat(),
                "source": "VSE",
                "destination": group_address,
                "value": value,
                "direction": "outgoing",
            })
            
            return {"status": "set", "address": group_address, "value": value, "internal": True}
        
        # KNX address - send telegram
        if value.lower() in ['true', '1', 'on']:
            val = True
        elif value.lower() in ['false', '0', 'off']:
            val = False
        else:
            val = int(value) if value.isdigit() else value
        
        if await knx_manager.send_telegram(group_address, val):
            return {"status": "sent", "address": group_address, "value": val}
        raise HTTPException(status_code=500, detail="Send failed")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/internal/set")
async def set_internal_value(address: str = Query(...), value: str = Query(...)):
    """Set value for internal address (or any address without sending KNX telegram)"""
    try:
        # Auto-create if IKO and not in DB
        existing = await db_manager.get_group_address(address)
        if not existing and address.upper().startswith("IKO:"):
            try:
                from models.group_address import GroupAddressCreate
                ga = GroupAddressCreate(
                    address=address, name=f"Auto: {address}",
                    is_internal=True, function="IKO"
                )
                await db_manager.create_group_address(ga)
            except Exception:
                pass
        
        await db_manager.update_group_address_value(address, value)
        # Also notify logic manager
        try:
            await logic_manager.on_address_changed(address, value)
        except Exception as e:
            logger.warning(f"Logic forward for {address}: {e}")
        
        # Broadcast to log
        await _broadcast_telegram({
            "type": "telegram",
            "timestamp": datetime.now().isoformat(),
            "source": "internal",
            "destination": address,
            "value": value,
            "direction": "outgoing",
        })
        
        return {"status": "set", "address": address, "value": value}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/knx/telegrams")
async def get_telegrams(count: int = 50):
    telegrams = knx_manager.get_recent_telegrams(count)
    return {
        "telegrams": [
            {
                "timestamp": t["timestamp"].isoformat() if hasattr(t["timestamp"], 'isoformat') else str(t["timestamp"]),
                "source": t["source"],
                "destination": t["destination"],
                "payload": t["payload"],
                "direction": t["direction"]
            }
            for t in telegrams
        ],
        "count": len(telegrams)
    }

@router.websocket("/ws/telegrams")
async def ws_telegrams(websocket: WebSocket):
    await websocket.accept()
    _ws_telegram_clients.append(websocket)
    
    # KNX telegram callback - forward real KNX bus traffic
    async def knx_callback(data):
        try:
            await websocket.send_json({
                "type": "telegram",
                "timestamp": data["timestamp"].isoformat() if hasattr(data["timestamp"], 'isoformat') else str(data["timestamp"]),
                "source": data.get("source", "KNX"),
                "destination": data.get("destination", "–"),
                "value": str(data.get("payload", "")),
                "direction": data.get("direction", "incoming"),
            })
        except Exception:
            pass
    
    knx_manager.register_telegram_callback(knx_callback)
    
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        knx_manager.unregister_telegram_callback(knx_callback)
        if websocket in _ws_telegram_clients:
            _ws_telegram_clients.remove(websocket)

@router.post("/knx/reconnect-gateway")
async def reconnect_knx_gateway():
    """Reconnect KNX gateway only (not a full restart)"""
    await knx_manager.disconnect()
    await asyncio.sleep(1)
    await knx_manager.connect()
    return {"status": "restarted"}

@router.get("/system/backup")
async def create_backup():
    """Create comprehensive system backup as JSON — includes all config, blocks, visu, DB"""
    from fastapi.responses import Response
    import base64
    
    try:
        base_dir = Path(__file__).parent.parent
        data_dir = base_dir / 'data'
        
        backup_data = {
            'backup_version': 2,
            'app_version': APP_VERSION,
            'created': datetime.now().isoformat(),
            'group_addresses': [],
            'logic_config': None,
            'block_positions': {},
            'visu_rooms': None,
            'custom_blocks': {},
            'vse_templates': {},
            'settings': {},
            'database_b64': None,
        }
        
        # 1. Group addresses from DB
        addresses = await db_manager.get_all_group_addresses()
        backup_data['group_addresses'] = [
            {
                'address': a.address,
                'name': a.name,
                'dpt': a.dpt,
                'room': a.room,
                'function': a.function,
                'is_internal': a.is_internal,
                'enabled': a.enabled
            }
            for a in addresses
        ]
        
        # 2. Logic config (blocks, pages, bindings)
        config_file = data_dir / 'logic_config.json'
        if config_file.exists():
            with open(config_file, 'r') as f:
                backup_data['logic_config'] = json.load(f)
        
        # 3. Block positions
        positions_file = data_dir / 'block_positions.json'
        if positions_file.exists():
            with open(positions_file, 'r') as f:
                backup_data['block_positions'] = json.load(f)
        
        # 4. Visu rooms (widgets, categories)
        visu_file = data_dir / 'visu_rooms.json'
        if visu_file.exists():
            with open(visu_file, 'r') as f:
                backup_data['visu_rooms'] = json.load(f)
        
        # 5. Custom blocks (.py files) — stored as base64
        custom_dir = data_dir / 'custom_blocks'
        if custom_dir.exists():
            for py_file in custom_dir.glob('*.py'):
                try:
                    content = py_file.read_text(encoding='utf-8')
                    backup_data['custom_blocks'][py_file.name] = content
                    logger.info(f"Backup: custom block {py_file.name}")
                except Exception as e:
                    logger.warning(f"Could not backup {py_file.name}: {e}")
        
        # 6. VSE templates from data/vse/
        vse_dir = data_dir / 'vse'
        if vse_dir.exists():
            for vse_file in vse_dir.glob('*.json'):
                try:
                    with open(vse_file, 'r') as f:
                        backup_data['vse_templates'][vse_file.name] = json.load(f)
                except Exception as e:
                    logger.warning(f"Could not backup VSE {vse_file.name}: {e}")
        
        # 7. Settings (.env)
        env_file = base_dir / '.env'
        if env_file.exists():
            with open(env_file, 'r') as f:
                for line in f:
                    if '=' in line and not line.strip().startswith('#'):
                        key, _, value = line.strip().partition('=')
                        backup_data['settings'][key] = value
        
        # 8. SQLite database as base64
        db_file = data_dir / 'knx.db'
        if db_file.exists():
            with open(db_file, 'rb') as f:
                backup_data['database_b64'] = base64.b64encode(f.read()).decode('ascii')
        
        backup_json = json.dumps(backup_data, indent=2, ensure_ascii=False)
        filename = f'knx-backup-{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        
        logger.info(f"Backup created: {len(backup_data['group_addresses'])} addresses, "
                    f"{len(backup_data.get('custom_blocks', {}))} custom blocks, "
                    f"{len(backup_data.get('vse_templates', {}))} VSE templates")
        
        return Response(
            content=backup_json,
            media_type='application/json',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )
        
    except Exception as e:
        logger.error(f"Backup error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/system/restore")
async def restore_backup(file: UploadFile = File(...)):
    """Restore system from comprehensive backup"""
    import base64
    
    try:
        content = await file.read()
        backup_data = json.loads(content.decode('utf-8'))
        
        base_dir = Path(__file__).parent.parent
        data_dir = base_dir / 'data'
        data_dir.mkdir(parents=True, exist_ok=True)
        
        restored = {
            'addresses': 0, 'blocks': 0, 'positions': 0,
            'visu_rooms': 0, 'custom_blocks': 0, 'vse_templates': 0,
            'settings': False, 'database': False
        }
        
        # 1. Restore group addresses
        if 'group_addresses' in backup_data:
            for addr_data in backup_data['group_addresses']:
                try:
                    ga = GroupAddressCreate(**addr_data)
                    existing = await db_manager.get_group_address(ga.address)
                    if existing:
                        await db_manager.update_group_address(ga.address, ga)
                    else:
                        await db_manager.create_group_address(ga)
                    restored['addresses'] += 1
                except Exception as e:
                    logger.warning(f"Could not restore address {addr_data.get('address')}: {e}")
        
        # 2. Restore logic config
        if backup_data.get('logic_config'):
            config_file = data_dir / 'logic_config.json'
            with open(config_file, 'w') as f:
                json.dump(backup_data['logic_config'], f, indent=2)
            restored['blocks'] = len(backup_data['logic_config'].get('blocks', []))
        
        # 3. Restore block positions
        if backup_data.get('block_positions'):
            positions_file = data_dir / 'block_positions.json'
            with open(positions_file, 'w') as f:
                json.dump(backup_data['block_positions'], f, indent=2)
            restored['positions'] = len(backup_data['block_positions'])
        
        # 4. Restore visu rooms
        if backup_data.get('visu_rooms'):
            visu_file = data_dir / 'visu_rooms.json'
            with open(visu_file, 'w') as f:
                json.dump(backup_data['visu_rooms'], f, indent=2, ensure_ascii=False)
            restored['visu_rooms'] = len(backup_data['visu_rooms']) if isinstance(backup_data['visu_rooms'], list) else 1
        
        # 5. Restore custom blocks (.py files)
        if backup_data.get('custom_blocks'):
            custom_dir = data_dir / 'custom_blocks'
            custom_dir.mkdir(parents=True, exist_ok=True)
            for filename, py_content in backup_data['custom_blocks'].items():
                if filename.endswith('.py'):
                    (custom_dir / filename).write_text(py_content, encoding='utf-8')
                    restored['custom_blocks'] += 1
                    logger.info(f"Restored custom block: {filename}")
        
        # 6. Restore VSE templates
        if backup_data.get('vse_templates'):
            vse_dir = data_dir / 'vse'
            vse_dir.mkdir(parents=True, exist_ok=True)
            for filename, vse_data in backup_data['vse_templates'].items():
                with open(vse_dir / filename, 'w') as f:
                    json.dump(vse_data, f, indent=2, ensure_ascii=False)
                restored['vse_templates'] += 1
        
        # 7. Restore settings
        if backup_data.get('settings'):
            env_file = base_dir / '.env'
            with open(env_file, 'w') as f:
                for key, value in backup_data['settings'].items():
                    f.write(f"{key}={value}\n")
            restored['settings'] = True
        
        # 8. Restore database (only if present and no addresses were restored from JSON)
        if backup_data.get('database_b64') and restored['addresses'] == 0:
            db_file = data_dir / 'knx.db'
            db_bytes = base64.b64decode(backup_data['database_b64'])
            with open(db_file, 'wb') as f:
                f.write(db_bytes)
            restored['database'] = True
            logger.info("Restored SQLite database from backup")
        
        summary_parts = []
        if restored['addresses']: summary_parts.append(f"{restored['addresses']} Adressen")
        if restored['blocks']: summary_parts.append(f"{restored['blocks']} Logikbausteine")
        if restored['visu_rooms']: summary_parts.append(f"{restored['visu_rooms']} Visu-Räume")
        if restored['custom_blocks']: summary_parts.append(f"{restored['custom_blocks']} Custom Blocks")
        if restored['vse_templates']: summary_parts.append(f"{restored['vse_templates']} VSE-Templates")
        if restored['settings']: summary_parts.append("Einstellungen")
        
        msg = f"Wiederhergestellt: {', '.join(summary_parts) or 'nichts'}"
        logger.info(msg)
        
        return {
            'status': 'success',
            'message': msg + ". Bitte Service neu starten für volle Wirkung.",
            'restored': restored
        }
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Ungültiges Backup-Format")
    except Exception as e:
        logger.error(f"Restore error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/system/update/upload")
async def upload_update(file: UploadFile = File(...)):
    import tempfile
    import subprocess
    import shutil
    import os
    
    try:
        filename = getattr(file, 'filename', 'update.tar.gz') or 'update.tar.gz'
        
        if not filename.lower().endswith(('.tar.gz', '.gz')):
            raise HTTPException(status_code=400, detail="Nur .tar.gz Dateien erlaubt")
        
        # Save uploaded file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.tar.gz') as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        try:
            # Extract to temp directory
            extract_dir = tempfile.mkdtemp()
            subprocess.run(['tar', '-xzf', tmp_path, '-C', extract_dir], check=True)
            
            base_dir = Path(__file__).parent.parent
            
            # Find the extracted folder
            extracted = list(Path(extract_dir).iterdir())
            if extracted:
                source_dir = extracted[0] if extracted[0].is_dir() else extract_dir
                
                # Copy static files (dashboard)
                static_src = source_dir / 'static'
                if static_src.exists():
                    static_dst = base_dir / 'static'
                    if static_dst.exists():
                        shutil.rmtree(static_dst)
                    shutil.copytree(static_src, static_dst)
                
                # Copy other updated files - INCLUDING logic, scripts, and vse!
                for item in ['api', 'knx', 'utils', 'models', 'config', 'logic', 'scripts']:
                    src = source_dir / item
                    if src.exists():
                        dst = base_dir / item
                        if dst.exists():
                            shutil.rmtree(dst)
                        shutil.copytree(src, dst)
                        logger.info(f"Updated: {item}/")
                
                # Copy VSE elements
                vse_src = source_dir / 'data' / 'vse'
                if vse_src.exists():
                    vse_dst = base_dir / 'data' / 'vse'
                    vse_dst.parent.mkdir(exist_ok=True)
                    if vse_dst.exists():
                        shutil.rmtree(vse_dst)
                    shutil.copytree(vse_src, vse_dst)
                    logger.info("Updated: data/vse/")
                
                # Merge custom_blocks - preserve user-uploaded blocks!
                custom_blocks_src = source_dir / 'data' / 'custom_blocks'
                if custom_blocks_src.exists():
                    custom_blocks_dst = base_dir / 'data' / 'custom_blocks'
                    custom_blocks_dst.mkdir(parents=True, exist_ok=True)
                    merged_files = []
                    for src_file in custom_blocks_src.iterdir():
                        if src_file.is_file():
                            dst_file = custom_blocks_dst / src_file.name
                            shutil.copy2(src_file, dst_file)
                            merged_files.append(src_file.name)
                    logger.info(f"Merged custom_blocks (user blocks preserved): {merged_files}")
                
                # Copy main.py if exists
                main_src = source_dir / 'main.py'
                if main_src.exists():
                    shutil.copy(main_src, base_dir / 'main.py')

                # Copy root-level files (README, install script, etc.)
                for root_file in ['README.md', 'install.sh', 'requirements.txt']:
                    rf_src = source_dir / root_file
                    if rf_src.exists():
                        shutil.copy(rf_src, base_dir / root_file)
                        logger.info(f"Updated: {root_file}")
            
            # Clear Python cache
            for root, dirs, files in os.walk(str(base_dir)):
                for d in dirs:
                    if d == '__pycache__':
                        cache_path = os.path.join(root, d)
                        try:
                            shutil.rmtree(cache_path)
                            logger.info(f"Cleared cache: {cache_path}")
                        except Exception:
                            pass
            
            # Cleanup temp
            shutil.rmtree(extract_dir)
            
            # Fix permissions BEFORE restart
            try:
                import os
                data_dir = base_dir / "data"
                data_dir.mkdir(parents=True, exist_ok=True)
                os.chmod(str(data_dir), 0o755)
                for f in data_dir.glob("*.json"):
                    os.chmod(str(f), 0o666)
                db_file = data_dir / "knx.db"
                if db_file.exists():
                    os.chmod(str(db_file), 0o666)
                logger.info("Fixed permissions after update")
            except Exception as e:
                logger.warning(f"Could not fix permissions: {e}")
            
            # Auto-restart service using detached script (survives service stop)
            try:
                import tempfile
                restart_script = tempfile.NamedTemporaryFile(
                    mode='w', suffix='.sh', delete=False, dir='/tmp'
                )
                restart_script.write('#!/bin/bash\n')
                restart_script.write('sleep 2\n')
                restart_script.write('systemctl restart knx-automation\n')
                restart_script.write(f'rm -f {restart_script.name}\n')
                restart_script.close()
                os.chmod(restart_script.name, 0o755)
                subprocess.Popen(
                    ['nohup', restart_script.name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    preexec_fn=os.setpgrp,  # Detach from parent process group
                )
                logger.info(f"Restart script scheduled: {restart_script.name}")
            except Exception as e:
                logger.error(f"Could not schedule restart: {e}")
                # Fallback: direct attempt
                try:
                    subprocess.Popen(['systemctl', 'restart', 'knx-automation'],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    pass
            
            return {"status": "success", "message": "Update installiert. Service wird neugestartet..."}
            
        finally:
            import os
            os.unlink(tmp_path)
            
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Entpacken fehlgeschlagen: {e}")
    except Exception as e:
        logger.error(f"Update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/settings/gateway")
async def update_settings(
    gateway_ip: str = Query(...),
    gateway_port: int = Query(3671),
    use_tunneling: bool = Query(True)
):
    from config import settings
    
    env_path = Path(__file__).parent.parent / '.env'
    env_content = f"""KNX_GATEWAY_IP={gateway_ip}
KNX_GATEWAY_PORT={gateway_port}
KNX_USE_TUNNELING={'true' if use_tunneling else 'false'}
KNX_USE_ROUTING={'false' if use_tunneling else 'true'}
"""
    
    with open(env_path, 'w') as f:
        f.write(env_content)
    
    settings.knx_gateway_ip = gateway_ip
    settings.knx_gateway_port = gateway_port
    settings.knx_use_tunneling = use_tunneling
    
    await knx_manager.disconnect()
    await asyncio.sleep(1)
    await knx_manager.connect()
    

    return {"status": "success", "gateway_ip": gateway_ip}


# ============ LOGIC BLOCKS API ============

@router.get("/logic/export")
async def export_logic_config():
    """Export all logic blocks and pages as downloadable JSON"""
    try:
        export_data = {
            "version": APP_VERSION,
            "exported_at": datetime.now().isoformat(),
            "blocks": logic_manager.get_all_blocks(),
            "pages": list(logic_manager._pages.values()) if hasattr(logic_manager, '_pages') else []
        }
        
        return StreamingResponse(
            iter([json.dumps(export_data, ensure_ascii=False, indent=2, default=str)]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=logic-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"}
        )
    except Exception as e:
        logger.error(f"Error exporting logic: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/logic/import")
async def import_logic_config(file: UploadFile = File(...)):
    """Import logic blocks from JSON file"""
    try:
        content = await file.read()
        data = json.loads(content.decode('utf-8'))
        
        blocks_imported = 0
        
        # Import blocks
        if "blocks" in data:
            for block_data in data["blocks"]:
                try:
                    block_type = block_data.get("block_type")
                    if not block_type:
                        continue
                    
                    # Create the block
                    page_id = block_data.get("page_id")
                    block = await logic_manager.create_block_async(block_type, page_id=page_id)
                    
                    # Restore position if available
                    if "position" in block_data:
                        block.position = block_data["position"]
                    
                    # Restore input bindings
                    if "input_bindings" in block_data:
                        for input_key, address in block_data["input_bindings"].items():
                            if address:
                                await logic_manager.bind_input_async(block.instance_id, input_key, address)
                    
                    # Restore output bindings
                    if "output_bindings" in block_data:
                        for output_key, address in block_data["output_bindings"].items():
                            if address:
                                await logic_manager.bind_output_async(block.instance_id, output_key, address)
                    
                    blocks_imported += 1
                except Exception as e:
                    logger.warning(f"Could not import block: {e}")
        
        logger.info(f"Imported {blocks_imported} logic blocks")
        return {"status": "imported", "blocks": blocks_imported}
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Ungültige JSON-Datei")
    except Exception as e:
        logger.error(f"Error importing logic: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/logic/blocks/available")
async def get_available_blocks():
    """Get list of all available block types (builtin + custom)"""
    return logic_manager.get_available_blocks()

@router.get("/logic/blocks")
async def get_all_blocks():
    """Get all block instances"""
    import logging
    logger = logging.getLogger(__name__)
    blocks = logic_manager.get_all_blocks()
    logger.info(f"Returning {len(blocks)} blocks: {[b['instance_id'] for b in blocks]}")
    return blocks


@router.get("/logic/status")
async def get_logic_status():
    """Get logic system status"""
    return {
        "blocks_count": len(logic_manager._blocks),
        "blocks": list(logic_manager._blocks.keys()),
        "pages_count": len(logic_manager._pages),
        "pages": list(logic_manager._pages.keys()),
        "available_types": list(ALL_BUILTIN_BLOCKS.keys()) + list(logic_manager._custom_block_classes.keys()),
        "running": logic_manager._running
    }


@router.post("/logic/blocks")
async def create_block(data: BlockCreate):
    """Create a new block instance"""
    try:
        # Convert empty string to None for page_id
        page_id = data.page_id if data.page_id else None
        logger.info(f"Creating block: type={data.block_type}, page_id={page_id}")
        block = await logic_manager.create_block_async(data.block_type, page_id=page_id)
        if not block:
            raise HTTPException(status_code=400, detail=f"Unknown block type: {data.block_type}")
        await logic_manager.save_to_db()
        return block.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating block {data.block_type}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fehler beim Erstellen: {str(e)}")

@router.get("/logic/blocks/{instance_id}")
async def get_block(instance_id: str):
    """Get a specific block"""
    block = logic_manager.get_block(instance_id)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    return block.to_dict()

@router.delete("/logic/blocks/{instance_id}")
async def delete_block(instance_id: str):
    """Delete a block instance"""
    if not logic_manager.delete_block(instance_id):
        raise HTTPException(status_code=404, detail="Block not found")
    await logic_manager.save_to_db()
    return {"status": "deleted"}

@router.post("/logic/blocks/{instance_id}/bind")
async def bind_block(instance_id: str, data: BindingCreate):
    """Bind block input or output to an address
    
    Supports BLOCK:instance_id:output_key format for direct block-to-block connections.
    This will automatically create an IKO address and bind both blocks.
    """
    # URL-decode the instance_id (FastAPI should do this, but be safe)
    from urllib.parse import unquote
    instance_id = unquote(instance_id)
    
    address = data.address
    
    # Verify block exists first with helpful error
    target_block = logic_manager.get_block(instance_id)
    if not target_block:
        available = list(logic_manager._blocks.keys())[:10]
        logger.error(f"bind_block: Block '{instance_id}' not found. Available: {available}")
        raise HTTPException(status_code=404, detail=f"Block '{instance_id}' nicht gefunden")
    
    # Handle BLOCK: addresses for direct connections
    if address and address.startswith('BLOCK:'):
        parts = address.split(':')
        if len(parts) == 3:
            source_instance = parts[1]
            source_output = parts[2]
            
            # Get source block for name and ID
            source_block = logic_manager.get_block(source_instance)
            if not source_block:
                raise HTTPException(status_code=404, detail=f"Quell-Block '{source_instance}' nicht gefunden")
            
            # Simplified IKO format: IKO:InstanceNum_BlockName:OutputKey
            id_parts = source_instance.split('_')
            instance_num = id_parts[-2] if len(id_parts) >= 3 else "0"
            block_name = getattr(source_block, '_name', None) or getattr(source_block, 'NAME', source_block.__class__.__name__)
            iko_address = f"IKO:{instance_num}_{block_name}:{source_output}"
            iko_name = f"{block_name}.{source_output}"
            
            # Create IKO if it doesn't exist
            try:
                existing = await db_manager.get_group_address(iko_address)
                if not existing:
                    await db_manager.create_group_address(GroupAddressCreate(
                        address=iko_address,
                        name=iko_name,
                        is_internal=True,
                        enabled=True
                    ))
                    logger.info(f"Created IKO for block connection: {iko_address}")
            except Exception as e:
                logger.warning(f"Could not create IKO: {e}")
            
            # Bind source block output to IKO
            logic_manager.bind_output(source_instance, source_output, iko_address)
            logger.info(f"Bound source {source_instance}.{source_output} -> {iko_address}")
            
            # Use IKO address for target binding
            address = iko_address
    
    if data.input_key:
        # Validate input key exists on block
        if data.input_key not in target_block.INPUTS:
            available_inputs = list(target_block.INPUTS.keys())
            logger.error(f"bind_block: Input key '{data.input_key}' not in block inputs: {available_inputs}")
            raise HTTPException(status_code=400, detail=f"Eingang '{data.input_key}' nicht gefunden. Verfügbar: {available_inputs}")
        if not logic_manager.bind_input(instance_id, data.input_key, address):
            raise HTTPException(status_code=400, detail=f"Binding fehlgeschlagen für {instance_id}.{data.input_key}")
    elif data.output_key:
        if data.output_key not in target_block.OUTPUTS:
            available_outputs = list(target_block.OUTPUTS.keys())
            logger.error(f"bind_block: Output key '{data.output_key}' not in block outputs: {available_outputs}")
            raise HTTPException(status_code=400, detail=f"Ausgang '{data.output_key}' nicht gefunden. Verfügbar: {available_outputs}")
        if not logic_manager.bind_output(instance_id, data.output_key, address):
            raise HTTPException(status_code=400, detail=f"Binding fehlgeschlagen für {instance_id}.{data.output_key}")
    else:
        raise HTTPException(status_code=400, detail="input_key oder output_key muss angegeben werden")
    
    await logic_manager.save_to_db()
    return {"status": "bound", "address": address}


@router.post("/logic/blocks/{instance_id}/unbind")
async def unbind_block(instance_id: str, data: dict):
    """Remove a binding from a block input or output"""
    from urllib.parse import unquote
    instance_id = unquote(instance_id)

    block = logic_manager.get_block(instance_id)
    if not block:
        raise HTTPException(status_code=404, detail=f"Block '{instance_id}' nicht gefunden")

    input_key = data.get("input_key")
    output_key = data.get("output_key")

    if input_key:
        if not logic_manager.unbind_input(instance_id, input_key):
            raise HTTPException(status_code=400, detail=f"Kein Binding für {input_key}")
    elif output_key:
        if not logic_manager.unbind_output(instance_id, output_key):
            raise HTTPException(status_code=400, detail=f"Kein Binding für {output_key}")
    else:
        raise HTTPException(status_code=400, detail="input_key oder output_key muss angegeben werden")

    await logic_manager.save_to_db()
    return {"status": "unbound"}


@router.post("/logic/blocks/{instance_id}/bind-output")
async def bind_block_output(instance_id: str, data: BindingCreate):
    """Bind block output to an address (alias endpoint)"""
    if not data.output_key:
        raise HTTPException(status_code=400, detail="Must specify output_key")
    if not logic_manager.bind_output(instance_id, data.output_key, data.address):
        raise HTTPException(status_code=400, detail="Invalid output binding")
    
    await logic_manager.save_to_db()
    return {"status": "bound"}

@router.post("/logic/blocks/{instance_id}/trigger")
async def trigger_block(instance_id: str):
    """Manually trigger a block's timer/poll function"""
    block = logic_manager.get_block(instance_id)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    
    # Try to call on_timer
    try:
        if hasattr(block, 'on_timer'):
            await block.on_timer()
            return {"status": "triggered", "instance_id": instance_id}
        elif hasattr(block, 'poll_data'):
            await block.poll_data()
            return {"status": "polled", "instance_id": instance_id}
        else:
            return {"status": "no_timer", "instance_id": instance_id}
    except Exception as e:
        return {"status": "error", "error": str(e)}


class InputValueSet(BaseModel):
    value: Optional[str] = None

@router.post("/logic/blocks/{instance_id}/input/{input_key}")
async def set_block_input_value(instance_id: str, input_key: str, data: InputValueSet):
    """Set a block input value directly"""
    logger.info(f"SET INPUT: block={instance_id}, key={input_key}, value={data.value}")
    
    block = logic_manager.get_block(instance_id)
    if not block:
        logger.error(f"Block not found: {instance_id}")
        raise HTTPException(status_code=404, detail="Block not found")
    
    if input_key not in block.INPUTS:
        logger.error(f"Unknown input {input_key} for block {instance_id}")
        raise HTTPException(status_code=400, detail=f"Unknown input: {input_key}")
    
    # Convert value based on input type
    input_config = block.INPUTS[input_key]
    input_type = input_config.get('type', 'str')
    
    raw_value = data.value
    converted_value = raw_value
    
    try:
        if raw_value is not None and raw_value != '':
            if input_type == 'bool':
                converted_value = raw_value.lower() in ('1', 'true', 'on', 'yes')
            elif input_type == 'int':
                converted_value = int(float(raw_value))
            elif input_type == 'float':
                converted_value = float(raw_value)
            else:
                converted_value = str(raw_value)
        else:
            converted_value = input_config.get('default')
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid value for type {input_type}: {raw_value}")
    
    # Set the value
    block.set_input(input_key, converted_value)
    logger.info(f"Set {instance_id} input {input_key} = {converted_value} (type: {input_type})")
    
    await logic_manager.save_to_db()
    return {"status": "ok", "input_key": input_key, "value": converted_value}


@router.get("/logic/blocks/{instance_id}/debug")
async def get_block_debug(instance_id: str):
    """Get detailed debug info for a block"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Debug request for block: {instance_id}")
    logger.info(f"Available blocks: {list(logic_manager._blocks.keys())}")
    
    block = logic_manager.get_block(instance_id)
    if not block:
        logger.error(f"Block not found: {instance_id}")
        raise HTTPException(status_code=404, detail=f"Block not found: {instance_id}. Available: {list(logic_manager._blocks.keys())}")
    
    logger.info(f"Found block: {block.__class__.__name__}")
    
    try:
        result = {
            "instance_id": instance_id,
            "block_type": block.__class__.__name__,
            "block_id": getattr(block, 'ID', 0),
            "enabled": getattr(block, '_enabled', None),
            "running": getattr(block, '_running', None),
            "timer_interval": getattr(block, '_timer_interval', 0),
            "timer_active": block._timer_task is not None and not block._timer_task.done() if hasattr(block, '_timer_task') and block._timer_task else False,
            "input_values": getattr(block, '_input_values', {}),
            "output_values": getattr(block, '_output_values', {}),
            "input_bindings": getattr(block, '_input_bindings', {}),
            "output_bindings": getattr(block, '_output_bindings', {}),
            "debug_values": getattr(block, '_debug_values', {}),
            "last_executed": block._last_executed.isoformat() if hasattr(block, '_last_executed') and block._last_executed else None
        }
        logger.info(f"Debug result: {result}")
        return result
    except Exception as e:
        logger.error(f"Error building debug info: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.post("/logic/blocks/{instance_id}/enable")
async def enable_block(instance_id: str, enabled: bool = Query(True)):
    """Enable or disable a block"""
    block = logic_manager.get_block(instance_id)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    block._enabled = enabled
    await logic_manager.save_to_db()
    return {"status": "ok", "enabled": enabled}

# ============ BLOCK POSITIONS API ============

@router.get("/logic/positions")
async def get_block_positions():
    """Get saved block positions"""
    try:
        positions_file = Path(__file__).parent.parent / 'data' / 'block_positions.json'
        if positions_file.exists():
            with open(positions_file, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Error loading positions: {e}")
        return {}

@router.post("/logic/positions")
async def save_block_positions(positions: dict):
    """Save block positions"""
    try:
        positions_file = Path(__file__).parent.parent / 'data' / 'block_positions.json'
        positions_file.parent.mkdir(parents=True, exist_ok=True)
        with open(positions_file, 'w') as f:
            json.dump(positions, f, indent=2)
        return {"status": "saved", "count": len(positions)}
    except Exception as e:
        logger.error(f"Error saving positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============ LOGIC PAGES API ============

@router.get("/logic/pages")
async def get_all_pages():
    """Get all logic pages"""
    return logic_manager.get_all_pages()

@router.post("/logic/pages")
async def create_page(data: PageCreate):
    """Create a new logic page"""
    import uuid
    logger.info(f"Creating page with data: name={data.name}, page_id={data.page_id}")
    try:
        # Generate page_id if not provided or empty
        page_id = data.page_id if data.page_id else f"page_{str(uuid.uuid4())[:8]}"
        logger.info(f"Using page_id: {page_id}")
        page = logic_manager.create_page(page_id, data.name, data.description or "", data.room or "")
        logger.info(f"Page created: {page}")
        await logic_manager.save_to_db()
        return page
    except ValueError as e:
        logger.error(f"ValueError creating page: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating page: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/logic/pages/{page_id}")
async def update_page(page_id: str, data: PageUpdate):
    """Update a page's name, description, or room"""
    page = logic_manager.update_page(page_id, name=data.name, description=data.description, room=data.room)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    await logic_manager.save_to_db()
    return page

@router.get("/logic/pages/{page_id}")
async def get_page(page_id: str):
    """Get a specific page"""
    page = logic_manager.get_page(page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return page

@router.delete("/logic/pages/{page_id}")
async def delete_page(page_id: str):
    """Delete a page and all its blocks"""
    if not logic_manager.delete_page(page_id):
        raise HTTPException(status_code=404, detail="Page not found")
    await logic_manager.save_to_db()
    return {"status": "deleted"}

# ============ CUSTOM BLOCKS API ============

@router.get("/logic/custom-blocks")
async def get_custom_block_files():
    """Get list of uploaded custom block files"""
    return logic_manager.get_custom_block_files()

@router.post("/logic/custom-blocks/upload")
async def upload_custom_block(file: UploadFile = File(...)):
    """Upload a custom block Python file"""
    if not file.filename.endswith('.py'):
        raise HTTPException(status_code=400, detail="Only .py files allowed")
    
    try:
        content = await file.read()
        result = await logic_manager.upload_block_file(file.filename, content)
        result['message'] = f"Block '{file.filename}' erfolgreich hochgeladen"
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/logic/custom-blocks/{filename}")
async def delete_custom_block(filename: str):
    """Delete a custom block file"""
    if not await logic_manager.delete_block_file(filename):
        raise HTTPException(status_code=404, detail="File not found")
    return {"status": "deleted"}

@router.post("/logic/custom-blocks/reload")
async def reload_custom_blocks():
    """Reload all custom blocks from disk"""
    try:
        await logic_manager._load_custom_blocks()
        loaded = list(logic_manager._custom_block_classes.keys())
        return {"status": "ok", "loaded": loaded}
    except Exception as e:
        logger.error(f"Error reloading custom blocks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/logic/custom-blocks/{filename}/code")
async def get_custom_block_code(filename: str):
    """Get source code of a custom block file"""
    try:
        code = logic_manager.get_block_file_code(filename)
        return {"filename": filename, "code": code}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")

@router.get("/logic/block-type/{block_type}/source")
async def get_block_type_source(block_type: str):
    """Get source code for a block type (builtin or custom)"""
    try:
        result = logic_manager.get_block_source_by_type(block_type)
        return result
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Source for {block_type} not found")

@router.put("/logic/custom-blocks/{filename}/code")
async def update_custom_block_code(filename: str, data: dict):
    """Update source code of a custom block file"""
    code = data.get("code", "")
    if not code:
        raise HTTPException(status_code=400, detail="No code provided")
    try:
        result = await logic_manager.update_block_file_code(filename, code)
        return result
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============ CHART HISTORY API ============

from api.chart_recorder import chart_recorder

@router.get("/charts/bindings")
async def get_chart_bindings():
    """Get chart KO bindings."""
    return chart_recorder.load_bindings()

@router.post("/charts/bindings")
async def save_chart_bindings(bindings: dict = Body(...)):
    """Save chart KO bindings (also used by recorder)."""
    chart_recorder.save_bindings(bindings)
    return {"status": "saved", "count": len(bindings)}

@router.get("/charts/history")
async def get_chart_history(
    metrics: str = "pv,consumption,temperatureIndoor,temperatureOutdoor,humidity,electricityPrice",
    hours: int = 24,
    bucket_minutes: int = 15
):
    """Get aggregated historical chart data.
    
    Args:
        metrics: comma-separated metric keys
        hours: how many hours back (default 24)
        bucket_minutes: aggregation bucket size (default 15)
    """
    metric_list = [m.strip() for m in metrics.split(",") if m.strip()]
    return chart_recorder.get_aggregated_history(metric_list, hours, bucket_minutes)

@router.get("/charts/history/raw")
async def get_chart_history_raw(
    metrics: str = "pv,consumption",
    hours: int = 24
):
    """Get raw (non-aggregated) historical data."""
    metric_list = [m.strip() for m in metrics.split(",") if m.strip()]
    return chart_recorder.get_history(metric_list, hours)

@router.get("/charts/daily")
async def get_chart_daily(
    metrics: str = "pv,consumption",
    days: int = 7
):
    """Get daily aggregated totals for weekly view."""
    metric_list = [m.strip() for m in metrics.split(",") if m.strip()]
    return chart_recorder.get_daily_totals(metric_list, days)

@router.get("/charts/stats")
async def get_chart_stats():
    """Get recording statistics."""
    return chart_recorder.get_stats()

@router.post("/charts/record-now")
async def trigger_chart_record():
    """Manually trigger a recording cycle."""
    recorded = await chart_recorder.record_once()
    return {"status": "recorded", "count": recorded}


# ============ SYSTEM API ============

@router.post("/system/update")
async def system_update(file: UploadFile = File(...)):
    """Upload and install system update"""
    import subprocess
    import tempfile
    import shutil
    
    if not file.filename.endswith(('.tar.gz', '.gz')):
        raise HTTPException(status_code=400, detail="Only .tar.gz files allowed")
    
    try:
        # Save uploaded file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.tar.gz') as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        # Extract to temp dir
        extract_dir = tempfile.mkdtemp()
        subprocess.run(['tar', '-xzf', tmp_path, '-C', extract_dir], check=True)
        
        # Find extracted content
        items = list(Path(extract_dir).iterdir())
        source_dir = items[0] if len(items) == 1 and items[0].is_dir() else extract_dir
        
        # Copy files to installation dir (preserve data)
        install_dir = Path(__file__).parent.parent
        for item in source_dir.iterdir():
            if item.name not in ('data', '.env', 'venv'):
                dest = install_dir / item.name
                if item.is_dir():
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)
        
        # Cleanup
        shutil.rmtree(extract_dir)
        Path(tmp_path).unlink()
        
        return {"status": "success", "message": "Update installiert. Bitte Service neustarten."}
        
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Entpacken fehlgeschlagen: {e}")
    except Exception as e:
        logger.error(f"Update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/system/restart")
async def system_restart():
    """Restart the service using a detached script that survives service stop"""
    import subprocess
    import os
    import tempfile
    
    try:
        # Save state first
        await logic_manager.save_to_db()
        await knx_manager.disconnect()
        
        # Create a detached restart script
        restart_script = tempfile.NamedTemporaryFile(
            mode='w', suffix='.sh', delete=False, dir='/tmp'
        )
        restart_script.write('#!/bin/bash\n')
        restart_script.write('sleep 2\n')
        restart_script.write('systemctl restart knx-automation\n')
        restart_script.write(f'rm -f {restart_script.name}\n')
        restart_script.close()
        os.chmod(restart_script.name, 0o755)
        
        subprocess.Popen(
            ['nohup', restart_script.name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setpgrp,
        )
        logger.info(f"Restart scheduled via {restart_script.name}")
        return {"status": "restarting", "message": "Service wird in 2 Sekunden neugestartet..."}
    except Exception as e:
        logger.error(f"Restart error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/knx/reconnect")
async def knx_reconnect():
    """Reconnect to KNX gateway"""
    await knx_manager.disconnect()
    await asyncio.sleep(1)
    await knx_manager.connect()
    return {"status": "reconnected", "connected": knx_manager.is_connected}

@router.delete("/group-addresses/clear")
async def clear_all_addresses():
    """Delete all group addresses"""
    try:
        await db_manager.clear_all_group_addresses()
        return {"status": "cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ LOGGING API ============

from datetime import datetime

# Import log_buffer from main
try:
    from main import log_buffer
except ImportError:
    import collections
    log_buffer = collections.deque(maxlen=500)

@router.get("/logs")
async def get_logs(level: str = None, filter: str = None, limit: int = 100):
    """Get recent log entries"""
    from main import log_buffer
    logs = list(log_buffer)
    
    # Format time
    for log in logs:
        if isinstance(log.get('time'), float):
            log['time'] = datetime.fromtimestamp(log['time']).strftime('%H:%M:%S')
    
    # Filter by level
    if level:
        logs = [l for l in logs if l['level'] == level.upper()]
    
    # Filter by text
    if filter:
        logs = [l for l in logs if filter.lower() in l['message'].lower() or filter.lower() in l.get('name', '').lower()]
    
    # Limit and reverse (newest first)
    return list(reversed(logs[-limit:]))

@router.delete("/logs")
async def clear_logs():
    """Clear log buffer"""
    from main import log_buffer
    log_buffer.clear()
    return {"status": "cleared"}

# ============ Standalone Visu View (Mobile/Tablet) ============
from fastapi.responses import HTMLResponse

@router.get("/visu/view", response_class=HTMLResponse)
async def visu_standalone_view_default():
    """Standalone visualization view - default page"""
    return generate_visu_html("default")

@router.get("/visu/view/{page_id}", response_class=HTMLResponse)
async def visu_standalone_view(page_id: str):
    """Standalone visualization view for mobile/tablet embedding"""
    return generate_visu_html(page_id)

def generate_visu_html(page_id: str) -> str:
    """Generate standalone HTML for visu page"""
    return f'''<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no, maximum-scale=1.0, minimum-scale=1.0, viewport-fit=cover">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="theme-color" content="#1a1a2e">
    <title>KNX Visu</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@mdi/font@7.2.96/css/materialdesignicons.min.css">
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;600;700&display=swap">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        html {{ 
            width: 100%;
            height: 100%;
            height: 100dvh;
            background: #1a1a2e;
        }}
        body {{ 
            font-family: 'Roboto', sans-serif;
            background: #1a1a2e;
            color: #fff;
            width: 100%;
            height: 100%;
            height: 100dvh;
            margin: 0;
            padding: 0;
            overflow: hidden;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            touch-action: none;
            -webkit-touch-callout: none;
            -webkit-user-select: none;
            user-select: none;
        }}
        .visu-wrapper {{
            width: 100vw;
            height: 100vh;
            height: 100dvh;
            display: flex;
            justify-content: center;
            align-items: center;
            overflow: hidden;
            background: #1a1a2e;
            position: absolute;
            top: 0;
            left: 0;
        }}
        .visu-container {{
            position: relative;
            transform-origin: center center;
        }}
        .visu-canvas {{
            position: relative;
            background: #1a1a2e;
        }}
        .visu-element {{
            position: absolute;
            cursor: pointer;
            transition: transform 0.1s;
        }}
        .visu-element:active {{
            transform: scale(0.98);
        }}
        /* Sensor Card Styles */
        .sensor-card {{
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 16px;
            border-radius: 12px;
            background: rgba(255,255,255,0.06);
            border: 1.5px solid rgba(88,166,255,0.4);
            height: 100%;
        }}
        .sensor-card-icon {{
            font-size: 28px;
            color: #58a6ff;
        }}
        .sensor-card-content {{
            flex: 1;
            min-width: 0;
        }}
        .sensor-card-label {{
            font-size: 12px;
            color: #888;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .sensor-card-value {{
            font-size: 22px;
            font-weight: 500;
            color: #fff;
        }}
        /* Nav Link Widget */
        .navlink {{
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            height: 100%;
        }}
        .navlink.button {{
            background: linear-gradient(145deg, #58a6ff, #4090e0);
            color: #fff;
            padding: 10px 20px;
            border-radius: 8px;
            font-weight: 500;
        }}
        .navlink.button:active {{ transform: scale(0.98); }}
        .navlink.card {{
            background: rgba(255,255,255,0.06);
            padding: 16px;
            border-radius: 12px;
            border: 2px solid rgba(88,166,255,0.4);
            flex-direction: column;
        }}
        .navlink.card .mdi {{ font-size: 32px; color: #58a6ff; }}
        .navlink.text-only {{ color: #58a6ff; text-decoration: underline; }}
        .navlink.icon-only {{
            width: 50px;
            height: 50px;
            background: rgba(88,166,255,0.15);
            border-radius: 50%;
            border: 2px solid #58a6ff;
        }}
        .navlink.icon-only .mdi {{ font-size: 24px; color: #58a6ff; }}
        /* Nav Menu Widget */
        .navmenu {{
            display: flex;
            gap: 8px;
            padding: 8px 16px;
            background: rgba(0,0,0,0.5);
            border-radius: 12px;
            backdrop-filter: blur(10px);
            justify-content: center;
            align-items: center;
            height: 100%;
        }}
        .navmenu .nav-item {{
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 8px 12px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s;
            color: rgba(255,255,255,0.6);
        }}
        .navmenu .nav-item:active {{ background: rgba(255,255,255,0.2); }}
        .navmenu .nav-item.active {{ background: #58a6ff; color: #fff; }}
        .navmenu .nav-item .mdi {{ font-size: 20px; margin-bottom: 4px; }}
        .navmenu .nav-dot {{
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: rgba(255,255,255,0.3);
            cursor: pointer;
        }}
        .navmenu .nav-dot.active {{ background: #58a6ff; transform: scale(1.2); }}
        /* Navigation */
        .visu-nav {{
            position: fixed;
            bottom: max(20px, env(safe-area-inset-bottom, 20px));
            left: 50%;
            transform: translateX(-50%);
            display: flex;
            gap: 8px;
            background: rgba(0,0,0,0.7);
            padding: 8px 16px;
            border-radius: 25px;
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            z-index: 1000;
        }}
        .visu-nav button {{
            background: rgba(255,255,255,0.1);
            border: none;
            color: #fff;
            padding: 8px 16px;
            border-radius: 15px;
            cursor: pointer;
            font-size: 12px;
        }}
        .visu-nav button.active {{
            background: #58a6ff;
        }}
        .visu-nav button:hover {{
            background: rgba(255,255,255,0.2);
        }}
        /* Fullscreen button */
        .fullscreen-btn {{
            position: fixed;
            top: max(10px, env(safe-area-inset-top, 10px));
            right: max(10px, env(safe-area-inset-right, 10px));
            background: rgba(0,0,0,0.5);
            border: none;
            color: #fff;
            width: 40px;
            height: 40px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 18px;
            z-index: 1000;
        }}
        /* Loading */
        .loading {{
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            color: #888;
        }}
    </style>
</head>
<body>
    <button class="fullscreen-btn" onclick="toggleFullscreen()">⛶</button>
    <div class="visu-wrapper" id="visuWrapper">
        <div class="visu-container" id="visuContainer">
            <div class="visu-canvas" id="visuCanvas">
                <div class="loading">Lade Visualisierung...</div>
            </div>
        </div>
    </div>
    <div class="visu-nav" id="visuNav"></div>
    
    <script>
        const API = '/api/v1';
        let visuPages = {{}};
        let currentPage = '{page_id}';
        let addresses = {{}};
        
        async function init() {{
            await loadAddresses();
            await loadVisuConfig();
            renderPage();
            scaleToFit();
            window.addEventListener('resize', scaleToFit);
            window.addEventListener('orientationchange', () => setTimeout(scaleToFit, 100));
            // Update values every 2 seconds
            setInterval(updateValues, 2000);
        }}
        
        function scaleToFit() {{
            const page = visuPages[currentPage];
            if (!page) return;
            
            const wrapper = document.getElementById('visuWrapper');
            const container = document.getElementById('visuContainer');
            const canvas = document.getElementById('visuCanvas');
            if (!container || !canvas || !wrapper) return;
            
            // Get page dimensions
            let pageWidth, pageHeight;
            if (page.size === 'phone') {{
                pageWidth = 375; pageHeight = 667;
            }} else if (page.size === 'tablet') {{
                pageWidth = 768; pageHeight = 1024;
            }} else if (page.size === 'desktop') {{
                pageWidth = 1920; pageHeight = 1080;
            }} else if (page.size === 'custom') {{
                pageWidth = page.customWidth || 1024;
                pageHeight = page.customHeight || 768;
            }} else {{
                // Auto size - no scaling needed
                container.style.transform = 'none';
                canvas.style.width = '100%';
                canvas.style.height = '100%';
                return;
            }}
            
            // Get actual available viewport size (accounts for safe areas)
            const viewportWidth = wrapper.clientWidth || window.innerWidth;
            const viewportHeight = wrapper.clientHeight || window.innerHeight;
            
            // Calculate scale to fit entire page in viewport
            const scaleX = viewportWidth / pageWidth;
            const scaleY = viewportHeight / pageHeight;
            // Use the smaller scale so entire page fits (no cropping)
            const scale = Math.min(scaleX, scaleY);
            
            // Set container size and scale
            container.style.width = pageWidth + 'px';
            container.style.height = pageHeight + 'px';
            container.style.transform = `scale(${{scale}})`;
            
            // Also set canvas size
            canvas.style.width = pageWidth + 'px';
            canvas.style.height = pageHeight + 'px';
            
            console.log('ScaleToFit: page', pageWidth, 'x', pageHeight, 'viewport', viewportWidth, 'x', viewportHeight, 'scale', scale.toFixed(3));
        }}
        
        async function loadAddresses() {{
            try {{
                const r = await fetch(API + '/group-addresses');
                const data = await r.json();
                data.forEach(a => {{
                    // Normalize: use last_value if value is not present
                    if (a.last_value !== undefined && a.value === undefined) {{
                        a.value = a.last_value;
                    }}
                    addresses[a.address] = a;
                }});
            }} catch(e) {{ console.error('Load addresses:', e); }}
        }}
        
        async function loadVisuConfig() {{
            try {{
                const r = await fetch(API + '/visu/config');
                visuPages = await r.json();
                renderNav();
            }} catch(e) {{ console.error('Load visu:', e); }}
        }}
        
        function renderNav() {{
            const nav = document.getElementById('visuNav');
            const pages = Object.values(visuPages);
            if (pages.length <= 1) {{
                nav.style.display = 'none';
                return;
            }}
            nav.innerHTML = pages.map(p => 
                `<button class="${{p.id === currentPage ? 'active' : ''}}" onclick="loadPage('${{p.id}}')">${{p.name}}</button>`
            ).join('');
        }}
        
        function loadPage(id) {{
            currentPage = id;
            renderPage();
            renderNav();
            // Update URL without reload
            history.replaceState(null, '', '/api/v1/visu/view/' + id);
        }}
        
        function renderPage() {{
            const page = visuPages[currentPage];
            if (!page) {{
                document.getElementById('visuCanvas').innerHTML = '<div class="loading">Seite nicht gefunden</div>';
                return;
            }}
            
            const canvas = document.getElementById('visuCanvas');
            
            // Apply size
            if (page.size === 'phone') {{
                canvas.style.width = '375px';
                canvas.style.height = '667px';
            }} else if (page.size === 'tablet') {{
                canvas.style.width = '768px';
                canvas.style.height = '1024px';
            }} else if (page.size === 'desktop') {{
                canvas.style.width = '1920px';
                canvas.style.height = '1080px';
            }} else if (page.size === 'custom') {{
                canvas.style.width = (page.customWidth || 1024) + 'px';
                canvas.style.height = (page.customHeight || 768) + 'px';
            }} else {{
                canvas.style.width = '100%';
                canvas.style.minHeight = '100vh';
            }}
            
            // Apply background
            if (page.bgColor) canvas.style.background = page.bgColor;
            if (page.bgImage) {{
                canvas.style.backgroundImage = `url('${{page.bgImage}}')`;
                canvas.style.backgroundSize = page.bgSize || 'cover';
            }}
            
            // Render widgets
            let html = '';
            (page.widgets || []).forEach(w => {{
                html += renderWidget(w);
            }});
            canvas.innerHTML = html || '<div class="loading" style="color:#555">Keine Widgets</div>';
            
            // Apply scaling after render
            setTimeout(scaleToFit, 0);
        }}
        
        function renderWidget(w) {{
            const addr = w.addr || w.ko1;
            const addrData = addresses[addr] || {{}};
            const value = addrData.value !== undefined ? addrData.value : '--';
            const v = w.vars || {{}};
            
            if (w.type === 'vse') {{
                const vseId = (w.vseId || '').toLowerCase();
                const vseName = (w.vseName || '').toLowerCase();
                if (vseId.includes('switch') || vseName.includes('switch') || vseName.includes('light')) {{
                    return renderSwitchCard(w, v, value);
                }}
                return renderSensorCard(w, v, value);
            }} else if (w.type === 'navlink') {{
                return renderNavLink(w);
            }} else if (w.type === 'navmenu') {{
                return renderNavMenu(w);
            }}
            return '';
        }}
        
        function renderNavLink(w) {{
            const targetPage = visuPages[w.targetPage];
            const pageName = targetPage?.name || w.targetPage;
            const icon = w.icon || 'arrow-right-circle';
            const style = w.style || 'button';
            const width = w.width || 120;
            const height = w.height || 40;
            
            let content = '';
            if(style === 'icon') {{
                content = `<div class="navlink icon-only" onclick="loadPage('${{w.targetPage}}')" title="${{pageName}}"><span class="mdi mdi-${{icon}}"></span></div>`;
            }} else if(style === 'text') {{
                content = `<div class="navlink text-only" onclick="loadPage('${{w.targetPage}}')">${{w.label || pageName}}</div>`;
            }} else if(style === 'card') {{
                content = `<div class="navlink card" onclick="loadPage('${{w.targetPage}}')"><span class="mdi mdi-${{icon}}"></span><span>${{w.label || pageName}}</span></div>`;
            }} else {{
                content = `<div class="navlink button" onclick="loadPage('${{w.targetPage}}')"><span class="mdi mdi-${{icon}}"></span><span>${{w.label || pageName}}</span></div>`;
            }}
            
            return `<div class="visu-element" style="left:${{w.x}}px;top:${{w.y}}px;width:${{width}}px;height:${{height}}px">${{content}}</div>`;
        }}
        
        function renderNavMenu(w) {{
            const pages = Object.values(visuPages);
            const style = w.style || 'icons';
            
            let menuHtml = pages.map(p => {{
                const isActive = p.id === currentPage;
                const pageIcon = p.icon || 'file-document-outline';
                if(style === 'dots') {{
                    return `<span class="nav-dot ${{isActive?'active':''}}" onclick="loadPage('${{p.id}}')" title="${{p.name}}"></span>`;
                }} else if(style === 'text') {{
                    return `<span class="nav-item ${{isActive?'active':''}}" onclick="loadPage('${{p.id}}')">${{p.name}}</span>`;
                }} else {{
                    return `<span class="nav-item ${{isActive?'active':''}}" onclick="loadPage('${{p.id}}')"><span class="mdi mdi-${{pageIcon}}"></span><span>${{p.name}}</span></span>`;
                }}
            }}).join('');
            
            return `<div class="visu-element" style="left:${{w.x}}px;top:${{w.y}}px;width:${{w.width||300}}px;height:${{w.height||60}}px"><div class="navmenu ${{w.style||'icons'}}">${{menuHtml}}</div></div>`;
        }}
        
        function renderSensorCard(w, v, rawValue) {{
            const numVal = parseFloat(rawValue) || 0;
            const decimals = parseInt(v.decimals || v.var3) || 1;
            const displayValue = isNaN(numVal) ? rawValue : numVal.toFixed(decimals);
            
            const icon = v.icon || v.var1 || 'thermometer';
            const label = v.label || v.var2 || w.label || 'Sensor';
            const unit = v.unit || '';
            const iconColor = v.iconColor || '#58a6ff';
            const iconSize = parseInt(v.iconSize || v.var4) || 28;
            const labelColor = v.labelColor || '#888888';
            const labelSize = parseInt(v.labelSize) || 12;
            const valueColor = v.valueColor || '#ffffff';
            const valueSize = parseInt(v.valueSize) || 22;
            const bgColor = v.bgColor || 'rgba(255,255,255,0.06)';
            const borderColor = v.borderColor || 'rgba(88,166,255,0.4)';
            const borderRadius = parseInt(v.borderRadius || v.var12) || 12;
            const borderWidth = parseFloat(v.borderWidth) || 1.5;
            
            // Navigation support
            const navTarget = v.navTarget || '';
            const navIndicator = v.navIndicator || '';
            const isClickable = navTarget && visuPages[navTarget];
            const clickHandler = isClickable ? `onclick="loadPage('${{navTarget}}')"` : '';
            const cursorStyle = isClickable ? 'cursor:pointer;' : '';
            
            // Navigation indicator
            let indicatorHtml = '';
            if (isClickable && navIndicator) {{
                const indicatorIcon = navIndicator === 'arrow' ? 'arrow-right' : 
                                     navIndicator === 'chevron' ? 'chevron-right' : 
                                     navIndicator === 'dots' ? 'dots-horizontal' : '';
                if (indicatorIcon) {{
                    indicatorHtml = `<span class="mdi mdi-${{indicatorIcon}}" style="font-size:18px;color:${{labelColor}};opacity:0.6"></span>`;
                }}
            }}
            
            return `
                <div class="visu-element" data-addr="${{w.addr||w.ko1}}" style="left:${{w.x}}px;top:${{w.y}}px;width:${{w.width||200}}px;height:${{w.height||60}}px">
                    <div class="sensor-card" ${{clickHandler}} style="background:${{bgColor}};border:${{borderWidth}}px solid ${{borderColor}};border-radius:${{borderRadius}}px;${{cursorStyle}}">
                        <span class="mdi mdi-${{icon}} sensor-card-icon" style="font-size:${{iconSize}}px;color:${{iconColor}}"></span>
                        <div class="sensor-card-content">
                            <div class="sensor-card-label" style="font-size:${{labelSize}}px;color:${{labelColor}}">${{label}}</div>
                            <div class="sensor-card-value" style="font-size:${{valueSize}}px;color:${{valueColor}}">${{displayValue}} ${{unit}}</div>
                        </div>
                        ${{indicatorHtml}}
                    </div>
                </div>
            `;
        }}
        
        function renderSwitchCard(w, v, rawValue) {{
            const isOn = rawValue === '1' || rawValue === true || rawValue === 'True' || parseFloat(rawValue) > 0;
            
            // Parse RGB string to CSS color
            const parseColor = (color, fallback) => {{
                if (!color) return fallback;
                if (color.startsWith('#')) return color;
                if (color.includes(',')) return 'rgb(' + color + ')';
                return fallback;
            }};
            
            // Icons
            const mainIcon = v.icon || v.var1 || 'lightbulb';
            const badgeIcon = v.badgeIcon || v.var2 || 'power';
            const iconSize = parseInt(v.iconSize || v.var7) || 40;
            const badgeSize = parseInt(v.badgeSize || v.var8) || 18;
            const badgeIconSize = Math.round(badgeSize * 0.65);
            const badgePosition = parseInt(v.badgePosition || v.var12) || 50;
            const badgeOffset = Math.round((100 - badgePosition) / 100 * badgeSize);
            
            // Icon Colors
            const colorOn = parseColor(v.colorOn || v.var3, '#ffc107');
            const colorOff = parseColor(v.colorOff || v.var4, '#9e9e9e');
            const color = isOn ? colorOn : colorOff;
            
            const badgeColorOn = parseColor(v.badgeColorOn || v.var13, '#4caf50');
            const badgeColorOff = parseColor(v.badgeColorOff || v.var14, '#f44336');
            const badgeColor = isOn ? badgeColorOn : badgeColorOff;
            
            // Border Colors (var17, var18) - separate from icon color
            const borderColorOn = parseColor(v.borderColorOn || v.var17, colorOn);
            const borderColorOff = parseColor(v.borderColorOff || v.var18, colorOff);
            const borderBaseColor = isOn ? borderColorOn : borderColorOff;
            
            // Border style (var19, var20)
            const borderWidth = parseFloat(v.borderWidth || v.var19) || 1.5;
            const borderOpacity = parseFloat(v.borderOpacity || v.var20) || 45;
            
            // Text
            const textOn = v.textOn || v.var5 || 'An';
            const textOff = v.textOff || v.var6 || 'Aus';
            const statusText = isOn ? textOn : textOff;
            const label = v.label || w.label || 'Licht';
            
            // Style
            const borderRadius = parseInt(v.borderRadius || v.var9) || 12;
            const glowEnabled = v.var10 === '1' || v.var10 === true || v.glowEnabled === true;
            
            // KO1 = Rückmeldeadresse (Status), KO2 = Schaltadresse
            const statusAddr = w.ko1 || w.addr || '';
            const switchAddr = w.ko2 || w.ko1 || w.addr || '';
            const onClickHandler = statusAddr ? `onclick="toggleSwitch('${{statusAddr}}','${{switchAddr}}')"` : '';
            
            // Box shadow - use icon color for glow
            const colorRgb = color.startsWith('rgb') ? color.replace('rgb(','').replace(')','') : '255,193,7';
            const boxShadow = (glowEnabled && isOn)
                ? `0 8px 22px rgba(0,0,0,0.24), 0 0 0 1px rgba(${{colorRgb}},0.20), 0 0 18px rgba(${{colorRgb}},0.14)`
                : '0 4px 12px rgba(0,0,0,0.2)';
            
            // Border color with opacity
            const borderRgb = borderBaseColor.startsWith('rgb') 
                ? borderBaseColor.replace('rgb(','').replace(')','') 
                : '255,193,7';
            const borderColor = `rgba(${{borderRgb}},${{borderOpacity/100}})`;
            
            return `
                <div class="visu-element" data-addr="${{w.addr || w.ko1 || ''}}" data-switch="${{switchAddr}}" data-state="${{isOn ? '1' : '0'}}"
                     style="left:${{w.x}}px;top:${{w.y}}px;width:${{w.width||160}}px;height:${{w.height||130}}px">
                    <div class="switch-card" ${{onClickHandler}} style="
                        width:100%;height:100%;
                        display:flex;flex-direction:column;align-items:center;justify-content:center;
                        padding:8px;border-radius:${{borderRadius}}px;
                        border:${{borderWidth}}px solid ${{borderColor}};
                        background:rgba(255,255,255,0.06);
                        box-sizing:border-box;
                        box-shadow:${{boxShadow}};
                        cursor:${{switchAddr ? 'pointer' : 'default'}};
                        transition:transform 0.2s ease;
                    ">
                        <div style="position:relative;flex-shrink:0;margin-top:4px">
                            <div style="width:${{iconSize}}px;height:${{iconSize}}px;display:flex;align-items:center;justify-content:center">
                                <span class="mdi mdi-${{mainIcon}} switch-icon" style="font-size:${{iconSize}}px;color:${{color}};line-height:1"></span>
                            </div>
                            <span class="switch-badge" style="
                                position:absolute;top:${{badgeOffset}}px;right:${{badgeOffset}}px;
                                width:${{badgeSize}}px;height:${{badgeSize}}px;
                                background:rgba(30,30,30,0.9);border-radius:50%;
                                display:flex;align-items:center;justify-content:center;
                                border:2px solid ${{badgeColor}};
                                box-shadow:0 2px 4px rgba(0,0,0,0.3);
                            ">
                                <span class="mdi mdi-${{badgeIcon}}" style="font-size:${{badgeIconSize}}px;color:${{badgeColor}};line-height:1"></span>
                            </span>
                        </div>
                        <div style="font-size:13px;font-weight:500;color:rgba(255,255,255,0.9);margin-top:6px;text-align:center;line-height:1.2">${{label}}</div>
                        <div class="switch-status" style="font-size:14px;font-weight:600;color:${{color}};margin-top:2px">${{statusText}}</div>
                    </div>
                </div>
            `;
        }}
        
        async function toggleSwitch(statusAddr, switchAddr) {{
            // statusAddr = Rückmeldeadresse (KO1) - zum Status lesen
            // switchAddr = Schaltadresse (KO2) - zum Senden
            if (!statusAddr) return;
            const sendAddr = switchAddr || statusAddr;
            
            // Lese aktuellen Status von der Rückmeldeadresse
            const current = addresses[statusAddr]?.value;
            const isOn = (current === '1' || current === 1 || current === true || current === 'True' || parseFloat(current) > 0);
            const newVal = isOn ? 0 : 1;
            
            console.log('Toggle: Status', statusAddr, '=', current, '-> Sende', newVal, 'auf', sendAddr);
            try {{
                // API uses query parameters, not JSON body!
                await fetch(API + '/knx/send?group_address=' + encodeURIComponent(sendAddr) + '&value=' + newVal, {{
                    method: 'POST'
                }});
                setTimeout(updateValues, 500);
            }} catch(e) {{ console.error('Toggle switch:', e); }}
        }}
        
        async function updateValues() {{
            try {{
                const r = await fetch(API + '/group-addresses');
                const data = await r.json();
                data.forEach(a => {{
                    // Normalize: use last_value if value is not present
                    if (a.last_value !== undefined && a.value === undefined) {{
                        a.value = a.last_value;
                    }}
                    addresses[a.address] = a;
                }});
                
                // Update displayed values
                document.querySelectorAll('[data-addr]').forEach(el => {{
                    const addr = el.dataset.addr;
                    const addrData = addresses[addr];
                    if (addrData) {{
                        // Sensor Card
                        const valueEl = el.querySelector('.sensor-card-value');
                        if (valueEl) {{
                            const page = visuPages[currentPage];
                            const widget = (page?.widgets || []).find(w => (w.addr || w.ko1) === addr);
                            if (widget) {{
                                const v = widget.vars || {{}};
                                const decimals = parseInt(v.decimals || v.var3) || 1;
                                const unit = v.unit || '';
                                const numVal = parseFloat(addrData.value);
                                const displayValue = isNaN(numVal) ? addrData.value : numVal.toFixed(decimals);
                                valueEl.textContent = displayValue + ' ' + unit;
                            }}
                        }}
                        
                        // Switch Card
                        const switchCard = el.querySelector('.switch-card');
                        if (switchCard) {{
                            const page = visuPages[currentPage];
                            const widget = (page?.widgets || []).find(w => (w.addr || w.ko1) === addr);
                            if (widget) {{
                                const v = widget.vars || {{}};
                                const isOn = addrData.value === '1' || addrData.value === 1 || addrData.value === true;
                                
                                const parseColor = (color, fallback) => {{
                                    if (!color) return fallback;
                                    if (color.startsWith('#')) return color;
                                    if (color.includes(',')) return 'rgb(' + color + ')';
                                    return fallback;
                                }};
                                
                                const colorOn = parseColor(v.colorOn || v.var3, '#ffc107');
                                const colorOff = parseColor(v.colorOff || v.var4, '#9e9e9e');
                                const color = isOn ? colorOn : colorOff;
                                
                                const badgeColorOn = parseColor(v.badgeColorOn || v.var13, '#4caf50');
                                const badgeColorOff = parseColor(v.badgeColorOff || v.var14, '#f44336');
                                const badgeColor = isOn ? badgeColorOn : badgeColorOff;
                                
                                const textOn = v.textOn || v.var5 || 'An';
                                const textOff = v.textOff || v.var6 || 'Aus';
                                
                                // Update icon color
                                const iconEl = el.querySelector('.switch-icon');
                                if (iconEl) iconEl.style.color = color;
                                
                                // Update badge
                                const badgeEl = el.querySelector('.switch-badge');
                                if (badgeEl) {{
                                    badgeEl.style.borderColor = badgeColor;
                                    const badgeIconEl = badgeEl.querySelector('.mdi');
                                    if (badgeIconEl) badgeIconEl.style.color = badgeColor;
                                }}
                                
                                // Update status text
                                const statusEl = el.querySelector('.switch-status');
                                if (statusEl) {{
                                    statusEl.textContent = isOn ? textOn : textOff;
                                    statusEl.style.color = color;
                                }}
                                
                                // Update border with separate border colors
                                const borderColorOn = parseColor(v.borderColorOn || v.var17, colorOn);
                                const borderColorOff = parseColor(v.borderColorOff || v.var18, colorOff);
                                const borderBaseColor = isOn ? borderColorOn : borderColorOff;
                                const borderOpacity = parseFloat(v.borderOpacity || v.var20) || 45;
                                const borderRgb = borderBaseColor.startsWith('rgb') 
                                    ? borderBaseColor.replace('rgb(','').replace(')','') 
                                    : '255,193,7';
                                const borderColor = `rgba(${{borderRgb}},${{borderOpacity/100}})`;
                                switchCard.style.borderColor = borderColor;
                                
                                // Update data-state for next toggle
                                el.dataset.state = isOn ? '1' : '0';
                            }}
                        }}
                    }}
                }});
            }} catch(e) {{ console.error('Update values:', e); }}
        }}
        
        function toggleFullscreen() {{
            if (!document.fullscreenElement) {{
                document.documentElement.requestFullscreen();
            }} else {{
                document.exitFullscreen();
            }}
        }}
        
        init();
    </script>
</body>
</html>'''
