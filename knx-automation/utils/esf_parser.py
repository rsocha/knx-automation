import zipfile
import xml.etree.ElementTree as ET
import re
import logging
from pathlib import Path
from typing import List, Optional, Dict

from models import GroupAddressCreate

logger = logging.getLogger(__name__)

class ESFParser:
    """Parser for ESF files, knxproj files, and various ETS export formats"""
    
    def __init__(self, esf_file_path: str, password: str = None):
        self.esf_path = Path(esf_file_path)
        self.password = password
        self.group_addresses = []
        self.project_info = {}
        logger.info(f"ESFParser init: file={esf_file_path}, password={'YES ('+str(len(password))+' chars)' if password else 'NO'}")
    
    def parse(self) -> List[GroupAddressCreate]:
        if not self.esf_path.exists():
            raise FileNotFoundError(f"File not found: {self.esf_path}")
        
        logger.info(f"Parsing: {self.esf_path}")
        
        # Check file type
        filename = self.esf_path.name.lower()
        
        if filename.endswith('.knxproj'):
            return self._parse_knxproj()
        elif filename.endswith('.esf'):
            return self._parse_esf()
        else:
            # Try to detect format
            try:
                with zipfile.ZipFile(self.esf_path, 'r') as zf:
                    if any('knx_master.xml' in f for f in zf.namelist()):
                        return self._parse_knxproj()
                    else:
                        return self._parse_esf()
            except zipfile.BadZipFile:
                return self._parse_esf()
    
    def _parse_knxproj(self) -> List[GroupAddressCreate]:
        """Parse ETS5/ETS6 knxproj file"""
        import tempfile
        import os
        
        logger.info(f"Parsing knxproj file, password provided: {self.password is not None and len(self.password or '') > 0}")
        
        try:
            with zipfile.ZipFile(self.esf_path, 'r') as outer_zip:
                # Find project zip (P-XXXX.zip)
                project_zips = [f for f in outer_zip.namelist() if f.startswith('P-') and f.endswith('.zip')]
                
                if not project_zips:
                    logger.warning("No project zip found in knxproj")
                    return []
                
                project_zip_name = project_zips[0]
                logger.info(f"Found project: {project_zip_name}")
                
                # Extract project zip to temp location
                with tempfile.TemporaryDirectory() as tmpdir:
                    outer_zip.extract(project_zip_name, tmpdir)
                    project_zip_path = Path(tmpdir) / project_zip_name
                    
                    # Check if inner zip uses AES encryption (method 99)
                    is_encrypted = False
                    try:
                        with zipfile.ZipFile(project_zip_path, 'r') as test_zip:
                            for info in test_zip.infolist():
                                if info.compress_type == 99:  # AES encryption
                                    is_encrypted = True
                                    break
                            if not is_encrypted:
                                # Try to read - unencrypted
                                self._parse_project_xml(test_zip, tmpdir)
                                return self.group_addresses
                    except Exception as e:
                        logger.info(f"Standard zipfile check failed: {e}")
                        is_encrypted = True
                    
                    if is_encrypted:
                        logger.info("Project zip is encrypted, trying pyzipper")
                        extracted = False
                        last_error = None
                        
                        # Try pyzipper first
                        try:
                            import pyzipper
                            
                            # Build password list with different encodings
                            passwords_to_try = []
                            if self.password:
                                # Try different encodings
                                pwd_str = self.password
                                passwords_to_try.append(pwd_str.encode('utf-8'))
                                passwords_to_try.append(pwd_str.encode('latin-1'))
                                passwords_to_try.append(pwd_str.encode('cp1252'))
                                # Also try raw bytes if already bytes
                                if isinstance(self.password, bytes):
                                    passwords_to_try.insert(0, self.password)
                                logger.info(f"Will try user-provided password with multiple encodings (length: {len(self.password)})")
                            
                            # Add empty passwords last
                            passwords_to_try.extend([b'', None])
                            
                            for i, pwd in enumerate(passwords_to_try):
                                try:
                                    logger.info(f"Trying pyzipper password {i+1}/{len(passwords_to_try)}: {type(pwd)}")
                                    with pyzipper.AESZipFile(project_zip_path) as inner_zip:
                                        if pwd is not None:
                                            inner_zip.setpassword(pwd)
                                        inner_zip.extractall(tmpdir)
                                        extracted = True
                                        logger.info(f"Successfully extracted with pyzipper password attempt {i+1}")
                                        break
                                except RuntimeError as e:
                                    last_error = str(e)
                                    logger.info(f"pyzipper attempt {i+1} failed: {e}")
                                    continue
                                except Exception as e:
                                    last_error = str(e)
                                    logger.info(f"pyzipper attempt {i+1} error: {type(e).__name__}: {e}")
                                    continue
                        except ImportError:
                            logger.info("pyzipper nicht installiert, versuche 7z")
                        
                        # Try 7z as fallback
                        if not extracted and self.password:
                            logger.info("Trying 7z as fallback...")
                            import subprocess
                            try:
                                result = subprocess.run(
                                    ['7z', 'x', f'-p{self.password}', str(project_zip_path), f'-o{tmpdir}', '-y'],
                                    capture_output=True, text=True, timeout=30
                                )
                                if result.returncode == 0:
                                    extracted = True
                                    logger.info("Successfully extracted with 7z")
                                else:
                                    logger.info(f"7z failed: {result.stderr or result.stdout}")
                                    last_error = result.stderr or result.stdout
                            except FileNotFoundError:
                                logger.info("7z not installed")
                            except subprocess.TimeoutExpired:
                                logger.info("7z timeout")
                            except Exception as e:
                                logger.info(f"7z error: {e}")
                        
                        if not extracted:
                            logger.error(f"Could not decrypt project zip. Last error: {last_error}")
                            raise ValueError("knxproj Datei ist passwortgeschützt. Bitte korrektes Passwort eingeben oder in ETS ohne Verschlüsselung exportieren.")
                        
                        # Find and parse 0.xml
                        zero_xml = Path(tmpdir) / '0.xml'
                        if zero_xml.exists():
                            self._parse_zero_xml(zero_xml)
                        else:
                            # Search for it
                            for root, dirs, files in os.walk(tmpdir):
                                if '0.xml' in files:
                                    self._parse_zero_xml(Path(root) / '0.xml')
                                    break
                
        except Exception as e:
            logger.error(f"knxproj parse error: {e}")
            raise
        
        logger.info(f"Found {len(self.group_addresses)} group addresses")
        return self.group_addresses
    
    def _parse_project_xml(self, zip_ref, tmpdir):
        """Parse project XML from knxproj"""
        file_list = zip_ref.namelist()
        
        # Look for 0.xml (group addresses)
        zero_xml = None
        for f in file_list:
            if f.endswith('0.xml') or f == '0.xml':
                zero_xml = f
                break
        
        if zero_xml:
            zip_ref.extract(zero_xml, tmpdir)
            self._parse_zero_xml(Path(tmpdir) / zero_xml)
    
    def _parse_zero_xml(self, xml_path: Path):
        """Parse the 0.xml file containing group addresses"""
        logger.info(f"Parsing {xml_path}")
        
        with open(xml_path, 'rb') as f:
            content = f.read()
        
        # Remove BOM if present
        if content.startswith(b'\xef\xbb\xbf'):
            content = content[3:]
        
        # Try different encodings
        for encoding in ['utf-8', 'iso-8859-1', 'cp1252']:
            try:
                root = ET.fromstring(content.decode(encoding))
                break
            except:
                continue
        else:
            raise ValueError("Could not decode XML file")
        
        # Parse group addresses
        self._parse_ets_group_addresses(root)
    
    def _parse_ets_group_addresses(self, root):
        """Parse group addresses from ETS XML format"""
        # Namespace handling
        ns = {}
        if root.tag.startswith('{'):
            ns_end = root.tag.find('}')
            ns['knx'] = root.tag[1:ns_end]
        
        # Find GroupAddress elements
        for elem in root.iter():
            tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            
            if tag == 'GroupAddress':
                addr_raw = elem.get('Address', '')
                name = elem.get('Name', '')
                dpt = elem.get('DatapointType', '')
                description = elem.get('Description', '')
                
                if not addr_raw:
                    continue
                
                # Convert numeric address to x/y/z format
                try:
                    addr_int = int(addr_raw)
                    main = (addr_int >> 11) & 0x1F
                    middle = (addr_int >> 8) & 0x07
                    sub = addr_int & 0xFF
                    address = f'{main}/{middle}/{sub}'
                except:
                    address = addr_raw
                
                if address and '/' in address:
                    self.group_addresses.append(GroupAddressCreate(
                        address=address,
                        name=name or description or f"GA_{address}",
                        dpt=self._normalize_dpt(dpt),
                        enabled=True
                    ))
        
        logger.info(f"Parsed {len(self.group_addresses)} addresses from ETS XML")
    
    def _parse_esf(self) -> List[GroupAddressCreate]:
        """Parse ESF (ETS3/4 export) file"""
        logger.info("Parsing ESF file")
        
        try:
            with zipfile.ZipFile(self.esf_path, 'r') as zip_ref:
                logger.info("File is a ZIP archive")
                self._parse_zip(zip_ref)
        except zipfile.BadZipFile:
            logger.info("Not a ZIP, trying as text/XML")
            with open(self.esf_path, 'rb') as f:
                header = f.read(500)
            
            if b'<?xml' in header or b'<KNX' in header:
                self._parse_xml_file()
            else:
                self._parse_text_file()
        
        logger.info(f"Found {len(self.group_addresses)} group addresses")
        return self.group_addresses
    
    def _parse_zip(self, zip_ref):
        file_list = zip_ref.namelist()
        
        xml_file = None
        for file in file_list:
            if file.endswith('/0.xml') or file == '0.xml':
                xml_file = file
                break
        
        if not xml_file:
            xml_files = [f for f in file_list if f.endswith('.xml') and 'project' not in f.lower()]
            if xml_files:
                xml_file = xml_files[0]
        
        if not xml_file:
            raise ValueError("No XML file found in archive")
        
        logger.info(f"Reading: {xml_file}")
        
        with zip_ref.open(xml_file) as f:
            content = f.read()
            
            if content.startswith(b'\xef\xbb\xbf'):
                content = content[3:]
            
            try:
                root = ET.fromstring(content.decode('utf-8'))
            except:
                root = ET.fromstring(content.decode('iso-8859-1'))
            
            self._parse_group_addresses(root)
    
    def _parse_xml_file(self):
        with open(self.esf_path, 'rb') as f:
            content = f.read()
        
        if content.startswith(b'\xef\xbb\xbf'):
            content = content[3:]
        
        for encoding in ['utf-8', 'iso-8859-1', 'cp1252']:
            try:
                root = ET.fromstring(content.decode(encoding))
                break
            except:
                continue
        
        self._parse_group_addresses(root)
    
    def _parse_text_file(self):
        for encoding in ['utf-8', 'iso-8859-1', 'cp1252']:
            try:
                with open(self.esf_path, 'r', encoding=encoding) as f:
                    content = f.read()
                break
            except:
                continue
        
        lines = content.strip().split('\n')
        start_line = 0
        
        if lines and '\t' not in lines[0]:
            self.project_info['name'] = lines[0].strip()
            start_line = 1
        
        for line in lines[start_line:]:
            line = line.strip()
            if not line:
                continue
            
            parts = line.split('\t')
            if len(parts) < 2:
                continue
            
            path_and_address = parts[0].strip()
            name = parts[1].strip() if len(parts) > 1 else ''
            dpt_raw = parts[2].strip() if len(parts) > 2 else ''
            
            ga_match = re.search(r'(\d+/\d+/\d+)', path_and_address)
            if ga_match:
                address = ga_match.group(1)
                
                path_parts = path_and_address[:ga_match.start()].rstrip('.').split('.')
                function = path_parts[0] if path_parts and path_parts[0] else None
                room = path_parts[-1] if len(path_parts) > 1 else None
                
                dpt = self._convert_eis_to_dpt(dpt_raw) if dpt_raw else None
                
                self.group_addresses.append(GroupAddressCreate(
                    address=address,
                    name=name or f"GA_{address}",
                    dpt=dpt,
                    room=room,
                    function=function,
                    enabled=True
                ))
    
    def _parse_group_addresses(self, root):
        ns = {}
        if root.tag.startswith('{'):
            ns_end = root.tag.find('}')
            ns = {'knx': root.tag[1:ns_end]}
        
        found = False
        for elem in root.iter():
            tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            
            if tag == 'GroupAddress' and 'Address' in elem.attrib:
                found = True
                addr_raw = elem.get('Address', '')
                name = elem.get('Name', '')
                dpt = elem.get('DatapointType', '')
                
                try:
                    addr_int = int(addr_raw)
                    main = (addr_int >> 11) & 0x1F
                    middle = (addr_int >> 8) & 0x07
                    sub = addr_int & 0xFF
                    address = f'{main}/{middle}/{sub}'
                except:
                    address = addr_raw
                
                if address:
                    self.group_addresses.append(GroupAddressCreate(
                        address=address,
                        name=name or f"GA_{address}",
                        dpt=self._normalize_dpt(dpt),
                        enabled=True
                    ))
        
        if not found:
            logger.info("No group addresses found - trying alternative search")
            self._parse_group_addresses_alternative(root)
    
    def _parse_group_addresses_alternative(self, root):
        for elem in root.iter():
            attribs = elem.attrib
            if 'Address' in attribs or 'address' in attribs:
                addr = attribs.get('Address', attribs.get('address', ''))
                name = attribs.get('Name', attribs.get('name', ''))
                
                if '/' in str(addr) or (addr.isdigit() and int(addr) > 0):
                    try:
                        if addr.isdigit():
                            addr_int = int(addr)
                            main = (addr_int >> 11) & 0x1F
                            middle = (addr_int >> 8) & 0x07
                            sub = addr_int & 0xFF
                            address = f'{main}/{middle}/{sub}'
                        else:
                            address = addr
                        
                        if address and not any(ga.address == address for ga in self.group_addresses):
                            self.group_addresses.append(GroupAddressCreate(
                                address=address,
                                name=name or f"GA_{address}",
                                enabled=True
                            ))
                    except:
                        pass
    
    def _convert_eis_to_dpt(self, eis_string: str) -> Optional[str]:
        eis_to_dpt = {
            'EIS 1': '1.001', 'EIS 2': '3.007', 'EIS 3': '10.001',
            'EIS 4': '11.001', 'EIS 5': '9.001', 'EIS 6': '5.001',
        }
        
        for eis, dpt in eis_to_dpt.items():
            if eis in eis_string:
                return dpt
        
        return None
    
    def _normalize_dpt(self, dpt: str) -> Optional[str]:
        if not dpt:
            return None
        
        # Handle DPST-X-Y format
        match = re.search(r'DPST?-?(\d+)-?(\d+)?', dpt)
        if match:
            main = match.group(1)
            sub = match.group(2) or '001'
            return f"{main}.{sub.zfill(3)}"
        
        # Handle X.YYY format
        match = re.search(r'(\d+)\.(\d+)', dpt)
        if match:
            return f"{match.group(1)}.{match.group(2).zfill(3)}"
        
        return dpt if dpt else None
