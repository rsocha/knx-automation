# KNX Automation v3.0.4

Ein modernes Home-Automation Dashboard für KNX-Systeme mit React/TypeScript Frontend.

## ✨ Features

### 🖥️ Modernes React Dashboard
- **Collapsible Sidebar** - Einklappbare Navigation links
- **Dark Theme** - Augenfreundliches dunkles Design
- **Responsive** - Optimiert für Desktop und Tablet
- **Echtzeit-Updates** - Polling für Live-Daten

### 📊 Seiten

| Seite | Beschreibung |
|-------|--------------|
| **Adressen** | Gruppenadressen verwalten, IKO-Generator, Live-Werte |
| **Visualisierung** | VSE-Widgets, Räume, Drag & Drop Editor |
| **Logik** | ReactFlow Visual Editor für Logik-Blöcke |
| **Log** | Echtzeit Telegramm-Protokoll |
| **Einstellungen** | API-Konfiguration, Visu-Backup |
| **System-Update** | Update hochladen, Neustart, Backup |

### 🔄 Server-Sync für Visualisierung
- Automatische Speicherung auf dem Server
- Kein Datenverlust bei Browser-Cache-Leerung
- Export/Import Funktion für Backups

---

## 🚀 Installation

### Erstinstallation

```bash
# 1. Paket entpacken
cd /opt
tar -xzf knx-automation-v3.0.4.tar.gz

# 2. In Verzeichnis wechseln
cd knx-automation

# 3. Python-Abhängigkeiten installieren
pip3 install -r requirements.txt

# 4. Systemd-Service einrichten
sudo cp knx-automation.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable knx-automation
sudo systemctl start knx-automation
```

### Update von bestehender Installation

```bash
# 1. Service stoppen
sudo systemctl stop knx-automation

# 2. Backup erstellen
cp -r /opt/knx-automation /opt/knx-automation-backup

# 3. Neues Paket entpacken (behält data/ Ordner)
cd /opt/knx-automation
tar -xzf /tmp/knx-automation-v3.0.4.tar.gz --strip-components=1

# 4. Cache löschen
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null

# 5. Service starten
sudo systemctl start knx-automation

# 6. Browser-Cache leeren: Strg+Shift+R
```

---

## 📁 Verzeichnisstruktur

```
knx-automation/
├── main.py              # FastAPI Hauptanwendung
├── api/
│   └── routes.py        # API-Endpunkte
├── knx/
│   └── connection.py    # KNX/IP Verbindung
├── logic/
│   ├── manager.py       # Logik-Engine
│   └── blocks/          # Verfügbare Bausteine
├── static/
│   ├── index.html       # React SPA
│   ├── assets/          # JS/CSS Bundles
│   └── vse/             # VSE Widget Templates
├── data/
│   ├── addresses.json   # Gruppenadressen
│   ├── logic_blocks.json
│   ├── logic_pages.json
│   └── visu_rooms.json  # Visualisierung (Server-Sync)
└── README.md
```

---

## 🔧 Konfiguration

### KNX Gateway

Bearbeite `config.yaml`:

```yaml
knx:
  gateway_ip: "192.168.0.10"
  gateway_port: 3671
  local_ip: "192.168.0.87"
  connection_type: "tunneling"  # oder "routing"
```

### API-URL im Dashboard

1. Öffne **Einstellungen** (Sidebar)
2. Trage die API-URL ein: `http://192.168.0.87:8000/api/v1`
3. Klicke **Speichern**

---

## 🎨 Visualisierung

### VSE Widget Templates

| Template | Beschreibung |
|----------|--------------|
| **Switch Card** | Schalter mit Icon, Status, Glow-Effekt |
| **Sensor Card** | Wertanzeige mit Icon und Label |
| **Strompreis Chart** | Balkendiagramm für EPEX-Preise |
| **Gauge Barometer** | Kreisförmige Wertanzeige |
| **Titel Card** | Überschrift/Header |

### Räume erstellen

1. Gehe zu **Visualisierung**
2. Klicke **+** im Räume-Panel (links)
3. Name und Kategorie eingeben
4. Raum auswählen
5. **+ Widget** klicken
6. Template wählen und konfigurieren

### Widget bearbeiten

1. **Edit** Button in Toolbar aktivieren
2. Widget anklicken → Bearbeiten-Dialog
3. KO-Adressen und Variablen konfigurieren
4. Speichern

