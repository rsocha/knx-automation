import { useState, useEffect, useMemo } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Search, Check } from "lucide-react";
import ColorPicker from "@/components/ui/color-picker";
import { useGroupAddresses } from "@/hooks/useKnx";
import type { VseTemplate, VseWidgetInstance } from "@/types/vse";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  widget: VseWidgetInstance | null;
  template: VseTemplate | null;
  onSave: (updated: VseWidgetInstance) => void;
}

export default function EditVseWidgetDialog({ open, onOpenChange, widget, template, onSave }: Props) {
  const [label, setLabel] = useState("");
  const [koBindings, setKoBindings] = useState<Record<string, string>>({});
  const [variableValues, setVariableValues] = useState<Record<string, any>>({});
  const [widthOverride, setWidthOverride] = useState<number | undefined>();
  const [heightOverride, setHeightOverride] = useState<number | undefined>();
  const [activeKoField, setActiveKoField] = useState<string | null>(null);
  const [koSearch, setKoSearch] = useState("");

  const { data: allAddresses = [] } = useGroupAddresses();

  const filteredAddresses = useMemo(() => {
    if (!koSearch) return allAddresses.slice(0, 50);
    const q = koSearch.toLowerCase();
    return allAddresses.filter((a) =>
      a.address.toLowerCase().includes(q) ||
      a.name?.toLowerCase().includes(q) ||
      a.group?.toLowerCase().includes(q)
    ).slice(0, 50);
  }, [allAddresses, koSearch]);

  // Sync state when widget changes
  useEffect(() => {
    if (widget && template) {
      setLabel(widget.label);
      setKoBindings({ ...widget.koBindings });
      setWidthOverride(widget.widthOverride);
      setHeightOverride(widget.heightOverride);
      const defaults = Object.fromEntries(
        Object.entries(template.variables).map(([k, v]) => [k, v.default])
      );
      setVariableValues({ ...defaults, ...widget.variableValues });
      setActiveKoField(null);
      setKoSearch("");
    }
  }, [widget, template]);

  if (!widget || !template) return null;

  const selectAddress = (address: string) => {
    if (activeKoField) {
      setKoBindings((prev) => ({ ...prev, [activeKoField]: address }));
      setActiveKoField(null);
      setKoSearch("");
    }
  };

  const handleSave = () => {
    // Only store values that differ from defaults
    const overrides: Record<string, any> = {};
    for (const [key, val] of Object.entries(variableValues)) {
      const def = template.variables[key]?.default;
      if (val !== def && val !== "" && val !== undefined) {
        overrides[key] = val;
      }
    }
    onSave({
      ...widget,
      label: label.trim() || widget.label,
      koBindings,
      variableValues: overrides,
      widthOverride,
      heightOverride,
    });
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-card border-border sm:max-w-lg max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="text-card-foreground">Widget bearbeiten</DialogTitle>
        </DialogHeader>

        <Tabs defaultValue="general" className="flex-1 min-h-0">
          <TabsList className="w-full">
            <TabsTrigger value="general" className="flex-1 text-xs">Allgemein</TabsTrigger>
            <TabsTrigger value="variables" className="flex-1 text-xs">Variablen</TabsTrigger>
          </TabsList>

          <TabsContent value="general" className="mt-3">
            <ScrollArea className="h-[380px] pr-2">
              <div className="space-y-4">
                {/* Label */}
                <div>
                  <Label className="text-muted-foreground text-xs">Bezeichnung</Label>
                  <Input
                    value={label}
                    onChange={(e) => setLabel(e.target.value)}
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
                    <ScrollArea className="h-28">
                      <div className="space-y-0.5">
                        {filteredAddresses.map((addr) => (
                          <button
                            key={addr.address}
                            className="w-full text-left px-2 py-1 rounded text-[10px] hover:bg-primary/10 transition-colors flex items-center gap-2"
                            onClick={() => selectAddress(addr.address)}
                          >
                            <span className="font-mono w-16 shrink-0 text-primary">{addr.address}</span>
                            <span className="truncate flex-1 text-foreground">{addr.name || "–"}</span>
                            {addr.is_internal && (
                              <span className="text-[9px] px-1 rounded bg-purple-500/20 text-purple-400">IKO</span>
                            )}
                          </button>
                        ))}
                      </div>
                    </ScrollArea>
                  </div>
                )}

                <div className="text-[10px] text-muted-foreground bg-secondary/50 rounded-lg p-2">
                  Template: <span className="font-mono">{template.name}</span> ({template.width}×{template.height})
                </div>

                {/* Size overrides */}
                <div className="space-y-2">
                  <Label className="text-muted-foreground text-xs">Größe (leer = Standard)</Label>
                  <div className="flex gap-2">
                    <div className="flex-1">
                      <Input
                        type="number"
                        value={widthOverride ?? ""}
                        onChange={(e) => setWidthOverride(e.target.value === "" ? undefined : Number(e.target.value))}
                        placeholder={String(template.width)}
                        className="bg-secondary border-border h-7 text-xs"
                      />
                      <span className="text-[9px] text-muted-foreground">Breite</span>
                    </div>
                    <div className="flex-1">
                      <Input
                        type="number"
                        value={heightOverride ?? ""}
                        onChange={(e) => setHeightOverride(e.target.value === "" ? undefined : Number(e.target.value))}
                        placeholder={String(template.height)}
                        className="bg-secondary border-border h-7 text-xs"
                      />
                      <span className="text-[9px] text-muted-foreground">Höhe</span>
                    </div>
                  </div>
                </div>
              </div>
            </ScrollArea>
          </TabsContent>

          <TabsContent value="variables" className="mt-3 min-h-0">
            <ScrollArea className="h-[380px] pr-2">
              <div className="space-y-3">
                {Object.entries(template.variables).map(([key, variable]) => (
                  <div key={key}>
                    <Label className="text-muted-foreground text-[10px]">
                      {variable.name}
                      <span className="ml-1 opacity-50 font-mono">({key})</span>
                    </Label>
                    {variable.type === "bool" ? (
                      <div className="flex gap-2 mt-1">
                        <button
                          onClick={() => setVariableValues((prev) => ({ ...prev, [key]: "1" }))}
                          className={`px-3 py-1 rounded text-xs transition-colors ${
                            variableValues[key] === "1" || variableValues[key] === true
                              ? "bg-primary text-primary-foreground"
                              : "bg-secondary text-muted-foreground"
                          }`}
                        >
                          An
                        </button>
                        <button
                          onClick={() => setVariableValues((prev) => ({ ...prev, [key]: "0" }))}
                          className={`px-3 py-1 rounded text-xs transition-colors ${
                            variableValues[key] === "0" || variableValues[key] === false
                              ? "bg-primary text-primary-foreground"
                              : "bg-secondary text-muted-foreground"
                          }`}
                        >
                          Aus
                        </button>
                      </div>
                    ) : variable.type === "number" ? (
                      <Input
                        type="number"
                        value={variableValues[key] ?? ""}
                        onChange={(e) =>
                          setVariableValues((prev) => ({
                            ...prev,
                            [key]: e.target.value === "" ? undefined : Number(e.target.value),
                          }))
                        }
                        className="bg-secondary border-border h-7 text-xs mt-1"
                      />
                    ) : variable.type === "color" ? (
                      <ColorPicker
                        value={variableValues[key] ?? variable.default ?? "255,255,255"}
                        onChange={(val) => setVariableValues((prev) => ({ ...prev, [key]: val }))}
                        className="mt-1"
                      />
                    ) : (
                      <Input
                        value={variableValues[key] ?? ""}
                        onChange={(e) => setVariableValues((prev) => ({ ...prev, [key]: e.target.value }))}
                        placeholder={String(variable.default || "")}
                        className="bg-secondary border-border h-7 text-xs mt-1"
                      />
                    )}
                  </div>
                ))}
              </div>
            </ScrollArea>
          </TabsContent>
        </Tabs>

        <Button onClick={handleSave} className="w-full bg-primary text-primary-foreground mt-2">
          Speichern
        </Button>
      </DialogContent>
    </Dialog>
  );
}
