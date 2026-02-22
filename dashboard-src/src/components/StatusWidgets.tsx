import { Wifi, WifiOff, Activity, Link, Zap } from "lucide-react";
import { useKnxStatus, useGroupAddresses } from "@/hooks/useKnx";

interface StatWidgetProps {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  color: string;
}

function StatWidget({ icon, label, value, color }: StatWidgetProps) {
  return (
    <div className="rounded-lg bg-card border border-border p-5 flex flex-col gap-3 animate-fade-in">
      <div className="text-muted-foreground">{icon}</div>
      <div>
        <div className={`text-3xl font-semibold font-mono ${color}`}>{value}</div>
        <div className="text-xs text-muted-foreground mt-1">{label}</div>
      </div>
    </div>
  );
}

export default function StatusWidgets() {
  const { data: status } = useKnxStatus();
  const { data: addresses } = useGroupAddresses();

  const totalAddresses = addresses?.length ?? 0;
  const internalCount = addresses?.filter((a) => a.is_internal).length ?? 0;
  const activeCount = addresses?.filter((a) => a.value && a.value !== "0" && a.value !== "false").length ?? 0;

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <StatWidget
        icon={status?.knx_connected ? <Wifi className="w-5 h-5" /> : <WifiOff className="w-5 h-5" />}
        label="KNX Gateway"
        value={status?.knx_connected ? "Online" : "Offline"}
        color={status?.knx_connected ? "text-knx-online" : "text-knx-offline"}
      />
      <StatWidget
        icon={<Activity className="w-5 h-5" />}
        label="Gruppenadressen"
        value={totalAddresses}
        color="text-knx-info"
      />
      <StatWidget
        icon={<Link className="w-5 h-5" />}
        label="Interne (IKO)"
        value={internalCount}
        color="text-knx-purple"
      />
      <StatWidget
        icon={<Zap className="w-5 h-5" />}
        label="Aktive Geräte"
        value={activeCount}
        color="text-knx-warning"
      />
    </div>
  );
}
