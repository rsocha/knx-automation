import { useState } from "react";
import { Server, Table, LayoutGrid, ScrollText, Cpu, Wifi, WifiOff, Settings, RefreshCw } from "lucide-react";
import { NavLink } from "@/components/NavLink";
import { useKnxStatus } from "@/hooks/useKnx";
import { getApiBase, setApiBase } from "@/services/knxApi";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarFooter,
  useSidebar,
} from "@/components/ui/sidebar";

const navItems = [
  { title: "Adressen", url: "/", icon: Table },
  { title: "Visualisierung", url: "/visu", icon: LayoutGrid },
  { title: "Logik", url: "/logic", icon: Cpu },
  { title: "Log", url: "/log", icon: ScrollText },
];

const systemItems = [
  { title: "Einstellungen", url: "/settings", icon: Settings },
  { title: "System-Update", url: "/update", icon: RefreshCw },
];

export default function AppSidebar() {
  const { data: status } = useKnxStatus();
  const { state } = useSidebar();
  const collapsed = state === "collapsed";
  const connected = status?.knx_connected ?? false;
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [apiUrl, setApiUrl] = useState(getApiBase());

  const saveUrl = () => {
    setApiBase(apiUrl);
    toast.success("URL gespeichert – Seite wird neu geladen...");
    setTimeout(() => window.location.reload(), 500);
  };

  return (
    <Sidebar collapsible="icon" className="border-r border-sidebar-border">
      <div className="h-14 flex items-center gap-2 px-4 border-b border-sidebar-border shrink-0">
        <Server className="w-5 h-5 text-primary shrink-0" />
        {!collapsed && (
          <div className="flex flex-col">
            <span className="font-semibold text-sidebar-foreground text-sm tracking-tight leading-tight">
              KNX Automation
            </span>
            <span className="text-[10px] text-muted-foreground font-mono">v3.0.26</span>
          </div>
        )}
      </div>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Navigation</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild tooltip={item.title}>
                    <NavLink to={item.url} end={item.url === "/"} className="hover:bg-sidebar-accent" activeClassName="bg-sidebar-accent text-sidebar-primary font-medium">
                      <item.icon className="w-4 h-4 shrink-0" />
                      <span>{item.title}</span>
                    </NavLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup>
          <SidebarGroupLabel>System</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {systemItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild tooltip={item.title}>
                    <NavLink to={item.url} className="hover:bg-sidebar-accent" activeClassName="bg-sidebar-accent text-sidebar-primary font-medium">
                      <item.icon className="w-4 h-4 shrink-0" />
                      <span>{item.title}</span>
                    </NavLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="border-t border-sidebar-border p-3">
        <div className="flex items-center gap-2">
          {connected ? (
            <>
              <div className="w-2 h-2 rounded-full bg-knx-online status-pulse shrink-0" />
              {!collapsed && (
                <>
                  <Wifi className="w-3.5 h-3.5 text-knx-online" />
                  <span className="text-knx-online font-mono text-[10px] truncate">{status?.gateway_ip}</span>
                </>
              )}
            </>
          ) : (
            <>
              <div className="w-2 h-2 rounded-full bg-knx-offline shrink-0" />
              {!collapsed && (
                <>
                  <WifiOff className="w-3.5 h-3.5 text-knx-offline" />
                  <span className="text-knx-offline text-[10px]">Offline</span>
                </>
              )}
            </>
          )}
        </div>
      </SidebarFooter>

      <Dialog open={settingsOpen} onOpenChange={setSettingsOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Backend-Verbindung</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label className="text-xs">API URL</Label>
              <Input
                value={apiUrl}
                onChange={(e) => setApiUrl(e.target.value)}
                placeholder="https://xxx.ngrok-free.dev/api/v1"
                className="mt-1 font-mono text-xs"
              />
            </div>
            <Button onClick={saveUrl} className="w-full">Speichern & Neu laden</Button>
          </div>
        </DialogContent>
      </Dialog>
    </Sidebar>
  );
}
