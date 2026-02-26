# KNX Automation Dashboard

Ein modernes Web-Dashboard zur Steuerung und Visualisierung von KNX Smart Home Systemen.

![Version](https://img.shields.io/badge/version-3.2.0-blue)

## 🚀 Features

### Dashboard
- Übersicht aller KNX Gruppenadressen mit Echtzeit-Statusanzeige
- **Werte senden** – Dialog zum Senden beliebiger Werte an KNX Bus und IKOs
- **Quick-Toggle** – Schalten von DPT-1 Adressen direkt in der Tabelle
- **Wert kopieren** – Klick auf Wert kopiert in die Zwischenablage (HTTP-kompatibel)
- Filter nach internen (IKO) / externen (KNX) Adressen
- Sortierung, Gruppenfilter, Batch-Operationen
- CSV-Import für Gruppenadressen
- Feste Spaltenbreiten — Wert-Spalte truncated mit Tooltip

### Logik-Editor
- **ReactFlow** basierter visueller Editor
- **Integrierte Bausteinbibliothek** – Sidebar links mit Suchfunktion
- **Drag-to-Connect** – Blöcke per Linie verbinden, IKOs werden automatisch erstellt
- **IKO-Deduplizierung** – Vorhandene IKOs werden wiederverwendet statt doppelt erstellt
- **Farbige Handles** – Eingänge blau, Ausgänge grün, KO-Nodes grün
- Logikseiten-Verwaltung mit Seitenbaum
- KO-Bindungen für Ein-/Ausgänge mit verbreitertem Dialog
- **Custom Blocks** – Eigene Python-Bausteine hochladen
- **Block-Erhaltung** – Nicht ladbare Blocks bleiben in Config erhalten
- Export/Import von Logik-Konfigurationen

### Visualisierung
- **VSE Widget System** – Visuelle Elemente für Schalter, Sensoren, Charts
- **Server-Sync** – Automatische Speicherung, auch bei SPA-Navigation
- **Drag & Drop** – Widgets frei positionieren und skalieren
- **Mobile Panel** – Standalone-Ansicht für Smartphones
- **Home Assistant Import** – YAML-Karten importieren

### System
- **Vollständiges Backup/Restore** – Exportiert/importiert alle Daten inkl. Custom Blocks, VSE-Templates, DB
- **Einstellungen** – API-Konfiguration, Visu Backup/Restore
- **System-Update** – Paket-Upload mit zuverlässigem Neustart (detached Script)
- **Dark/Light Mode** – Vollständiger Theme-Support inkl. ReactFlow
- **Berechtigungen** – Automatische Fix-Funktion
- **Kein Browser-Cache-Problem** – `index.html` wird mit no-cache Headers ausgeliefert

## 📁 Verzeichnisstruktur

```
/opt/knx-automation/
├── static/                    # Kompiliertes Frontend
│   ├── index.html            # React Dashboard (no-cache)
│   ├── assets/               # JS/CSS Bundles (content-hash)
│   └── vse/                  # Widget Templates (JSON)
├── dashboard-src/             # React Source Code
│   ├── src/
│   │   ├── components/       # UI-Komponenten
│   │   ├── pages/            # Seiten
│   │   ├── hooks/            # React Query Hooks
│   │   └── services/         # API-Funktionen
│   └── package.json
├── data/
│   ├── knx.db                # SQLite Datenbank
│   ├── logic_config.json     # Logik-Konfiguration
│   ├── visu_rooms.json       # Visualisierungs-Konfiguration
│   ├── block_positions.json  # Positionen im Logik-Editor
│   ├── custom_blocks/        # Eigene Python-Bausteine
│   └── vse/                  # VSE Templates
├── api/
│   └── routes.py             # FastAPI Routes (APP_VERSION zentral)
├── logic/
│   ├── base.py               # BaseLogicBlock (permissive binding)
│   ├── manager.py            # LogicManager (Block-Erhaltung)
│   └── blocks/               # Eingebaute Bausteine
├── knx/                       # KNX-Verbindung (xknx)
├── main.py                    # FastAPI Server (no-cache SPA)
├── install.sh                 # Installationsskript
└── README.md
```

## 🔧 Installation

```bash
# 1. System-Pakete installieren
sudo ./install.sh

# 2. Dashboard-Paket entpacken
cd /opt/knx-automation
tar -xzf knx-automation-v3.2.0.tar.gz --strip-components=1

# 3. Service starten
systemctl start knx-automation

# 4. Dashboard öffnen
# http://<IP>:8000
```

## 🔄 Update

### Über die Web-UI
1. Dashboard öffnen → **System-Update**
2. `.tar.gz` Paket hochladen
3. Automatischer Neustart (detached Script)

### Manuell
```bash
cd /opt/knx-automation
systemctl stop knx-automation
tar -xzf knx-automation-v3.2.0.tar.gz --strip-components=1 --overwrite
find . -name "__pycache__" -exec rm -rf {} + 2>/dev/null
systemctl start knx-automation
```

> **Hinweis:** Eigene Custom Blocks in `data/custom_blocks/` werden beim Update erhalten (Merge statt Replace).

## 💾 Backup & Restore

### Backup erstellen
Dashboard → **System-Update** → **Backup herunterladen**

Das Backup enthält:
- Alle Gruppenadressen (KNX + IKO)
- Logik-Konfiguration (Blöcke, Seiten, Bindings, Positionen)
- Custom Blocks (.py-Dateien)
- Visu-Räume mit allen Widgets
- VSE-Templates
- Einstellungen (.env)
- SQLite-Datenbank

### Backup einspielen
Dashboard → **System-Update** → **Backup einspielen** → `.json` Datei auswählen

Funktioniert auch auf einer frischen Neuinstallation.

### API
```bash
# Backup herunterladen
curl -o backup.json http://<IP>:8000/api/v1/system/backup

# Backup einspielen
curl -X POST -F "file=@backup.json" http://<IP>:8000/api/v1/system/restore
```

## 📋 Changelog

### v3.2.0 (2026-02-26)
- **Vollständiges Backup/Restore** – Exportiert alle Daten inkl. Custom Blocks (.py), VSE-Templates, DB als JSON
- **IKO-Deduplizierung** – `/group-addresses/ensure` Endpoint: erstellt nur wenn nicht vorhanden
- **KO-Dialog verbreitert** – Zweizeilige Darstellung für lange IKO-Namen
- **Visu-Speicherung repariert** – Save on unmount bei SPA-Navigation, Query-Cache Update
- **Browser-Cache gelöst** – `index.html` mit no-cache HTTP-Headers und Meta-Tags
- **Adresstabelle** – Feste Spaltenbreiten, Wert truncated mit Tooltip, Klick zum Kopieren
- **Restart zuverlässig** – Detached Bash-Script mit nohup/setpgrp, überlebt Service-Stop
- **Version zentral** – APP_VERSION Konstante statt 4x hardcoded, ein /system/restart Endpoint
- **Handle-Farben** – Eingänge blau, Ausgänge grün, KO-Nodes grün
- **Block-Erhaltung** – Nicht ladbare Blocks bleiben in logic_config.json erhalten
- **Permissive Binding** – Unbekannte Input/Output Keys werden mit Warning akzeptiert
- **URL-Encoding** – encodeURIComponent() auf alle instance_id API-Aufrufe
- **AttributeError Fix** – getattr() für _name bei Block-Verbindungen

### v3.1.0 (2026-02-26)
- **Neues Farbschema** – Blau statt Grün (hsl 199 89% 48%)
- **Send-Dialog** – Werte an Bus/KO senden direkt aus der Adresstabelle
- **Quick-Toggle** – AN/AUS Buttons für DPT-1 Adressen
- **Logik-Sidebar** – Bausteinbibliothek fest links integriert mit Suchfunktion
- **Drag-to-Connect** – Verbindungslinie mit automatischer IKO-Erstellung
- **Custom Blocks Schutz** – Update überschreibt keine benutzer-hochgeladenen Bausteine
- **Stabilität** – Atomare Config-Speicherung, Lock für concurrent writes
- **Bare Except Fix** – Alle except: durch except Exception: ersetzt
- **Dark Mode** – ReactFlow colorMode korrekt synchronisiert

### v3.0.31
- Dark Mode Fix für ReactFlow
- Frontend/Backend Version-Sync

### v3.0.29
- Initiales VSE Widget System
- Logic Editor mit ReactFlow
- KO/IKO Management
- Visu-Editor mit Drag & Drop

## 🛠 Entwicklung

```bash
cd dashboard-src
npm install
npm run dev          # Development Server
npm run build        # Production Build → ../static/
```

## 📡 API

Base URL: `http://<host>:8000/api/v1`

| Endpunkt | Methode | Beschreibung |
|---|---|---|
| `/status` | GET | Systemstatus |
| `/group-addresses` | GET | Alle Gruppenadressen |
| `/group-addresses` | POST | Adresse erstellen |
| `/group-addresses/ensure` | POST | Adresse erstellen oder vorhandene zurückgeben |
| `/group-addresses/{addr}` | PUT | Adresse bearbeiten |
| `/group-addresses/{addr}` | DELETE | Adresse löschen |
| `/knx/send` | POST | Wert an KNX senden |
| `/logic/blocks` | GET | Alle Logikblöcke |
| `/logic/blocks` | POST | Block erstellen |
| `/logic/blocks/{id}/bind` | POST | KO binden |
| `/logic/available` | GET | Verfügbare Blocktypen |
| `/logic/custom-blocks` | GET | Custom Block Dateien |
| `/logic/custom-blocks/upload` | POST | Block hochladen (.py) |
| `/visu/rooms` | GET | Visu-Räume laden |
| `/visu/rooms` | POST | Visu-Räume speichern |
| `/system/update/upload` | POST | Update-Paket installieren |
| `/system/restart` | POST | System neustarten |
| `/system/backup` | GET | Vollständiges Backup herunterladen |
| `/system/restore` | POST | Backup einspielen |

## 📄 Lizenz

Privat – Alle Rechte vorbehalten.
