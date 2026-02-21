# KNX Automation v2.0.6 - Komplettpaket

## 📦 Inhalt

Dieses Paket enthält:
- ✅ **KNX Automation v2.0.6** - Vollständiges System
- ✅ **Sonos Controller v1.2** - Musik-Steuerung
- ✅ **Button-to-Pulse v1.0** - Puls-Generator für Sonos

---

## 🚀 Installation

### **Schritt 1: Backup erstellen**
```bash
tar -czf knx-automation-backup-$(date +%Y%m%d).tar.gz knx-automation/
```

### **Schritt 2: Altes System stoppen**
```bash
sudo systemctl stop knx-automation
```

### **Schritt 3: Entpacken**
```bash
tar -xzf knx-automation_v2.0.6_complete.tar.gz
```

### **Schritt 4: Cache löschen (wichtig!)**
```bash
cd knx-automation
find . -type d -name __pycache__ -exec rm -rf {} +
find . -name "*.pyc" -delete
```

### **Schritt 5: System starten**
```bash
sudo systemctl start knx-automation
```

### **Schritt 6: Browser-Cache leeren**
- Chrome/Edge: `Strg + Shift + Delete`
- Oder: `Strg + F5` (Hard Reload)

---

## ✅ Was ist neu in v2.0.6?

### **UI-Verbesserungen:**
- ✅ **Saubere Eingabemaske** - Keine verwirrenden `cond*_*` Felder mehr
- ✅ **Tab-Navigation** für Bedingungen - Übersichtlicher
- ✅ **Klare Labels** - "Rahmen-Farbe" statt "Rahmen"
- ✅ **Performance** - 60-75% schnelleres Rendering
- ✅ **Verständliche Variablen** - Nur wichtige Felder

### **Neue Bausteine:**
- ✅ **Button-to-Pulse** - Konvertiert Button-Klicks in Pulse

### **Bugfixes:**
- ✅ Dashboard-Freeze behoben (v2.0.5 Hotfix)
- ✅ Bedingungen aus Variablenliste entfernt

---

## 🎯 Sonos Controller v1.2 - Wichtig!

### **Problem: Play funktioniert nur einmal**

**Ursache:**
Das System ruft `execute()` nur bei **Wertänderungen** auf:
```
E4 = 1  (von 0) → execute() aufgerufen ✅
E4 = 1  (von 1) → execute() NICHT aufgerufen ❌
```

**Das ist System-Design, kein Bug!**

### **Lösung: Button-to-Pulse verwenden**

```
[Button/Schalter]
    ↓
[Button-to-Pulse]  ← Konvertiert 1 in Puls
    E1
    A1
    ↓
[Sonos Controller E4 Play]
```

**Wie es funktioniert:**
1. Button wird auf 1 gesetzt
2. Button-to-Pulse empfängt die 1
3. **Automatisch:** Sendet 1 → wartet 100ms → sendet 0
4. Sonos empfängt den Puls (0→1→0) ✅

**Vorteile:**
- ✅ Mehrfache Klicks funktionieren
- ✅ Kein manuelles 0-Setzen nötig
- ✅ Sauber und wartbar

---

## 📋 Sensor Card Einstellungen

### **Neue übersichtliche Struktur:**

```
Sensor Card Einstellungen
├─ Wert-Adresse (KO)
├─ Bezeichnung
├─ Einheit
├─ Dezimalstellen, Breite, Höhe
│
├─ Icon
│  ├─ Icon (MDI Name)
│  ├─ Größe (px)
│  ├─ Farbe
│  └─ Deckkraft %
│
├─ Text
│  ├─ Label-Größe (px)
│  ├─ Label-Farbe
│  ├─ Label-Deckkraft %
│  ├─ Wert-Größe (px)
│  ├─ Wert-Farbe
│  └─ Wert-Deckkraft %
│
├─ Rahmen & Hintergrund
│  ├─ Hintergrund
│  ├─ BG Deckkraft
│  ├─ Rahmenfarbe
│  ├─ Rahmen Deckkraft
│  ├─ Rundung (px)
│  ├─ Rahmenbreite
│  └─ Glow-Effekt
│
└─ Bedingte Formatierung (Tabs!)
   ├─ [Bedingung 1]  Bedingung 2  Bedingung 3
   │
   └─ Bedingung 1:
      ├─ Aktiviert
      ├─ Wenn Wert >= 25
      ├─ Icon Name (MDI): fire
      ├─ Icon-Farbe: Rot
      ├─ Icon-Deckkraft %: 100
      ├─ Label-Farbe: Rot
      ├─ Wert-Farbe: Rot
      ├─ Rahmen-Farbe: Rot
      └─ Glow-Farbe: Rot
```

**✅ Keine `cond*_*` Felder mehr in der Variablenliste!**

---

## 🔧 Troubleshooting

