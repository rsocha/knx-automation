import { useState, useMemo } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Search, Check } from "lucide-react";
import type { VseTemplate, VseWidgetInstance } from "@/types/vse";
import { useGroupAddresses } from "@/hooks/useKnx";
import { generateUUID } from "@/lib/uuid";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  templates: VseTemplate[];
  onAdd: (widget: VseWidgetInstance) => void;
}

export default function AddVseWidgetDialog({ open, onOpenChange, templates, onAdd }: Props) {
  const [selectedTemplate, setSelectedTemplate] = useState<string>("");
  const [label, setLabel] = useState("");
  const [koBindings, setKoBindings] = useState<Record<string, string>>({});
  const [activeKoField, setActiveKoField] = useState<string | null>(null);
  const [koSearch, setKoSearch] = useState("");
  
  const { data: allAddresses = [] } = useGroupAddresses();
  const template = templates.find((t) => t.id === selectedTemplate);

  const filteredAddresses = useMemo(() => {
    if (!koSearch) return allAddresses.slice(0, 50);
    const q = koSearch.toLowerCase();
    return allAddresses.filter((a) =>
      a.address.toLowerCase().includes(q) ||
      a.name?.toLowerCase().includes(q) ||
      a.group?.toLowerCase().includes(q)
    ).slice(0, 50);
  }, [allAddresses, koSearch]);

  const handleAdd = () => {
    if (!template || !label.trim()) return;
    onAdd({
      id: generateUUID(),
      templateId: template.id,
      label: label.trim(),
      roomId: "",
      koBindings,
      variableValues: {},
      x: 0,
      y: 0,
    });
    setLabel("");
    setKoBindings({});
    setSelectedTemplate("");
    setActiveKoField(null);
    onOpenChange(false);
  };

  const selectAddress = (address: string) => {
    if (activeKoField) {
      setKoBindings((prev) => ({ ...prev, [activeKoField]: address }));
      setActiveKoField(null);
      setKoSearch("");
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-card border-border sm:max-w-lg max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="text-card-foreground">VSE Widget hinzufügen</DialogTitle>
        </DialogHeader>
        
        <ScrollArea className="flex-1 pr-2">
          <div className="space-y-4 mt-2">
            {/* Template selection */}
            <div>
              <Label className="text-muted-foreground text-xs">Widget-Vorlage</Label>
              <div className="grid grid-cols-2 gap-2 mt-1 max-h-48 overflow-y-auto">
                {templates.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => {
                      setSelectedTemplate(t.id);
                      setKoBindings({});
                      setActiveKoField(null);
                    }}
                    className={`p-2 rounded-lg border text-left transition-colors ${
                      selectedTemplate === t.id
                        ? "border-primary bg-primary/10"
                        : "border-border bg-secondary hover:bg-muted"
                    }`}
                  >
                    <div className="text-xs font-medium text-foreground truncate">{t.name}</div>
                    <div className="text-[9px] text-muted-foreground font-mono">{t.width}×{t.height}</div>
                  </button>
                ))}
              </div>
            </div>

            {template && (
              <>
                <div>
                  <Label className="text-muted-foreground text-xs">Bezeichnung</Label>
                  <Input 
                    value={label} 
                    onChange={(e) => setLabel(e.target.value)} 
                    placeholder="z.B. Deckenlicht" 
                    className="bg-secondary border-border mt-1 h-8"
                  />
                </div>

                {/* KO Bindings */}
                {Object.keys(template.inputs).length > 0 && (
                  <div className="space-y-2">
                    <Label className="text-muted-foreground text-xs">KO-Zuordnungen</Label>
                    {Object.entries(template.inputs).map(([key, input]) => (
                      <div key={key} className="flex items-center gap-2">
                        <span className="text-[10px] text-foreground w-24 shrink-0 truncate" title={input.name}>
                          {input.name}
                        </span>
                        <div className="flex-1 relative">
                          <Input
                            value={koBindings[key] || ""}
                            onChange={(e) => setKoBindings((prev) => ({ ...prev, [key]: e.target.value }))}
                            onFocus={() => {
                              setActiveKoField(key);
                              setKoSearch("");
                            }}
                            placeholder="Adresse wählen..."
                            className="bg-secondary border-border h-7 text-xs font-mono pr-8"
                          />
                          {koBindings[key] && (
                            <Check className="absolute right-2 top-1/2 -translate-y-1/2 w-3 h-3 text-green-500" />
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* KO Address Picker */}
                {activeKoField && (
                  <div className="border border-border rounded-lg p-2 bg-secondary/50">
                    <div className="relative mb-2">
                      <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-muted-foreground" />
                      <Input
                        value={koSearch}
                        onChange={(e) => setKoSearch(e.target.value)}
                        placeholder="Adresse suchen..."
                        className="h-7 text-xs pl-7 bg-background border-border"
                        autoFocus
                      />
                    </div>
                    <ScrollArea className="h-32">
                      <div className="space-y-0.5">
                        {filteredAddresses.map((addr) => (
                          <button
                            key={addr.address}
                            className="w-full text-left px-2 py-1.5 rounded text-[10px] hover:bg-primary/10 transition-colors flex items-center gap-2"
                            onClick={() => selectAddress(addr.address)}
                          >
                            <span className="font-mono shrink-0 text-primary" style={{ minWidth: 50 }}>{addr.address}</span>
                            <span className="truncate flex-1 text-foreground text-[9px]">{addr.name || "–"}</span>
                            {addr.is_internal && (
                              <span className="text-[8px] px-1 rounded bg-purple-500/20 text-purple-400 shrink-0">IKO</span>
                            )}
                          </button>
                        ))}
                        {filteredAddresses.length === 0 && (
                          <div className="text-xs text-muted-foreground text-center py-2">
                            Keine Adressen gefunden
                          </div>
                        )}
                      </div>
                    </ScrollArea>
                  </div>
                )}
              </>
            )}
          </div>
        </ScrollArea>

        {template && (
          <Button 
            onClick={handleAdd} 
            className="w-full bg-primary text-primary-foreground mt-2" 
            disabled={!label.trim()}
          >
            Hinzufügen
          </Button>
        )}
      </DialogContent>
    </Dialog>
  );
}
