import { useState, useEffect } from "react";
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
import { useUpdateGroupAddress } from "@/hooks/useKnx";
import { GroupAddress } from "@/types/knx";
import { toast } from "sonner";

interface Props {
  address: GroupAddress | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export default function EditAddressDialog({ address, open, onOpenChange }: Props) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [dpt, setDpt] = useState("");
  const [isInternal, setIsInternal] = useState(false);
  const [initialValue, setInitialValue] = useState("");
  const updateAddr = useUpdateGroupAddress();

  useEffect(() => {
    if (address) {
      setName(address.name || "");
      setDescription(address.description || "");
      setDpt(address.dpt || "");
      setIsInternal(address.is_internal || false);
      setInitialValue((address as any).initial_value || address.value || "");
    }
  }, [address]);

  const handleSubmit = () => {
    if (!address) return;
    updateAddr.mutate(
      {
        address: address.address,
        data: { name, description: description || undefined, dpt: dpt || undefined, is_internal: isInternal, initial_value: isInternal && initialValue ? initialValue : undefined },
      },
      {
        onSuccess: () => {
          toast.success(`${address.address} aktualisiert`);
          onOpenChange(false);
        },
        onError: (err) => toast.error(err.message),
      }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-card border-border">
        <DialogHeader>
          <DialogTitle className="text-card-foreground">
            Adresse bearbeiten: <span className="font-mono text-primary">{address?.address}</span>
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4 mt-2">
          <div>
            <Label className="text-muted-foreground text-xs">Name</Label>
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
          <Button onClick={handleSubmit} disabled={updateAddr.isPending} className="w-full bg-primary text-primary-foreground">
            {updateAddr.isPending ? "Speichere..." : "Speichern"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
