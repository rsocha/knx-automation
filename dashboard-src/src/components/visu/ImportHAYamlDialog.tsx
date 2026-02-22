import { useState, useRef, useCallback } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Checkbox } from "@/components/ui/checkbox";
import { Upload, FileText, Lightbulb, Type, Zap, Search } from "lucide-react";
import { parseHAYaml, mapToVseType, extractVseVariables, type ParsedHACard } from "@/lib/haYamlParser";
import { useGroupAddresses } from "@/hooks/useKnx";
import type { VseWidgetInstance } from "@/types/vse";
import { toast } from "sonner";
import { generateUUID } from "@/lib/uuid";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onImport: (widgets: VseWidgetInstance[]) => void;
}

interface CardMapping {
  card: ParsedHACard;
  selected: boolean;
  label: string;
  koStatus: string;
  koSend: string;
  vseType: string;
}

export default function ImportHAYamlDialog({ open, onOpenChange, onImport }: Props) {
  const [step, setStep] = useState<"input" | "mapping">("input");
  const [yamlText, setYamlText] = useState("");
  const [mappings, setMappings] = useState<CardMapping[]>([]);
  const [koSearch, setKoSearch] = useState("");
  const [activeKoField, setActiveKoField] = useState<{ idx: number; field: "koStatus" | "koSend" } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const { data: allAddresses = [] } = useGroupAddresses();

  const handleParse = useCallback(() => {
    if (!yamlText.trim()) {
      toast.error("Kein YAML eingegeben");
      return;
    }
    const cards = parseHAYaml(yamlText);
    if (cards.length === 0) {
      toast.error("Keine Karten im YAML gefunden");
      return;
    }
    setMappings(
      cards.map((card) => ({
        card,
        selected: true,
        label: card.primary || card.entity?.split(".").pop() || "Widget",
        koStatus: "",
        koSend: "",
        vseType: mapToVseType(card),
      }))
    );
    setStep("mapping");
    toast.success(`${cards.length} Karte(n) erkannt`);
  }, [yamlText]);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      setYamlText(ev.target?.result as string || "");
    };
    reader.readAsText(file);
  };

  const handleImport = () => {
    const selected = mappings.filter((m) => m.selected);
    if (selected.length === 0) {
      toast.error("Keine Karten ausgewählt");
      return;
    }
    const widgets: VseWidgetInstance[] = selected.map((m) => {
      const vars = extractVseVariables(m.card);
      return {
        id: generateUUID(),
        templateId: m.vseType === "titleCard" ? "title-card" : "switch-card",
        label: m.label,
        roomId: "",
        koBindings: {
          ...(m.koStatus ? { ko1: m.koStatus } : {}),
          ...(m.koSend ? { ko2: m.koSend } : {}),
        },
        variableValues: vars,
        x: 0,
        y: 0,
      };
    });
    onImport(widgets);
    toast.success(`${widgets.length} Widget(s) importiert`);
    resetState();
    onOpenChange(false);
  };

  const resetState = () => {
    setStep("input");
    setYamlText("");
    setMappings([]);
    setKoSearch("");
    setActiveKoField(null);
  };

  const updateMapping = (idx: number, updates: Partial<CardMapping>) => {
    setMappings((prev) => prev.map((m, i) => (i === idx ? { ...m, ...updates } : m)));
  };

  const filteredAddresses = allAddresses.filter((a) => {
    if (!koSearch) return true;
    const q = koSearch.toLowerCase();
    return (
      a.address.toLowerCase().includes(q) ||
      a.name?.toLowerCase().includes(q) ||
      a.group?.toLowerCase().includes(q)
    );
  });

  const cardTypeIcon = (type: string) => {
    if (type.includes("title")) return <Type className="w-4 h-4 text-accent" />;
    return <Lightbulb className="w-4 h-4 text-primary" />;
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) resetState();
        onOpenChange(o);
      }}
    >
      <DialogContent className="bg-card border-border sm:max-w-2xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="text-card-foreground flex items-center gap-2">
            <Zap className="w-5 h-5 text-primary" />
            Home Assistant YAML Import
          </DialogTitle>
        </DialogHeader>

        {step === "input" && (
          <div className="space-y-4 mt-2">
            <div>
              <Label className="text-muted-foreground text-xs">YAML einfügen</Label>
              <Textarea
                value={yamlText}
                onChange={(e) => setYamlText(e.target.value)}
                placeholder={`type: custom:mushroom-template-card\nentity: light.wohnzimmer\nprimary: Wohnzimmer\ntap_action:\n  action: toggle`}
                className="bg-secondary border-border mt-1 font-mono text-xs min-h-[200px]"
              />
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">oder</span>
              <Button
                variant="outline"
                size="sm"
                className="gap-1 text-xs"
                onClick={() => fileRef.current?.click()}
              >
                <Upload className="w-3.5 h-3.5" />
                YAML-Datei hochladen
              </Button>
              <input
                ref={fileRef}
                type="file"
                accept=".yaml,.yml,.txt"
                className="hidden"
                onChange={handleFileUpload}
              />
            </div>
            <Button onClick={handleParse} className="w-full" disabled={!yamlText.trim()}>
              <FileText className="w-4 h-4 mr-2" />
              YAML analysieren
            </Button>
          </div>
        )}

        {step === "mapping" && (
          <div className="space-y-3 flex-1 overflow-hidden flex flex-col">
            <div className="text-xs text-muted-foreground">
              {mappings.length} Karte(n) erkannt – wähle aus und weise KOs zu:
            </div>

            <ScrollArea className="flex-1 pr-2">
              <div className="space-y-2">
                {mappings.map((m, idx) => (
                  <div
                    key={m.card.id}
                    className={`rounded-lg border p-3 transition-colors ${
                      m.selected ? "border-primary/30 bg-primary/5" : "border-border bg-secondary/30 opacity-60"
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <Checkbox
                        checked={m.selected}
                        onCheckedChange={(checked) => updateMapping(idx, { selected: !!checked })}
                      />
                      {cardTypeIcon(m.card.type)}
                      <span className="text-[10px] font-mono text-muted-foreground">{m.card.type}</span>
                      {m.card.entity && (
                        <span className="text-[10px] font-mono text-accent">{m.card.entity}</span>
                      )}
                    </div>

                    {m.selected && (
                      <div className="grid grid-cols-3 gap-2 mt-2">
                        <div>
                          <Label className="text-[10px] text-muted-foreground">Bezeichnung</Label>
                          <Input
                            value={m.label}
                            onChange={(e) => updateMapping(idx, { label: e.target.value })}
                            className="h-7 text-xs bg-secondary border-border mt-0.5"
                          />
                        </div>
                        {m.vseType !== "titleCard" && (
                          <>
                            <div>
                              <Label className="text-[10px] text-muted-foreground">Status-KO</Label>
                              <div className="relative">
                                <Input
                                  value={m.koStatus}
                                  onChange={(e) => updateMapping(idx, { koStatus: e.target.value })}
                                  onFocus={() => {
                                    setActiveKoField({ idx, field: "koStatus" });
                                    setKoSearch("");
                                  }}
                                  placeholder="z.B. 1/1/1"
                                  className="h-7 text-xs font-mono bg-secondary border-border mt-0.5"
                                />
                              </div>
                            </div>
                            <div>
                              <Label className="text-[10px] text-muted-foreground">Sende-KO</Label>
                              <Input
                                value={m.koSend}
                                onChange={(e) => updateMapping(idx, { koSend: e.target.value })}
                                onFocus={() => {
                                  setActiveKoField({ idx, field: "koSend" });
                                  setKoSearch("");
                                }}
                                placeholder="z.B. 1/1/1"
                                className="h-7 text-xs font-mono bg-secondary border-border mt-0.5"
                              />
                            </div>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </ScrollArea>

            {/* KO Quick-Selector */}
            {activeKoField && (
              <div className="border-t border-border pt-2">
                <div className="relative mb-1">
                  <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-muted-foreground" />
                  <Input
                    value={koSearch}
                    onChange={(e) => setKoSearch(e.target.value)}
                    placeholder="KO suchen..."
                    className="h-7 text-xs pl-7 bg-secondary border-border"
                    autoFocus
                  />
                </div>
                <ScrollArea className="h-28">
                  <div className="space-y-0.5">
                    {filteredAddresses.slice(0, 30).map((addr) => (
                      <button
                        key={addr.address}
                        className="w-full text-left px-2 py-1 rounded text-[10px] hover:bg-secondary transition-colors flex items-center gap-2"
                        onClick={() => {
                          if (activeKoField) {
                            updateMapping(activeKoField.idx, { [activeKoField.field]: addr.address });
                            setActiveKoField(null);
                          }
                        }}
                      >
                        <span className="font-mono w-16 shrink-0">{addr.address}</span>
                        <span className="truncate flex-1">{addr.name || "–"}</span>
                        {addr.is_internal && (
                          <span className="text-[9px] px-1 rounded bg-knx-purple/15 text-knx-purple">IKO</span>
                        )}
                      </button>
                    ))}
                  </div>
                </ScrollArea>
              </div>
            )}

            <div className="flex gap-2 pt-2 border-t border-border">
              <Button variant="outline" onClick={() => setStep("input")} className="flex-1">
                Zurück
              </Button>
              <Button
                onClick={handleImport}
                className="flex-1"
                disabled={!mappings.some((m) => m.selected)}
              >
                {mappings.filter((m) => m.selected).length} Widget(s) importieren
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
