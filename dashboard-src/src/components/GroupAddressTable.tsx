import React, { useState, useMemo } from "react";
import { Search, Plus, Trash2, Power, Pencil, ChevronDown, ChevronRight, Zap } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useGroupAddresses, useSendKnxCommand, useDeleteGroupAddress } from "@/hooks/useKnx";
import { useLogicBlocks } from "@/hooks/useLogic";
import { GroupAddress } from "@/types/knx";
import { toast } from "sonner";
import AddAddressDialog from "./AddAddressDialog";
import EditAddressDialog from "./EditAddressDialog";
import GenerateIKODialog from "./GenerateIKODialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuCheckboxItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

function isOn(value?: string): boolean {
  if (!value) return false;
  const v = value.toLowerCase();
  return v === "1" || v === "true" || v === "on" || parseFloat(v) > 0;
}

function AddressRow({
  addr,
  filter,
  selected,
  onToggleSelect,
  onEdit,
  onToggle,
  sendPending,
}: {
  addr: GroupAddress;
  filter: string;
  selected: boolean;
  onToggleSelect: () => void;
  onEdit: () => void;
  onToggle: () => void;
  sendPending: boolean;
}) {
  return (
    <tr className="border-b border-border/50 hover:bg-secondary/50 transition-colors">
      <td className="p-3">
        <input type="checkbox" className="rounded" checked={selected} onChange={onToggleSelect} />
      </td>
      <td className="p-3 font-mono text-knx-info">{addr.address}</td>
      <td className="p-3 text-card-foreground">{addr.name || "–"}</td>
      <td className="p-3 text-muted-foreground font-mono text-xs">{addr.dpt || "–"}</td>
      <td className="p-3">
        <span
          className={`font-mono text-xs px-2 py-0.5 rounded ${
            isOn(addr.value) ? "bg-knx-online/15 text-knx-online" : "bg-secondary text-muted-foreground"
          }`}
        >
          {addr.value ?? "–"}
        </span>
      </td>
      <td className="p-3">
        {addr.is_internal ? (
          <span className="text-xs px-2 py-0.5 rounded bg-knx-purple/15 text-knx-purple">IKO</span>
        ) : (
          <span className="text-xs px-2 py-0.5 rounded bg-knx-info/15 text-knx-info">KNX</span>
        )}
      </td>
      <td className="p-3 text-center">
        <div className="flex items-center justify-center gap-1">
          <Button variant="ghost" size="sm" onClick={onEdit} className="text-muted-foreground hover:text-foreground" title="Bearbeiten">
            <Pencil className="w-3.5 h-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggle}
            disabled={sendPending}
            className={`transition-colors ${isOn(addr.value) ? "text-knx-online hover:text-knx-offline" : "text-muted-foreground hover:text-knx-online"}`}
            title="Schalten"
          >
            <Power className="w-4 h-4" />
          </Button>
        </div>
      </td>
    </tr>
  );
}

