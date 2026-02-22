import { useState, useEffect } from "react";
import type { VisuRoom, VseTemplate, VseWidgetInstance } from "@/types/vse";
import DraggableWidget from "@/components/visu/DraggableWidget";
import { getApiBase } from "@/services/knxApi";

// Use correct paths with /static prefix
const BUILTIN_TEMPLATES: string[] = [
  "/static/vse/switch-card.vse.json",
  "/static/vse/strompreis-chart.vse.json",
  "/static/vse/gauge-barometer.vse.json",
  "/static/vse/sensor-card.vse.json",
  "/static/vse/markdown-card.vse.json",
  "/static/vse/simple-value.vse.json",
  "/static/vse/simple-toggle.vse.json",
  "/static/vse/compass-speedometer.vse.json",
];

const TITLE_TEMPLATE: VseTemplate = {
  id: "title-card",
  name: "Titel-Karte",
  description: "Header/Titel Karte",
  category: "Layout",
  width: 200,
  height: 50,
  render: "titleCard",
  inputs: {},
  variables: { subtitle: { name: "subtitle", type: "text", default: "" } },
};

async function loadRoomsFromServer(): Promise<VisuRoom[]> {
  try {
    const res = await fetch(`${getApiBase()}/visu/rooms`, {
      headers: { "ngrok-skip-browser-warning": "true" }
    });
    if (res.ok) {
      const data = await res.json();
      return Array.isArray(data) ? data : [];
    }
  } catch (err) {
    console.error("[Panel] Failed to load rooms from server:", err);
  }
  return [];
}

export default function VisuPanel() {
  const [rooms, setRooms] = useState<VisuRoom[]>([]);
  const [activeRoomId, setActiveRoomId] = useState<string | null>(null);
  const [templates, setTemplates] = useState<VseTemplate[]>([]);
  const [loading, setLoading] = useState(true);

  // Load rooms from server
  useEffect(() => {
    loadRoomsFromServer().then((serverRooms) => {
      console.log("[Panel] Loaded rooms:", serverRooms.length);
      setRooms(serverRooms);
      setLoading(false);
    });
  }, []);

  // Load templates
  useEffect(() => {
    Promise.all(
      BUILTIN_TEMPLATES.map((url) =>
        fetch(url).then((r) => r.json()).catch(() => null)
      )
    ).then((results) => {
      const loaded = results.filter(Boolean) as VseTemplate[];
      console.log("[Panel] Loaded templates:", loaded.map(t => t.id));
      setTemplates([...loaded, TITLE_TEMPLATE]);
    });
  }, []);

  // Set active room when rooms load
  useEffect(() => {
    if (rooms.length > 0 && !rooms.find((r) => r.id === activeRoomId)) {
      setActiveRoomId(rooms[0].id);
    }
  }, [rooms, activeRoomId]);

  const activeRoom = rooms.find((r) => r.id === activeRoomId);

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-muted-foreground">Lade Visualisierung...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Room tabs */}
      {rooms.length > 1 && (
        <div className="flex gap-1 p-2 overflow-x-auto bg-card border-b border-border shrink-0">
          {rooms.map((r) => (
            <button
              key={r.id}
              onClick={() => setActiveRoomId(r.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors ${
                r.id === activeRoomId
                  ? "bg-primary text-primary-foreground"
                  : "bg-secondary text-muted-foreground"
              }`}
            >
              {r.name}
            </button>
          ))}
        </div>
      )}

      {/* Widgets */}
      <div className="flex-1 relative overflow-auto p-2">
        {activeRoom?.widgets.map((widget) => {
          const template = templates.find((t) => t.id === widget.templateId);
          if (!template) {
            console.warn("[Panel] Template not found:", widget.templateId);
            return null;
          }
          return (
            <DraggableWidget
              key={widget.id}
              widget={widget}
              template={template}
              editMode={false}
              onMove={() => {}}
              onResize={() => {}}
              onEdit={() => {}}
              onRemove={() => {}}
            />
          );
        })}
        {rooms.length === 0 && (
          <div className="flex items-center justify-center h-64 text-muted-foreground text-sm text-center px-4">
            Keine Räume vorhanden.<br/>
            Erstelle Widgets auf der Visu-Seite.
          </div>
        )}
        {activeRoom && activeRoom.widgets.length === 0 && (
          <div className="flex items-center justify-center h-64 text-muted-foreground text-sm">
            Keine Widgets in diesem Raum
          </div>
        )}
      </div>
    </div>
  );
}
