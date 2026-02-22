import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import ColorPicker from "@/components/ui/color-picker";
import type { VisuRoom, RoomBackground } from "@/types/vse";
import { Paintbrush, Image, Type, Palette, Trash2, Plus } from "lucide-react";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  room: VisuRoom | null;
  categories: string[];
  onSave: (room: VisuRoom) => void;
  onDelete?: (roomId: string) => void;
  onAddCategory: (category: string) => void;
}

export default function RoomSettingsDialog({ 
  open, 
  onOpenChange, 
  room, 
  categories,
  onSave, 
  onDelete,
  onAddCategory 
}: Props) {
  const [name, setName] = useState("");
  const [category, setCategory] = useState("");
  const [icon, setIcon] = useState("");
  const [newCategory, setNewCategory] = useState("");
  const [background, setBackground] = useState<RoomBackground>({
    type: "color",
    color: "20,20,25",
    opacity: 100,
  });

  useEffect(() => {
    if (room) {
      setName(room.name);
      setCategory(room.category);
      setIcon(room.icon || "");
      setBackground(room.background || {
        type: "color",
        color: "20,20,25",
        opacity: 100,
      });
    }
  }, [room]);

  const handleSave = () => {
    if (!room || !name.trim()) return;
    onSave({
      ...room,
      name: name.trim(),
      category,
      icon: icon || undefined,
      background,
    });
    onOpenChange(false);
  };

  const handleAddCategory = () => {
    if (newCategory.trim() && !categories.includes(newCategory.trim())) {
      onAddCategory(newCategory.trim());
      setCategory(newCategory.trim());
      setNewCategory("");
    }
  };

  const handleDelete = () => {
    if (room && onDelete && confirm(`Raum "${room.name}" wirklich löschen?\n\nAlle Widgets in diesem Raum werden ebenfalls gelöscht.`)) {
      onDelete(room.id);
      onOpenChange(false);
    }
  };

  if (!room) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-card border-border sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-card-foreground flex items-center gap-2">
            <Paintbrush className="w-5 h-5 text-primary" />
            Raum bearbeiten
          </DialogTitle>
        </DialogHeader>

        <Tabs defaultValue="general" className="mt-2">
          <TabsList className="grid w-full grid-cols-2 bg-secondary">
            <TabsTrigger value="general">Allgemein</TabsTrigger>
            <TabsTrigger value="background">Hintergrund</TabsTrigger>
          </TabsList>

          <TabsContent value="general" className="space-y-4 mt-4">
            {/* Name */}
            <div>
              <Label className="text-xs text-muted-foreground flex items-center gap-1">
                <Type className="w-3 h-3" /> Name
              </Label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Raumname"
                className="bg-secondary border-border mt-1"
              />
            </div>

            {/* Category */}
            <div>
              <Label className="text-xs text-muted-foreground">Kategorie</Label>
              <Select value={category} onValueChange={setCategory}>
                <SelectTrigger className="bg-secondary border-border mt-1">
                  <SelectValue placeholder="Kategorie wählen" />
                </SelectTrigger>
                <SelectContent>
                  {categories.map((cat) => (
                    <SelectItem key={cat} value={cat}>{cat}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              
              {/* Add new category */}
              <div className="flex gap-2 mt-2">
                <Input
                  value={newCategory}
                  onChange={(e) => setNewCategory(e.target.value)}
                  placeholder="Neue Kategorie..."
                  className="bg-secondary border-border text-sm h-8"
                />
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={handleAddCategory}
                  disabled={!newCategory.trim()}
                >
                  <Plus className="w-4 h-4" />
                </Button>
              </div>
            </div>

            {/* Icon */}
            <div>
              <Label className="text-xs text-muted-foreground">Icon (Emoji oder MDI)</Label>
              <Input
                value={icon}
                onChange={(e) => setIcon(e.target.value)}
                placeholder="🏠 oder home"
                className="bg-secondary border-border mt-1"
              />
            </div>
          </TabsContent>

          <TabsContent value="background" className="space-y-4 mt-4">
            {/* Background Type */}
            <div>
              <Label className="text-xs text-muted-foreground">Hintergrund-Typ</Label>
              <Select 
                value={background.type} 
                onValueChange={(val: "color" | "gradient" | "image") => 
                  setBackground({ ...background, type: val })
                }
              >
                <SelectTrigger className="bg-secondary border-border mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="color">Farbe</SelectItem>
                  <SelectItem value="gradient">Farbverlauf</SelectItem>
                  <SelectItem value="image">Bild</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Color Background */}
            {background.type === "color" && (
              <>
                <div>
                  <Label className="text-xs text-muted-foreground flex items-center gap-1">
                    <Palette className="w-3 h-3" /> Hintergrundfarbe
                  </Label>
                  <ColorPicker
                    value={background.color || "20,20,25"}
                    onChange={(val) => setBackground({ ...background, color: val })}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground">Deckkraft (%)</Label>
                  <Input
                    type="number"
                    min={0}
                    max={100}
                    value={background.opacity ?? 100}
                    onChange={(e) => setBackground({ ...background, opacity: Number(e.target.value) })}
                    className="bg-secondary border-border mt-1"
                  />
                </div>
              </>
            )}

            {/* Gradient Background */}
            {background.type === "gradient" && (
              <>
                <div>
                  <Label className="text-xs text-muted-foreground">Startfarbe</Label>
                  <ColorPicker
                    value={background.gradientStart || "30,30,40"}
                    onChange={(val) => setBackground({ ...background, gradientStart: val })}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground">Endfarbe</Label>
                  <ColorPicker
                    value={background.gradientEnd || "10,10,15"}
                    onChange={(val) => setBackground({ ...background, gradientEnd: val })}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground">Winkel (°)</Label>
                  <Input
                    type="number"
                    min={0}
                    max={360}
                    value={background.gradientAngle ?? 180}
                    onChange={(e) => setBackground({ ...background, gradientAngle: Number(e.target.value) })}
                    className="bg-secondary border-border mt-1"
                  />
                </div>
              </>
            )}

            {/* Image Background */}
            {background.type === "image" && (
              <>
                <div>
                  <Label className="text-xs text-muted-foreground flex items-center gap-1">
                    <Image className="w-3 h-3" /> Bild-URL
                  </Label>
                  <Input
                    value={background.imageUrl || ""}
                    onChange={(e) => setBackground({ ...background, imageUrl: e.target.value })}
                    placeholder="https://..."
                    className="bg-secondary border-border mt-1"
                  />
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground">Bild-Deckkraft (%)</Label>
                  <Input
                    type="number"
                    min={0}
                    max={100}
                    value={background.imageOpacity ?? 30}
                    onChange={(e) => setBackground({ ...background, imageOpacity: Number(e.target.value) })}
                    className="bg-secondary border-border mt-1"
                  />
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground">Bildgröße</Label>
                  <Select 
                    value={background.imageSize || "cover"} 
                    onValueChange={(val: "cover" | "contain" | "auto") => 
                      setBackground({ ...background, imageSize: val })
                    }
                  >
                    <SelectTrigger className="bg-secondary border-border mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="cover">Ausfüllen (cover)</SelectItem>
                      <SelectItem value="contain">Einpassen (contain)</SelectItem>
                      <SelectItem value="auto">Original (auto)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </>
            )}

            {/* Preview */}
            <div>
              <Label className="text-xs text-muted-foreground">Vorschau</Label>
              <div 
                className="mt-1 h-20 rounded-lg border border-border"
                style={getBackgroundStyle(background)}
              />
            </div>
          </TabsContent>
        </Tabs>

        <div className="flex gap-2 mt-4">
          {onDelete && (
            <Button variant="destructive" size="sm" onClick={handleDelete}>
              <Trash2 className="w-4 h-4 mr-1" /> Löschen
            </Button>
          )}
          <div className="flex-1" />
          <Button variant="outline" onClick={() => onOpenChange(false)}>Abbrechen</Button>
          <Button onClick={handleSave}>Speichern</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function getBackgroundStyle(bg?: RoomBackground): React.CSSProperties {
  if (!bg) return { background: "rgb(20,20,25)" };

  switch (bg.type) {
    case "color":
      return {
        background: `rgba(${bg.color || "20,20,25"}, ${(bg.opacity ?? 100) / 100})`,
      };
    case "gradient":
      return {
        background: `linear-gradient(${bg.gradientAngle || 180}deg, rgb(${bg.gradientStart || "30,30,40"}), rgb(${bg.gradientEnd || "10,10,15"}))`,
      };
    case "image":
      return {
        backgroundImage: `url(${bg.imageUrl})`,
        backgroundSize: bg.imageSize || "cover",
        backgroundPosition: "center",
        backgroundRepeat: "no-repeat",
        opacity: (bg.imageOpacity ?? 30) / 100,
      };
    default:
      return { background: "rgb(20,20,25)" };
  }
}
