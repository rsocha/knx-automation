import { useState, useRef } from "react";
import { Settings, Server, RefreshCw, Download, Upload, AlertTriangle, LayoutGrid, Package, Smartphone, QrCode } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { getApiBase, setApiBase, fetchStatus, exportVisuConfig, importVisuConfig } from "@/services/knxApi";
import { useKnxStatus } from "@/hooks/useKnx";

export default function SettingsPage() {
  const { data: status, refetch } = useKnxStatus();
  const [apiUrl, setApiUrl] = useState(getApiBase());
  const [isRestarting, setIsRestarting] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [isUploadingTemplate, setIsUploadingTemplate] = useState(false);
  const [showQR, setShowQR] = useState(false);
  const importInputRef = useRef<HTMLInputElement>(null);
  const templateInputRef = useRef<HTMLInputElement>(null);

  const panelUrl = `${window.location.origin}/panel`;

  const handleSaveApiUrl = () => {
    setApiBase(apiUrl);
    toast.success("API URL gespeichert - Seite wird neu geladen");
    setTimeout(() => window.location.reload(), 500);
  };

  const testConnection = async () => {
    try {
      const res = await fetch(`${apiUrl}/status`, {
        headers: { "ngrok-skip-browser-warning": "true" }
      });
      if (res.ok) {
        toast.success("✅ Verbindung erfolgreich!");
        refetch();
      } else {
        toast.error("❌ Server antwortet nicht korrekt");
      }
    } catch {
      toast.error("❌ Keine Verbindung zum Server");
    }
  };

  const handleTemplateUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.endsWith('.vse.json') && !file.name.endsWith('.json')) {
      toast.error("Nur .vse.json oder .json Dateien erlaubt");
      return;
    }

    setIsUploadingTemplate(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      
      const res = await fetch(`${getApiBase()}/vse/upload`, {
        method: "POST",
        body: formData,
      });
      
      if (res.ok) {
        const data = await res.json();
        toast.success(`Template "${data.name || file.name}" hochgeladen! Seite neu laden.`);
      } else {
        const err = await res.json().catch(() => ({}));
        toast.error(err.detail || "Upload fehlgeschlagen");
      }
    } catch (err) {
      toast.error("Upload fehlgeschlagen");
    } finally {
      setIsUploadingTemplate(false);
      if (templateInputRef.current) templateInputRef.current.value = "";
    }
  };

  const downloadTemplates = () => {
    window.open(`${getApiBase()}/vse/download`, "_blank");
  };

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

  const handleExportVisu = () => {
    exportVisuConfig();
    toast.success("Export gestartet");
  };

  const handleImportVisu = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.endsWith('.json')) {
      toast.error("Nur JSON-Dateien werden unterstützt");
      return;
    }

    setIsImporting(true);
    try {
      const result = await importVisuConfig(file);
      toast.success(`Import erfolgreich: ${result.rooms} Räume importiert`);
      setTimeout(() => window.location.reload(), 1000);
    } catch (err: any) {
      toast.error(`Import fehlgeschlagen: ${err.message}`);
    } finally {
      setIsImporting(false);
      if (importInputRef.current) {
        importInputRef.current.value = '';
      }
    }
  };

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Settings className="w-5 h-5 text-primary" />
        <h1 className="text-xl font-semibold">Einstellungen</h1>
      </div>

      {/* API Settings */}
      <div className="rounded-lg bg-card border border-border p-5">
        <h2 className="font-medium mb-4 flex items-center gap-2">
          <Server className="w-4 h-4" /> API-Verbindung
        </h2>
        
        <div className="space-y-4">
          <div>
            <Label className="text-xs text-muted-foreground">KNX API URL</Label>
            <div className="flex gap-2 mt-1">
              <Input
                value={apiUrl}
                onChange={(e) => setApiUrl(e.target.value)}
                placeholder="http://192.168.0.87:8000/api/v1"
                className="flex-1 font-mono text-sm"
              />
              <Button variant="secondary" onClick={testConnection}>
                Testen
              </Button>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Die URL deines FastAPI KNX-Servers
            </p>
          </div>
          
          <Button onClick={handleSaveApiUrl}>
            Speichern & Neu laden
          </Button>
        </div>
      </div>

      {/* Visu Backup/Restore */}
      <div className="rounded-lg bg-card border border-border p-5">
        <h2 className="font-medium mb-4 flex items-center gap-2">
          <LayoutGrid className="w-4 h-4" /> Visualisierung Backup
        </h2>
        
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Exportiere oder importiere deine Visualisierungs-Konfiguration (Räume, Widgets, Positionen).
            Die Konfiguration wird automatisch auf dem Server gespeichert.
          </p>
          
          <div className="flex gap-3">
            <Button variant="secondary" onClick={handleExportVisu}>
              <Download className="w-4 h-4 mr-2" />
              Export
            </Button>
            
            <div className="relative">
              <input
                ref={importInputRef}
                type="file"
                accept=".json"
                onChange={handleImportVisu}
                className="absolute inset-0 opacity-0 cursor-pointer"
                disabled={isImporting}
              />
              <Button variant="outline" disabled={isImporting}>
                <Upload className="w-4 h-4 mr-2" />
                {isImporting ? "Importiere..." : "Import"}
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Widget Templates */}
      <div className="rounded-lg bg-card border border-border p-5">
        <h2 className="font-medium mb-4 flex items-center gap-2">
          <Package className="w-4 h-4" /> Widget Templates (VSE)
        </h2>
        
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Lade eigene Widget-Templates hoch oder lade alle Templates herunter.
            Templates müssen als <code className="bg-muted px-1 rounded">.vse.json</code> Datei vorliegen.
          </p>
          
          <div className="flex gap-3">
            <Button variant="secondary" onClick={downloadTemplates}>
              <Download className="w-4 h-4 mr-2" />
              Alle Templates
            </Button>
            
            <div className="relative">
              <input
                ref={templateInputRef}
                type="file"
                accept=".json,.vse.json"
                onChange={handleTemplateUpload}
                className="absolute inset-0 opacity-0 cursor-pointer"
                disabled={isUploadingTemplate}
              />
              <Button variant="outline" disabled={isUploadingTemplate}>
                <Upload className="w-4 h-4 mr-2" />
                {isUploadingTemplate ? "Lade hoch..." : "Template hochladen"}
              </Button>
            </div>
          </div>
          
          <div className="text-xs text-muted-foreground bg-muted/50 rounded p-3 mt-3">
            <strong>Eigenes Widget erstellen (ohne Programmierung!):</strong>
            <ol className="list-decimal ml-4 mt-1 space-y-1">
              <li>Kopiere ein bestehendes Template (z.B. <code>simple-value.vse.json</code>)</li>
              <li>Ändere <code>id</code>, <code>name</code> und Variablen</li>
              <li>Setze <code>"render": "dynamic"</code> für automatisches Rendering</li>
              <li>Lade das Template hier hoch - fertig!</li>
            </ol>
          </div>
        </div>
      </div>

      {/* Logic Backup */}
      <div className="rounded-lg bg-card border border-border p-5">
        <h2 className="font-medium mb-4 flex items-center gap-2">
          <Settings className="w-4 h-4" /> Logik-Bausteine Backup
        </h2>
        
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Exportiere oder importiere deine Logik-Bausteine und Verbindungen.
          </p>
          
          <div className="flex gap-3">
            <Button variant="secondary" onClick={() => {
              window.open(`${getApiBase()}/logic/export`, "_blank");
              toast.success("Export gestartet");
            }}>
              <Download className="w-4 h-4 mr-2" />
              Export
            </Button>
            
            <div className="relative">
              <input
                type="file"
                accept=".json"
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  
                  const formData = new FormData();
                  formData.append("file", file);
                  
                  try {
                    const res = await fetch(`${getApiBase()}/logic/import`, {
                      method: "POST",
                      body: formData,
                    });
                    if (res.ok) {
                      const data = await res.json();
                      toast.success(`Import erfolgreich: ${data.blocks || 0} Blöcke`);
                      setTimeout(() => window.location.reload(), 1000);
                    } else {
                      toast.error("Import fehlgeschlagen");
                    }
                  } catch {
                    toast.error("Import fehlgeschlagen");
                  }
                  e.target.value = "";
                }}
                className="absolute inset-0 opacity-0 cursor-pointer"
              />
              <Button variant="outline">
                <Upload className="w-4 h-4 mr-2" />
                Import
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* iPhone/Mobile Panel */}
      <div className="rounded-lg bg-card border border-border p-5">
        <h2 className="font-medium mb-4 flex items-center gap-2">
          <Smartphone className="w-4 h-4" /> Mobile Panel (iPhone/Android)
        </h2>
        
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Öffne das Panel auf deinem Smartphone als Vollbild-App.
          </p>
          
          <div className="bg-muted/50 rounded p-3 space-y-2">
            <Label className="text-xs text-muted-foreground">Panel URL:</Label>
            <div className="flex gap-2">
              <Input 
                value={panelUrl} 
                readOnly 
                className="font-mono text-xs"
              />
              <Button 
                variant="outline" 
                size="sm"
                onClick={() => {
                  navigator.clipboard.writeText(panelUrl);
                  toast.success("URL kopiert!");
                }}
              >
                Kopieren
              </Button>
            </div>
          </div>
          
          <div className="text-xs text-muted-foreground bg-muted/50 rounded p-3">
            <strong>📱 Zum Home-Bildschirm hinzufügen:</strong>
            <div className="mt-2 space-y-2">
              <div><strong>iPhone Safari:</strong> Teilen-Button → "Zum Home-Bildschirm"</div>
              <div><strong>Android Chrome:</strong> Menü (⋮) → "Zum Startbildschirm hinzufügen"</div>
            </div>
          </div>
          
          <Button 
            variant="outline" 
            onClick={() => setShowQR(!showQR)}
            className="w-full"
          >
            <QrCode className="w-4 h-4 mr-2" />
            {showQR ? "QR-Code ausblenden" : "QR-Code anzeigen"}
          </Button>
          
          {showQR && (
            <div className="flex justify-center p-4 bg-white rounded-lg">
              <img 
                src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(panelUrl)}`}
                alt="QR Code für Panel"
                className="w-48 h-48"
              />
            </div>
          )}
        </div>
      </div>

      {/* Connection Status */}
      <div className="rounded-lg bg-card border border-border p-5">
        <h2 className="font-medium mb-4">Verbindungsstatus</h2>
        
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <div className="text-xs text-muted-foreground mb-1">Status</div>
            <div className={status?.knx_connected ? "text-knx-online" : "text-knx-offline"}>
              {status?.knx_connected ? "● Verbunden" : "○ Getrennt"}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground mb-1">Gateway IP</div>
            <div className="font-mono">{status?.gateway_ip || "–"}</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground mb-1">Verbindungstyp</div>
            <div className="font-mono">{status?.connection_type || "–"}</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground mb-1">Adressen</div>
            <div className="font-mono">{status?.group_address_count ?? 0}</div>
          </div>
        </div>

        <Button variant="outline" className="mt-4" onClick={() => refetch()}>
          <RefreshCw className="w-4 h-4 mr-2" />
          Status aktualisieren
        </Button>
      </div>

      {/* System Actions */}
      <div className="rounded-lg bg-card border border-border p-5">
        <h2 className="font-medium mb-4 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-knx-warning" /> System
        </h2>
        
        <div className="space-y-3">
          <Button
            onClick={handleRestart}
            disabled={isRestarting}
            variant="destructive"
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
          <p className="text-xs text-muted-foreground">
            Startet den KNX-Server und alle Dienste neu
          </p>
        </div>
      </div>

      {/* Version Info */}
      <div className="text-center text-xs text-muted-foreground space-y-1">
        <p>KNX Dashboard v3.0.15</p>
        <p>Backend: {status?.version || "–"}</p>
      </div>
    </div>
  );
}
