import { useMemo, useRef } from "react";
import { ChevronRight, Upload, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useLogicStore, type LogicBlockDef, parseLogicBlockPython } from "@/stores/logicStore";
import { toast } from "sonner";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";

interface Props {
  onAddInstance: (block: LogicBlockDef) => void;
}

export default function BlockLibraryPanel({ onAddInstance }: Props) {
  const { blocks, addBlock, removeBlock } = useLogicStore();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const grouped = useMemo(() => {
    const map: Record<string, LogicBlockDef[]> = {};
    blocks.forEach((b) => {
      const cat = b.category || "Allgemein";
      if (!map[cat]) map[cat] = [];
      map[cat].push(b);
    });
    return map;
  }, [blocks]);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const source = ev.target?.result as string;
      const parsed = parseLogicBlockPython(source);
      if (!parsed) {
        toast.error("Konnte LogicBlock nicht parsen");
        return;
      }
      const id = `block-${Date.now()}`;
      addBlock({ ...parsed, id });
      toast.success(`"${parsed.name}" importiert`);
    };
    reader.readAsText(file);
    e.target.value = "";
  };

  return (
    <div className="w-56 border-r border-border bg-card flex flex-col shrink-0">
      <div className="px-3 py-2 border-b border-border flex items-center justify-between">
        <span className="text-xs font-semibold text-foreground">Bausteine</span>
        <Button
          size="sm"
          variant="ghost"
          className="h-6 w-6 p-0"
          onClick={() => fileInputRef.current?.click()}
          title="Baustein importieren"
        >
          <Upload className="w-3.5 h-3.5" />
        </Button>
        <input ref={fileInputRef} type="file" accept=".py" className="hidden" onChange={handleFileUpload} />
      </div>

      <ScrollArea className="flex-1">
        <div className="p-1">
          {Object.keys(grouped).length === 0 && (
            <p className="text-[10px] text-muted-foreground px-2 py-4 text-center">
              Keine Bausteine importiert. Lade eine .py Datei hoch.
            </p>
          )}
          {Object.entries(grouped).map(([category, catBlocks]) => (
            <Collapsible key={category} defaultOpen>
              <CollapsibleTrigger className="flex items-center gap-1 w-full px-2 py-1 text-[11px] font-semibold text-muted-foreground hover:text-foreground group">
                <ChevronRight className="w-3 h-3 transition-transform group-data-[state=open]:rotate-90" />
                {category}
                <span className="ml-auto text-[10px] font-mono">{catBlocks.length}</span>
              </CollapsibleTrigger>
              <CollapsibleContent>
                {catBlocks.map((block) => (
                  <div
                    key={block.id}
                    className="flex items-center gap-1 px-2 py-1 mx-1 rounded hover:bg-secondary group"
                  >
                    <button
                      className="flex-1 text-left text-[10px] text-foreground truncate"
                      onClick={() => onAddInstance(block)}
                      title={block.description}
                    >
                      <Plus className="w-3 h-3 inline mr-1 text-primary" />
                      {block.name}
                    </button>
                    <button
                      className="opacity-0 group-hover:opacity-100 transition-opacity"
                      onClick={() => {
                        removeBlock(block.id);
                        toast.success(`"${block.name}" entfernt`);
                      }}
                    >
                      <Trash2 className="w-3 h-3 text-destructive" />
                    </button>
                  </div>
                ))}
              </CollapsibleContent>
            </Collapsible>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}
