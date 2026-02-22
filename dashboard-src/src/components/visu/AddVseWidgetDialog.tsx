import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import type { VseTemplate, VseWidgetInstance } from "@/types/vse";
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

  const template = templates.find((t) => t.id === selectedTemplate);

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
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-card border-border sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-card-foreground">VSE Widget hinzufügen</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 mt-2">
          {/* Template selection */}
          <div>
            <Label className="text-muted-foreground text-xs">Widget-Vorlage</Label>
            <div className="grid grid-cols-2 gap-2 mt-1">
              {templates.map((t) => (
                <button
                  key={t.id}
                  onClick={() => {
                    setSelectedTemplate(t.id);
                    setKoBindings({});
                  }}
                  className={`p-3 rounded-lg border text-left transition-colors ${
                    selectedTemplate === t.id
                      ? "border-primary bg-primary/10"
                      : "border-border bg-secondary hover:bg-muted"
                  }`}
                >
                  <div className="text-xs font-medium text-foreground">{t.name}</div>
                  <div className="text-[10px] text-muted-foreground mt-0.5">{t.description}</div>
                  <div className="text-[9px] text-muted-foreground font-mono mt-1">{t.width}×{t.height}</div>
                </button>
              ))}
            </div>
          </div>

          {template && (
            <>
              <div>
                <Label className="text-muted-foreground text-xs">Bezeichnung</Label>
                <Input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="z.B. Deckenlicht" className="bg-secondary border-border mt-1" />
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

              <Button onClick={handleAdd} className="w-full bg-primary text-primary-foreground" disabled={!label.trim()}>
                Hinzufügen
              </Button>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
