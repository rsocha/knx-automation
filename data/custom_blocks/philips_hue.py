"""
Philips Hue Bridge (v1.0) – Remanent

Steuert Philips Hue Lampen über die Hue Bridge mittels phue-Bibliothek.

Voraussetzung:
  pip install phue

Ersteinrichtung:
  Beim ersten Verbinden MUSS der Link-Button auf der Hue Bridge
  gedrückt werden! Der Block versucht 30 Sekunden lang eine Registrierung.
  Danach ist die Verbindung dauerhaft gespeichert.

Eingänge:
- E1: Bridge IP-Adresse (z.B. 192.168.1.50)
- E2: Lampen-Nr. (1-basiert) ODER Lampenname (Text)
- E3: Ein/Aus (1=Ein, 0=Aus, <0 ignoriert)
- E4: Helligkeit (0-100%, <0 ignoriert) – wird auf 0-254 skaliert
- E5: Farbton/Hue (0-360°, <0 ignoriert) – wird auf 0-65535 skaliert
- E6: Sättigung (0-100%, <0 ignoriert) – wird auf 0-254 skaliert
- E7: Farbtemperatur Kelvin (2000-6500K, <0 ignoriert) – wird auf Mired umgerechnet
- E8: Trigger (1 = Verbinden/Reload)
- E9: Szene aktivieren (Szenen-Name, leer = ignoriert)
- E10: Übergangszeit in Sekunden (0-30, Standard: 0.4)

Ausgänge:
- A1: Verbunden (1/0)
- A2: Anzahl Lampen
- A3: Gewählte Lampe – Name
- A4: Gewählte Lampe – Ein/Aus (1/0)
- A5: Gewählte Lampe – Helligkeit (0-100%)
- A6: Gewählte Lampe – Erreichbar (1/0)
- A7: Alle Lampen als JSON [{id, name, on, bri, reachable, type}, ...]
- A8: Status-Text
- A9: Alle Szenen als JSON [{id, name, lights}, ...]
- A10: Debug

Besonderheiten:
- Erstverbindung erfordert Tastendruck auf der Bridge
- Credentials werden in /tmp/phue_bridge_<IP>.json gespeichert
- Automatischer Reconnect bei Verbindungsfehlern
- Update-Loop liest alle X Minuten den Lampenstatus
- Lampen können per Nummer (1-basiert) oder Name angesprochen werden
"""

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

try:
    from logic.base import LogicBlock
except ImportError:
    class LogicBlock:
        """Stub for standalone testing"""
        ID = 0; NAME = ""; VERSION = ""; CATEGORY = ""
        REMANENT = False
        INPUTS: dict = {}; OUTPUTS: dict = {}
        def __init__(self, instance_id=None, db_manager=None):
            self._input_values = {}; self._output_values = {}
        def get_input(self, key, default=None):
            return self._input_values.get(key, default)
        def set_output(self, key, value):
            self._output_values[key] = value
        def debug(self, key, msg):
            logger.info(f"[{self.NAME}] {key}: {msg}")


