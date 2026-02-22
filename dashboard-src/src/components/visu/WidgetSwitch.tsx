import { Switch } from "@/components/ui/switch";
import { useSendKnxCommand, useGroupAddresses } from "@/hooks/useKnx";
import { Power } from "lucide-react";

interface Props {
  label: string;
  statusAddress: string;
  sendAddress: string;
}

export default function WidgetSwitch({ label, statusAddress, sendAddress }: Props) {
  const { data: addresses } = useGroupAddresses();
  const send = useSendKnxCommand();

  const ga = addresses?.find((a) => a.address === statusAddress);
  const isOn = ga?.value === "True" || ga?.value === "1" || ga?.value === "true";

  const toggle = () => {
    send.mutate({ address: sendAddress, value: isOn ? 0 : 1 });
  };

  return (
    <div className="bg-card border border-border rounded-xl p-4 flex flex-col items-center gap-3 min-w-[140px]">
      <Power className={`w-6 h-6 ${isOn ? "text-primary" : "text-muted-foreground"}`} />
      <span className="text-sm font-medium text-foreground truncate w-full text-center">{label}</span>
      <Switch checked={isOn} onCheckedChange={toggle} disabled={send.isPending} />
      <span className="text-xs font-mono text-muted-foreground">{statusAddress}</span>
    </div>
  );
}
