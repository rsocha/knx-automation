import { useGroupAddresses } from "@/hooks/useKnx";
import { Activity } from "lucide-react";

interface Props {
  label: string;
  statusAddress: string;
  unit?: string;
}

export default function WidgetStatusDisplay({ label, statusAddress, unit }: Props) {
  const { data: addresses } = useGroupAddresses();
  const ga = addresses?.find((a) => a.address === statusAddress);
  const value = ga?.value ?? "–";

  return (
    <div className="bg-card border border-border rounded-xl p-4 flex flex-col items-center gap-2 min-w-[140px]">
      <Activity className="w-5 h-5 text-accent" />
      <span className="text-sm font-medium text-foreground truncate w-full text-center">{label}</span>
      <span className="text-2xl font-mono font-semibold text-foreground">
        {value}{unit ? <span className="text-sm text-muted-foreground ml-1">{unit}</span> : null}
      </span>
      <span className="text-xs font-mono text-muted-foreground">{statusAddress}</span>
    </div>
  );
}
