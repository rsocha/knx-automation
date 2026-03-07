"""
Philips Hue Bridge (v2.1) – Remanent

Steuert Philips Hue Lampen und Gruppen über die Hue Bridge via phue.

============================================================
INSTALLATION:
  pip install phue

ERSTEINRICHTUNG:
  1. Block hinzufügen, an E1 die IP der Bridge setzen
  2. Auf der Hue Bridge den LINK-BUTTON drücken
  3. Trigger (E8) auf 1 setzen
  4. Der Block registriert sich automatisch und speichert
     die Credentials in /tmp/phue_bridge_<IP>.json
  5. Ab jetzt verbindet sich der Block automatisch bei jedem Start.

LAMPE STEUERN:
  An E2 die Lampen-Nummer oder den Namen setzen:
    E2 = 1         → Lampe Nr. 1
    E2 = Küche     → Lampe mit Namen "Küche"

GRUPPE STEUERN:
  An E2 den Gruppen-Namen mit "G:" Prefix setzen:
    E2 = G:Wohnzimmer  → Gruppe "Wohnzimmer"
    E2 = G:1            → Gruppe Nr. 1
  Gruppen steuern alle enthaltenen Lampen gleichzeitig.

GERÄTE AUSLESEN:
  A11 = Lesbare Lampenliste:  "1 → Küche (Ein, 80%)"
  A12 = Lesbare Gruppenliste: "G:1 → Wohnzimmer [Lampe1, Lampe2] (Ein)"
  A8  = JSON aller Lampen,  A13 = JSON aller Gruppen,  A10 = JSON aller Szenen
============================================================

Eingänge:
- E1:  Bridge IP-Adresse (z.B. 192.168.1.50)
- E2:  Lampe (Nr/Name) oder Gruppe (G:Nr / G:Name)
- E3:  Ein/Aus (1=Ein, 0=Aus, <0 ignoriert)
- E4:  Helligkeit (0-100%)
- E5:  Farbton/Hue (0-360°)
- E6:  Sättigung (0-100%)
- E7:  Farbtemperatur Kelvin (2000-6500K)
- E8:  Trigger (1 = Verbinden/Reload)
- E9:  Szene aktivieren (Name, optional mit G:Gruppe)
- E10: Übergangszeit in Sekunden (0-30)

Ausgänge:
- A1:  Verbunden (1/0)
- A2:  Anzahl Lampen
- A3:  Gewähltes Ziel – Name
- A4:  Gewähltes Ziel – Ein/Aus (1/0)
- A5:  Gewähltes Ziel – Helligkeit (0-100%)
- A6:  Gewähltes Ziel – Farbtemperatur (Kelvin, 0=unbekannt)
- A7:  Gewähltes Ziel – Erreichbar (1/0) bzw. all_on bei Gruppen
- A8:  Alle Lampen (JSON)
- A9:  Status-Text
- A10: Alle Szenen (JSON)
- A11: Lampen-Liste (Text)
- A12: Gruppen-Liste (Text)
- A13: Alle Gruppen (JSON)
- A14: Anzahl Gruppen
- A15: Debug

Versionshistorie:
v2.1 – Farbtemperatur-Ausgang A6 (Kelvin), Ausgänge neu nummeriert A6-A15
v2.0 – Gruppen-Unterstützung: G: Prefix an E2, Gruppen-Ausgänge,
       set_group für Gruppensteuerung, Szene mit Gruppen-ID
v1.3 – sys.path Fix für phue Import
v1.2 – Lifecycle-Fix, execute(), HELP-Text
v1.1 – Geräteliste A10
v1.0 – Erstversion
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

try:
    from logic.base import LogicBlock
except ImportError:
    from abc import ABC, abstractmethod
    class LogicBlock(ABC):
        ID = 0; NAME = ""; VERSION = ""; CATEGORY = ""
        REMANENT = False; HELP = ""
        INPUTS: dict = {}; OUTPUTS: dict = {}
        def __init__(self, instance_id=None):
            self.instance_id = instance_id
            self._input_values = {}; self._output_values = {}
            self._running = False; self._debug_values = {}
        def get_input(self, key):
            return self._input_values.get(key)
        def set_output(self, key, value):
            self._output_values[key] = value
        def debug(self, key, msg):
            self._debug_values[key] = str(msg)
        def on_start(self): self._running = True
        def on_stop(self): self._running = False
        @abstractmethod
        def execute(self, triggered_by=None): pass


class PhilipsHue(LogicBlock):
    """Philips Hue Bridge – Lampen- und Gruppensteuerung via phue"""

    ID = 20060
    NAME = "Philips Hue"
    VERSION = "2.1"
    CATEGORY = "Geräte"
    REMANENT = True

    HELP = """
