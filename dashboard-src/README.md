# KNX Dashboard - React Source Code

Dieses Verzeichnis enthält den Source Code des React/TypeScript Dashboards.

## Voraussetzungen

- Node.js 18+ 
- npm 9+

## Installation

```bash
cd dashboard-src
npm install
```

## Entwicklung

```bash
npm run dev
```

Öffnet einen Dev-Server auf http://localhost:5173

## Build

```bash
npm run build
```

Das kompilierte Dashboard landet in `dist/` und muss nach `../static/` kopiert werden:

```bash
cp dist/index.html ../static/
cp -r dist/assets ../static/
```

## Struktur

```
src/
├── components/
│   ├── visu/           # Widget-Komponenten
│   │   ├── VseDynamicWidget.tsx   # Generischer Widget-Renderer
│   │   ├── VseSwitchCard.tsx      # Schalter-Widget
│   │   ├── VseSensorCard.tsx      # Sensor-Widget
│   │   ├── VseGaugeBarometer.tsx  # Gauge-Widget
│   │   ├── VseStrompreisChart.tsx # Strompreis-Chart
│   │   ├── VseMarkdownCard.tsx    # Markdown/Titel-Widget
│   │   └── VseRenderer.tsx        # Widget-Registry
│   └── ui/             # shadcn/ui Komponenten
├── pages/
│   ├── Visualization.tsx  # Visu-Editor
│   ├── SettingsPage.tsx   # Einstellungen
│   ├── LogicPage.tsx      # Logik-Editor
│   └── ...
├── services/
│   └── knxApi.ts       # API-Funktionen
├── hooks/
│   └── useKnx.ts       # React Hooks
└── types/
    └── vse.ts          # TypeScript Typen
```

## Neues Widget erstellen

### Option 1: Dynamisches Widget (ohne Programmierung)

Erstelle eine JSON-Datei mit `"render": "dynamic"` - wird automatisch gerendert!

### Option 2: Custom React-Komponente

1. Erstelle `src/components/visu/VseMyWidget.tsx`
2. Registriere in `VseRenderer.tsx`
3. Erstelle passendes JSON-Template
4. `npm run build`