export default function GroupAddressTable() {
  const { data: addresses, isLoading, isError } = useGroupAddresses();
  const sendCmd = useSendKnxCommand();
  const deleteAddr = useDeleteGroupAddress();
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<"all" | "knx" | "internal">("all");
  const [selectedGroups, setSelectedGroups] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());
  const [showAdd, setShowAdd] = useState(false);
  const [showGenerate, setShowGenerate] = useState(false);
  const [editAddr, setEditAddr] = useState<GroupAddress | null>(null);

  const { data: logicBlocks = [] } = useLogicBlocks();

  // Derive IKO groups from address pattern IKO:instanceId:port
  const ikoGroups = useMemo(() => {
    if (!addresses) return [];
    const groups = new Set<string>();
    addresses.forEach((a) => {
      if (a.is_internal) {
        // Try API group field first
        if (a.group) {
          groups.add(a.group);
        } else {
          // Derive from IKO address pattern: IKO:instanceId:port
          const match = a.address.match(/^IKO:([^:]+):/);
          if (match) {
            const instanceId = match[1];
            const block = logicBlocks.find((b) => b.instance_id === instanceId);
            const groupName = block ? `${block.name} #${block.block_id}` : instanceId;
            groups.add(groupName);
          }
        }
      }
    });
    return Array.from(groups).sort();
  }, [addresses, logicBlocks]);

  // Helper: derive group name for an IKO address
  const getIkoGroupName = (a: GroupAddress): string | null => {
    if (a.group) return a.group;
    const match = a.address.match(/^IKO:([^:]+):/);
    if (match) {
      const instanceId = match[1];
      const block = logicBlocks.find((b) => b.instance_id === instanceId);
      return block ? `${block.name} #${block.block_id}` : instanceId;
    }
    return null;
  };

  const filtered = useMemo(() => {
    if (!addresses) return [];
    let list = addresses;
    if (filter === "knx") list = list.filter((a) => !a.is_internal);
    else if (filter === "internal") {
      list = list.filter((a) => a.is_internal);
      if (selectedGroups.size > 0) {
        list = list.filter((a) => {
          const groupName = getIkoGroupName(a);
          return groupName && selectedGroups.has(groupName);
        });
      }
    }
    if (!search) return list;
    const q = search.toLowerCase();
    return list.filter(
      (a) =>
        a.address.includes(q) ||
        a.name?.toLowerCase().includes(q) ||
        a.description?.toLowerCase().includes(q) ||
        (getIkoGroupName(a) || "").toLowerCase().includes(q)
    );
  }, [addresses, search, filter, selectedGroups, logicBlocks]);


  const groupedIKOs = useMemo(() => {
    if (filter !== "internal") return null;
    const map: Record<string, GroupAddress[]> = {};
    const ungrouped: GroupAddress[] = [];
    filtered.forEach((a) => {
      const groupName = getIkoGroupName(a);
      if (groupName) {
        if (!map[groupName]) map[groupName] = [];
        map[groupName].push(a);
      } else {
        ungrouped.push(a);
      }
    });
    return { groups: map, ungrouped };
  }, [filtered, filter, logicBlocks]);

  const toggleSwitch = (addr: GroupAddress) => {
    const currentlyOn = isOn(addr.value);
    const newValue = currentlyOn ? 0 : 1;
    sendCmd.mutate(
      { address: addr.address, value: newValue },
      {
        onSuccess: () => toast.success(`${addr.name || addr.address}: ${newValue ? "AN" : "AUS"}`),
        onError: (err) => toast.error(`Fehler: ${err.message}`),
      }
    );
  };

  const toggleSelect = (address: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(address)) next.delete(address);
      else next.add(address);
      return next;
    });
  };

  const deleteSelected = () => {
    selected.forEach((addr) => {
      deleteAddr.mutate(addr, {
        onSuccess: () => toast.success(`${addr} gelöscht`),
        onError: (err) => toast.error(`Fehler: ${err.message}`),
      });
    });
    setSelected(new Set());
  };

  const toggleGroupFilter = (group: string) => {
    setSelectedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(group)) next.delete(group);
      else next.add(group);
      return next;
    });
  };

  const toggleGroupCollapse = (group: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(group)) next.delete(group);
      else next.add(group);
      return next;
    });
  };

  const colSpan = 7;

  const renderTableHead = () => (
    <thead>
      <tr className="text-muted-foreground text-xs uppercase border-b border-border">
        <th className="p-3 text-left w-10">
          <input
            type="checkbox"
            className="rounded"
            checked={selected.size === filtered.length && filtered.length > 0}
            onChange={() => {
              if (selected.size === filtered.length) setSelected(new Set());
              else setSelected(new Set(filtered.map((a) => a.address)));
            }}
          />
        </th>
        <th className="p-3 text-left">Adresse</th>
        <th className="p-3 text-left">Name</th>
        <th className="p-3 text-left">DPT</th>
        <th className="p-3 text-left">Wert</th>
        <th className="p-3 text-left">Typ</th>
        <th className="p-3 text-center">Aktionen</th>
      </tr>
    </thead>
  );

  const renderRows = (rows: GroupAddress[]) =>
    rows.map((addr) => (
      <AddressRow
        key={addr.address}
        addr={addr}
        filter={filter}
        selected={selected.has(addr.address)}
        onToggleSelect={() => toggleSelect(addr.address)}
        onEdit={() => setEditAddr(addr)}
        onToggle={() => toggleSwitch(addr)}
        sendPending={sendCmd.isPending}
      />
    ));

  const renderGroupedBody = () => {
    if (!groupedIKOs) return null;
    const { groups, ungrouped } = groupedIKOs;
    const sortedGroups = Object.keys(groups).sort();

    return (
      <tbody>
        {sortedGroups.map((groupName) => {
          const isCollapsed = collapsedGroups.has(groupName);
          const groupAddrs = groups[groupName];
          return (
            <React.Fragment key={groupName}>
              <tr
                className="bg-accent/5 border-b border-border cursor-pointer hover:bg-accent/10 transition-colors"
                onClick={() => toggleGroupCollapse(groupName)}
              >
                <td colSpan={colSpan} className="p-2">
                  <div className="flex items-center gap-2">
                    <ChevronRight
                      className={`w-4 h-4 text-accent transition-transform ${!isCollapsed ? "rotate-90" : ""}`}
                    />
                    <span className="text-xs font-semibold text-accent">{groupName}</span>
                    <span className="text-[10px] text-muted-foreground font-mono">{groupAddrs.length} Adresse(n)</span>
                  </div>
                </td>
              </tr>
              {!isCollapsed && renderRows(groupAddrs)}
            </React.Fragment>
          );
        })}
        {ungrouped.length > 0 && (
          <>
            {sortedGroups.length > 0 && (
              <tr className="bg-secondary/30 border-b border-border">
                <td colSpan={colSpan} className="p-2">
                  <span className="text-xs font-semibold text-muted-foreground">Ohne Gruppe</span>
                </td>
              </tr>
            )}
            {renderRows(ungrouped)}
          </>
        )}
      </tbody>
    );
  };

  const renderFlatBody = () => (
    <tbody>
      {isLoading && (
        <tr>
          <td colSpan={colSpan} className="p-8 text-center text-muted-foreground">Lade Adressen...</td>
        </tr>
      )}
      {isError && (
        <tr>
          <td colSpan={colSpan} className="p-8 text-center text-knx-offline">Verbindung zum KNX-Server fehlgeschlagen</td>
        </tr>
      )}
      {!isLoading && filtered.length === 0 && !isError && (
        <tr>
          <td colSpan={colSpan} className="p-8 text-center text-muted-foreground">Keine Adressen gefunden</td>
        </tr>
      )}
      {renderRows(filtered)}
    </tbody>
  );

  return (
    <div className="rounded-lg bg-card border border-border animate-fade-in">
      <div className="flex items-center justify-between p-4 border-b border-border flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <h2 className="font-semibold text-card-foreground">KNX Gruppenadressen</h2>
          <div className="flex items-center rounded-md border border-border overflow-hidden text-xs">
            {([["all", "Alle"], ["knx", "KNX"], ["internal", "IKO"]] as const).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setFilter(key)}
                className={`px-3 py-1 transition-colors ${
                  filter === key
                    ? "bg-primary text-primary-foreground"
                    : "bg-secondary text-muted-foreground hover:text-foreground"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          {/* IKO Group Filter - always visible in internal mode */}
          {filter === "internal" && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" className="h-7 text-xs gap-1">
                  <ChevronDown className="w-3 h-3" />
                  {selectedGroups.size > 0 ? `${selectedGroups.size} Gruppe(n)` : "Alle Gruppen"}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="max-h-60 overflow-y-auto bg-popover border-border z-50">
                {ikoGroups.length === 0 ? (
                  <div className="px-3 py-2 text-xs text-muted-foreground">
                    Keine Gruppen vorhanden – generiere IKOs aus Bausteinen
                  </div>
                ) : (
                  <>
                    {ikoGroups.map((group) => (
                      <DropdownMenuCheckboxItem
                        key={group}
                        checked={selectedGroups.has(group)}
                        onCheckedChange={() => toggleGroupFilter(group)}
                      >
                        {group}
                      </DropdownMenuCheckboxItem>
                    ))}
                    {selectedGroups.size > 0 && (
                      <DropdownMenuCheckboxItem
                        checked={false}
                        onCheckedChange={() => setSelectedGroups(new Set())}
                        className="text-muted-foreground border-t border-border mt-1 pt-1"
                      >
                        Alle anzeigen
                      </DropdownMenuCheckboxItem>
                    )}
                  </>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Suchen..."
              className="pl-9 w-48 bg-secondary border-border"
            />
          </div>
          {selected.size > 0 && (
            <Button variant="destructive" size="sm" onClick={deleteSelected}>
              <Trash2 className="w-4 h-4 mr-1" /> {selected.size} löschen
            </Button>
          )}
          <Button
            size="sm"
            variant="outline"
            onClick={() => setShowGenerate(true)}
            className="gap-1 text-accent border-accent/30 hover:bg-accent/10"
          >
            <Zap className="w-4 h-4" /> IKOs generieren
          </Button>
          <Button size="sm" onClick={() => setShowAdd(true)} className="bg-primary text-primary-foreground hover:bg-primary/90">
            <Plus className="w-4 h-4 mr-1" /> Hinzufügen
          </Button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          {renderTableHead()}
          {filter === "internal" && groupedIKOs && (groupedIKOs.groups && Object.keys(groupedIKOs.groups).length > 0)
            ? renderGroupedBody()
            : renderFlatBody()
          }
        </table>
      </div>

      <AddAddressDialog open={showAdd} onOpenChange={setShowAdd} />
      <EditAddressDialog address={editAddr} open={!!editAddr} onOpenChange={(open) => !open && setEditAddr(null)} />
      <GenerateIKODialog open={showGenerate} onOpenChange={setShowGenerate} />
    </div>
  );
}
