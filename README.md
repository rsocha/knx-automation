# KNX Automation Dashboard

Ein modernes Web-Dashboard zur Steuerung und Visualisierung von KNX Smart Home Systemen.

![Version](https://img.shields.io/badge/version-3.0.9-blue)

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

### Logik-Editor
- **ReactFlow** basierter visueller Editor
- Logik-Blöcke per Drag & Drop verbinden
- KO-Bindungen für Ein-/Ausgänge
- Seiten zur Organisation von Logik

### System
- **Einstellungen** - API-Konfiguration, Visu Backup/Restore
- **System-Update** - Paket-Upload mit automatischem Neustart
- **Telegram-Log** - Echtzeit KNX Bus-Monitor

## 📁 Verzeichnisstruktur

```
/opt/knx-automation/
├── static/                    # Frontend
│   ├── index.html            # React Dashboard
│   ├── index-classic.html    # Klassisches Dashboard (Backup)
│   ├── assets/               # JS/CSS Bundles
│   └── vse/                  # VSE Widget Templates
│       ├── switch-card.vse.json
│       ├── sensor-card.vse.json
│       ├── gauge-barometer.vse.json
│       └── strompreis-chart.vse.json
├── data/                      # Persistente Daten
│   ├── visu_rooms.json       # Visualisierungs-Räume
│   └── knx.db                # SQLite Datenbank
├── api/
│   └── routes.py             # FastAPI Routen
├── knx/
│   └── connection.py         # KNX/IP Verbindung
├── logic/
│   └── manager.py            # Logik-Block System
├── main.py                   # FastAPI Server
└── README.md                 # Diese Datei
```

## 🔧 Installation

### Erstinstallation

```bash
# 1. Verzeichnis erstellen
sudo mkdir -p /opt/knx-automation
cd /opt/knx-automation

# 2. Paket entpacken
tar -xzf /tmp/knx-automation-v3.0.9.tar.gz --strip-components=1

# 3. Python-Abhängigkeiten (falls nicht vorhanden)
pip install fastapi uvicorn xknx aiosqlite

# 4. Service einrichten (optional)
sudo cp knx-automation.service /etc/systemd/system/
sudo systemctl enable knx-automation
sudo systemctl start knx-automation
```

### Update

```bash
cd /opt/knx-automation
tar -xzf /tmp/knx-automation-v3.0.9.tar.gz --strip-components=1
sudo systemctl restart knx-automation
```

**Wichtig:** Nach dem Update im Browser `Strg+Shift+R` für Hard-Refresh!

## 🌐 URLs

| URL | Beschreibung |
|-----|--------------|
| `http://SERVER:8000/` | Dashboard |
| `http://SERVER:8000/visu` | Visualisierung |
| `http://SERVER:8000/logic` | Logik-Editor |
| `http://SERVER:8000/log` | Telegram-Log |
| `http://SERVER:8000/settings` | Einstellungen |
| `http://SERVER:8000/update` | System-Update |
| `http://SERVER:8000/panel` | Mobile Panel (Standalone) |
| `http://SERVER:8000/api/v1/docs` | API Dokumentation |

## 📱 VSE Widget Templates

### switch-card
Schalter im Mushroom Card Design mit:
- Status-Anzeige (Ein/Aus)
- Klick zum Schalten
- Anpassbare Icons und Farben
- Glow-Effekt

**KO Bindings:**
- `ko1`: Status-Adresse (lesen)
- `ko2`: Schalt-Adresse (schreiben)

### sensor-card
Sensor-Anzeige für Temperatur, Luftfeuchtigkeit, etc.
- Numerischer Wert mit Einheit
- Anpassbare Farben und Icons

**KO Bindings:**
- `ko1`: Wert-Adresse

### gauge-barometer
Rundes Gauge für Leistung, Prozent, etc.
- SVG-basierte Anzeige
- Zwei Werte möglich (aktuell/gesamt)

**KO Bindings:**
- `ko1`: Primärer Wert
- `ko2`: Sekundärer Wert (optional)

### strompreis-chart
24h EPEX Strompreis-Chart mit:
- Farbcodierte Balken nach Preis
- "Jetzt" Marker
- Min/Max Anzeige
- Korrekte Zeitzonenerkennung für EPEX-Daten

**KO Bindings:**
- `ko1`: JSON Array mit `[{t: unix_timestamp, p: preis_ct}]`

**Variablen:**
- `var13`: "Daten sind echte UTC" - auf 0 lassen für EPEX-Daten

## 🔌 API Endpoints

### KNX
- `GET /api/v1/status` - Systemstatus
- `GET /api/v1/health` - Health Check mit Version
- `GET /api/v1/group-addresses` - Alle Gruppenadressen
- `POST /api/v1/knx/send?group_address=X&value=Y` - Telegramm senden

### Visualisierung
- `GET /api/v1/visu/rooms` - Räume abrufen
- `POST /api/v1/visu/rooms` - Räume speichern
- `GET /api/v1/visu/export` - Backup herunterladen
- `POST /api/v1/visu/import` - Backup hochladen

### Logik
- `GET /api/v1/logic/blocks` - Alle Blöcke
- `POST /api/v1/logic/blocks` - Block erstellen
- `DELETE /api/v1/logic/blocks/{id}` - Block löschen
- `POST /api/v1/logic/blocks/{id}/bind` - KO binden

## 🛠️ Troubleshooting

### Widgets werden nicht angezeigt
1. Browser-Konsole öffnen (F12)
2. Nach `[Visu]` Meldungen suchen
3. Prüfen ob Templates geladen werden

### Schalten funktioniert nicht
1. Toast-Meldung beachten
2. Browser-Konsole prüfen: `[Switch]` Logs
3. Server-Logs: `journalctl -u knx-automation -f`

### Strompreis-Chart zeigt falsche Zeit
- Variable "Daten sind echte UTC" auf 0 setzen
- EPEX-Daten verwenden lokale Zeit als UTC-Timestamps

## 📋 Changelog

### v3.0.9 (2025-02-21)
- README hinzugefügt
- Code-Cleanup

### v3.0.7
- Strompreis-Chart Zeitzonenfix für EPEX Daten

### v3.0.5
- `crypto.randomUUID()` Polyfill für HTTP/ältere Browser

### v3.0.4
- Switch-Card: Toast-Benachrichtigungen beim Schalten
- Bessere Fehlerbehandlung

### v3.0.0
- Komplettes Redesign mit React/TypeScript
- shadcn/ui Komponenten
- ReactFlow Logik-Editor
- VSE Widget System
- Server-seitige Visu-Speicherung

## 🔒 Sicherheit

- Dashboard ist **nicht** für öffentliches Internet gedacht
- Nur im lokalen Netzwerk betreiben
- Optional: Reverse Proxy mit Auth (nginx + Basic Auth)

## 📄 Lizenz

Proprietär - Alle Rechte vorbehalten.
