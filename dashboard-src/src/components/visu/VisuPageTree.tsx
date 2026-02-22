import { useMemo } from "react";
import { ChevronRight, Home, Sofa, BedDouble, UtensilsCrossed, TreePine, Plus, Trash2, FolderOpen, Settings2, Cpu, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import type { VisuRoom } from "@/types/vse";
import MdiIcon from "./MdiIcon";

const CATEGORY_ICONS: Record<string, React.ElementType> = {
  Wohnbereich: Sofa,
  Schlafbereich: BedDouble,
  Küche: UtensilsCrossed,
  Außen: TreePine,
  Außenbereich: TreePine,
  Technik: Cpu,
  Sonstiges: Sparkles,
  Allgemein: Home,
};

interface Props {
  rooms: VisuRoom[];
  activeRoomId: string | null;
  onSelectRoom: (roomId: string) => void;
  onAddRoom: () => void;
  onDeleteRoom: (roomId: string) => void;
  onEditRoom?: (room: VisuRoom) => void;
}

export default function VisuPageTree({ rooms, activeRoomId, onSelectRoom, onAddRoom, onDeleteRoom, onEditRoom }: Props) {
  const grouped = useMemo(() => {
    const map: Record<string, VisuRoom[]> = {};
    rooms.forEach((r) => {
      const cat = r.category || "Allgemein";
      if (!map[cat]) map[cat] = [];
      map[cat].push(r);
    });
    return map;
  }, [rooms]);

  const renderRoomIcon = (room: VisuRoom) => {
    if (room.icon) {
      // Check if it's an emoji (starts with emoji characters)
      if (/^[\p{Emoji}]/u.test(room.icon)) {
        return <span className="text-xs">{room.icon}</span>;
      }
      // Otherwise it's an MDI icon name
      return <MdiIcon name={room.icon} size={12} />;
    }
    return <Home className="w-3 h-3 shrink-0" />;
  };

  return (
    <div className="w-52 border-r border-border bg-card flex flex-col shrink-0">
      <div className="px-3 py-2 border-b border-border flex items-center justify-between">
        <span className="text-xs font-semibold text-foreground">Räume</span>
        <Button size="sm" variant="ghost" className="h-6 w-6 p-0" onClick={onAddRoom} title="Neuer Raum">
          <Plus className="w-3.5 h-3.5" />
        </Button>
      </div>
      <ScrollArea className="flex-1">
        <div className="p-1">
          {Object.keys(grouped).length === 0 && (
            <div className="px-3 py-8 text-center">
              <FolderOpen className="w-8 h-8 mx-auto mb-2 text-muted-foreground/30" />
              <p className="text-[10px] text-muted-foreground">Keine Räume vorhanden</p>
            </div>
          )}
          {Object.entries(grouped).map(([category, catRooms]) => {
            const CatIcon = CATEGORY_ICONS[category] || Home;
            return (
              <Collapsible key={category} defaultOpen>
                <CollapsibleTrigger className="flex items-center gap-1.5 w-full px-2 py-1.5 text-[11px] font-semibold text-muted-foreground hover:text-foreground group">
                  <ChevronRight className="w-3 h-3 transition-transform group-data-[state=open]:rotate-90" />
                  <CatIcon className="w-3.5 h-3.5" />
                  {category}
                  <span className="ml-auto text-[10px] font-mono">{catRooms.length}</span>
                </CollapsibleTrigger>
                <CollapsibleContent>
                  {catRooms.map((room) => (
                    <div
                      key={room.id}
                      className={`flex items-center gap-1.5 px-2 py-1.5 mx-1 rounded cursor-pointer group text-[11px] ${
                        activeRoomId === room.id
                          ? "bg-primary/10 text-primary font-medium"
                          : "hover:bg-secondary text-foreground"
                      }`}
                      onClick={() => onSelectRoom(room.id)}
                    >
                      {renderRoomIcon(room)}
                      <span className="truncate flex-1">{room.name}</span>
                      <span className="text-[9px] text-muted-foreground font-mono">{room.widgets.length}</span>
                      {onEditRoom && (
                        <button
                          className="opacity-0 group-hover:opacity-100 p-0.5 hover:bg-secondary rounded"
                          onClick={(e) => {
                            e.stopPropagation();
                            onEditRoom(room);
                          }}
                          title="Raum bearbeiten"
                        >
                          <Settings2 className="w-3 h-3 text-muted-foreground" />
                        </button>
                      )}
                      <button
                        className="opacity-0 group-hover:opacity-100 p-0.5 hover:bg-destructive/10 rounded"
                        onClick={(e) => {
                          e.stopPropagation();
                          onDeleteRoom(room.id);
                        }}
                        title="Raum löschen"
                      >
                        <Trash2 className="w-3 h-3 text-destructive" />
                      </button>
                    </div>
                  ))}
                </CollapsibleContent>
              </Collapsible>
            );
          })}
        </div>
      </ScrollArea>
    </div>
  );
}
