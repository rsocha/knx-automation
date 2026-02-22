# KNX Automation Dashboard

Ein modernes Web-Dashboard zur Steuerung und Visualisierung von KNX Smart Home Systemen.

![Version](https://img.shields.io/badge/version-3.0.23-blue)

## 🚀 Features

### Dashboard (Adressen)
- Übersicht aller KNX Gruppenadressen
- Echtzeit-Statusanzeige mit Polling
- Senden von Befehlen direkt aus der Tabelle
- Filter nach internen/externen Adressen

### Visualisierung
- **VSE Widget System** - Visuelle Elemente für Schalter, Sensoren, Charts
- **Server-Sync** - Automatische Speicherung auf dem Server
- **Drag & Drop** - Widgets frei positionieren und skalieren
- **Mobile Panel** - Standalone-Ansicht für Smartphones
- **Home Assistant Import** - YAML-Karten importieren
- **Widget Upload/Download** - Eigene Templates verwalten

### Logik-Editor
- **ReactFlow** basierter visueller Editor
- Logik-Blöcke per Drag & Drop verbinden
- KO-Bindungen für Ein-/Ausgänge
- Export/Import von Logik-Konfigurationen

### System
- **Einstellungen** - API-Konfiguration, Visu Backup/Restore
- **Widget Templates** - Upload/Download von VSE Templates
- **Mobile Panel** - QR-Code für iPhone/Android
- **System-Update** - Paket-Upload mit automatischem Neustart

## 📁 Verzeichnisstruktur

```
/opt/knx-automation/
├── static/                    # Kompiliertes Frontend
│   ├── index.html            # React Dashboard
│   ├── assets/               # JS/CSS Bundles
│   └── vse/                  # Widget Templates (JSON)
├── dashboard-src/             # React Source Code
│   ├── src/
│   │   ├── components/visu/  # Widget-Komponenten
│   │   ├── pages/            # Seiten
│   │   └── services/         # API-Funktionen
│   ├── package.json
│   └── README.md             # Entwickler-Doku
├── data/
│   ├── visu_rooms.json       # Visualisierungs-Räume
│   ├── logic_config.json     # Logik-Blöcke
│   └── knx.db                # SQLite Datenbank
├── api/routes.py              # Backend API
├── main.py                    # FastAPI Server
├── install.sh                 # Installations-Script
└── README.md                  # Diese Datei
```

## 🔧 Installation

### Erstinstallation

```bash
# 1. Verzeichnis erstellen
sudo mkdir -p /opt/knx-automation
cd /opt/knx-automation

# 2. Paket entpacken
tar -xzf /tmp/knx-automation-v3.0.19.tar.gz --strip-components=1

# 3. Installer ausführen (installiert Python-Pakete + Service)
sudo ./install.sh

# 4. Service starten
systemctl start knx-automation
```

### Update

```bash
cd /opt/knx-automation
tar -xzf /tmp/knx-automation-v3.0.19.tar.gz --strip-components=1
systemctl restart knx-automation
```

**Wichtig:** Nach dem Update im Browser `Strg+Shift+R`!

## 🌐 URLs

| URL | Beschreibung |
|-----|--------------|
| `http://SERVER:8000/` | Dashboard (Adressen) |
| `http://SERVER:8000/visu` | Visualisierung (Editor) |
| `http://SERVER:8000/panel` | Mobile Panel (Vollbild) |
| `http://SERVER:8000/logic` | Logik-Editor |
| `http://SERVER:8000/settings` | Einstellungen |
| `http://SERVER:8000/update` | System-Update |
| `http://SERVER:8000/api/v1/docs` | API-Dokumentation |

## 📱 Mobile Panel (iPhone/Android)

### Zum Home-Bildschirm hinzufügen:

1. **URL öffnen:** `http://SERVER:8000/panel`
2. **iPhone Safari:** Teilen-Button (□↑) → "Zum Home-Bildschirm"
3. **Android Chrome:** Menü (⋮) → "Zum Startbildschirm hinzufügen"

**QR-Code:** Einstellungen → Mobile Panel → "QR-Code anzeigen"

## 🏠 Home Assistant YAML Import

Du kannst Home Assistant Mushroom-Card YAML direkt importieren und in VSE-Widgets umwandeln.

### So funktioniert's:

1. **Visu öffnen:** `http://SERVER:8000/visu`
2. **Import klicken** (in der Toolbar)
3. **YAML einfügen** oder Datei hochladen
4. **"YAML analysieren"** klicken
5. **KO-Adressen zuweisen** für jede erkannte Karte
6. **Importieren**

### Unterstützte HA-Karten:

- `custom:mushroom-template-card` → switch-card
- `custom:mushroom-light-card` → switch-card
- `custom:mushroom-entity-card` → switch-card
- `custom:mushroom-title-card` → title-card
- Andere Karten werden als switch-card importiert

### Beispiel YAML:

```yaml
type: custom:mushroom-template-card
entity: light.wohnzimmer
primary: Wohnzimmer Licht
icon: mdi:lightbulb
tap_action:
  action: toggle
```

Nach dem Import kannst du die KO-Adressen (Status + Schalten) zuweisen.

## 📱 VSE Widget Templates

### Verfügbare Widgets

| Widget | Beschreibung | KO Bindings |
|--------|--------------|-------------|
| switch-card | Schalter (Mushroom-Style) | ko1: Status, ko2: Schaltadresse |
| sensor-card | Sensor-Anzeige | ko1: Wert |
| gauge-barometer | Rundes Gauge/Barometer | ko1: Primärwert, ko2: Sekundär (weißer Zeiger) |
| strompreis-chart | 24h EPEX Preischart | ko1: JSON Array |
| markdown-card | Titel mit Icon/Emoji | - (nur Label) |
| compass-speedometer | Kompass mit Geschwindigkeit | ko1: Speed, ko2: Richtung blau, ko3: Richtung grau |
| media-player | Sonos Musikplayer | ko1-13: Titel, Artist, Cover, Controls, Volume |
| shape-separator | Linie/Form für Layout | - (nur visuelle Trennung) |
| simple-value | Dynamische Wertanzeige | ko1: Wert |
| simple-toggle | Dynamischer Schalter | ko1: Status, ko2: Schalten |

### Widget Templates verwalten

**Download:** Einstellungen → Widget Templates → "Alle Templates"  
**Upload:** Einstellungen → Widget Templates → "Template hochladen"

## 🛠️ Eigenes Widget erstellen

### Option 1: Dynamisches Widget (OHNE Programmierung!)

Einfach ein JSON-Template erstellen und hochladen - wird automatisch gerendert!

```json
{
  "id": "temperatur-anzeige",
  "name": "Temperatur Anzeige",
  "description": "Zeigt Temperaturwert an",
  "category": "sensors",
  "width": 150,
  "height": 100,
  "render": "dynamic",
  "inputs": {
    "ko1": { "name": "Temperatur", "type": "number" }
  },
  "variables": {
    "icon": { "name": "Icon", "type": "icon", "default": "thermometer" },
    "unit": { "name": "Einheit", "type": "text", "default": "°C" },
    "decimals": { "name": "Dezimalstellen", "type": "number", "default": 1 }
  }
}
```

**Unterstützte Variablen für dynamische Widgets:**

| Variable | Beschreibung | Default |
|----------|--------------|---------|
| `icon` | MDI Icon-Name oder Emoji | - |
| `icon_size` | Icon-Größe in px | 32 |
| `icon_color` | Icon-Farbe (RGB) | 255,255,255 |
| `unit` | Einheit (z.B. "°C") | - |
| `decimals` | Dezimalstellen | 1 |
| `font_size` | Wert-Schriftgröße | 24 |
| `bg_color` | Hintergrund (RGB) | 40,40,40 |
| `bg_opacity` | Deckkraft 0-100 | 10 |
| `layout` | vertical/horizontal/icon-top | vertical |
| `clickable` | "1" für Toggle | - |
| `value_on` / `value_off` | Text für An/Aus | An/Aus |

**render-Typen:** `"dynamic"`, `"generic"`, `"custom"` oder jeder unbekannte Typ.

### Option 2: Custom React-Komponente

Für komplexe Widgets (wie gauge-barometer, strompreis-chart):

1. Komponente in `dashboard-src/src/components/visu/` erstellen
2. In `VseRenderer.tsx` registrieren
3. `npm run build` ausführen
4. Nach `static/` kopieren

Siehe `dashboard-src/README.md` für Details.

## 🔌 API Endpoints

### KNX
- `GET /api/v1/status` - Systemstatus
- `GET /api/v1/group-addresses` - Alle Gruppenadressen
- `POST /api/v1/knx/send?group_address=X&value=Y` - Telegramm senden

### Visualisierung
- `GET /api/v1/visu/rooms` - Räume abrufen
- `POST /api/v1/visu/rooms` - Räume speichern
- `GET /api/v1/visu/export` - Backup herunterladen
- `POST /api/v1/visu/import` - Backup hochladen

### VSE Templates
- `GET /api/v1/vse/templates` - Alle Templates auflisten
- `POST /api/v1/vse/upload` - Template hochladen
- `GET /api/v1/vse/download` - Alle Templates als ZIP

### Logik
- `GET /api/v1/logic/blocks` - Alle Blöcke
- `GET /api/v1/logic/export` - Logik-Backup
- `POST /api/v1/logic/import` - Logik wiederherstellen

## 📋 Changelog

### v3.0.23 (2026-02-22)
- **Neu:** KO-Adressenauswahl mit Suche beim Hinzufügen/Bearbeiten von Widgets
- **Fix:** Widget-Dialog passt sich jetzt an Bildschirmgröße an (max 85% Höhe)
- **Fix:** Alle Dialoge sind scrollbar, Speichern-Button immer sichtbar

### v3.0.22 (2026-02-22)
- **Neu:** Media Player mit separaten Play/Pause KOs (ko9=Play, ko14=Pause)
- **Neu:** Eigene Kategorien hinzufügen und verwalten
- **Neu:** Raum-Einstellungen bearbeiten (Hintergrundfarbe, Farbverlauf, Bilder)
- **Neu:** Raum-Icons (Emoji oder MDI)
- Vorbereitung für Multi-Device Visualisierungen

### v3.0.21 (2026-02-22)
- **Neu:** Visueller ColorPicker für Farbauswahl in VSE Widgets
- **Fix:** Version-Anzeige in System-Update Seite
- **Fix:** Datenbank readonly Problem dokumentiert

### v3.0.20 (2026-02-22)
- **Neu:** Media Player Widget (Sonos) mit Cover, Steuerung, Lautstärke
- **Neu:** Shape Separator Widget (Linien, Rechtecke, Kreise)
- **Neu:** PWA Support - Fullscreen ohne Adressleiste auf iPhone/Android
- **Neu:** Safe-Area-Insets für Notch-Bereich
- README aktualisiert

### v3.0.19 (2026-02-22)
- **Fix:** Gauge-Widget min=0 funktioniert jetzt (vorher Fallback auf 960)
- **Fix:** Mobile Panel lädt Räume vom Server statt localStorage
- **Neu:** Compass-Speedometer Widget
- **Neu:** Logik Export/Import in Einstellungen
- README komplett überarbeitet mit HA Import Anleitung

### v3.0.18
- Panel lädt jetzt korrekt vom Server-API
- Template-Pfade korrigiert

### v3.0.17
- Compass-Speedometer Widget hinzugefügt

### v3.0.16
- Logging reduziert (weniger Spam)
- Source Code im Paket (dashboard-src/)

### v3.0.15
- Explizite Routen für /panel, /visu, etc.

### v3.0.11
- VseDynamicWidget für Widgets ohne Programmierung

### v3.0.10
- Widget Template Upload/Download
- Mobile Panel mit QR-Code

### v3.0.7
- Strompreis-Chart Zeitzonenfix (EPEX)

### v3.0.0
- Komplettes Redesign mit React/TypeScript

## 📄 Lizenz

Proprietär - Alle Rechte vorbehalten.
