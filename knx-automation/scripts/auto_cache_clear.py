#!/usr/bin/env python3
"""
Auto Cache Cleaner für KNX Automation

Wird automatisch beim Systemstart ausgeführt und löscht den Python-Cache.
Verhindert, dass alte Versionen von Bausteinen im Cache bleiben.

Verwendung:
- Automatisch: Wird beim Systemstart aufgerufen
- Manuell: python3 auto_cache_clear.py
"""

import os
import sys
import shutil
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def clear_python_cache(root_dir='.'):
    """
    Löscht alle __pycache__ Ordner und .pyc Dateien
    
    Args:
        root_dir: Wurzelverzeichnis zum Durchsuchen
    
    Returns:
        Anzahl gelöschter Items
    """
    root_path = Path(root_dir).resolve()
    logger.info(f"Durchsuche: {root_path}")
    
    pycache_count = 0
    pyc_count = 0
    
    try:
        for root, dirs, files in os.walk(root_path):
            # Lösche __pycache__ Ordner
            if '__pycache__' in dirs:
                cache_path = os.path.join(root, '__pycache__')
                try:
                    shutil.rmtree(cache_path)
                    logger.debug(f"Gelöscht: {cache_path}")
                    pycache_count += 1
                except Exception as e:
                    logger.warning(f"Fehler bei {cache_path}: {e}")
            
            # Lösche .pyc Dateien
            for file in files:
                if file.endswith('.pyc'):
                    pyc_path = os.path.join(root, file)
                    try:
                        os.remove(pyc_path)
                        logger.debug(f"Gelöscht: {pyc_path}")
                        pyc_count += 1
                    except Exception as e:
                        logger.warning(f"Fehler bei {pyc_path}: {e}")
        
        total = pycache_count + pyc_count
        logger.info(f"Cache gelöscht: {pycache_count} Ordner, {pyc_count} Dateien")
        return total
        
    except Exception as e:
        logger.error(f"Fehler beim Cache-Löschen: {e}")
        return 0


def reload_logic_blocks():
    """
    Erzwingt Neuladung aller LogicBlock-Module
    """
    try:
        import importlib
        import sys
        
        # Finde alle geladenen logic.blocks Module
        to_reload = []
        for module_name in list(sys.modules.keys()):
            if module_name.startswith('logic.blocks.'):
                to_reload.append(module_name)
        
        # Lösche sie aus sys.modules
        for module_name in to_reload:
            logger.debug(f"Entlade Modul: {module_name}")
            del sys.modules[module_name]
        
        logger.info(f"Module entladen: {len(to_reload)}")
        return len(to_reload)
        
    except Exception as e:
        logger.error(f"Fehler beim Modul-Neuladen: {e}")
        return 0


def main():
    """Hauptfunktion"""
    logger.info("=" * 60)
    logger.info("KNX Automation - Auto Cache Cleaner")
    logger.info("=" * 60)
    
    # Bestimme Arbeitsverzeichnis
    if len(sys.argv) > 1:
        work_dir = sys.argv[1]
    else:
        # Wenn als Modul geladen, verwende das Projekt-Root
        work_dir = Path(__file__).parent.parent if Path(__file__).parent.name == 'scripts' else '.'
    
    # Cache löschen
    total = clear_python_cache(work_dir)
    
    # Module neu laden (nur wenn als Teil der Anwendung geladen)
    if 'logic' in sys.modules:
        reload_logic_blocks()
    
    logger.info("=" * 60)
    if total > 0:
        logger.info("✓ Cache erfolgreich gelöscht")
    else:
        logger.info("ℹ Kein Cache gefunden")
    logger.info("=" * 60)
    
    return 0 if total > 0 else 1


if __name__ == '__main__':
    sys.exit(main())
