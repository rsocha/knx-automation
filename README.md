# KNX Automation

![Version](https://img.shields.io/badge/version-3.6.6-blue)
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
tar xzf knx-automation-v3.6.1.tar.gz
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
tar xzf knx-automation-v3.6.1.tar.gz --strip-components=1 --overwrite
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

### v3.9.2
- **Resize komplett überarbeitet** – CSS-Scaling entfernt, Widgets bekommen echte Zielgröße; kein unscharfer Text, kein Clipping
- **Doppelklick zum Bearbeiten** – Keine schwebenden Buttons mehr; Doppelklick öffnet Bearbeiten-Dialog
- **Löschen-Button** – Kleiner Mülleimer unten links im Widget (Edit-Modus)
- **Edit-Modus** – Gestrichelte Umrandung, Hinweis "Doppelklick = Bearbeiten"

### v3.9.1
- **Panel Card** – `type: panel` mit Hold-Buttons, Status-Kacheln, Alert-Banner; Preset "Garage Panel"

### v3.9.0
- **Custom Cards proportional skalieren** – Beim Resize wird jetzt CSS `transform: scale()` verwendet statt den Inhalt abzuschneiden; Card wird in Design-Größe gerendert und dann auf die Zielgröße skaliert
- **Eigene Card-Vorlagen erstellen** – Im YAML-Tab: "Speichern" Button zum Anlegen eigener Presets, "Export" als .yaml Datei, "Import" von .yaml Dateien; eigene Vorlagen erscheinen im Bereich "Meine Vorlagen" mit Löschen-Option; Backend-API: GET/POST/DELETE `/api/v1/card-presets`

### v3.8.2
- **Müllabfuhr Datumslogik** – Entity liefert jetzt ein Datum (vom iCal-Baustein), Card berechnet automatisch Tage bis Abholung und zeigt "in X Tagen (DD.MM.)" / "Morgen (DD.MM.)" / "Heute (DD.MM.)"; Farbwechsel: 1 Tag vorher = Warnfarbe, am Tag = rot; "Nächste Abholung" wird automatisch aus dem frühesten Termin berechnet (kein extra `next_entity` KO nötig); Datumsformate: ISO `2025-03-22`, deutsch `22.03.2025` oder `22.03.`, Unix-Timestamp

### v3.8.1
- **Widget Breiten-Fix** – Bearbeiten/Löschen-Buttons haben Widgets nicht mehr breiter gemacht; äußerer Container hat jetzt explizite `width/height`, Buttons ragen visuell darüber hinaus ohne die Größe zu beeinflussen

### v3.8.0
- **Neue Custom Card: Müllabfuhr** – `type: waste` mit konfigurierbaren Tonnen (name, entity, icon, Farben für normal/heute/morgen), "Nächste Abholung" Zeile, 2×2 Grid mit farbigen Rahmen, Alert-Banner bei Heute/Morgen, Preset in der Bibliothek

### v3.7.11
- **Resize Handle exakt am Rahmen** – Doppel-Skalierung behoben: Widgets die intern `instance.widthOverride` lesen (Compass, MediaPlayer, SwitchCard, SensorCard) wurden doppelt verkleinert; jetzt wird dem Widget eine bereinigte Instance ohne Overrides übergeben, CSS `scale(scaleX, scaleY)` füllt den Container komplett; ResizableWidget hat `overflow:hidden`

### v3.7.10
- **Resize-Handle Fix** – Punkt sitzt jetzt direkt am Rahmen (`right:0, bottom:0`) statt 3px außerhalb; Größenanzeige (z.B. "160×140") jetzt innerhalb des Widgets statt darunter

### v3.7.9
- **Compass Speedometer** – 1:1 Nachbau des EDOMI VSE-Originals: 64 Ticks, Pfeil mit Einkerbung an der Basis (außen→innen), "N" oben, S-Positionsmarker unten, Schwellen-Rahmenfarbe, Richtung als "337° NNW", dünner Wert (font-weight 300), alle Original-Variablen (var1-var14)

### v3.7.8
- **Compass Speedometer Fix** – Pfeile zeigen jetzt von außen nach innen (Basis am Ring, Spitze zum Zentrum); dunkles Design mit konfigurierbarer Hintergrundfarbe (var7), Deckkraft (var8), Rahmenfarbe (var9), Rahmen-Deckkraft (var10), Rahmenstärke (var11), Border-Radius (var12), Tick-Farbe (var13) – konsistent mit allen anderen Widgets

### v3.7.7
- **Logik-Editor Ports-Fix** – Handle-Punkte (Verbindungspunkte) sind jetzt exakt auf der Zeile des jeweiligen Ein-/Ausgangs; bei unterschiedlicher Anzahl Ein-/Ausgänge werden Leer-Zeilen eingefügt; fixe Zeilenhöhe (44px) verhindert Verschiebung

### v3.7.6
- **Compass Speedometer Redesign** – Komplett neues Design nach Vorbild: helles/dunkles Theme (var16), feine 72er-Teilung, kleine Dreieck-Pfeile, "N" oben, großer Wert mittig, Richtungstext, konfigurierbarer Wert-Schriftgröße

### v3.7.5
- **Custom Card Vorschau-Fix** – Ring-Vorschau im Dialog zeigt jetzt Gradient, Label-Position, Icon-Offset, Padding und Label-Größe korrekt an
- **Custom Card Padding** – Neues YAML-Feld `style.padding` für Abstand zum Rahmen (Standard: 8px)
- **Custom Card Label-Größe** – `style.label_size` wird jetzt auch in Ring-Cards angewendet

### v3.7.4
- **Proportionales Widget-Scaling** – Alle VSE-Widgets skalieren jetzt proportional beim Resize (CSS `transform: scale()`), statt dass Elemente verschwinden
- **Custom Card Ring** – Label-Position (`label_position: top/bottom`), Label-Offset (`label_offset_x/y`), Icon-Offset (`icon_offset_x/y`) im YAML konfigurierbar

### v3.7.3
- **Custom Card RingGauge Upgrade** – Ring im ring-tile-card Style: Farbverlauf (colorLow/colorMid/colorHigh), Punkt-Indikator am Wert, Glow-Effekt, dickerer Ring
- **Gauge VSE Widget** – bleibt unverändert (klassischer Zeiger-Stil)

### v3.7.2
- **Light Widget** – Icon-Position per var28 (Y) und var29 (X) verschiebbar
- **Widget Bearbeiten-Dialog** – ScrollArea vergrößert (`calc(85vh-180px)`), alle Variablen scrollbar; Tab zeigt Anzahl
- **VSE Template Cache-Fix** – Templates werden jetzt mit `?v=timestamp` geladen, keine veralteten Variablen mehr durch Browser-Cache

### v3.7.1
- **Visu Zoom** – Device-Frame hat jetzt Zoom-Steuerung (50%–200%) mit +/- Buttons; bei 200% scrollt der Bereich automatisch; keine maximale Größenbeschränkung mehr

### v3.7.0
- **Media Player Redesign** – Komplett überarbeitetes Sonos-Widget: Play/Stop Toggle auf Haupttaste, Pause separat, dunkles glassmorphes Design, animierter Cover-Rahmen bei Wiedergabe, Status-Indikator, kompakter Aufbau
- **IKO Dialog Fix** – "Generieren"-Button im Popup war durch `overflow-hidden` abgeschnitten; Button jetzt immer sichtbar am unteren Rand
- **Adress-Toolbar** – Buttons auf zwei Zeilen aufgeteilt (Filter+Suche oben, Aktionen unten) für bessere Sichtbarkeit

### v3.6.9
- **Gauge Widget** – Wert- und Einheit-Schriftgröße jetzt einstellbar (var21/var22)
- **Visu Edit-Modus** – Switch/Light Widget toggelt nicht mehr beim Verschieben im Bearbeitungsmodus (transparenter Overlay blockiert Klicks)

### v3.6.8
- **Kosten-Dashboard** – Neuer "Kosten" Tab: Stundenkosten (Netzbezug × EPEX-Preis), Tageskosten (30 Tage), Monatsübersicht mit Fallback auf Verbrauchsdaten
- **Netzbezug-KO** – Neues Binding "Netzbezug" für Strom vom Netz (getrennt von Gesamtverbrauch)
- **Block-Upload Fix** – Browser-Suffixe wie `(1)`, `(2)` werden beim Upload entfernt; Duplikaterkennung über Block-ID verhindert doppelte Dateien
- **VSE Widget-Add Fix** – Typ-Mismatch behoben: Alle VSE-Widgets (Strompreis, Gauge, Sensor etc.) können wieder hinzugefügt werden
- **Sonne & Mond v2.1** – Garantiertes Mitternachts-Update, ephem berechnet immer heutigen Tag

### v3.6.6
- **Fronius Gen24 v1.6** – Neue Ausgänge A30 (Batterie Laden aktuell W) und A31 (Batterie Entladen aktuell W)

### v3.6.5
- **Energie: Batterie KOs** – Batterie Laden + Entladen als neue Datenquellen in KO-Zuordnung
- Quick Stats mit 6 Karten (PV, Verbrauch, Bat. Laden, Bat. Entladen, Temperatur, Strompreis)
- Energie-Chart: Batterie Lade/Entlade-Kurven (grün/orange)
- Wochenübersicht: Batterie kWh-Balken pro Tag

### v3.6.4
- **Fix: Block-Bindings triggern execute()** – `_write_output` ruft jetzt `on_address_changed()` auf, damit gebundene Blöcke ihre `execute()` ausführen (vorher wurden nur Werte gesetzt ohne Verarbeitung)
- **Fix: KNX-Output-Routing** – Auch bei echten KNX-Adressen werden gebundene Blöcke direkt benachrichtigt (Bus-Echo ist unzuverlässig)

### v3.6.3
- **Fix: Quelltext-Editor Flackern** – Uncontrolled Textarea + useMemo für stabile block-Referenz, useEffect nur auf block.type
- **Fix: Verbindungslinien löschen** – `/unbind` API-Route, `unbind_input()`/`unbind_output()` im Manager, Delete-Taste für Edges
- **Fix: Binding lösen im Port-Popup** – "Lösen"-Button wenn Port gebunden ist
- **Fix: Manager Startup-Reihenfolge** – `restore_remanent_state()` jetzt VOR `on_start()`
- **Fix: MinMax aus base.py entfernt** – nur Custom-Block in data/custom_blocks

### v3.6.2
- **Fix: Manager Startup-Reihenfolge** – `restore_remanent_state()` jetzt VOR `on_start()`
- **Fix: MinMax aus base.py entfernt** – nur noch Custom-Block in data/custom_blocks/
- **Fix: Hilfe-Dialog Flackern** – useEffect Dependency `[code]` entfernt, stopPropagation auf alle Keydown
- **Fix: Hilfe-Dialog Ctrl+A/Ctrl+C** – Focus-Trap verhindert, Ctrl+C erlaubt
- **Fix: Card bearbeiten zeigt gespeicherte Werte** – useEffect sync beim Öffnen
### v3.6.1
- **Fix: Custom Cards auf Panel/iPhone** – `CUSTOM_CARD_TEMPLATE` fehlte in VisuPanel.tsx
- **Fix: Volume-Slider Mediaplayer** – Touch/Pointer-Events, `touch-action: none`, `onValueCommit` statt `onValueChange`
- **Fix: Slider in Edit-Mode** – Drag-Handler überspringt jetzt `role=slider` und `data-interactive` Elemente
- Toggle: Schalt-KO + Status-KO getrennt konfigurierbar

### v3.6.0
- **Custom Card System**: Neue Karten mit visueller Konfiguration – Wert-Karten, Schalter, Ring-Gauges, Markdown-Überschriften
- **Ring-Gauge**: SVG-Ring-Anzeige für Sensoren (inspiriert von ring-tile-card), Min/Max/Stärke konfigurierbar
- **YAML-Editor**: Karten per YAML definieren wie in Home Assistant – mit Live-Preview und bidirektionaler Synchronisation
- **7 YAML-Vorlagen**: Sensor Ring, Netzbezug, PV Ertrag, Batterie, Schalter, Überschrift, Luftqualität
- Glassmorphic Design mit Backdrop-Blur und konfigurierbarem Glow
- Bedingte Formatierung: Icon-Farbe, Rahmen, Glow ändern sich basierend auf KO-Wert
- Live-Vorschau im Card-Editor mit 4 Tabs (Grundlagen, Aussehen, Bedingungen, YAML)
- Icon-Palette mit 24 MDI-Vorlagen + Emoji-Support
- Aktionen: Toggle, Wert senden, Seitennavigation
- Templates: `{value}`, `{unit}` Platzhalter für Wertanzeige
- Shields.io Badges in README (License, Platform, KNX, Python, React)

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
