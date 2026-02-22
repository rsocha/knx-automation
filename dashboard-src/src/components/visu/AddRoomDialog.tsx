import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAdd: (name: string, category: string) => void;
}

const CATEGORIES = ["Wohnbereich", "Schlafbereich", "Küche", "Außen", "Allgemein"];

export default function AddRoomDialog({ open, onOpenChange, onAdd }: Props) {
  const [name, setName] = useState("");
  const [category, setCategory] = useState("Wohnbereich");

  const handleAdd = () => {
    if (!name.trim()) return;
    onAdd(name.trim(), category);
    setName("");
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-card border-border sm:max-w-sm">
        <DialogHeader>
          <DialogTitle className="text-card-foreground">Neuer Raum</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 mt-2">
          <div>
            <Label className="text-muted-foreground text-xs">Raumname</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="z.B. Wohnzimmer" className="bg-secondary border-border mt-1" />
          </div>
          <div>
            <Label className="text-muted-foreground text-xs">Kategorie</Label>
            <Select value={category} onValueChange={setCategory}>
              <SelectTrigger className="bg-secondary border-border mt-1">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CATEGORIES.map((c) => (
                  <SelectItem key={c} value={c}>{c}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button onClick={handleAdd} className="w-full bg-primary text-primary-foreground" disabled={!name.trim()}>
            Erstellen
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
