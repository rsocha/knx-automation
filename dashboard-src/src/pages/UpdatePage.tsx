import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { 
  RefreshCw, Upload, Download, AlertTriangle, 
  CheckCircle, Server, HardDrive, Cpu, Clock
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { getApiBase, fetchStatus } from "@/services/knxApi";

interface SystemStatus {
  version?: string;
  knx_connected: boolean;
  gateway_ip: string;
  connection_type: string;
  group_address_count: number;
  uptime?: number;
}

export default function UpdatePage() {
  const [isRestarting, setIsRestarting] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);

  const { data: status, refetch } = useQuery({
    queryKey: ["system-status"],
    queryFn: fetchStatus,
    refetchInterval: isRestarting ? 2000 : 10000,
  });

  const handleRestart = async () => {
    if (!confirm("System wirklich neu starten?\n\nAlle laufenden Prozesse werden beendet.")) {
      return;
    }

    setIsRestarting(true);
    toast.info("System wird neu gestartet...");

    try {
      await fetch(`${getApiBase()}/system/restart`, { method: "POST" });
      
      let attempts = 0;
      const checkConnection = setInterval(async () => {
        attempts++;
        try {
          await fetchStatus();
          clearInterval(checkConnection);
          setIsRestarting(false);
          toast.success("System erfolgreich neu gestartet!");
          refetch();
        } catch {
          if (attempts > 30) {
            clearInterval(checkConnection);
            setIsRestarting(false);
            toast.error("Timeout - bitte Seite manuell neu laden");
          }
        }
      }, 2000);
    } catch (err) {
      setIsRestarting(false);
      toast.error("Fehler beim Neustart");
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.endsWith('.tar.gz') && !file.name.endsWith('.tgz')) {
      toast.error("Nur .tar.gz Dateien werden unterstützt");
      return;
    }

    if (!confirm(`Update-Paket "${file.name}" installieren?\n\nDas System wird nach der Installation neu gestartet.`)) {
      e.target.value = '';
      return;
    }

    setUploadProgress(0);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const xhr = new XMLHttpRequest();
      
      xhr.upload.addEventListener("progress", (ev) => {
        if (ev.lengthComputable) {
          setUploadProgress(Math.round((ev.loaded / ev.total) * 100));
        }
      });

      xhr.addEventListener("load", () => {
        setUploadProgress(null);
        e.target.value = '';
        if (xhr.status === 200) {
          toast.success("Update erfolgreich installiert!");
          setTimeout(() => handleRestart(), 1000);
        } else {
          toast.error("Upload fehlgeschlagen");
        }
      });

      xhr.addEventListener("error", () => {
        setUploadProgress(null);
        e.target.value = '';
        toast.error("Upload fehlgeschlagen");
      });

      xhr.open("POST", `${getApiBase()}/system/update`);
      xhr.send(formData);
    } catch (err) {
      setUploadProgress(null);
      e.target.value = '';
      toast.error("Upload fehlgeschlagen");
    }
  };

  const formatUptime = (seconds?: number) => {
    if (!seconds) return "–";
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    if (days > 0) return `${days}d ${hours}h ${mins}m`;
    if (hours > 0) return `${hours}h ${mins}m`;
    return `${mins}m`;
  };

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <RefreshCw className="w-5 h-5 text-primary" />
        <h1 className="text-xl font-semibold">System-Update</h1>
      </div>

      {/* System Status */}
      <div className="rounded-lg bg-card border border-border p-5">
        <h2 className="font-medium mb-4 flex items-center gap-2">
          <Server className="w-4 h-4" /> System-Status
        </h2>
        
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="space-y-1">
            <div className="text-xs text-muted-foreground flex items-center gap-1">
              <HardDrive className="w-3 h-3" /> Version
            </div>
            <div className="font-mono font-medium">{status?.version || "–"}</div>
          </div>
          
          <div className="space-y-1">
            <div className="text-xs text-muted-foreground flex items-center gap-1">
              <Cpu className="w-3 h-3" /> Gateway
            </div>
            <div className="font-mono text-sm">{status?.gateway_ip || "–"}</div>
          </div>
          
          <div className="space-y-1">
            <div className="text-xs text-muted-foreground flex items-center gap-1">
              <Clock className="w-3 h-3" /> Uptime
            </div>
            <div className="font-mono text-sm">{formatUptime((status as any)?.uptime)}</div>
          </div>
          
          <div className="space-y-1">
            <div className="text-xs text-muted-foreground">Status</div>
            <div className={`flex items-center gap-1 text-sm ${status?.knx_connected ? "text-knx-online" : "text-knx-offline"}`}>
              {status?.knx_connected ? (
                <>
                  <CheckCircle className="w-4 h-4" /> Verbunden
                </>
              ) : (
                <>
                  <AlertTriangle className="w-4 h-4" /> Getrennt
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Update Upload */}
      <div className="rounded-lg bg-card border border-border p-5">
        <h2 className="font-medium mb-4 flex items-center gap-2">
          <Upload className="w-4 h-4" /> Update installieren
        </h2>
        
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Lade ein Update-Paket (.tar.gz) hoch um das System zu aktualisieren.
            Nach der Installation wird das System automatisch neu gestartet.
          </p>
          
          <div className="flex items-center gap-3">
            <Input
              type="file"
              accept=".tar.gz,.tgz"
              onChange={handleFileUpload}
              disabled={uploadProgress !== null || isRestarting}
              className="flex-1"
            />
          </div>

          {uploadProgress !== null && (
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>Upload läuft...</span>
                <span>{uploadProgress}%</span>
              </div>
              <div className="w-full bg-secondary rounded-full h-2">
                <div
                  className="bg-primary h-2 rounded-full transition-all"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* System Restart */}
      <div className="rounded-lg bg-card border border-border p-5">
        <h2 className="font-medium mb-4 flex items-center gap-2">
          <RefreshCw className="w-4 h-4" /> System neu starten
        </h2>
        
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Startet den KNX-Server und alle Dienste neu. 
            Laufende Verbindungen werden kurzzeitig unterbrochen.
          </p>
          
          <Button
            onClick={handleRestart}
            disabled={isRestarting}
            variant="destructive"
            className="w-full sm:w-auto"
          >
            {isRestarting ? (
              <>
                <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                Neustart läuft...
              </>
            ) : (
              <>
                <RefreshCw className="w-4 h-4 mr-2" />
                System neu starten
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Backup Download */}
      <div className="rounded-lg bg-card border border-border p-5">
        <h2 className="font-medium mb-4 flex items-center gap-2">
          <Download className="w-4 h-4" /> Backup erstellen
        </h2>
        
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Erstelle ein Backup der aktuellen Konfiguration (Adressen, Logik-Blöcke, Visualisierung).
          </p>
          
          <Button
            variant="secondary"
            onClick={() => {
              window.open(`${getApiBase()}/system/backup`, "_blank");
              toast.success("Backup-Download gestartet");
            }}
          >
            <Download className="w-4 h-4 mr-2" />
            Backup herunterladen
          </Button>
        </div>
      </div>
    </div>
  );
}
