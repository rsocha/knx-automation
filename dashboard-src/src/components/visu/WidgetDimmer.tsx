import { Slider } from "@/components/ui/slider";
import { useSendKnxCommand, useGroupAddresses } from "@/hooks/useKnx";
import { SunDim } from "lucide-react";
import { useState, useEffect } from "react";

interface Props {
  label: string;
  statusAddress: string;
  sendAddress: string;
}

export default function WidgetDimmer({ label, statusAddress, sendAddress }: Props) {
  const { data: addresses } = useGroupAddresses();
  const send = useSendKnxCommand();

  const ga = addresses?.find((a) => a.address === statusAddress);
  const currentValue = ga?.value !== undefined ? Math.round(Number(ga.value)) : 0;
  const [localValue, setLocalValue] = useState(currentValue);
  const [isDragging, setIsDragging] = useState(false);

  useEffect(() => {
    if (!isDragging) setLocalValue(currentValue);
  }, [currentValue, isDragging]);

  const commitValue = (val: number) => {
    setIsDragging(false);
    send.mutate({ address: sendAddress, value: val });
  };

  const pct = Math.min(100, Math.max(0, isDragging ? localValue : currentValue));

  return (
    <div className="bg-card border border-border rounded-xl p-4 flex flex-col items-center gap-3 min-w-[180px]">
      <SunDim className={`w-6 h-6 ${pct > 0 ? "text-knx-warning" : "text-muted-foreground"}`} />
      <span className="text-sm font-medium text-foreground truncate w-full text-center">{label}</span>
      <span className="text-2xl font-mono font-semibold text-foreground">{pct}%</span>
      <Slider
        min={0}
        max={100}
        step={1}
        value={[isDragging ? localValue : currentValue]}
        onValueChange={([v]) => { setIsDragging(true); setLocalValue(v); }}
        onValueCommit={([v]) => commitValue(v)}
        className="w-full"
      />
      <span className="text-xs font-mono text-muted-foreground">{statusAddress}</span>
    </div>
  );
}
