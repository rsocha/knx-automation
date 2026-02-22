import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
    }
  }, [widget, template]);

  if (!widget || !template) return null;

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

          <TabsContent value="general" className="mt-3 space-y-4">
            {/* Label */}
            <div>
              <Label className="text-muted-foreground text-xs">Bezeichnung</Label>
              <Input
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                className="bg-secondary border-border mt-1"
              />
            </div>

            {/* KO Bindings */}
            <div className="space-y-2">
              <Label className="text-muted-foreground text-xs">KO-Zuordnungen</Label>
              {Object.entries(template.inputs).map(([key, input]) => (
                <div key={key} className="flex items-center gap-2">
                  <span className="text-[10px] text-foreground w-28 shrink-0">{input.name}</span>
                  <Input
                    value={koBindings[key] || ""}
                    onChange={(e) => setKoBindings((prev) => ({ ...prev, [key]: e.target.value }))}
                    placeholder="z.B. 1/1/1"
                    className="bg-secondary border-border h-7 text-xs font-mono"
                  />
                </div>
              ))}
            </div>

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
          </TabsContent>

          <TabsContent value="variables" className="mt-3 min-h-0">
            <ScrollArea className="h-[340px] pr-2">
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
                      <Input
                        value={variableValues[key] ?? ""}
                        onChange={(e) => setVariableValues((prev) => ({ ...prev, [key]: e.target.value }))}
                        placeholder="R,G,B"
                        className="bg-secondary border-border h-7 text-xs font-mono mt-1"
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
