# KNX Automation

![Version](https://img.shields.io/badge/version-3.6.0-blue)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Raspberry_Pi_%7C_Linux-orange)](https://www.raspberrypi.com/)
[![KNX](https://img.shields.io/badge/KNX-IP_Tunneling-red)](https://www.knx.org/)
[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-18-blue?logo=react)](https://react.dev/)



Webbasierte KNX-Hausautomation mit visueller Logik-Engine, Dashboard und integrierter Gerätesteuerung.

## Features

### Dashboard & Visualisierung
- **VSE-Visualisierung** – Eigene Räume mit Widgets (Schalter, Dimmer, Jalousien, Mediaplayer, Szenen)
- **Custom Cards** – Frei konfigurierbare Karten mit KO-Bindung, bedingter Formatierung und Glassmorphic Design
- **Energie-Dashboard** – PV-Ertrag, Batteriespeicher, Verbrauch und Strompreis (EPEX Spot) in Echtzeit
- **Charts** – Historische Diagramme für Energie, Temperatur, Luftfeuchtigkeit mit konfigurierbaren KO-Bindungen

### Logik-Engine
- **Visuelle Programmierung** – Bausteine per Drag & Drop verbinden (React Flow)
- **Seiten & Räume** – Logik nach Räumen gruppiert mit freier Namensgebung
- **IKO-Adressen** – Interne Kommunikation zwischen Bausteinen (auto-generiert)
- **KO-Bindung** – Gruppenadressen an Ein-/Ausgänge binden (durchsuchbar mit Filter)
- **Block-Dokumentation** – ? Button zeigt Doku, Versionshistorie und editierbaren Quellcode
- **Remanenz** – Bausteine können ihren Zustand über Reboots speichern (⚡ Icon im Header)
- **Hot-Reload** – Bausteine hochladen, Code bearbeiten, sofort neu laden

### Mitgelieferte Bausteine

| Nr. | Name | Kategorie | Version | Remanent | Beschreibung |
|-----|------|-----------|---------|----------|--------------|
| 20027 | SONOS Controller | Audio | 1.4 | ✅ | SOAP-Steuerung für Sonos (Play/Pause/Volume/Radio/TTS/Genre-Farben) |
| 20028 | FRITZ!DECT 200 | Energie | 1.0 | – | AVM Smart-Plug mit Leistungsmessung und Kostenberechnung |
| 20030 | Ecowitt WS90 | Wetter | 1.0 | – | Wetterstation (Temperatur, Wind, Regen, UV, Solar) |
| 20031 | OAuth2 TokenManager | System | 1.0 | – | OAuth2-Token-Verwaltung mit automatischem Refresh |
| 20032 | EPEX Spot Price | Energie | 1.0 | – | Strompreis-Abfrage (Awattar API) |
| 20033 | Netatmo Homecoach | Klima | 1.0 | – | Raumklima (CO₂, Temperatur, Luftfeuchtigkeit, Lärm) |
| 20042 | Sonne & Mond | Hilfsmittel | 2.0 | ✅ | Sonnenauf-/untergang, Dämmerung, Mondphase, Tag/Nacht |
| 20043 | Timer | Hilfsmittel | 2.1 | ✅ | Countdown-Timer mit HH:MM-Anzeige und Remanenz |
| 20044 | iCal-Termine | Kalender | 2.0 | – | Kalender-Abfrage mit 5 Suchslots und Vorwarnung |
| — | AND / OR / NOT | Logik | – | – | Logik-Gatter |
| — | Threshold | Logik | – | – | Schwellwert-Vergleich |
| — | Add / Multiply | Mathe | – | – | Rechenoperationen |
| — | MinMax | Mathe | – | – | Minimum/Maximum-Erkennung |

### Telegramm-Log
- **Persistenter WebSocket** – Log bleibt erhalten bei Seitenwechsel
- **Live-Anzeige** – KNX-Telegramme und IKO-Befehle in Echtzeit
- **Filter & Export** – Nach Adresse/Wert/Richtung filtern, CSV-Export

### Weitere Features
- KNX Gateway (KNXnet/IP Tunneling)
- ESF/knxproj Import für Gruppenadressen
- Backup & Restore
- Auto-Update über Dashboard
- Dark Theme

---

## Installation

### Voraussetzungen
- Raspberry Pi 4 oder Linux-Server (Ubuntu 22.04+, Debian 11+)
- Python 3.10+
- KNXnet/IP Gateway im Netzwerk

### Schnellinstallation
```bash
tar xzf knx-automation-v3.6.0.tar.gz
cd knx-automation
chmod +x install.sh
sudo ./install.sh
```

Oberfläche: **http://<IP>:8000**

---

## Update

### Über das Dashboard
Einstellungen → Update → `.tar.gz` hochladen → Automatischer Neustart

### Manuell
```bash
cd /opt/knx-automation
tar xzf knx-automation-v3.6.0.tar.gz --strip-components=1 --overwrite
find . -name "__pycache__" -exec rm -rf {} + 2>/dev/null
systemctl restart knx-automation
```

---

## Eigene Bausteine erstellen

Python-Dateien in `data/custom_blocks/`.

### Minimales Beispiel
```python
from logic.base import LogicBlock

class MeinBaustein(LogicBlock):
    ID = 99001
    NAME = "Mein Baustein"
    DESCRIPTION = "Kurzbeschreibung"
    VERSION = "1.0"
    CATEGORY = "Custom"
    REMANENT = False  # True für Zustandsspeicherung über Reboots

    HELP = """Funktionsweise:
Beschreibung was der Baustein tut.

Versionshistorie:
v1.0 – Erstversion"""

    INPUTS = {
        'E1': {'name': 'Eingang', 'type': 'int', 'default': 0},
    }
    OUTPUTS = {
        'A1': {'name': 'Ausgang', 'type': 'int', 'default': 0},
    }

    def execute(self, triggered_by=None):
        wert = self.get_input('E1')
        self.set_output('A1', wert * 2)
```

### Remanenter Baustein
```python
class MeinRemanentBlock(LogicBlock):
    REMANENT = True

    def get_remanent_state(self):
        """Wird alle 60s + bei Shutdown aufgerufen"""
        return {'mein_wert': self._counter}

    def restore_remanent_state(self, state):
        """Wird beim Start aufgerufen, vor on_start()"""
        self._counter = state.get('mein_wert', 0)
```

### Wichtige Hinweise
- `set_input()` Override **muss** `force_trigger=False` als Parameter haben
- `execute()` ist synchron – für async: `asyncio.ensure_future()` verwenden
- `debug(key, value)` für das Debug-Panel (nicht `set_debug`)
- HELP-Text: Zeilen die mit `:` enden werden als Überschriften dargestellt

---

## API

REST-API unter `http://<IP>:8000/api/`

| Methode | Pfad | Beschreibung |
|---------|------|--------------|
| GET | `/api/group-addresses` | Alle Gruppenadressen |
| POST | `/api/knx/send?group_address=1/2/3&value=1` | Telegramm senden |
| GET | `/api/logic/blocks` | Alle Logikblock-Instanzen |
| GET | `/api/logic/available-blocks` | Verfügbare Bausteintypen |
| GET | `/api/logic/block-type/{type}/source` | Quellcode eines Bausteins |
| WS | `/api/ws/telegrams` | WebSocket für Live-Telegramme |

---

## Changelog

### v3.6.0
- **Custom Card System**: Neue Karten mit visueller Konfiguration – Wert-Karten, Schalter, Markdown-Überschriften
- Glassmorphic Design mit Backdrop-Blur und konfigurierbarem Glow
- Bedingte Formatierung: Icon-Farbe, Rahmen, Glow ändern sich basierend auf KO-Wert
- Live-Vorschau im Card-Editor mit 3 Tabs (Grundlagen, Aussehen, Bedingungen)
- Icon-Palette mit 24 MDI-Vorlagen + Emoji-Support
- Aktionen: Toggle, Wert senden, Seitennavigation
- Templates: `{value}`, `{unit}` Platzhalter für Wertanzeige
- Update-Endpoint kopiert jetzt auch README.md, install.sh, requirements.txt
- Shields.io Badges in README

### v3.5.0
- Block-Dokumentation: ? Button mit Doku (HELP-Text, Ein-/Ausgänge) und editierbarem Quellcode
- HELP-Feld in der Basisklasse: Funktionsbeschreibung + Versionshistorie pro Baustein
- Remanenz-Framework: Bausteine speichern Zustand über Reboots (auto-save alle 60s + Shutdown)
- Code-Editor: Ctrl+A markiert nur Code (nicht ganze Seite), Ctrl+S speichert, Tab = 4 Leerzeichen
- Sonne & Mond v2.0: Trigger, Auto-Update, Dämmerung, Tag/Nacht, Mondbeleuchtung %, 8 Mondphasen
- Timer v2.1: Remanenz + neuer Ausgang A3 (Restzeit als HH:MM)
- SONOS Controller v1.4: Remanenz für Settings (Volume/Bass/IP), force_trigger Signatur-Fix
- iCal-Termine v2.0: Eigener Parser, file:// Support, Datumsvergleich-Fix
- Persistenter Telegramm-Log (WebSocket überlebt Seitenwechsel)
- Version-Anzeige korrigiert (war hardcoded auf 3.4.3)

### v3.4.x
- IKO-Routing (Prefix-Erkennung, Auto-Create, WebSocket-Broadcast)
- VSE Media Player Klick-Fix
- Logik-Seiten mit Raum-Gruppierung
- Energie-Dashboard mit KO-Binding
- ESF/knxproj Import, Charts, Backup & Restore

### v3.3.0
- Charts/Energy-Seite mit Recharts
- KO-Binding-Dialog mit Adresse/Name/Gruppen-Filter
- KNX Gateway Einstellungen

### v3.2.0
- Send Value Dialog
- Blaues Farbschema
- Logik-Editor mit IKO-Deduplication
- Browser-Cache-Fix

### v3.0.0
- Erstversion mit Dashboard, VSE-Visualisierung und Logik-Engine
