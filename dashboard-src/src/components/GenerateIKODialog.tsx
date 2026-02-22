import { useState, useMemo } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Zap, Cpu, ChevronRight } from "lucide-react";
import { useLogicBlocks, useAvailableBlocks, useBindBlock } from "@/hooks/useLogic";
import { useCreateGroupAddress } from "@/hooks/useKnx";
import { toast } from "sonner";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface PortSelection {
  key: string;
  name: string;
  type: "input" | "output";
  selected: boolean;
}

export default function GenerateIKODialog({ open, onOpenChange }: Props) {
  const { data: blocks = [] } = useLogicBlocks();
  const { data: availableBlocks = [] } = useAvailableBlocks();
  const createAddr = useCreateGroupAddress();
  const bindBlock = useBindBlock();

  const [selectedBlockId, setSelectedBlockId] = useState<string | null>(null);
  const [ports, setPorts] = useState<PortSelection[]>([]);
  const [autoBind, setAutoBind] = useState(true);
  const [generating, setGenerating] = useState(false);

  const selectedBlock = blocks.find((b) => b.instance_id === selectedBlockId);

  const selectBlock = (instanceId: string) => {
    const block = blocks.find((b) => b.instance_id === instanceId);
    if (!block) return;
    setSelectedBlockId(instanceId);

    const inputPorts: PortSelection[] = Object.entries(block.inputs).map(([key, cfg]) => ({
      key,
      name: cfg.config?.name || key,
      type: "input",
      selected: true,
    }));
    const outputPorts: PortSelection[] = Object.entries(block.outputs).map(([key, cfg]) => ({
      key,
      name: cfg.config?.name || key,
      type: "output",
      selected: true,
    }));
    setPorts([...inputPorts, ...outputPorts]);
  };

  const togglePort = (key: string) => {
    setPorts((prev) =>
      prev.map((p) => (p.key === key ? { ...p, selected: !p.selected } : p))
    );
  };

  const toggleAll = (selected: boolean) => {
    setPorts((prev) => prev.map((p) => ({ ...p, selected })));
  };

  const handleGenerate = async () => {
    if (!selectedBlock) return;
    const selectedPorts = ports.filter((p) => p.selected);
    if (selectedPorts.length === 0) {
      toast.error("Keine Ports ausgewählt");
      return;
    }

    setGenerating(true);
    const blockName = selectedBlock.name || selectedBlock.block_type;
    const groupName = `${blockName} #${selectedBlock.block_id}`;
    let successCount = 0;
    
    // Extract instance number from instance_id (e.g., "200352_SonosController_5_062328" -> "5")
    const idParts = selectedBlock.instance_id.split('_');
    const instanceNum = idParts.length >= 3 ? idParts[idParts.length - 2] : "0";

    for (const port of selectedPorts) {
      const portDir = port.type === "input" ? "E" : "A";
      // Simplified IKO format: IKO:InstanceNumber_BlockName:PortKey
      const address = `IKO:${instanceNum}_${blockName}:${port.key}`;

      try {
        await createAddr.mutateAsync({
          address,
          name: `${blockName} ${portDir}:${port.name}`,
          description: `Auto-generiert für ${blockName} ${port.type} ${port.key}`,
          is_internal: true,
          group: groupName,
        });

        if (autoBind) {
          const data = port.type === "input"
            ? { input_key: port.key, address }
            : { output_key: port.key, address };
          await bindBlock.mutateAsync({ instanceId: selectedBlock.instance_id, data });
        }

        successCount++;
      } catch (err: any) {
        // Might already exist - continue
        console.warn(`IKO ${address}: ${err.message}`);
      }
    }

    setGenerating(false);
    toast.success(`${successCount} IKO(s) für "${blockName}" generiert`);
    onOpenChange(false);
    setSelectedBlockId(null);
    setPorts([]);
  };

  // Group blocks by category
  const grouped = useMemo(() => {
    const map: Record<string, typeof blocks> = {};
    blocks.forEach((b) => {
      const avail = availableBlocks.find((a) => a.type === b.block_type);
      const cat = avail?.category || "Allgemein";
      if (!map[cat]) map[cat] = [];
      map[cat].push(b);
    });
    return map;
  }, [blocks, availableBlocks]);

  const selectedInputs = ports.filter((p) => p.type === "input");
  const selectedOutputs = ports.filter((p) => p.type === "output");

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) {
          setSelectedBlockId(null);
          setPorts([]);
        }
        onOpenChange(o);
      }}
    >
      <DialogContent className="bg-card border-border sm:max-w-lg max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-card-foreground">
            <Zap className="w-5 h-5 text-accent" />
            IKOs aus Baustein generieren
          </DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-hidden flex flex-col space-y-3">
          {/* Step 1: Select Block */}
          <div>
            <Label className="text-xs text-muted-foreground">Baustein auswählen</Label>
            <ScrollArea className="h-40 mt-1 rounded border border-border">
              <div className="p-1">
                {Object.keys(grouped).length === 0 && (
                  <p className="text-[10px] text-muted-foreground text-center py-4">
                    Keine Logikbausteine vorhanden
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
                        <button
                          key={block.instance_id}
                          onClick={() => selectBlock(block.instance_id)}
                          className={`w-full text-left px-3 py-1.5 rounded text-xs transition-colors flex items-center gap-2 ${
                            selectedBlockId === block.instance_id
                              ? "bg-primary/10 text-primary"
                              : "hover:bg-secondary text-foreground"
                          }`}
                        >
                          <Cpu className="w-3.5 h-3.5 shrink-0" />
                          <span className="font-mono text-[10px] text-muted-foreground">#{block.block_id}</span>
                          <span className="truncate">{block.name || block.block_type}</span>
                          <span className="ml-auto text-[9px] text-muted-foreground">
                            {Object.keys(block.inputs).length}E / {Object.keys(block.outputs).length}A
                          </span>
                        </button>
                      ))}
                    </CollapsibleContent>
                  </Collapsible>
                ))}
              </div>
            </ScrollArea>
          </div>

          {/* Step 2: Select Ports */}
          {selectedBlock && (
            <div>
              <div className="flex items-center justify-between mb-1">
                <Label className="text-xs text-muted-foreground">
                  Ein-/Ausgänge ({ports.filter((p) => p.selected).length}/{ports.length} ausgewählt)
                </Label>
                <div className="flex gap-1">
                  <Button variant="ghost" size="sm" className="h-5 text-[10px] px-1" onClick={() => toggleAll(true)}>
                    Alle
                  </Button>
                  <Button variant="ghost" size="sm" className="h-5 text-[10px] px-1" onClick={() => toggleAll(false)}>
                    Keine
                  </Button>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                {/* Inputs */}
                <div className="rounded border border-border p-2">
                  <div className="text-[10px] font-semibold text-accent mb-1">Eingänge</div>
                  {selectedInputs.length === 0 && (
                    <p className="text-[9px] text-muted-foreground">Keine Eingänge</p>
                  )}
                  {selectedInputs.map((port) => (
                    <label
                      key={port.key}
                      className="flex items-center gap-1.5 py-0.5 cursor-pointer"
                    >
                      <Checkbox
                        checked={port.selected}
                        onCheckedChange={() => togglePort(port.key)}
                        className="w-3.5 h-3.5"
                      />
                      <span className="text-[10px] font-mono text-muted-foreground">{port.key}</span>
                      <span className="text-[10px] text-foreground truncate">{port.name}</span>
                    </label>
                  ))}
                </div>
                {/* Outputs */}
                <div className="rounded border border-border p-2">
                  <div className="text-[10px] font-semibold text-primary mb-1">Ausgänge</div>
                  {selectedOutputs.length === 0 && (
                    <p className="text-[9px] text-muted-foreground">Keine Ausgänge</p>
                  )}
                  {selectedOutputs.map((port) => (
                    <label
                      key={port.key}
                      className="flex items-center gap-1.5 py-0.5 cursor-pointer"
                    >
                      <Checkbox
                        checked={port.selected}
                        onCheckedChange={() => togglePort(port.key)}
                        className="w-3.5 h-3.5"
                      />
                      <span className="text-[10px] font-mono text-muted-foreground">{port.key}</span>
                      <span className="text-[10px] text-foreground truncate">{port.name}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Auto-bind option */}
              <label className="flex items-center gap-2 mt-2 cursor-pointer">
                <Checkbox
                  checked={autoBind}
                  onCheckedChange={(c) => setAutoBind(!!c)}
                />
                <span className="text-xs text-muted-foreground">IKOs automatisch an Ports binden</span>
              </label>
            </div>
          )}

          {/* Generate button */}
          {selectedBlock && (
            <Button
              onClick={handleGenerate}
              disabled={generating || ports.filter((p) => p.selected).length === 0}
              className="w-full"
            >
              <Zap className="w-4 h-4 mr-2" />
              {generating
                ? "Generiere..."
                : `${ports.filter((p) => p.selected).length} IKO(s) generieren`}
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