class PhilipsHue(LogicBlock):
    """Philips Hue Bridge – Lampensteuerung via phue"""

    ID = 20060
    NAME = "Philips Hue"
    VERSION = "1.0"
    CATEGORY = "Geräte"
    REMANENT = True

    INPUTS = {
        "E1":  {"name": "Bridge IP",               "type": "text",   "description": "IP-Adresse der Hue Bridge"},
        "E2":  {"name": "Lampe (Nr/Name)",          "type": "text",   "description": "Lampen-Nr. (1-basiert) oder Name"},
        "E3":  {"name": "Ein/Aus",                  "type": "float",  "description": "1=Ein, 0=Aus, <0 ignoriert"},
        "E4":  {"name": "Helligkeit %",             "type": "float",  "description": "0-100%, <0 ignoriert"},
        "E5":  {"name": "Farbton (Hue) °",          "type": "float",  "description": "0-360°, <0 ignoriert"},
        "E6":  {"name": "Sättigung %",              "type": "float",  "description": "0-100%, <0 ignoriert"},
        "E7":  {"name": "Farbtemp. Kelvin",         "type": "float",  "description": "2000-6500K, <0 ignoriert"},
        "E8":  {"name": "Trigger",                  "type": "float",  "description": "1 = Verbinden/Reload"},
        "E9":  {"name": "Szene Name",               "type": "text",   "description": "Szene aktivieren (leer=ignoriert)"},
        "E10": {"name": "Übergangszeit (s)",         "type": "float",  "description": "0-30 Sekunden, Standard 0.4"},
    }

    OUTPUTS = {
        "A1":  {"name": "Verbunden",                "type": "float",  "description": "1 = mit Bridge verbunden"},
        "A2":  {"name": "Anzahl Lampen",            "type": "float",  "description": "Anzahl der Lampen"},
        "A3":  {"name": "Lampe Name",               "type": "text",   "description": "Name der gewählten Lampe"},
        "A4":  {"name": "Lampe Ein/Aus",            "type": "float",  "description": "1=Ein, 0=Aus"},
        "A5":  {"name": "Lampe Helligkeit %",       "type": "float",  "description": "Helligkeit 0-100%"},
        "A6":  {"name": "Lampe Erreichbar",         "type": "float",  "description": "1=Erreichbar, 0=Nicht erreichbar"},
        "A7":  {"name": "Alle Lampen (JSON)",       "type": "text",   "description": "JSON Array aller Lampen"},
        "A8":  {"name": "Status",                   "type": "text",   "description": "Status-/Fehlermeldung"},
        "A9":  {"name": "Szenen (JSON)",            "type": "text",   "description": "JSON Array aller Szenen"},
        "A10": {"name": "Debug",                    "type": "text",   "description": "Debug-Informationen"},
    }

    def __init__(self, instance_id=None, db_manager=None):
        super().__init__(instance_id, db_manager)
        self._bridge = None
        self._connected = False
        self._running = False
        self._task = None
        self._lights_cache = []
        self._scenes_cache = []
        self._last_host = ""
        self._last_light_select = ""
        self._last_scene = ""

    # ─── Lifecycle ──────────────────────────────────────────────────────

    def on_start(self):
        """Start the block – connect to bridge and begin update loop"""
        self._running = True
        self._task = asyncio.ensure_future(self._run())

    def on_stop(self):
        """Stop the block"""
        self._running = False
        if self._task:
            self._task.cancel()
        self._bridge = None
        self._connected = False

    def on_input_change(self, key: str, value: Any):
        """Handle input changes"""
        if key == "E8" and value and float(value) >= 1:
            # Trigger: reconnect
            asyncio.ensure_future(self._connect())
            return

        if key == "E3":
            # On/Off
            asyncio.ensure_future(self._set_on_off(value))
            return

        if key in ("E4", "E5", "E6", "E7"):
            # Light properties
            asyncio.ensure_future(self._set_light_property(key, value))
            return

        if key == "E9" and value and str(value).strip():
            # Activate scene
            asyncio.ensure_future(self._activate_scene(str(value).strip()))
            return

        if key == "E2":
            # Light selection changed → update outputs
            asyncio.ensure_future(self._update_selected_light())
            return

        if key == "E1" and value and str(value).strip() != self._last_host:
            # IP changed → reconnect
            asyncio.ensure_future(self._connect())
            return

    # ─── Main loop ──────────────────────────────────────────────────────

    async def _run(self):
        """Main loop: connect and periodically update light status"""
        await asyncio.sleep(2)  # Startup delay

        await self._connect()

        while self._running:
            try:
                # Update interval from E10 or default 60s
                try:
                    interval_raw = self.get_input("E10")
                    interval = max(30, float(interval_raw or 60) if interval_raw else 60)
                except (ValueError, TypeError):
                    interval = 60

                await asyncio.sleep(interval)

                if self._connected and self._bridge:
                    await self._load_lights()
                    await self._update_selected_light()
                else:
                    await self._connect()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.debug("Loop-Fehler", str(e))
                await asyncio.sleep(30)

    # ─── Connection ─────────────────────────────────────────────────────

    async def _connect(self):
        """Connect to the Hue Bridge"""
        host = str(self.get_input("E1", "") or "").strip()
        if not host:
            self.set_output("A8", "Keine Bridge-IP konfiguriert")
            self.set_output("A1", 0)
            return

        self._last_host = host
        self.set_output("A8", f"Verbinde mit {host}...")
        self.debug("Connect", f"Verbinde mit {host}")

        try:
            from phue import Bridge

            # Config file for storing credentials
            config_path = f"/tmp/phue_bridge_{host.replace('.', '_')}.json"

            # Run blocking connection in executor
            loop = asyncio.get_event_loop()
            bridge = await loop.run_in_executor(
                None,
                lambda: Bridge(ip=host, config_file_path=config_path)
            )

            # Try to connect (may require button press on first run)
            await loop.run_in_executor(None, bridge.connect)

            self._bridge = bridge
            self._connected = True
            self.set_output("A1", 1)

            # Load lights and scenes
            await self._load_lights()
            await self._load_scenes()
            await self._update_selected_light()

            self.set_output("A8", f"Verbunden – {len(self._lights_cache)} Lampen")
            self.debug("Connect", f"OK – {len(self._lights_cache)} Lampen, {len(self._scenes_cache)} Szenen")

        except ImportError:
            self.set_output("A8", "FEHLER: phue nicht installiert (pip install phue)")
            self.set_output("A1", 0)
            self.debug("Connect", "phue library fehlt!")

        except Exception as e:
            err_msg = str(e)
            if "button" in err_msg.lower() or "link" in err_msg.lower() or "101" in err_msg:
                self.set_output("A8", "BUTTON auf Bridge drücken und Trigger senden!")
            else:
                self.set_output("A8", f"Verbindungsfehler: {err_msg[:80]}")
            self.set_output("A1", 0)
            self._connected = False
            self.debug("Connect-Fehler", err_msg[:120])

    # ─── Load data ──────────────────────────────────────────────────────

    async def _load_lights(self):
        """Load all lights from the bridge"""
        if not self._bridge:
            return

        try:
            loop = asyncio.get_event_loop()
            api = await loop.run_in_executor(None, self._bridge.get_api)

            lights_data = api.get("lights", {})
            lights_list = []

            for light_id, info in sorted(lights_data.items(), key=lambda x: int(x[0])):
                state = info.get("state", {})
                bri_raw = state.get("bri", 0)
                lights_list.append({
                    "id": int(light_id),
                    "name": info.get("name", f"Light {light_id}"),
                    "on": state.get("on", False),
                    "bri": round(bri_raw / 254 * 100) if bri_raw else 0,
                    "bri_raw": bri_raw,
                    "hue": state.get("hue"),
                    "sat": state.get("sat"),
                    "ct": state.get("ct"),
                    "reachable": state.get("reachable", False),
                    "type": info.get("type", ""),
                    "modelid": info.get("modelid", ""),
                    "colormode": state.get("colormode", ""),
                })

            self._lights_cache = lights_list
            self.set_output("A2", len(lights_list))
            self.set_output("A7", json.dumps(lights_list, ensure_ascii=False))

        except Exception as e:
            self.debug("LoadLights-Fehler", str(e))
            if "connection" in str(e).lower() or "timeout" in str(e).lower():
                self._connected = False
                self.set_output("A1", 0)
                self.set_output("A8", f"Verbindung verloren: {str(e)[:60]}")

    async def _load_scenes(self):
        """Load all scenes from the bridge"""
        if not self._bridge:
            return

        try:
            loop = asyncio.get_event_loop()
            api = await loop.run_in_executor(None, self._bridge.get_api)

            scenes_data = api.get("scenes", {})
            scenes_list = []

            for scene_id, info in scenes_data.items():
                scenes_list.append({
                    "id": scene_id,
                    "name": info.get("name", ""),
                    "lights": info.get("lights", []),
                    "type": info.get("type", ""),
                })

            # Sort by name
            scenes_list.sort(key=lambda s: s["name"].lower())
            self._scenes_cache = scenes_list
            self.set_output("A9", json.dumps(scenes_list, ensure_ascii=False))

        except Exception as e:
            self.debug("LoadScenes-Fehler", str(e))

    # ─── Selected light ────────────────────────────────────────────────

    def _resolve_light(self):
        """Resolve E2 input to a light ID (int) for phue.
        Returns (light_id: int, light_info: dict) or (None, None)."""
        select = str(self.get_input("E2", "") or "").strip()
        if not select or not self._lights_cache:
            return None, None

        # Try as number first (1-based)
        try:
            idx = int(float(select))
            for light in self._lights_cache:
                if light["id"] == idx:
                    return idx, light
            # Fallback: index into list
            if 1 <= idx <= len(self._lights_cache):
                light = self._lights_cache[idx - 1]
                return light["id"], light
            return None, None
        except (ValueError, TypeError):
            pass

        # Try as name (case-insensitive)
        select_lower = select.lower()
        for light in self._lights_cache:
            if light["name"].lower() == select_lower:
                return light["id"], light

        # Partial match
        for light in self._lights_cache:
            if select_lower in light["name"].lower():
                return light["id"], light

        return None, None

    async def _update_selected_light(self):
        """Update outputs for the currently selected light"""
        light_id, light = self._resolve_light()

        if light:
            self.set_output("A3", light["name"])
            self.set_output("A4", 1 if light["on"] else 0)
            self.set_output("A5", light["bri"])
            self.set_output("A6", 1 if light["reachable"] else 0)
        else:
            select = str(self.get_input("E2", "") or "").strip()
            self.set_output("A3", f"? ({select})" if select else "")
            self.set_output("A4", 0)
            self.set_output("A5", 0)
            self.set_output("A6", 0)

    # ─── Control ────────────────────────────────────────────────────────

    def _get_transition_time(self) -> Optional[int]:
        """Get transition time in deciseconds from E10"""
        try:
            val = self.get_input("E10")
            if val is not None and val != "":
                secs = float(val)
                if secs >= 0:
                    return max(0, min(300, int(secs * 10)))  # 0-30sec in deciseconds
        except (ValueError, TypeError):
            pass
        return None  # phue default (0.4s = 4 deciseconds)

    async def _set_on_off(self, value):
        """Set light on/off"""
        if not self._bridge or not self._connected:
            return

        try:
            val = float(value)
        except (ValueError, TypeError):
            return

        if val < 0:
            return

        light_id, _ = self._resolve_light()
        if light_id is None:
            self.debug("Ein/Aus", "Keine Lampe ausgewählt")
            return

        on_state = val >= 1
        tt = self._get_transition_time()

        try:
            loop = asyncio.get_event_loop()
            if tt is not None:
                await loop.run_in_executor(
                    None,
                    lambda: self._bridge.set_light(light_id, 'on', on_state, transitiontime=tt)
                )
            else:
                await loop.run_in_executor(
                    None,
                    lambda: self._bridge.set_light(light_id, 'on', on_state)
                )

            self.set_output("A4", 1 if on_state else 0)
            self.debug("Ein/Aus", f"Lampe {light_id}: {'Ein' if on_state else 'Aus'}")

            # Refresh after short delay
            await asyncio.sleep(0.5)
            await self._load_lights()
            await self._update_selected_light()

        except Exception as e:
            self.set_output("A8", f"Fehler Ein/Aus: {str(e)[:60]}")
            self.debug("Ein/Aus-Fehler", str(e))

    async def _set_light_property(self, key: str, value):
        """Set a light property (brightness, hue, saturation, color temp)"""
        if not self._bridge or not self._connected:
            return

        try:
            val = float(value)
        except (ValueError, TypeError):
            return

        if val < 0:
            return

        light_id, _ = self._resolve_light()
        if light_id is None:
            return

        tt = self._get_transition_time()
        command = {}

        if key == "E4":
            # Brightness: 0-100% → 0-254
            bri = max(0, min(254, int(val / 100 * 254)))
            command["bri"] = bri
            # Auto turn on if brightness > 0
            if bri > 0:
                command["on"] = True

        elif key == "E5":
            # Hue: 0-360° → 0-65535
            hue_val = max(0, min(65535, int(val / 360 * 65535)))
            command["hue"] = hue_val
            command["on"] = True

        elif key == "E6":
            # Saturation: 0-100% → 0-254
            sat = max(0, min(254, int(val / 100 * 254)))
            command["sat"] = sat

        elif key == "E7":
            # Color temperature: Kelvin → Mired (1000000/K)
            kelvin = max(2000, min(6500, val))
            mired = max(153, min(500, int(1000000 / kelvin)))
            command["ct"] = mired
            command["on"] = True

        if not command:
            return

        if tt is not None:
            command["transitiontime"] = tt

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._bridge.set_light(light_id, command)
            )

            prop_names = {"E4": "Helligkeit", "E5": "Farbton", "E6": "Sättigung", "E7": "Farbtemp."}
            self.debug("Set", f"Lampe {light_id}: {prop_names.get(key, key)} = {val}")

            # Refresh
            await asyncio.sleep(0.3)
            await self._load_lights()
            await self._update_selected_light()

        except Exception as e:
            self.set_output("A8", f"Fehler Setzen: {str(e)[:60]}")
            self.debug("Set-Fehler", str(e))

    async def _activate_scene(self, scene_name: str):
        """Activate a scene by name"""
        if not self._bridge or not self._connected:
            return

        # Find scene by name (case-insensitive)
        scene_id = None
        scene_name_lower = scene_name.lower()

        for scene in self._scenes_cache:
            if scene["name"].lower() == scene_name_lower:
                scene_id = scene["id"]
                break

        # Partial match
        if not scene_id:
            for scene in self._scenes_cache:
                if scene_name_lower in scene["name"].lower():
                    scene_id = scene["id"]
                    break

        if not scene_id:
            self.set_output("A8", f"Szene '{scene_name}' nicht gefunden")
            self.debug("Szene", f"Nicht gefunden: {scene_name}")
            return

        try:
            loop = asyncio.get_event_loop()

            # Activate scene via group 0 (all lights)
            # phue: b.activate_scene(group_id, scene_id)
            await loop.run_in_executor(
                None,
                lambda: self._bridge.activate_scene(0, scene_id)
            )

            self.set_output("A8", f"Szene '{scene_name}' aktiviert")
            self.debug("Szene", f"Aktiviert: {scene_name} ({scene_id})")

            # Refresh
            await asyncio.sleep(1)
            await self._load_lights()
            await self._update_selected_light()

        except Exception as e:
            self.set_output("A8", f"Szene-Fehler: {str(e)[:60]}")
            self.debug("Szene-Fehler", str(e))

    # ─── Remanent state ─────────────────────────────────────────────────

    def get_remanent_state(self) -> dict:
        """Save state for persistence across restarts"""
        return {
            "outputs": dict(self._output_values),
            "lights_cache": self._lights_cache,
            "scenes_cache": self._scenes_cache,
        }

    def restore_remanent_state(self, state: dict):
        """Restore state from persistence"""
        if not state:
            return
        if "outputs" in state:
            for key, val in state["outputs"].items():
                self._output_values[key] = val
        if "lights_cache" in state:
            self._lights_cache = state["lights_cache"]
        if "scenes_cache" in state:
            self._scenes_cache = state["scenes_cache"]
