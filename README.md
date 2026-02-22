# KNX Automation Dashboard

Ein modernes Web-Dashboard zur Steuerung und Visualisierung von KNX Smart Home Systemen.

![Version](https://img.shields.io/badge/version-3.0.15-blue)

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
- **HA Import** - Home Assistant YAML Import
- **Widget Upload/Download** - Eigene Templates verwalten

### Logik-Editor
- **ReactFlow** basierter visueller Editor
- Logik-Blöcke per Drag & Drop verbinden
- KO-Bindungen für Ein-/Ausgänge

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
│   └── knx.db                # SQLite Datenbank
├── api/routes.py              # Backend API
├── main.py                    # FastAPI Server
├── install.sh                 # Installations-Script
└── README.md                  # Diese Datei
```

## 🔧 Installation

```bash
cd /opt/knx-automation
tar -xzf /tmp/knx-automation-v3.0.10.tar.gz --strip-components=1
sudo systemctl restart knx-automation
```

**Wichtig:** Nach dem Update im Browser `Strg+Shift+R`!

## 🌐 URLs

| URL | Beschreibung |
|-----|--------------|
| `http://SERVER:8000/` | Dashboard |
| `http://SERVER:8000/visu` | Visualisierung |
| `http://SERVER:8000/panel` | Mobile Panel |
| `http://SERVER:8000/settings` | Einstellungen |

## 📱 Mobile Panel (iPhone/Android)

### Zum Home-Bildschirm hinzufügen:

1. **URL öffnen:** `http://SERVER:8000/panel`
2. **iPhone Safari:** Teilen-Button (□↑) → "Zum Home-Bildschirm"
3. **Android Chrome:** Menü (⋮) → "Zum Startbildschirm hinzufügen"

**QR-Code:** In Einstellungen → Mobile Panel → "QR-Code anzeigen"

## 📱 VSE Widget Templates

### Verfügbare Widgets

| Widget | Beschreibung | KO Bindings |
|--------|--------------|-------------|
| switch-card | Schalter mit Status | ko1: Status, ko2: Schaltadresse |
| sensor-card | Sensor-Anzeige | ko1: Wert |
| gauge-barometer | Rundes Gauge | ko1: Primärwert, ko2: Sekundär |
| strompreis-chart | EPEX Preischart | ko1: JSON Array |
| markdown-card | Titel mit Icon | - (nur Label) |

### Widget Templates verwalten

**Download:** Einstellungen → Widget Templates → "Alle Templates"  
**Upload:** Einstellungen → Widget Templates → "Template hochladen"

## 🛠️ Eigenes Widget erstellen

### Option 1: Dynamisches Widget (OHNE Programmierung!)

Einfach ein JSON-Template erstellen und hochladen - das Widget wird automatisch gerendert!

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
    "ko1": {
      "name": "Temperatur",
      "type": "number"
    }
  },
  "variables": {
    "icon": { "name": "Icon", "type": "icon", "default": "thermometer" },
    "icon_size": { "name": "Icon Größe", "type": "number", "default": 28 },
    "icon_color": { "name": "Icon Farbe", "type": "text", "default": "255,193,7" },
    "unit": { "name": "Einheit", "type": "text", "default": "°C" },
    "decimals": { "name": "Dezimalstellen", "type": "number", "default": 1 },
    "font_size": { "name": "Schriftgröße", "type": "number", "default": 28 },
    "bg_color": { "name": "Hintergrund", "type": "text", "default": "40,40,40" },
    "bg_opacity": { "name": "Deckkraft %", "type": "number", "default": 90 },
    "layout": { "name": "Layout", "type": "text", "default": "vertical" }
  }
}
```

**Unterstützte Variablen für dynamische Widgets:**

| Variable | Beschreibung | Default |
|----------|--------------|---------|
| `icon` | MDI Icon-Name oder Emoji | - |
| `icon_size` | Icon-Größe in px | 32 |
| `icon_color` | Icon-Farbe (RGB) | 255,255,255 |
| `text_color` | Textfarbe (RGB) | 255,255,255 |
| `bg_color` | Hintergrundfarbe (RGB) | 40,40,40 |
| `bg_opacity` | Deckkraft 0-100 | 10 |
| `border_radius` | Eckenradius px | 12 |
| `border_color` | Rahmenfarbe (RGB) | - |
| `border_width` | Rahmenstärke px | 0 |
| `padding` | Innenabstand px | 12 |
| `font_size` | Wert-Schriftgröße px | 24 |
| `label_size` | Label-Schriftgröße px | 12 |
| `unit` | Einheit (z.B. "°C") | - |
| `decimals` | Dezimalstellen | 1 |
| `layout` | vertical/horizontal/icon-left/icon-top | vertical |
| `clickable` | "1" für Toggle-Funktion | - |
| `value_on` | Text bei Wert=1 | An |
| `value_off` | Text bei Wert=0 | Aus |

**render-Typen für automatisches Rendering:**
- `"render": "dynamic"` - Generischer Renderer
- `"render": "generic"` - Alias für dynamic
- `"render": "custom"` - Alias für dynamic
- Jeder unbekannte render-Typ nutzt ebenfalls den dynamischen Renderer

### Option 2: Custom React-Komponente (für komplexe Widgets)

> ⚠️ **Hinweis:** Dieser Abschnitt ist nur für fortgeschrittene Entwickler!  
> Die Datei `VseMyWidget.tsx` ist nur ein **Beispiel** und nicht im Paket enthalten.  
> Für die meisten Widgets reicht Option 1 (dynamische Widgets) völlig aus!

```json
{
  "id": "my-widget",
  "name": "Mein Widget",
  "description": "Beschreibung",
  "category": "custom",
  "width": 200,
  "height": 100,
  "render": "myWidget",
  "inputs": {
    "ko1": {
      "name": "Hauptwert",
      "type": "number"
    }
  },
  "variables": {
    "var1": {
      "name": "Farbe",
      "type": "text",
      "default": "255,193,7"
    }
  }
}
```

### 2. React-Komponente erstellen

Datei: `src/components/visu/VseMyWidget.tsx`

```tsx
import type { VseWidgetInstance, VseTemplate } from "@/types/vse";
import { useGroupAddresses } from "@/hooks/useKnx";

