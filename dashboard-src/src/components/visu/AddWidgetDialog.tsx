import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { VisuWidget } from "@/types/knx";
import { generateUUID } from "@/lib/uuid";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAdd: (widget: VisuWidget) => void;
}

export default function AddWidgetDialog({ open, onOpenChange, onAdd }: Props) {
  const [type, setType] = useState("switch");
  const [label, setLabel] = useState("");
  const [statusAddr, setStatusAddr] = useState("");
  const [sendAddr, setSendAddr] = useState("");
  const [unit, setUnit] = useState("");

  const handleAdd = () => {
    if (!label || !statusAddr) return;
    const widget: VisuWidget = {
      id: generateUUID(),
      type,
      label,
      statusAddress: statusAddr,
      sendAddress: sendAddr || undefined,
      unit: unit || undefined,
    } as VisuWidget & { unit?: string };
    onAdd(widget);
    setLabel("");
    setStatusAddr("");
    setSendAddr("");
    setUnit("");
    onOpenChange(false);
  };

  const needsSendAddr = type === "switch" || type === "dimmer";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-card border-border">
        <DialogHeader>
          <DialogTitle className="text-card-foreground">Widget hinzufügen</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 mt-2">
          <div>
            <Label className="text-muted-foreground text-xs">Widget-Typ</Label>
            <Select value={type} onValueChange={setType}>
              <SelectTrigger className="bg-secondary border-border mt-1">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="switch">Schalter</SelectItem>
                <SelectItem value="dimmer">Dimmer</SelectItem>
                <SelectItem value="status">Statusanzeige</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-muted-foreground text-xs">Bezeichnung</Label>
            <Input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="z.B. Deckenlicht" className="bg-secondary border-border mt-1" />
          </div>
          <div>
            <Label className="text-muted-foreground text-xs">Status-Gruppenadresse</Label>
            <Input value={statusAddr} onChange={(e) => setStatusAddr(e.target.value)} placeholder="z.B. 1/4/6" className="bg-secondary border-border mt-1 font-mono" />
          </div>
          {needsSendAddr && (
            <div>
              <Label className="text-muted-foreground text-xs">Sende-Gruppenadresse</Label>
              <Input value={sendAddr} onChange={(e) => setSendAddr(e.target.value)} placeholder="z.B. 1/1/6" className="bg-secondary border-border mt-1 font-mono" />
            </div>
          )}
          {type === "status" && (
            <div>
              <Label className="text-muted-foreground text-xs">Einheit (optional)</Label>
              <Input value={unit} onChange={(e) => setUnit(e.target.value)} placeholder="z.B. °C, %, lux" className="bg-secondary border-border mt-1" />
            </div>
          )}
          <Button onClick={handleAdd} className="w-full bg-primary text-primary-foreground" disabled={!label || !statusAddr}>
            Hinzufügen
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
