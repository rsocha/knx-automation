"""
VSE (Visual Element) Parser for EDOMI-compatible visualization elements
"""
import re
import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class VSEParser:
    """Parser for EDOMI VSE files"""
    
    def __init__(self, vse_path: str = "data/vse"):
        self.vse_path = Path(vse_path)
        self.vse_path.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, Dict] = {}
    
    def parse_file(self, filepath: str) -> Optional[Dict]:
        """Parse a single VSE file"""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            vse = {
                'id': Path(filepath).stem.split('_')[0],
                'filename': Path(filepath).name,
                'def': {},
                'properties': [],
                'editor_js': '',
                'visu_js': '',
                'shared_js': '',
                'help': ''
            }
            
            # Parse DEF section
            def_match = re.search(r'###\[DEF\]###(.*?)###\[/DEF\]###', content, re.DOTALL)
            if def_match:
                vse['def'] = self._parse_def(def_match.group(1))
            
            # Parse PROPERTIES section
            props_match = re.search(r'###\[PROPERTIES\]###(.*?)###\[/PROPERTIES\]###', content, re.DOTALL)
            if props_match:
                vse['properties'] = self._parse_properties(props_match.group(1))
            
            # Parse JS sections
            editor_match = re.search(r'###\[EDITOR\.JS\]###(.*?)###\[/EDITOR\.JS\]###', content, re.DOTALL)
            if editor_match:
                vse['editor_js'] = editor_match.group(1).strip()
            
            visu_match = re.search(r'###\[VISU\.JS\]###(.*?)###\[/VISU\.JS\]###', content, re.DOTALL)
            if visu_match:
                vse['visu_js'] = visu_match.group(1).strip()
            
            shared_match = re.search(r'###\[SHARED\.JS\]###(.*?)###\[/SHARED\.JS\]###', content, re.DOTALL)
            if shared_match:
                vse['shared_js'] = shared_match.group(1).strip()
            
            # Parse HELP section
            help_match = re.search(r'###\[HELP\]###(.*?)###\[/HELP\]###', content, re.DOTALL)
            if help_match:
                vse['help'] = help_match.group(1).strip()
            
            return vse
            
        except Exception as e:
            logger.error(f"Error parsing VSE file {filepath}: {e}")
            return None
    
    def _parse_def(self, content: str) -> Dict:
        """Parse DEF section"""
        result = {
            'name': 'Unknown',
            'xsize': 100,
            'ysize': 50,
            'text': '',
            'vars': {},
            'flags': {}
        }
        
        for line in content.strip().split('\n'):
            line = line.strip()
            if not line or not line.startswith('['):
                continue
            
            match = re.match(r'\[(\w+)\s*=\s*(.+)\]', line)
            if match:
                key = match.group(1)
                value = match.group(2).strip()
                
                if key == 'name':
                    result['name'] = value
                elif key == 'xsize':
                    result['xsize'] = int(value)
                elif key == 'ysize':
                    result['ysize'] = int(value)
                elif key == 'text':
                    result['text'] = value
                elif key.startswith('var'):
                    result['vars'][key] = value
                elif key.startswith('flag'):
                    result['flags'][key] = value == '1'
                elif key.startswith('caption'):
                    result[key] = value
        
        return result
    
    def _parse_properties(self, content: str) -> List[Dict]:
        """Parse PROPERTIES section"""
        properties = []
        current_row = None
        
        for line in content.strip().split('\n'):
            line = line.strip()
            if not line or not line.startswith('['):
                continue
            
            # Row definition
            if line.startswith('[row'):
                row_match = re.match(r'\[row(?:=(.+))?\]', line)
                if row_match:
                    current_row = row_match.group(1) or ''
                continue
            
            # Column definition (skip)
            if line.startswith('[columns'):
                continue
            
            # Variable definition
            var_match = re.match(r'\[(var\d+)\s*=\s*(.+)\]', line)
            if var_match:
                var_name = var_match.group(1)
                var_def = var_match.group(2)
                
                # Parse: type,span,'label','default' or type,span,'label','options'
                parts = []
                in_quote = False
                current = ''
                for char in var_def:
                    if char == "'" and not in_quote:
                        in_quote = True
                    elif char == "'" and in_quote:
                        in_quote = False
                    elif char == ',' and not in_quote:
                        parts.append(current.strip().strip("'"))
                        current = ''
                        continue
                    current += char
                parts.append(current.strip().strip("'"))
                
                if len(parts) >= 4:
                    prop = {
                        'var': var_name,
                        'type': parts[0],
                        'span': int(parts[1]) if parts[1].isdigit() else 1,
                        'label': parts[2],
                        'default': parts[3],
                        'row': current_row
                    }
                    
                    # Parse select options
                    if parts[0] == 'select' and '#' in parts[3]:
                        options = []
                        for opt in parts[3].split('|'):
                            if '#' in opt:
                                val, label = opt.split('#', 1)
                                options.append({'value': val, 'label': label})
                        prop['options'] = options
                    
                    properties.append(prop)
        
        return properties
    
    def get_all_elements(self) -> List[Dict]:
        """Get all available VSE elements"""
        elements = []
        
        for filepath in self.vse_path.glob('*_vse.php'):
            vse = self.parse_file(str(filepath))
            if vse:
                elements.append({
                    'id': vse['id'],
                    'name': vse['def'].get('name', 'Unknown'),
                    'filename': vse['filename'],
                    'xsize': vse['def'].get('xsize', 100),
                    'ysize': vse['def'].get('ysize', 50),
                    'text': vse['def'].get('text', ''),
                    'vars': vse['def'].get('vars', {}),
                    'properties': vse['properties']
                })
        
        return sorted(elements, key=lambda x: x['id'])
    
    def get_element(self, element_id: str) -> Optional[Dict]:
        """Get a specific VSE element by ID"""
        for filepath in self.vse_path.glob(f'{element_id}_vse.php'):
            return self.parse_file(str(filepath))
        return None
    
    def get_element_js(self, element_id: str) -> str:
        """Get combined JS for an element"""
        vse = self.get_element(element_id)
        if not vse:
            return ''
        
        # Replace VSEID placeholder with actual ID
        shared = vse['shared_js'].replace('VSE_VSEID', f'VSE_{element_id}')
        visu = vse['visu_js'].replace('VSE_VSEID', f'VSE_{element_id}')
        
        return f"{shared}\n\n{visu}"
    
    def save_element(self, filename: str, content: str) -> bool:
        """Save a VSE file"""
        try:
            filepath = self.vse_path / filename
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            logger.error(f"Error saving VSE file: {e}")
            return False
    
    def delete_element(self, filename: str) -> bool:
        """Delete a VSE file"""
        try:
            filepath = self.vse_path / filename
            if filepath.exists():
                filepath.unlink()
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting VSE file: {e}")
            return False


# Global instance
vse_parser = VSEParser()