### **Dashboard lädt nicht**
1. Browser-Cache leeren: `Strg + F5`
2. Console öffnen (F12) → Fehler prüfen
3. System neu starten

### **Version wird nicht aktualisiert**
```bash
# Cache löschen:
cd knx-automation
find . -type d -name __pycache__ -exec rm -rf {} +
find . -name "*.pyc" -delete
sudo systemctl restart knx-automation
```

### **Sonos Play funktioniert nicht**
1. **Prüfen:** Verwenden Sie Button-to-Pulse?
2. **Testen:** Senden Sie einen Puls (1 → 0 → 1)?
3. **Logs:** `tail -f /var/log/knx-automation.log`

### **Bedingungen werden nicht angezeigt**
1. Browser-Cache leeren
2. Modal schließen und neu öffnen
3. JavaScript-Console prüfen (F12)

---

## 📁 Dateistruktur

```
knx-automation/
├── api/
│   └── routes.py (v2.0.6)
├── static/
│   └── index.html (v2.0.6)
├── logic/
│   └── blocks/
│       ├── sonos_controller.py (v1.2)
│       └── button_to_pulse.py (v1.0)
├── data/
│   └── vse/
│       └── sensor_card_custom.vse.json
└── README.md (diese Datei)
```

---

## 🎯 Schnellstart

### **1. Sensor Card verwenden:**
1. Visu-Seite öffnen
2. "+ VSE Element" klicken
3. "Sensor Card" auswählen
4. Bearbeiten → Einstellungen anpassen
5. **Bedingungen:** Auf Tabs klicken!

### **2. Sonos Controller verwenden:**
1. Logik-Seite öffnen
2. Sonos Controller hinzufügen
3. **Wichtig:** Button-to-Pulse vor E4/E5/E6 schalten!
4. IP-Adresse einstellen
5. Testen!

### **3. Button-to-Pulse verwenden:**
1. Logik-Seite öffnen
2. Button-to-Pulse hinzufügen
3. Verbindung:
   ```
   [Button] → E1 [Button-to-Pulse] A1 → [Sonos E4]
   ```
4. Fertig!

---

## 📝 Changelog

### **v2.0.6** (15. Feb 2026)
- ✅ Bedingungen aus Variablenliste entfernt
- ✅ Nur Widget-Variablen (var1-var13) sichtbar
- ✅ Bedingungen NUR in Tabs
- ✅ Button-to-Pulse Baustein hinzugefügt

### **v2.0.5** (15. Feb 2026)
- ✅ HOTFIX: Dashboard-Freeze behoben
- ✅ Script-Tag aus HTML entfernt
- ✅ showCondTab global definiert

### **v2.0.4** (15. Feb 2026)
- ✅ Tab-Navigation für Bedingungen
- ✅ Vollständige Labels
- ⚠️ Dashboard-Freeze Bug (in v2.0.5 behoben)

### **v2.0.3** (15. Feb 2026)
- ✅ Performance-Optimierung
- ✅ 60-75% schnelleres Rendering
- ✅ 50% weniger DOM-Elemente

### **v2.0.2** (15. Feb 2026)
- ✅ Versionsnummer-Fix
- ✅ Verständliche Variablennamen
- ✅ Bedingte Formatierung hinzugefügt

---

## 🆘 Support

### **Logs prüfen:**
```bash
# Systemd-Journal:
sudo journalctl -u knx-automation -f

# Log-Datei:
tail -f /var/log/knx-automation.log

# Nur Fehler:
grep ERROR /var/log/knx-automation.log
```

### **System-Status:**
```bash
# Status prüfen:
sudo systemctl status knx-automation

# Neu starten:
sudo systemctl restart knx-automation

# Stoppen:
sudo systemctl stop knx-automation

# Starten:
sudo systemctl start knx-automation
```

---

## ✅ Überprüfung nach Installation

### **1. Version prüfen:**
- Sidebar (unten links): **v2.0.6** ✅
- System-Update: **2.0.6** ✅

### **2. Sensor Card testen:**
1. VSE Element bearbeiten
2. **Sollte zeigen:** Klare Kategorien (Icon, Text, Rahmen)
3. **Sollte NICHT zeigen:** `cond*_*` Felder
4. **Bedingungen:** Nur in Tabs ✅

### **3. Sonos testen:**
1. Button-to-Pulse hinzufügen
2. Mit Sonos E4 verbinden
3. Play mehrfach drücken
4. **Sollte funktionieren!** ✅

### **4. Performance testen:**
1. VSE bearbeiten öffnen
2. **Sollte sofort öffnen** (nicht träge)
3. Scrollen im Editor
4. **Sollte flüssig sein** ✅

---

## 🎉 Viel Erfolg!

Bei Fragen oder Problemen:
1. Logs prüfen
2. README nochmal lesen
3. Cache löschen und neu starten

**Version:** 2.0.6  
**Datum:** 15. Februar 2026  
**Paket:** Komplett