---

## ⚡ Logik-Editor

### Blöcke hinzufügen

1. Gehe zu **Logik**
2. **Bausteine** Panel rechts öffnen
3. Block per Klick hinzufügen
4. Block auf Canvas positionieren

### Verfügbare Bausteine

| Kategorie | Blöcke |
|-----------|--------|
| **Logik** | AND, OR, NOT, XOR |
| **Vergleich** | Greater, Less, Equal, Threshold |
| **Math** | Add, Multiply, Clamp, Scale |
| **Zeit** | Timer, Delay, Scheduler |
| **Trigger** | Edge Detector, Pulse Generator |
| **Integration** | Sonos Controller, Fronius |

### KO-Binding

1. Port anklicken (Eingang oder Ausgang)
2. **KO verbinden** wählen
3. Gruppenadresse auswählen oder eingeben
4. Speichern

---

## 📡 API-Endpunkte

### Status
```
GET /api/v1/status
GET /api/v1/health
```

### Gruppenadressen
```
GET    /api/v1/group-addresses
POST   /api/v1/group-addresses
PUT    /api/v1/group-addresses/{address}
DELETE /api/v1/group-addresses/{address}
```

### KNX Senden
```
POST /api/v1/knx/send?group_address=1/2/3&value=1
```

### Visualisierung
```
GET  /api/v1/visu/rooms
POST /api/v1/visu/rooms
GET  /api/v1/visu/export
POST /api/v1/visu/import
```

### Logik
```
GET    /api/v1/logic/blocks
POST   /api/v1/logic/blocks
DELETE /api/v1/logic/blocks/{instance_id}
POST   /api/v1/logic/blocks/{instance_id}/bind
```

---

## 🐛 Troubleshooting

### Dashboard lädt nicht

```bash
# 1. Service-Status prüfen
sudo systemctl status knx-automation

# 2. Logs prüfen
sudo journalctl -u knx-automation -f

# 3. Browser-Cache leeren
Strg + Shift + R
```

### KNX-Verbindung fehlgeschlagen

```bash
# 1. Gateway erreichbar?
ping 192.168.0.10

# 2. Port offen?
nc -zv 192.168.0.10 3671

# 3. Logs prüfen
grep -i "knx\|connection" /var/log/knx-automation.log
```

### Widgets werden nicht angezeigt

1. Browser-Konsole öffnen (F12)
2. Nach `[Visu]` Logs suchen
3. Prüfen ob Templates geladen werden
4. API-URL in Einstellungen prüfen

### Schalten funktioniert nicht

1. Klicke auf Switch-Card
2. Prüfe Toast-Nachricht (unten rechts)
3. Wenn "Senden fehlgeschlagen":
   - KNX-Verbindung prüfen (Sidebar grün?)
   - Adresse existiert?
   - Server-Logs prüfen

---

## 📝 Changelog

### v3.0.4 (21. Feb 2026)
- ✅ Toast-Benachrichtigungen beim Schalten
- ✅ Bessere Fehlerbehandlung in Switch-Card
- ✅ Debug-Logs mit [Switch] Prefix

### v3.0.3 (21. Feb 2026)
- ✅ Komplett überarbeitete Visualization.tsx
- ✅ Bessere Sync-Logik
- ✅ Debug-Logs mit [Visu] Prefix

### v3.0.2 (21. Feb 2026)
- ✅ Template-Pfade korrigiert
- ✅ VSE-Dateien in /static/vse/

### v3.0.1 (21. Feb 2026)
- ✅ Deutlicher Sync-Status Badge
- ✅ Räume/Widget-Zähler in Toolbar

### v3.0.0 (21. Feb 2026)
- 🎉 **Komplett neues React/TypeScript Dashboard**
- ✅ Collapsible Sidebar Navigation
- ✅ Server-Sync für Visualisierung
- ✅ ReactFlow Logik-Editor
- ✅ Einstellungen & System-Update Seiten
- ✅ Shadcn/ui Komponenten
- ✅ React Query für State Management

### v2.x (Feb 2026)
- Vanilla JavaScript Dashboard
- VSE Widget System
- Logik-Blöcke

---

## 📄 Lizenz

MIT License

---

## 🔗 Links

- **Dashboard:** http://192.168.0.87:8000/
- **API Docs:** http://192.168.0.87:8000/docs

---

**Version:** 3.0.4  
**Datum:** 21. Februar 2026
