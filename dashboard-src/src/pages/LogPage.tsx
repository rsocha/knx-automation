import { useState } from "react";
import { useKnxLog, KnxLogEntry } from "@/stores/knxLogStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Trash2, ScrollText, Search, ArrowUp, ArrowDown, AlertTriangle, Info } from "lucide-react";

const typeConfig: Record<KnxLogEntry["type"], { icon: typeof ArrowUp; color: string; label: string }> = {
  send: { icon: ArrowUp, color: "text-primary", label: "SEND" },
  receive: { icon: ArrowDown, color: "text-accent", label: "RECV" },
  error: { icon: AlertTriangle, color: "text-destructive", label: "ERR" },
  info: { icon: Info, color: "text-knx-warning", label: "INFO" },
};

export default function LogPage() {
  const { entries, clear } = useKnxLog();
  const [filter, setFilter] = useState("");

  const filtered = filter
    ? entries.filter(
        (e) =>
          e.address.includes(filter) ||
          e.message?.toLowerCase().includes(filter.toLowerCase()) ||
          e.value?.includes(filter)
      )
    : entries;

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <ScrollText className="w-5 h-5 text-primary" />
          <h1 className="text-xl font-semibold text-foreground">Telegramm-Log</h1>
          <span className="text-xs text-muted-foreground font-mono">({entries.length} Einträge)</span>
        </div>
        <Button variant="ghost" size="sm" onClick={clear} className="text-muted-foreground hover:text-destructive">
          <Trash2 className="w-4 h-4 mr-1" /> Löschen
        </Button>
      </div>

      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <Input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter nach Adresse, Wert oder Nachricht…"
          className="pl-9 bg-secondary border-border font-mono text-sm"
        />
      </div>

      {filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
          <ScrollText className="w-12 h-12 mb-4 opacity-30" />
          <p className="text-sm">Noch keine Telegramme aufgezeichnet</p>
          <p className="text-xs mt-1">Telegramme werden beim Senden und Empfangen hier protokolliert</p>
        </div>
      ) : (
        <ScrollArea className="h-[calc(100vh-220px)]">
          <div className="space-y-1">
            {filtered.map((entry) => {
              const cfg = typeConfig[entry.type];
              const Icon = cfg.icon;
              const time = new Date(entry.timestamp);
              const timeStr = time.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) + "." + String(time.getMilliseconds()).padStart(3, "0");

              return (
                <div key={entry.id} className="flex items-center gap-3 px-3 py-2 rounded-md bg-card border border-border hover:border-muted-foreground/20 transition-colors">
                  <Icon className={`w-4 h-4 shrink-0 ${cfg.color}`} />
                  <span className="text-xs font-mono text-muted-foreground w-24 shrink-0">{timeStr}</span>
                  <span className={`text-xs font-mono font-semibold w-10 shrink-0 ${cfg.color}`}>{cfg.label}</span>
                  <span className="text-sm font-mono text-foreground w-20 shrink-0">{entry.address}</span>
                  {entry.value !== undefined && <span className="text-sm font-mono text-accent font-semibold">= {entry.value}</span>}
                  {entry.message && <span className="text-xs text-muted-foreground truncate">{entry.message}</span>}
                </div>
              );
            })}
          </div>
        </ScrollArea>
      )}
    </div>
  );
}