Philips Hue Bridge Integration

INSTALLATION:
  pip install phue

ERSTEINRICHTUNG:
  1. E1 = IP-Adresse der Hue Bridge
  2. LINK-BUTTON auf der Bridge drücken
  3. E8 = 1 (Trigger) → Block registriert sich
  4. Ab jetzt automatische Verbindung beim Start

LAMPE STEUERN (E2):
  E2 = 1           → Lampe Nr. 1
  E2 = Küche       → Lampe "Küche"

GRUPPE STEUERN (E2 mit G: Prefix):
  E2 = G:Wohnzimmer → Gruppe "Wohnzimmer"
  E2 = G:1          → Gruppe Nr. 1

STEUERUNG (gilt für Lampen UND Gruppen):
  E3  = 1/0       → Ein/Aus
  E4  = 0-100     → Helligkeit %
  E5  = 0-360     → Farbton °
  E6  = 0-100     → Sättigung %
  E7  = 2000-6500 → Farbtemperatur K
  E9  = Szenenname → Szene aktivieren
  E10 = 0-30      → Übergangszeit Sek.

GERÄTE AUSLESEN:
  A11 = Lampenliste: "1 → Küche (Ein, 80%)"
  A12 = Gruppenliste: "G:1 → Wohnzimmer [Küche, Flur] (Ein)"
  A8  = JSON Lampen, A13 = JSON Gruppen, A10 = JSON Szenen

AUSGÄNGE GEWÄHLTES ZIEL (A3-A7):
  A3 = Name, A4 = Ein/Aus, A5 = Helligkeit %
  A6 = Farbtemperatur (Kelvin), A7 = Erreichbar/All_on
