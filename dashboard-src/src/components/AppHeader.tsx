import { useState } from "react";
import { useLocation, Link } from "react-router-dom";
import { Settings, Server, Wifi, WifiOff, LayoutGrid, Table, ScrollText } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { getApiBase, setApiBase } from "@/services/knxApi";
import { useKnxStatus } from "@/hooks/useKnx";
import { toast } from "sonner";

export default function AppHeader() {
  const { data: status } = useKnxStatus();
  const location = useLocation();
  const [showSettings, setShowSettings] = useState(false);
  const [apiUrl, setApiUrl] = useState(getApiBase());

  const saveSettings = () => {
    setApiBase(apiUrl);
    toast.success("API URL gespeichert – Seite wird neu geladen");
    setTimeout(() => window.location.reload(), 500);
  };

  const connected = status?.knx_connected ?? false;

  return (
    <>
      <header className="h-14 border-b border-border bg-card flex items-center justify-between px-5">
        <div className="flex items-center gap-3">
          <Server className="w-5 h-5 text-primary" />
          <span className="font-semibold text-foreground tracking-tight">KNX Automation</span>
          <span className="text-xs text-muted-foreground font-mono mr-4">v2.5.7</span>
          <nav className="flex items-center gap-1">
            <Link
              to="/"
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                location.pathname === "/" ? "bg-secondary text-foreground" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Table className="w-3.5 h-3.5" /> Adressen
            </Link>
            <Link
              to="/visu"
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                location.pathname === "/visu" ? "bg-secondary text-foreground" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <LayoutGrid className="w-3.5 h-3.5" /> Visualisierung
            </Link>
            <Link
              to="/log"
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                location.pathname === "/log" ? "bg-secondary text-foreground" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <ScrollText className="w-3.5 h-3.5" /> Log
            </Link>
          </nav>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-sm">
            {connected ? (
              <>
                <div className="w-2 h-2 rounded-full bg-knx-online status-pulse" />
                <Wifi className="w-4 h-4 text-knx-online" />
                <span className="text-knx-online font-mono text-xs">{status?.gateway_ip}</span>
              </>
            ) : (
              <>
                <div className="w-2 h-2 rounded-full bg-knx-offline" />
                <WifiOff className="w-4 h-4 text-knx-offline" />
                <span className="text-knx-offline text-xs">Offline</span>
              </>
            )}
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowSettings(true)}
            className="text-muted-foreground hover:text-foreground"
          >
            <Settings className="w-4 h-4" />
          </Button>
        </div>
      </header>

      <Dialog open={showSettings} onOpenChange={setShowSettings}>
        <DialogContent className="bg-card border-border">
          <DialogHeader>
            <DialogTitle className="text-card-foreground">Einstellungen</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            <div>
              <Label className="text-muted-foreground text-xs">KNX API URL</Label>
              <Input
                value={apiUrl}
                onChange={(e) => setApiUrl(e.target.value)}
                placeholder="http://192.168.0.87:8000/api/v1"
                className="bg-secondary border-border mt-1 font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground mt-1">
                Die URL deines FastAPI KNX-Servers
              </p>
            </div>
            <Button onClick={saveSettings} className="w-full bg-primary text-primary-foreground">
              Speichern
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
