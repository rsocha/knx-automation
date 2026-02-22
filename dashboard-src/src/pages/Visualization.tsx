import { useState, useEffect, useCallback, useRef } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { LayoutGrid, Plus, Monitor, Settings2, FileUp, Smartphone, Cloud, CloudOff, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import type { VisuRoom, VseTemplate, VseWidgetInstance, DEFAULT_CATEGORIES } from "@/types/vse";
import VisuPageTree from "@/components/visu/VisuPageTree";
import DeviceFrame from "@/components/visu/DeviceFrame";
import DraggableWidget from "@/components/visu/DraggableWidget";
import AddRoomDialog from "@/components/visu/AddRoomDialog";
import AddVseWidgetDialog from "@/components/visu/AddVseWidgetDialog";
import EditVseWidgetDialog from "@/components/visu/EditVseWidgetDialog";
import ImportHAYamlDialog from "@/components/visu/ImportHAYamlDialog";
import RoomSettingsDialog, { getBackgroundStyle } from "@/components/visu/RoomSettingsDialog";
import { fetchVisuRooms, saveVisuRooms } from "@/services/knxApi";
import { generateUUID } from "@/lib/uuid";

const ROOMS_KEY = "knx_visu_rooms";
const CATEGORIES_KEY = "knx_visu_categories";

// Default categories
const INITIAL_CATEGORIES = [
  "Wohnbereich",
  "Schlafbereich", 
  "Außenbereich",
  "Küche",
  "Technik",
  "Sonstiges"
];

// Built-in templates
const BUILTIN_TEMPLATES: string[] = [
  "/static/vse/switch-card.vse.json",
  "/static/vse/strompreis-chart.vse.json",
  "/static/vse/gauge-barometer.vse.json",
  "/static/vse/sensor-card.vse.json",
  "/static/vse/markdown-card.vse.json",
  "/static/vse/simple-value.vse.json",
  "/static/vse/simple-toggle.vse.json",
  "/static/vse/compass-speedometer.vse.json",
  "/static/vse/media-player.vse.json",
  "/static/vse/shape-separator.vse.json",
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

// Local storage helpers
function loadLocalRooms(): VisuRoom[] {
  try { 
    const data = localStorage.getItem(ROOMS_KEY);
    console.log("[Visu] Loading from localStorage:", data ? "found" : "empty");
    return data ? JSON.parse(data) : []; 
  } catch (e) { 
    console.error("[Visu] Error loading from localStorage:", e);
    return []; 
  }
}

function saveLocalRooms(rooms: VisuRoom[]) {
  console.log("[Visu] Saving to localStorage:", rooms.length, "rooms");
  localStorage.setItem(ROOMS_KEY, JSON.stringify(rooms));
}

export default function Visualization() {
  // State
  const [rooms, setRooms] = useState<VisuRoom[]>([]);
  const [activeRoomId, setActiveRoomId] = useState<string | null>(null);
  const [templates, setTemplates] = useState<VseTemplate[]>([]);
  const [templatesLoaded, setTemplatesLoaded] = useState(false);
  const [showAddRoom, setShowAddRoom] = useState(false);
  const [showAddWidget, setShowAddWidget] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [showDevice, setShowDevice] = useState(true);
  const [editingWidget, setEditingWidget] = useState<VseWidgetInstance | null>(null);
  const [editingRoom, setEditingRoom] = useState<VisuRoom | null>(null);
  const [syncStatus, setSyncStatus] = useState<"synced" | "syncing" | "error" | "loading">("loading");
  const [initialLoadDone, setInitialLoadDone] = useState(false);
  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  
  // Custom categories
  const [categories, setCategories] = useState<string[]>(() => {
    try {
      const saved = localStorage.getItem(CATEGORIES_KEY);
      return saved ? JSON.parse(saved) : INITIAL_CATEGORIES;
    } catch {
      return INITIAL_CATEGORIES;
    }
  });

  // Save categories to localStorage when they change
  useEffect(() => {
    localStorage.setItem(CATEGORIES_KEY, JSON.stringify(categories));
  }, [categories]);

  const addCategory = useCallback((category: string) => {
    if (!categories.includes(category)) {
      setCategories(prev => [...prev, category]);
      toast.success(`Kategorie "${category}" hinzugefügt`);
    }
  }, [categories]);

  // Load rooms from server
  const { data: serverRooms, isLoading: isLoadingRooms, error: roomsError, refetch: refetchRooms } = useQuery({
    queryKey: ["visu-rooms"],
    queryFn: async () => {
      console.log("[Visu] Fetching rooms from server...");
      const data = await fetchVisuRooms();
      console.log("[Visu] Server returned:", data?.length ?? 0, "rooms");
      return data;
    },
    staleTime: 30000,
    refetchOnWindowFocus: false,
    retry: 2,
  });

  // Save mutation with retry
  const saveMutation = useMutation({
    mutationFn: saveVisuRooms,
    onSuccess: () => {
      console.log("[Visu] Saved to server successfully");
      setSyncStatus("synced");
    },
    onError: (err: any) => {
      console.error("[Visu] Failed to save to server:", err);
      setSyncStatus("error");
      
      // Show error with helpful message
      const errorMsg = err?.message || String(err);
      if (errorMsg.includes("Schreibrechte") || errorMsg.includes("readonly")) {
        toast.error("Speichern fehlgeschlagen: Keine Schreibrechte. Bitte auf System-Update → 'Berechtigungen korrigieren' klicken.", {
          duration: 8000,
        });
      } else {
        toast.error(`Speichern fehlgeschlagen: ${errorMsg}`, {
          duration: 5000,
        });
      }
    },
    retry: 2,
    retryDelay: 1000,
  });

  // Load templates on mount
  useEffect(() => {
    const loadTemplates = async () => {
      console.log("[Visu] Loading templates...");
      const results: VseTemplate[] = [];
      
      for (const url of BUILTIN_TEMPLATES) {
        try {
          console.log("[Visu] Fetching template:", url);
          const res = await fetch(url);
          if (res.ok) {
            const data = await res.json();
            results.push(data);
            console.log("[Visu] Loaded template:", data.id);
          } else {
            console.error("[Visu] Failed to load template:", url, res.status);
          }
        } catch (err) {
          console.error("[Visu] Error loading template:", url, err);
        }
      }
      
      const allTemplates = [...results, TITLE_TEMPLATE];
      setTemplates(allTemplates);
      setTemplatesLoaded(true);
      console.log("[Visu] Total templates loaded:", allTemplates.length);
      
      if (results.length === 0) {
        toast.error("Keine VSE-Templates gefunden!");
      } else {
        toast.success(`${results.length} Templates geladen`);
      }
    };
    
    loadTemplates();
  }, []);

  // Initial load from server or localStorage
  useEffect(() => {
    if (initialLoadDone) return;
    
    if (roomsError) {
      console.log("[Visu] Server error, falling back to localStorage");
      const localRooms = loadLocalRooms();
      setRooms(localRooms);
      setSyncStatus("error");
      setInitialLoadDone(true);
      if (localRooms.length > 0) {
        toast.info(`${localRooms.length} Räume aus Cache geladen`);
      }
      return;
    }
    
    if (serverRooms !== undefined) {
      console.log("[Visu] Server data received:", serverRooms.length, "rooms");
      if (serverRooms.length > 0) {
        setRooms(serverRooms);
        saveLocalRooms(serverRooms);
        toast.success(`${serverRooms.length} Raum/Räume vom Server geladen`);
      } else {
        const localRooms = loadLocalRooms();
        if (localRooms.length > 0) {
          console.log("[Visu] Server empty, using localStorage");
          setRooms(localRooms);
          saveMutation.mutate(localRooms);
        }
      }
      setSyncStatus("synced");
      setInitialLoadDone(true);
    }
  }, [serverRooms, roomsError, initialLoadDone, saveMutation]);

  // Set active room when rooms change
  useEffect(() => {
    if (rooms.length > 0 && !rooms.find((r) => r.id === activeRoomId)) {
      setActiveRoomId(rooms[0].id);
    }
  }, [rooms, activeRoomId]);

  // Auto-save with debounce
  const saveToServer = useCallback((roomsToSave: VisuRoom[]) => {
    if (!initialLoadDone) return;
    
    saveLocalRooms(roomsToSave);
    
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }
    
    setSyncStatus("syncing");
    saveTimeoutRef.current = setTimeout(() => {
      saveMutation.mutate(roomsToSave);
    }, 1500);
  }, [saveMutation, initialLoadDone]);

  // Save when rooms change
  useEffect(() => {
    if (initialLoadDone) {
      saveToServer(rooms);
    }
  }, [rooms, initialLoadDone, saveToServer]);

  const activeRoom = rooms.find((r) => r.id === activeRoomId);

  // Room operations
  const addRoom = useCallback((name: string, category: string) => {
    console.log("[Visu] Adding room:", name);
    const newRoom: VisuRoom = {
      id: generateUUID(),
      name,
      category,
      widgets: [],
    };
    setRooms((prev) => [...prev, newRoom]);
    setActiveRoomId(newRoom.id);
    toast.success(`Raum "${name}" erstellt`);
  }, []);

  const deleteRoom = useCallback((roomId: string) => {
    if (!confirm("Raum wirklich löschen?")) return;
    setRooms((prev) => prev.filter((r) => r.id !== roomId));
    toast.success("Raum gelöscht");
  }, []);

  const updateRoom = useCallback((updatedRoom: VisuRoom) => {
    setRooms((prev) =>
      prev.map((r) => (r.id === updatedRoom.id ? updatedRoom : r))
    );
    toast.success(`Raum "${updatedRoom.name}" aktualisiert`);
  }, []);

  // Widget operations
  const addWidget = useCallback((widget: VseWidgetInstance) => {
    if (!activeRoomId) return;
    setRooms((prev) =>
      prev.map((r) =>
        r.id === activeRoomId
          ? { ...r, widgets: [...r.widgets, { ...widget, roomId: activeRoomId }] }
          : r
      )
    );
    toast.success(`Widget "${widget.label}" hinzugefügt`);
  }, [activeRoomId]);

  const importWidgets = useCallback((widgets: VseWidgetInstance[]) => {
    if (!activeRoomId) return;
    setRooms((prev) =>
      prev.map((r) =>
        r.id === activeRoomId
          ? { ...r, widgets: [...r.widgets, ...widgets.map((w) => ({ ...w, roomId: activeRoomId }))] }
          : r
      )
    );
    toast.success(`${widgets.length} Widgets importiert`);
  }, [activeRoomId]);

  const removeWidget = useCallback((widgetId: string) => {
    setRooms((prev) =>
      prev.map((r) => ({
        ...r,
        widgets: r.widgets.filter((w) => w.id !== widgetId),
      }))
    );
  }, []);

  const updateWidget = useCallback((updated: VseWidgetInstance) => {
    setRooms((prev) =>
      prev.map((r) => ({
        ...r,
        widgets: r.widgets.map((w) => (w.id === updated.id ? updated : w)),
      }))
    );
    toast.success("Widget aktualisiert");
  }, []);

  const resizeWidget = useCallback((widgetId: string, w: number, h: number) => {
    setRooms((prev) =>
      prev.map((r) => ({
        ...r,
        widgets: r.widgets.map((widget) =>
          widget.id === widgetId ? { ...widget, widthOverride: w, heightOverride: h } : widget
        ),
      }))
    );
  }, []);

  const moveWidget = useCallback((widgetId: string, x: number, y: number) => {
    setRooms((prev) =>
      prev.map((r) => ({
        ...r,
        widgets: r.widgets.map((widget) =>
          widget.id === widgetId ? { ...widget, x, y } : widget
        ),
      }))
    );
  }, []);

  // Render room content
  const renderRoomContent = () => {
    if (isLoadingRooms && !initialLoadDone) {
      return (
        <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
          <Cloud className="w-12 h-12 mb-4 opacity-50 animate-pulse" />
          <p className="text-sm">Lade Räume vom Server...</p>
        </div>
      );
    }

    if (!templatesLoaded) {
      return (
        <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
          <RefreshCw className="w-12 h-12 mb-4 opacity-50 animate-spin" />
          <p className="text-sm">Lade Templates...</p>
        </div>
      );
    }

    if (rooms.length === 0) {
      return (
        <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
          <LayoutGrid className="w-12 h-12 mb-4 opacity-30" />
          <p className="text-sm">Keine Räume vorhanden</p>
          <Button size="sm" variant="outline" className="mt-4" onClick={() => setShowAddRoom(true)}>
            <Plus className="w-4 h-4 mr-1" /> Ersten Raum erstellen
          </Button>
        </div>
      );
    }

    if (!activeRoom) {
      return (
        <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
          <LayoutGrid className="w-12 h-12 mb-4 opacity-30" />
          <p className="text-sm">Wähle einen Raum</p>
        </div>
      );
    }

    if (activeRoom.widgets.length === 0) {
      return (
        <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
          <LayoutGrid className="w-10 h-10 mb-3 opacity-30" />
          <p className="text-sm">Keine Widgets in "{activeRoom.name}"</p>
          <Button size="sm" variant="outline" className="mt-4" onClick={() => setShowAddWidget(true)}>
            <Plus className="w-4 h-4 mr-1" /> Widget hinzufügen
          </Button>
        </div>
      );
    }

    return (
      <div 
        className="relative w-full h-full min-h-[400px]"
        style={getBackgroundStyle(activeRoom.background)}
      >
        {activeRoom.widgets.map((widget) => {
          const template = templates.find((t) => t.id === widget.templateId);
          if (!template) {
            return (
              <div
                key={widget.id}
                style={{ position: "absolute", left: widget.x, top: widget.y }}
                className="p-2 bg-destructive/20 rounded text-xs text-destructive"
              >
                Template "{widget.templateId}" fehlt
              </div>
            );
          }
          return (
            <DraggableWidget
              key={widget.id}
              widget={widget}
              template={template}
              editMode={editMode}
              onMove={(x, y) => moveWidget(widget.id, x, y)}
              onResize={(w, h) => resizeWidget(widget.id, w, h)}
              onEdit={() => setEditingWidget(widget)}
              onRemove={() => removeWidget(widget.id)}
            />
          );
        })}
      </div>
    );
  };

  return (
    <div className="h-[calc(100vh-3.5rem)] flex flex-col">
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-border bg-card shrink-0 flex-wrap">
        <LayoutGrid className="w-5 h-5 text-primary" />
        <h1 className="text-lg font-semibold text-foreground">Visualisierung</h1>
        {activeRoom && (
          <span className="text-xs text-muted-foreground font-mono">{activeRoom.name}</span>
        )}
        
        {/* Sync Status */}
        <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium ${
          syncStatus === "synced" ? "bg-green-500/15 text-green-500" : 
          syncStatus === "syncing" ? "bg-yellow-500/15 text-yellow-500" : 
          syncStatus === "loading" ? "bg-blue-500/15 text-blue-500" :
          "bg-red-500/15 text-red-500"
        }`}>
          {syncStatus === "synced" && <><Cloud className="w-3 h-3" /> OK</>}
          {syncStatus === "syncing" && <><Cloud className="w-3 h-3 animate-pulse" /> Sync</>}
          {syncStatus === "loading" && <><RefreshCw className="w-3 h-3 animate-spin" /> Load</>}
          {syncStatus === "error" && <><CloudOff className="w-3 h-3" /> Offline</>}
        </div>
        
        {/* Stats */}
        <span className="text-[10px] text-muted-foreground">
          {rooms.length}R / {rooms.reduce((a, r) => a + r.widgets.length, 0)}W / {templates.length}T
        </span>
        
        <div className="ml-auto flex items-center gap-1.5 flex-wrap">
          <Button size="sm" variant="ghost" className="h-7 px-2" onClick={() => refetchRooms()} title="Neu laden">
            <RefreshCw className="w-3.5 h-3.5" />
          </Button>
          <Button size="sm" variant="outline" className="h-7 text-xs gap-1" onClick={() => {
            const url = `${window.location.origin}/panel#${btoa(encodeURIComponent(JSON.stringify(rooms)))}`;
            navigator.clipboard.writeText(url);
            toast.success("Panel-Link kopiert");
          }} disabled={rooms.length === 0}>
            <Smartphone className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Panel</span>
          </Button>
          <Button size="sm" variant={showDevice ? "default" : "outline"} className="h-7 text-xs gap-1" onClick={() => setShowDevice(!showDevice)}>
            <Monitor className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Device</span>
          </Button>
          <Button size="sm" variant={editMode ? "secondary" : "ghost"} className="h-7 text-xs gap-1" onClick={() => setEditMode(!editMode)}>
            <Settings2 className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">{editMode ? "Fertig" : "Bearbeiten"}</span>
          </Button>
          <Button size="sm" variant="outline" className="h-7 text-xs gap-1" onClick={() => setShowImport(true)} disabled={!activeRoomId}>
            <FileUp className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Import</span>
          </Button>
          <Button size="sm" className="h-7 text-xs gap-1" onClick={() => setShowAddWidget(true)} disabled={!activeRoomId || templates.length === 0}>
            <Plus className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Widget</span>
          </Button>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Left: Room tree */}
        <VisuPageTree
          rooms={rooms}
          activeRoomId={activeRoomId}
          onSelectRoom={setActiveRoomId}
          onAddRoom={() => setShowAddRoom(true)}
          onDeleteRoom={deleteRoom}
          onEditRoom={(room) => setEditingRoom(room)}
        />

        {/* Main content */}
        <div className="flex-1 overflow-auto flex items-center justify-center p-4 bg-background">
          {showDevice ? (
            <DeviceFrame>{renderRoomContent()}</DeviceFrame>
          ) : (
            <div className="w-full h-full">{renderRoomContent()}</div>
          )}
        </div>
      </div>

      {/* Dialogs */}
      <AddRoomDialog 
        open={showAddRoom} 
        onOpenChange={setShowAddRoom} 
        onAdd={addRoom}
        categories={categories}
        onAddCategory={addCategory}
      />
      <AddVseWidgetDialog
        open={showAddWidget}
        onOpenChange={setShowAddWidget}
        templates={templates}
        onAdd={addWidget}
      />
      {editingWidget && (
        <EditVseWidgetDialog
          open={!!editingWidget}
          onOpenChange={(open) => { if (!open) setEditingWidget(null); }}
          widget={editingWidget}
          template={templates.find((t) => t.id === editingWidget.templateId) || null}
          onSave={updateWidget}
        />
      )}
      <ImportHAYamlDialog open={showImport} onOpenChange={setShowImport} onImport={importWidgets} />
      <RoomSettingsDialog
        open={!!editingRoom}
        onOpenChange={(open) => { if (!open) setEditingRoom(null); }}
        room={editingRoom}
        categories={categories}
        onSave={updateRoom}
        onDelete={deleteRoom}
        onAddCategory={addCategory}
      />
    </div>
  );
}