"""

    INPUTS = {
        "E1":  {"name": "Bridge IP",               "type": "text",   "description": "IP-Adresse der Hue Bridge"},
        "E2":  {"name": "Ziel (Lampe/G:Gruppe)",    "type": "text",   "description": "Lampe: Nr/Name – Gruppe: G:Nr oder G:Name"},
        "E3":  {"name": "Ein/Aus",                  "type": "float",  "description": "1=Ein, 0=Aus, <0 ignoriert"},
        "E4":  {"name": "Helligkeit %",             "type": "float",  "description": "0-100%, <0 ignoriert"},
        "E5":  {"name": "Farbton (Hue) °",          "type": "float",  "description": "0-360°, <0 ignoriert"},
        "E6":  {"name": "Sättigung %",              "type": "float",  "description": "0-100%, <0 ignoriert"},
        "E7":  {"name": "Farbtemp. Kelvin",         "type": "float",  "description": "2000-6500K, <0 ignoriert"},
        "E8":  {"name": "Trigger",                  "type": "float",  "description": "1 = Verbinden/Reload"},
        "E9":  {"name": "Szene Name",               "type": "text",   "description": "Szene aktivieren"},
        "E10": {"name": "Übergangszeit (s)",         "type": "float",  "description": "0-30 Sekunden"},
    }

    OUTPUTS = {
        "A1":  {"name": "Verbunden",                "type": "float"},
        "A2":  {"name": "Anzahl Lampen",            "type": "float"},
        "A3":  {"name": "Ziel Name",                "type": "text",   "description": "Name der gewählten Lampe/Gruppe"},
        "A4":  {"name": "Ziel Ein/Aus",             "type": "float"},
        "A5":  {"name": "Ziel Helligkeit %",        "type": "float"},
        "A6":  {"name": "Ziel Farbtemp. K",         "type": "float",  "description": "Farbtemperatur in Kelvin"},
        "A7":  {"name": "Ziel Erreichbar/AnyOn",    "type": "float"},
        "A8":  {"name": "Alle Lampen (JSON)",       "type": "text"},
        "A9":  {"name": "Status",                   "type": "text"},
        "A10": {"name": "Szenen (JSON)",            "type": "text"},
        "A11": {"name": "Lampen-Liste",             "type": "text",   "description": "1 → Name (Ein, 80%)"},
        "A12": {"name": "Gruppen-Liste",            "type": "text",   "description": "G:1 → Name [Lampen] (Ein)"},
        "A13": {"name": "Alle Gruppen (JSON)",      "type": "text"},
        "A14": {"name": "Anzahl Gruppen",           "type": "float"},
        "A15": {"name": "Debug",                    "type": "text"},
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._bridge = None
        self._connected = False
        self._update_task = None
        self._lights_cache = []   # [{id, name, on, bri, ...}, ...]
        self._groups_cache = []   # [{id, name, on, any_on, bri, lights, type}, ...]
        self._scenes_cache = []
        self._last_host = ""

    # ─── Lifecycle ──────────────────────────────────────────────────────

    def on_start(self):
        super().on_start()
        self.debug("Version", self.VERSION)
        if self._update_task is None or self._update_task.done():
            self._update_task = asyncio.ensure_future(self._update_loop())

    def on_stop(self):
        if self._update_task and not self._update_task.done():
            self._update_task.cancel()
            self._update_task = None
        self._bridge = None
        self._connected = False
        super().on_stop()

    def execute(self, triggered_by=None):
        if triggered_by == "E8":
            val = self.get_input("E8")
            if val and float(val or 0) >= 1:
                asyncio.ensure_future(self._connect())
        elif triggered_by == "E3":
            asyncio.ensure_future(self._send_command())
        elif triggered_by in ("E4", "E5", "E6", "E7"):
            asyncio.ensure_future(self._send_property(triggered_by))
        elif triggered_by == "E9":
            scene = str(self.get_input("E9") or "").strip()
            if scene:
                asyncio.ensure_future(self._activate_scene(scene))
        elif triggered_by == "E2":
            asyncio.ensure_future(self._update_selected())
        elif triggered_by == "E1":
            host = str(self.get_input("E1") or "").strip()
            if host and host != self._last_host:
                asyncio.ensure_future(self._connect())

    # ─── Main loop ──────────────────────────────────────────────────────

    async def _update_loop(self):
        await asyncio.sleep(3)
        await self._connect()
        while self._running:
            try:
                await asyncio.sleep(60)
                if self._connected and self._bridge:
                    await self._load_all()
                    await self._update_selected()
                else:
                    await self._connect()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.debug("Loop", str(e))
                await asyncio.sleep(30)

    # ─── Connection ─────────────────────────────────────────────────────

    async def _connect(self):
        host = str(self.get_input("E1") or "").strip()
        if not host:
            self.set_output("A9", "Keine Bridge-IP")
            self.set_output("A1", 0)
            return

        self._last_host = host
        self.set_output("A9", f"Verbinde mit {host}...")

        Bridge = None
        try:
            from phue import Bridge
        except ImportError:
            import sys
            for p in ["/usr/local/lib/python3.9/site-packages",
                      "/usr/local/lib/python3.10/site-packages",
                      "/usr/local/lib/python3.11/site-packages",
                      "/usr/local/lib/python3.12/site-packages",
                      "/usr/lib/python3/dist-packages"]:
                if p not in sys.path:
                    sys.path.append(p)
            try:
                from phue import Bridge
            except ImportError:
                pass

        if Bridge is None:
            import sys
            self.set_output("A9", f"phue nicht gefunden (Python: {sys.executable})")
            self.set_output("A1", 0)
            self.debug("Import", f"path: {sys.path[:3]}")
            return

        try:
            config = f"/tmp/phue_bridge_{host.replace('.', '_')}.json"
            loop = asyncio.get_event_loop()
            bridge = await loop.run_in_executor(None,
                lambda: Bridge(ip=host, config_file_path=config))
            await loop.run_in_executor(None, bridge.connect)

            self._bridge = bridge
            self._connected = True
            self.set_output("A1", 1)

            await self._load_all()
            await self._update_selected()

            nl = len(self._lights_cache)
            ng = len(self._groups_cache)
            ns = len(self._scenes_cache)
            self.set_output("A9", f"Verbunden – {nl} Lampen, {ng} Gruppen, {ns} Szenen")
            self.debug("Connect", f"OK – {nl}L {ng}G {ns}S")

        except Exception as e:
            err = str(e)
            if "button" in err.lower() or "link" in err.lower() or "101" in err:
                self.set_output("A9", "BUTTON auf Bridge drücken, dann Trigger!")
            else:
                self.set_output("A9", f"Fehler: {err[:80]}")
            self.set_output("A1", 0)
            self._connected = False
            self.debug("Fehler", err[:120])

    # ─── Load data ──────────────────────────────────────────────────────

    async def _load_all(self):
        """Load lights, groups, scenes from bridge"""
        if not self._bridge:
            return
        try:
            loop = asyncio.get_event_loop()
            api = await loop.run_in_executor(None, self._bridge.get_api)

            # ── Lights ──
            lights_data = api.get("lights", {})
            lights = []
            light_names = {}  # id → name for group display
            for lid, info in sorted(lights_data.items(), key=lambda x: int(x[0])):
                st = info.get("state", {})
                bri_raw = st.get("bri", 0)
                name = info.get("name", f"Light {lid}")
                light_names[lid] = name
                lights.append({
                    "id": int(lid),
                    "name": name,
                    "on": st.get("on", False),
                    "bri": round(bri_raw / 254 * 100) if bri_raw else 0,
                    "bri_raw": bri_raw,
                    "hue": st.get("hue"),
                    "sat": st.get("sat"),
                    "ct": st.get("ct"),
                    "reachable": st.get("reachable", False),
                    "type": info.get("type", ""),
                    "modelid": info.get("modelid", ""),
                    "colormode": st.get("colormode", ""),
                })
            self._lights_cache = lights
            self.set_output("A2", len(lights))
            self.set_output("A8", json.dumps(lights, ensure_ascii=False))

            # Readable lights list
            lines = []
            for l in lights:
                s = "Ein" if l["on"] else "Aus"
                if l["on"]:
                    s += f", {l['bri']}%"
                if not l["reachable"]:
                    s += ", ✗"
                lines.append(f"{l['id']} → {l['name']} ({s})")
            self.set_output("A11", "\n".join(lines))

            # ── Groups ──
            groups_data = api.get("groups", {})
            groups = []
            for gid, info in sorted(groups_data.items(), key=lambda x: int(x[0])):
                action = info.get("action", {})
                state = info.get("state", {})
                bri_raw = action.get("bri", 0)
                light_ids = info.get("lights", [])
                member_names = [light_names.get(lid, f"#{lid}") for lid in light_ids]
                groups.append({
                    "id": int(gid),
                    "name": info.get("name", f"Group {gid}"),
                    "type": info.get("type", ""),       # Room, Zone, LightGroup
                    "class": info.get("class", ""),      # Living room, Kitchen, ...
                    "on": action.get("on", False),
                    "any_on": state.get("any_on", False),
                    "all_on": state.get("all_on", False),
                    "bri": round(bri_raw / 254 * 100) if bri_raw else 0,
                    "bri_raw": bri_raw,
                    "hue": action.get("hue"),
                    "sat": action.get("sat"),
                    "ct": action.get("ct"),
                    "lights": light_ids,
                    "light_names": member_names,
                })
            self._groups_cache = groups
            self.set_output("A13", json.dumps(groups, ensure_ascii=False))
            self.set_output("A14", len(groups))

            # Readable groups list
            glines = []
            for g in groups:
                s = "Ein" if g["any_on"] else "Aus"
                if g["all_on"]:
                    s = "Alle Ein"
                if g["any_on"] and g["bri"]:
                    s += f", {g['bri']}%"
                members = ", ".join(g["light_names"][:4])
                if len(g["light_names"]) > 4:
                    members += f", +{len(g['light_names'])-4}"
                gtype = g["type"]
                if gtype == "Room":
                    gtype = "Raum"
                elif gtype == "Zone":
                    gtype = "Zone"
                glines.append(f"G:{g['id']} → {g['name']} ({gtype}) [{members}] ({s})")
            self.set_output("A12", "\n".join(glines))

            # ── Scenes ──
            scenes_data = api.get("scenes", {})
            scenes = []
            for sid, info in scenes_data.items():
                scenes.append({
                    "id": sid,
                    "name": info.get("name", ""),
                    "lights": info.get("lights", []),
                    "group": info.get("group", ""),
                    "type": info.get("type", ""),
                })
            scenes.sort(key=lambda s: s["name"].lower())
            self._scenes_cache = scenes
            self.set_output("A10", json.dumps(scenes, ensure_ascii=False))

        except Exception as e:
            self.debug("Load", str(e))
            if "connect" in str(e).lower() or "timeout" in str(e).lower():
                self._connected = False
                self.set_output("A1", 0)
                self.set_output("A9", f"Verbindung verloren: {str(e)[:60]}")

    # ─── Resolve target ────────────────────────────────────────────────

    def _resolve_target(self):
        """Resolve E2 to target. Returns ('light', id, info) or ('group', id, info) or (None, None, None)"""
        select = str(self.get_input("E2") or "").strip()
        if not select:
            return None, None, None

        # ── Group? ──
        if select.upper().startswith("G:"):
            gsel = select[2:].strip()
            if not gsel or not self._groups_cache:
                return None, None, None

            # Try as number
            try:
                gid = int(float(gsel))
                for g in self._groups_cache:
                    if g["id"] == gid:
                        return "group", gid, g
                return None, None, None
            except (ValueError, TypeError):
                pass

            # By name (exact then partial)
            gl = gsel.lower()
            for g in self._groups_cache:
                if g["name"].lower() == gl:
                    return "group", g["id"], g
            for g in self._groups_cache:
                if gl in g["name"].lower():
                    return "group", g["id"], g
            return None, None, None

        # ── Light ──
        if not self._lights_cache:
            return None, None, None

        # Try as number
        try:
            idx = int(float(select))
            for l in self._lights_cache:
                if l["id"] == idx:
                    return "light", idx, l
            return None, None, None
        except (ValueError, TypeError):
            pass

        # By name
        sl = select.lower()
        for l in self._lights_cache:
            if l["name"].lower() == sl:
                return "light", l["id"], l
        for l in self._lights_cache:
            if sl in l["name"].lower():
                return "light", l["id"], l

        return None, None, None

    async def _update_selected(self):
        """Update A3-A7 for the selected target"""
        kind, tid, info = self._resolve_target()
        if kind == "light" and info:
            self.set_output("A3", info["name"])
            self.set_output("A4", 1 if info["on"] else 0)
            self.set_output("A5", info["bri"])
            # Farbtemperatur: Mired → Kelvin (1000000/mired)
            ct_mired = info.get("ct")
            self.set_output("A6", round(1000000 / ct_mired) if ct_mired and ct_mired > 0 else 0)
            self.set_output("A7", 1 if info["reachable"] else 0)
        elif kind == "group" and info:
            self.set_output("A3", f"⬡ {info['name']}")
            self.set_output("A4", 1 if info["any_on"] else 0)
            self.set_output("A5", info["bri"])
            ct_mired = info.get("ct")
            self.set_output("A6", round(1000000 / ct_mired) if ct_mired and ct_mired > 0 else 0)
            self.set_output("A7", 1 if info["all_on"] else 0)
        else:
            sel = str(self.get_input("E2") or "").strip()
            self.set_output("A3", f"? ({sel})" if sel else "")
            self.set_output("A4", 0)
            self.set_output("A5", 0)
            self.set_output("A6", 0)
            self.set_output("A7", 0)

    # ─── Control ────────────────────────────────────────────────────────

    def _get_tt(self) -> Optional[int]:
        try:
            val = self.get_input("E10")
            if val is not None and val != "":
                return max(0, min(300, int(float(val) * 10)))
        except (ValueError, TypeError):
            pass
        return None

    async def _send_command(self):
        """Ein/Aus from E3 → light or group"""
        if not self._bridge or not self._connected:
            return
        try:
            val = float(self.get_input("E3") or -1)
        except (ValueError, TypeError):
            return
        if val < 0:
            return

        kind, tid, _ = self._resolve_target()
        if not kind:
            self.debug("Ein/Aus", "Kein Ziel ausgewählt")
            return

        on = val >= 1
        tt = self._get_tt()
        loop = asyncio.get_event_loop()

        try:
            if kind == "light":
                if tt is not None:
                    await loop.run_in_executor(None,
                        lambda: self._bridge.set_light(tid, 'on', on, transitiontime=tt))
                else:
                    await loop.run_in_executor(None,
                        lambda: self._bridge.set_light(tid, 'on', on))
            else:  # group
                cmd = {"on": on}
                if tt is not None:
                    cmd["transitiontime"] = tt
                await loop.run_in_executor(None,
                    lambda: self._bridge.set_group(tid, cmd))

            self.set_output("A4", 1 if on else 0)
            self.debug("Ein/Aus", f"{kind} {tid}: {'Ein' if on else 'Aus'}")

            await asyncio.sleep(0.5)
            await self._load_all()
            await self._update_selected()
        except Exception as e:
            self.set_output("A9", f"Fehler: {str(e)[:60]}")

    async def _send_property(self, key: str):
        """Set bri/hue/sat/ct from E4-E7 → light or group"""
        if not self._bridge or not self._connected:
            return
        try:
            val = float(self.get_input(key) or -1)
        except (ValueError, TypeError):
            return
        if val < 0:
            return

        kind, tid, _ = self._resolve_target()
        if not kind:
            return

        tt = self._get_tt()
        cmd = {}

        if key == "E4":
            bri = max(0, min(254, int(val / 100 * 254)))
            cmd["bri"] = bri
            if bri > 0:
                cmd["on"] = True
        elif key == "E5":
            cmd["hue"] = max(0, min(65535, int(val / 360 * 65535)))
            cmd["on"] = True
        elif key == "E6":
            cmd["sat"] = max(0, min(254, int(val / 100 * 254)))
        elif key == "E7":
            kelvin = max(2000, min(6500, val))
            cmd["ct"] = max(153, min(500, int(1000000 / kelvin)))
            cmd["on"] = True

        if not cmd:
            return
        if tt is not None:
            cmd["transitiontime"] = tt

        loop = asyncio.get_event_loop()
        try:
            if kind == "light":
                await loop.run_in_executor(None, lambda: self._bridge.set_light(tid, cmd))
            else:
                await loop.run_in_executor(None, lambda: self._bridge.set_group(tid, cmd))

            names = {"E4": "Helligkeit", "E5": "Farbton", "E6": "Sättigung", "E7": "Farbtemp."}
            self.debug("Set", f"{kind} {tid}: {names.get(key)} = {val}")

            await asyncio.sleep(0.3)
            await self._load_all()
            await self._update_selected()
        except Exception as e:
            self.set_output("A9", f"Fehler: {str(e)[:60]}")

    async def _activate_scene(self, scene_name: str):
        """Activate scene by name. Optionally with group context."""
        if not self._bridge or not self._connected:
            return

        # Find scene
        sid = None
        sn = scene_name.lower()
        for sc in self._scenes_cache:
            if sc["name"].lower() == sn:
                sid = sc["id"]
                break
        if not sid:
            for sc in self._scenes_cache:
                if sn in sc["name"].lower():
                    sid = sc["id"]
                    break
        if not sid:
            self.set_output("A9", f"Szene '{scene_name}' nicht gefunden")
            return

        # Determine group_id: if E2 is G:x use that, else 0
        gid = 0
        kind, tid, _ = self._resolve_target()
        if kind == "group":
            gid = tid

        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, lambda: self._bridge.activate_scene(gid, sid))
            self.set_output("A9", f"Szene '{scene_name}' aktiviert" + (f" (Gruppe {gid})" if gid else ""))
            self.debug("Szene", f"{scene_name} → G:{gid}")

            await asyncio.sleep(1)
            await self._load_all()
            await self._update_selected()
        except Exception as e:
            self.set_output("A9", f"Szene-Fehler: {str(e)[:60]}")

    # ─── Remanent ───────────────────────────────────────────────────────

    def get_remanent_state(self) -> dict:
        return {
            "outputs": dict(self._output_values),
            "lights_cache": self._lights_cache,
            "groups_cache": self._groups_cache,
            "scenes_cache": self._scenes_cache,
        }

    def restore_remanent_state(self, state: dict):
        if not state:
            return
        for k, v in state.get("outputs", {}).items():
            self._output_values[k] = v
        self._lights_cache = state.get("lights_cache", [])
        self._groups_cache = state.get("groups_cache", [])
        self._scenes_cache = state.get("scenes_cache", [])
