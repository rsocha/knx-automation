import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Plus } from "lucide-react";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAdd: (name: string, category: string) => void;
  categories: string[];
  onAddCategory: (category: string) => void;
}

export default function AddRoomDialog({ open, onOpenChange, onAdd, categories, onAddCategory }: Props) {
  const [name, setName] = useState("");
  const [category, setCategory] = useState(categories[0] || "Wohnbereich");
  const [newCategory, setNewCategory] = useState("");

  const handleAdd = () => {
    if (!name.trim()) return;
    onAdd(name.trim(), category);
    setName("");
    onOpenChange(false);
  };

  const handleAddCategory = () => {
    if (newCategory.trim() && !categories.includes(newCategory.trim())) {
      onAddCategory(newCategory.trim());
      setCategory(newCategory.trim());
      setNewCategory("");
    }
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
                {categories.map((c) => (
                  <SelectItem key={c} value={c}>{c}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            
            {/* Add new category inline */}
            <div className="flex gap-2 mt-2">
              <Input
                value={newCategory}
                onChange={(e) => setNewCategory(e.target.value)}
                placeholder="Neue Kategorie..."
                className="bg-secondary border-border text-sm h-8 flex-1"
              />
              <Button 
                variant="outline" 
                size="sm"
                onClick={handleAddCategory}
                disabled={!newCategory.trim()}
                className="h-8"
              >
                <Plus className="w-4 h-4" />
              </Button>
            </div>
          </div>
          <Button onClick={handleAdd} className="w-full bg-primary text-primary-foreground" disabled={!name.trim()}>
            Erstellen
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