interface Props {
  instance: VseWidgetInstance;
  template: VseTemplate;
}

export default function VseMyWidget({ instance, template }: Props) {
  const { data: addresses } = useGroupAddresses();
  
  const vars = {
    ...Object.fromEntries(
      Object.entries(template.variables).map(([k, v]) => [k, v.default])
    ),
    ...instance.variableValues,
  };
  
  const valueAddr = instance.koBindings["ko1"];
  const ga = addresses?.find((a) => a.address === valueAddr);
  const value = ga?.value || "0";
  
  return (
    <div style={{ 
      width: template.width, 
      height: template.height,
      background: "rgba(255,255,255,0.1)",
      borderRadius: 12,
      padding: 16,
    }}>
      <div style={{ color: "#fff" }}>{instance.label}</div>
      <div style={{ color: `rgb(${vars.var1})`, fontSize: 24 }}>
        {value}
      </div>
    </div>
  );
}
```

### 3. In VseRenderer registrieren

Datei: `src/components/visu/VseRenderer.tsx`

```tsx
import VseMyWidget from "./VseMyWidget";

const RENDERERS: Record<string, React.ComponentType<Props>> = {
  // ... andere Widgets
  myWidget: VseMyWidget,  // render Name aus JSON
};
```

### 4. Template hochladen

1. JSON als `my-widget.vse.json` speichern
2. Einstellungen → Widget Templates → "Template hochladen"
3. Seite neu laden (Strg+Shift+R)

## 🔌 API Endpoints

### KNX
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

## 📋 Changelog

### v3.0.10 (2025-02-21)
- Toolbar-Text wieder sichtbar
- Widget Template Upload/Download
- Mobile Panel mit QR-Code
- Neues Widget: markdown-card
- README mit Widget-Erstellungsanleitung

### v3.0.7
- Strompreis-Chart Zeitzonenfix

### v3.0.5
- crypto.randomUUID() Polyfill

### v3.0.0
- Komplettes Redesign mit React/TypeScript

## 📄 Lizenz

Proprietär - Alle Rechte vorbehalten.
