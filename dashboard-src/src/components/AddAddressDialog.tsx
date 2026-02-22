import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useCreateGroupAddress } from "@/hooks/useKnx";
import { toast } from "sonner";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export default function AddAddressDialog({ open, onOpenChange }: Props) {
  const [address, setAddress] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [dpt, setDpt] = useState("");
  const [isInternal, setIsInternal] = useState(false);
  const [initialValue, setInitialValue] = useState("");
  const createAddr = useCreateGroupAddress();

  const handleSubmit = () => {
    if (!address || !name) {
      toast.error("Adresse und Name sind erforderlich");
      return;
    }
    createAddr.mutate(
      { address, name, description: description || undefined, dpt: dpt || undefined, is_internal: isInternal, initial_value: isInternal && initialValue ? initialValue : undefined },
      {
        onSuccess: () => {
          toast.success(`${address} erstellt`);
          onOpenChange(false);
          setAddress("");
          setName("");
          setDescription("");
          setDpt("");
          setIsInternal(false);
          setInitialValue("");
        },
        onError: (err) => toast.error(err.message),
      }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-card border-border">
        <DialogHeader>
          <DialogTitle className="text-card-foreground">Neue Gruppenadresse</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 mt-2">
          <div>
            <Label className="text-muted-foreground text-xs">Adresse *</Label>
            <Input value={address} onChange={(e) => setAddress(e.target.value)} placeholder="1/1/1" className="bg-secondary border-border mt-1" />
          </div>
          <div>
            <Label className="text-muted-foreground text-xs">Name *</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Licht Wohnzimmer" className="bg-secondary border-border mt-1" />
          </div>
          <div>
            <Label className="text-muted-foreground text-xs">Beschreibung</Label>
            <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Optional" className="bg-secondary border-border mt-1" />
          </div>
          <div>
            <Label className="text-muted-foreground text-xs">DPT</Label>
            <Input value={dpt} onChange={(e) => setDpt(e.target.value)} placeholder="DPT1.001" className="bg-secondary border-border mt-1" />
          </div>
          <div className="flex items-center justify-between">
            <Label className="text-muted-foreground text-xs">Interne Adresse (IKO)</Label>
            <Switch checked={isInternal} onCheckedChange={setIsInternal} />
          </div>
          {isInternal && (
            <div>
              <Label className="text-muted-foreground text-xs">Initialwert</Label>
              <Input value={initialValue} onChange={(e) => setInitialValue(e.target.value)} placeholder="z.B. 0, true, 22.5" className="bg-secondary border-border mt-1" />
            </div>
          )}
          <Button onClick={handleSubmit} disabled={createAddr.isPending} className="w-full bg-primary text-primary-foreground">
            {createAddr.isPending ? "Erstelle..." : "Erstellen"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
