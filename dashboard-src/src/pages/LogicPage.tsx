import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  useReactFlow,
  ReactFlowProvider,
  type Connection,
  type Edge,
  type Node,
  BackgroundVariant,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Cpu, Plus, Trash2, FileText, Package, ChevronRight, Edit2, RefreshCw, Lock, Unlock, Search, Zap } from "lucide-react";
import { useLogicStore } from "@/stores/logicStore";
import LogicBlockNode from "@/components/logic/LogicBlockNode";
import KONode from "@/components/logic/KONode";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  useLogicBlocks,
  useLogicPages,
  useAvailableBlocks,
  useBlockPositions,
  useCreateBlock,
  useDeleteBlock,
  useBindBlock,
  useUnbindBlock,
  useSetBlockInput,
  useCreatePage,
  useDeletePage,
  useSavePositions,
} from "@/hooks/useLogic";
import { useGroupAddresses, useCreateGroupAddress } from "@/hooks/useKnx";
import type { BackendBlock } from "@/services/knxApi";

const nodeTypes = { logicBlock: LogicBlockNode, koNode: KONode };

function LogicPageInner() {
  const reactFlowInstance = useReactFlow();
  const { data: backendBlocks = [], isLoading: blocksLoading } = useLogicBlocks();
  const { data: backendPages = [] } = useLogicPages();
  const { data: availableBlocks = [] } = useAvailableBlocks();
  const { data: savedPositions = {} } = useBlockPositions();
  const { data: allAddresses = [] } = useGroupAddresses();
  const createAddressMut = useCreateGroupAddress();

  const createBlockMut = useCreateBlock();
  const deleteBlockMut = useDeleteBlock();
  const bindBlockMut = useBindBlock();
  const unbindBlockMut = useUnbindBlock();
  const setInputMut = useSetBlockInput();
  const createPageMut = useCreatePage();
  const deletePageMut = useDeletePage();
  const savePositionsMut = useSavePositions();

  const [activePageId, setActivePageId] = useState<string>("default");
  const [showLibrary, setShowLibrary] = useState(false);
  const [locked, setLocked] = useState(false);
  const [renamingPageId, setRenamingPageId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const viewportsRef = useRef<Record<string, { x: number; y: number; zoom: number }>>({});
  const initialFitDoneRef = useRef<Set<string>>(new Set());
  // Stable position store: remembers node positions across page switches
  const nodePositionsRef = useRef<Record<string, { x: number; y: number }>>({});

  // Save viewport before switching pages, and snapshot all node positions
  const handlePageSwitch = useCallback((newPageId: string) => {
    try {
      const vp = reactFlowInstance.getViewport();
      viewportsRef.current[activePageId] = vp;
      // Snapshot current node positions from React Flow
      const rfNodes = reactFlowInstance.getNodes();
      rfNodes.forEach((n) => {
        nodePositionsRef.current[n.id] = { x: n.position.x, y: n.position.y };
      });
    } catch {}
    setActivePageId(newPageId);
  }, [activePageId, reactFlowInstance]);

  // Restore viewport after page switch
  useEffect(() => {
    const stored = viewportsRef.current[activePageId];
    if (stored) {
      setTimeout(() => reactFlowInstance.setViewport(stored, { duration: 0 }), 50);
    } else if (!initialFitDoneRef.current.has(activePageId)) {
      initialFitDoneRef.current.add(activePageId);
      setTimeout(() => reactFlowInstance.fitView({ duration: 200 }), 150);
    }
  }, [activePageId, reactFlowInstance]);

  // Set active page to first available
  useEffect(() => {
    if (backendPages.length > 0 && !backendPages.find((p) => p.page_id === activePageId)) {
      handlePageSwitch(backendPages[0].page_id);
    }
  }, [backendPages, activePageId]);

  // Filter blocks for active page
  const pageBlocks = useMemo(
    () => backendBlocks.filter((b) => (b.page_id || "default") === activePageId),
    [backendBlocks, activePageId]
  );

  // KO dialog state
  const [koDialog, setKoDialog] = useState<{
    open: boolean;
    instanceId: string;
    portKey: string;
    portType: "input" | "output";
  } | null>(null);
  const [koAddress, setKoAddress] = useState("");
  const [koSearch, setKoSearch] = useState("");
  // Port popup state
  const [portPopup, setPortPopup] = useState<{
    instanceId: string;
    portKey: string;
    portType: "input" | "output";
  } | null>(null);
  const [portValue, setPortValue] = useState("");

  const openPortPopup = useCallback(
    (nodeId: string, portKey: string, portType: "input" | "output") => {
      const block = backendBlocks.find((b) => b.instance_id === nodeId);
      const currentVal = portType === "input"
        ? block?.input_values[portKey] ?? ""
        : block?.output_values[portKey] ?? "";
      setPortValue(String(currentVal));
      setPortPopup({ instanceId: nodeId, portKey, portType });
    },
    [backendBlocks]
  );

  const handlePortValueSave = () => {
    if (!portPopup) return;
    if (portPopup.portType === "input") {
      setInputMut.mutate(
        { instanceId: portPopup.instanceId, inputKey: portPopup.portKey, value: portValue },
        { onSuccess: () => toast.success(`Wert gesetzt: ${portValue}`) }
      );
    }
    setPortPopup(null);
  };

  const handlePortConnectKO = () => {
    if (!portPopup) return;
    setKoDialog({
      open: true,
      instanceId: portPopup.instanceId,
      portKey: portPopup.portKey,
      portType: portPopup.portType,
    });
    setKoSearch("");
    setKoAddress("");
    setPortPopup(null);
  };

  const handleCreateIKO = () => {
    if (!portPopup) return;
    const block = backendBlocks.find((b) => b.instance_id === portPopup.instanceId);
    if (!block) return;
    const blockName = block.name || block.block_type;
    const groupName = `${blockName} #${block.block_id}`;
    const portDir = portPopup.portType === "input" ? "E" : "A";
    const address = `IKO:${block.instance_id}:${portPopup.portKey}`;
    const portCfg = portPopup.portType === "input"
      ? block.inputs[portPopup.portKey]
      : block.outputs[portPopup.portKey];
    const portName = portCfg?.config?.name || portPopup.portKey;

    createAddressMut.mutate(
      {
        address,
        name: `${blockName} ${portDir}:${portName}`,
        description: `Auto-generiert für ${blockName} ${portPopup.portType} ${portPopup.portKey}`,
        is_internal: true,
        group: groupName,
      },
      {
        onSuccess: () => {
          // Auto-bind to the port
          const data = portPopup.portType === "input"
            ? { input_key: portPopup.portKey, address }
            : { output_key: portPopup.portKey, address };
          bindBlockMut.mutate(
            { instanceId: portPopup.instanceId, data },
            { onSuccess: () => toast.success(`IKO ${address} erstellt und gebunden`) }
          );
          setPortPopup(null);
        },
        onError: (err) => toast.error(`Fehler: ${err.message}`),
      }
    );
  };

  // Filtered addresses for KO selector
  const filteredAddresses = useMemo(() => {
    if (!koSearch) return allAddresses;
    const q = koSearch.toLowerCase();
    return allAddresses.filter(
      (a) =>
        a.address.toLowerCase().includes(q) ||
        a.name?.toLowerCase().includes(q) ||
        a.group?.toLowerCase().includes(q)
    );
  }, [allAddresses, koSearch]);

  const handleBindKO = () => {
    if (!koDialog || !koAddress.trim()) return;
    const data = koDialog.portType === "input"
      ? { input_key: koDialog.portKey, address: koAddress.trim() }
      : { output_key: koDialog.portKey, address: koAddress.trim() };
    bindBlockMut.mutate(
      { instanceId: koDialog.instanceId, data },
      {
        onSuccess: () => {
          toast.success(`KO ${koAddress} an ${koDialog.portKey} gebunden`);
          setKoDialog(null);
          setKoAddress("");
        },
      }
    );
  };

  // Build React Flow nodes from backend data
  const flowNodes: Node[] = useMemo(() => {
    return pageBlocks.map((block, idx) => {
      const pos = nodePositionsRef.current[block.instance_id] 
        || savedPositions[block.instance_id] 
        || { x: 100 + (idx % 3) * 320, y: 80 + Math.floor(idx / 3) * 250 };
      const inputs = Object.entries(block.inputs).map(([key, cfg]) => ({
        key,
        name: cfg.config?.name || key,
        type: cfg.config?.type || "str",
        default: cfg.config?.default,
      }));
      const outputs = Object.entries(block.outputs).map(([key, cfg]) => ({
        key,
        name: cfg.config?.name || key,
        type: cfg.config?.type || "str",
        default: cfg.config?.default,
      }));
      // Cross-reference with available blocks for category/version
      const avail = availableBlocks.find((a) => a.type === block.block_type);
      return {
        id: block.instance_id,
        type: "logicBlock",
        position: pos,
        data: {
          label: block.name || block.block_type,
          category: avail?.category || block.block_type,
          instanceId: block.instance_id,
          blockId: String(block.block_id),
          version: (avail as any)?.version || "",
          inputs,
          outputs,
          inputValues: block.input_values,
          outputValues: block.output_values,
          inputBindings: block.input_bindings,
          outputBindings: block.output_bindings,
          onConnectKO: (_nodeId: string, portKey: string, portType: "input" | "output") => {
            openPortPopup(block.instance_id, portKey, portType);
          },
        },
      };
    });
  }, [pageBlocks, savedPositions, openPortPopup, availableBlocks]);

  // Build edges from bindings (blocks connected via same address)
  const flowEdges: Edge[] = useMemo(() => {
    const edges: Edge[] = [];
    // Find connections: if block A output binds to address X, and block B input binds to address X
    const outputMap = new Map<string, { instanceId: string; portKey: string }>();
    pageBlocks.forEach((block) => {
      Object.entries(block.output_bindings || {}).forEach(([key, addr]) => {
        if (addr) outputMap.set(addr, { instanceId: block.instance_id, portKey: key });
      });
    });
    pageBlocks.forEach((block) => {
      Object.entries(block.input_bindings || {}).forEach(([key, addr]) => {
        if (addr && outputMap.has(addr)) {
          const src = outputMap.get(addr)!;
          edges.push({
            id: `${src.instanceId}-${src.portKey}-${block.instance_id}-${key}`,
            source: src.instanceId,
            sourceHandle: `out-${src.portKey}`,
            target: block.instance_id,
            targetHandle: `in-${key}`,
            animated: true,
            style: { stroke: "hsl(142, 60%, 45%)", strokeWidth: 2 },
          });
        }
      });
    });
    return edges;
  }, [pageBlocks]);

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const prevPageIdRef = useRef(activePageId);

  // Wrap onNodesChange to track positions
  const handleNodesChange = useCallback(
    (changes: any) => {
      onNodesChange(changes);
      // Save position changes to ref
      changes.forEach((c: any) => {
        if (c.type === "position" && c.position) {
          nodePositionsRef.current[c.id] = { x: c.position.x, y: c.position.y };
        }
      });
    },
    [onNodesChange]
  );

  // Sync nodes when backend data or page changes
  useEffect(() => {
    const isPageSwitch = prevPageIdRef.current !== activePageId;
    prevPageIdRef.current = activePageId;

    if (isPageSwitch) {
      // Full replacement on page switch
      setNodes(flowNodes);
    } else {
      // Data-only update: preserve positions from React Flow state
      setNodes((currentNodes) => {
        const currentPosMap = new Map(currentNodes.map((n) => [n.id, n.position]));
        const currentIds = new Set(currentNodes.map((n) => n.id));
        const newIds = new Set(flowNodes.map((n) => n.id));

        // Keep existing positions, add new nodes, remove deleted
        return flowNodes.map((fn) => ({
          ...fn,
          position: currentPosMap.get(fn.id) || fn.position,
        }));
      });
    }
  }, [flowNodes, setNodes, activePageId]);

  useEffect(() => {
    setEdges(flowEdges);
  }, [flowEdges, setEdges]);

  const onConnect = useCallback(
    (params: Connection) => {
      // When user draws a connection, bind via backend using BLOCK: address
      if (params.source && params.target && params.sourceHandle && params.targetHandle) {
        const outputKey = params.sourceHandle.replace("out-", "");
        const inputKey = params.targetHandle.replace("in-", "");
        // Use BLOCK: address format for block-to-block connections
        bindBlockMut.mutate({
          instanceId: params.target,
          data: { input_key: inputKey, address: `BLOCK:${params.source}:${outputKey}` },
        });
        setEdges((eds) =>
          addEdge({ ...params, animated: true, style: { stroke: "hsl(142, 60%, 45%)", strokeWidth: 2 } }, eds)
        );
      }
    },
    [setEdges, bindBlockMut]
  );

  const onNodeDragStop = useCallback(
    (_: any, node: Node) => {
      // Save position to ref and backend
      nodePositionsRef.current[node.id] = { x: node.position.x, y: node.position.y };
      const newPositions = { ...savedPositions, [node.id]: { x: node.position.x, y: node.position.y } };
      savePositionsMut.mutate(newPositions);
    },
    [savedPositions, savePositionsMut]
  );

  const onNodesDelete = useCallback(
    (deleted: Node[]) => {
      deleted.forEach((n) => {
        deleteBlockMut.mutate(n.id);
      });
    },
    [deleteBlockMut]
  );

  const onEdgesDelete = useCallback(
    (deleted: Edge[]) => {
      deleted.forEach((edge) => {
        if (edge.target && edge.targetHandle) {
          const inputKey = edge.targetHandle.replace("in-", "");
          unbindBlockMut.mutate(
            { instanceId: edge.target, data: { input_key: inputKey } },
            { onSuccess: () => toast.success(`Verbindung gelöst: ${inputKey}`) }
          );
        }
      });
    },
    [unbindBlockMut]
  );

  const addBlockInstance = useCallback(
    (blockType: string) => {
      createBlockMut.mutate(
        { blockType, pageId: activePageId },
        { onSuccess: (block) => toast.success(`"${block.name}" erstellt`) }
      );
    },
    [createBlockMut, activePageId]
  );

  // Pages management
  const addNewPage = () => {
    createPageMut.mutate(
      { name: `Seite ${backendPages.length + 1}` },
      {
        onSuccess: (page) => {
          handlePageSwitch(page.page_id);
          toast.success("Neue Logikseite erstellt");
        },
      }
    );
  };

  // Grouped available blocks for library
  const grouped = useMemo(() => {
    const map: Record<string, typeof availableBlocks> = {};
    availableBlocks.forEach((b) => {
      const cat = b.category || "Allgemein";
      if (!map[cat]) map[cat] = [];
      map[cat].push(b);
    });
    return map;
  }, [availableBlocks]);

  const currentBlock = koDialog
    ? backendBlocks.find((b) => b.instance_id === koDialog.instanceId)
    : null;

  return (
    <div className="h-[calc(100vh-3.5rem)] flex flex-col">
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-border bg-card shrink-0">
        <Cpu className="w-5 h-5 text-primary" />
        <h1 className="text-lg font-semibold text-foreground">Logik-Editor</h1>
        <span className="text-xs text-muted-foreground font-mono">
          {backendPages.find((p) => p.page_id === activePageId)?.name || activePageId}
        </span>
        {blocksLoading && <RefreshCw className="w-3.5 h-3.5 text-muted-foreground animate-spin" />}
        <div className="ml-auto flex items-center gap-1">
          <Button
            size="sm"
            variant={locked ? "default" : "outline"}
            className="h-7 text-xs gap-1"
            onClick={() => setLocked(!locked)}
            title={locked ? "Ansicht entsperren" : "Ansicht sperren"}
          >
            {locked ? <Lock className="w-3.5 h-3.5" /> : <Unlock className="w-3.5 h-3.5" />}
            {locked ? "Gesperrt" : "Sperren"}
          </Button>
          <Button
            size="sm"
            variant={showLibrary ? "default" : "outline"}
            className="h-7 text-xs gap-1"
            onClick={() => setShowLibrary(!showLibrary)}
          >
            <Package className="w-3.5 h-3.5" />
            Bibliothek
          </Button>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Left Panel: Logic Pages */}
        <div className="w-48 border-r border-border bg-card flex flex-col shrink-0">
          <div className="px-3 py-2 border-b border-border flex items-center justify-between">
            <span className="text-xs font-semibold text-foreground">Logikseiten</span>
            <Button size="sm" variant="ghost" className="h-6 w-6 p-0" onClick={addNewPage} title="Neue Seite">
              <Plus className="w-3.5 h-3.5" />
            </Button>
          </div>
          <ScrollArea className="flex-1">
            <div className="p-1">
              {backendPages.length === 0 && (
                <div
                  className={`flex items-center gap-1 px-2 py-1.5 mx-1 rounded cursor-pointer text-[11px] ${
                    activePageId === "default" ? "bg-primary/10 text-primary font-medium" : "hover:bg-secondary text-foreground"
                  }`}
                  onClick={() => handlePageSwitch("default")}
                >
                  <FileText className="w-3.5 h-3.5 shrink-0" />
                  <span className="truncate flex-1">Standard</span>
                </div>
              )}
              {backendPages.map((page) => (
                <div
                  key={page.page_id}
                  className={`flex items-center gap-1 px-2 py-1.5 mx-1 rounded cursor-pointer group text-[11px] ${
                    activePageId === page.page_id
                      ? "bg-primary/10 text-primary font-medium"
                      : "hover:bg-secondary text-foreground"
                  }`}
                  onClick={() => handlePageSwitch(page.page_id)}
                >
                  <FileText className="w-3.5 h-3.5 shrink-0" />
                  <span className="truncate flex-1">{page.name}</span>
                  <span className="text-[9px] text-muted-foreground font-mono">{page.block_count}</span>
                  <div className="opacity-0 group-hover:opacity-100 flex items-center gap-0.5">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        deletePageMut.mutate(page.page_id, {
                          onSuccess: () => {
                            if (activePageId === page.page_id) {
                              handlePageSwitch(backendPages.find((p) => p.page_id !== page.page_id)?.page_id || "default");
                            }
                            toast.success("Seite gelöscht");
                          },
                        });
                      }}
                    >
                      <Trash2 className="w-3 h-3 text-destructive" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>
        </div>

        {/* React Flow Canvas */}
        <div className="flex-1">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={locked ? undefined : handleNodesChange}
            onEdgesChange={locked ? undefined : onEdgesChange}
            onConnect={locked ? undefined : onConnect}
            onNodeDragStop={locked ? undefined : onNodeDragStop}
            onNodesDelete={locked ? undefined : onNodesDelete}
            onEdgesDelete={locked ? undefined : onEdgesDelete}
            nodeTypes={nodeTypes}
            nodesDraggable={!locked}
            nodesConnectable={!locked}
            elementsSelectable={!locked}
            panOnDrag={!locked}
            zoomOnScroll={!locked}
            zoomOnDoubleClick={!locked}
            zoomOnPinch={!locked}
            edgesReconnectable={!locked}
            className="bg-background"
            defaultEdgeOptions={{ animated: true, selectable: true, style: { stroke: "hsl(142, 60%, 45%)", strokeWidth: 2, cursor: "pointer" } }}
            edgesFocusable
          >
            <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="hsl(220, 14%, 20%)" />
            <Controls className="!bg-card !border-border !shadow-lg [&>button]:!bg-secondary [&>button]:!border-border [&>button]:!text-foreground [&>button:hover]:!bg-muted" />
            <MiniMap className="!bg-card !border-border" nodeColor="hsl(142, 60%, 45%)" maskColor="hsl(220, 20%, 10%, 0.8)" />
          </ReactFlow>
        </div>

        {/* Block Library Panel (toggleable) */}
        {showLibrary && (
          <div className="w-56 border-l border-border bg-card flex flex-col shrink-0">
            <div className="px-3 py-2 border-b border-border">
              <span className="text-xs font-semibold text-foreground">Verfügbare Bausteine</span>
            </div>
            <ScrollArea className="flex-1">
              <div className="p-1">
                {Object.keys(grouped).length === 0 && (
                  <p className="text-[10px] text-muted-foreground px-2 py-4 text-center">
                    Keine Bausteine verfügbar.
                  </p>
                )}
                {Object.entries(grouped).map(([category, catBlocks]) => (
                  <Collapsible key={category} defaultOpen>
                    <CollapsibleTrigger className="flex items-center gap-1 w-full px-2 py-1 text-[11px] font-semibold text-muted-foreground hover:text-foreground group">
                      <ChevronRight className="w-3 h-3 transition-transform group-data-[state=open]:rotate-90" />
                      {category}
                      <span className="ml-auto text-[10px] font-mono">{catBlocks.length}</span>
                    </CollapsibleTrigger>
                    <CollapsibleContent>
                      {catBlocks.map((block) => (
                        <div
                          key={block.type}
                          className="flex items-center gap-1 px-2 py-1 mx-1 rounded hover:bg-secondary"
                        >
                          <button
                            className="flex-1 text-left text-[10px] text-foreground truncate"
                            onClick={() => addBlockInstance(block.type)}
                            title={block.description}
                          >
                            <Plus className="w-3 h-3 inline mr-1 text-primary" />
                            {block.name}
                          </button>
                        </div>
                      ))}
                    </CollapsibleContent>
                  </Collapsible>
                ))}
              </div>
            </ScrollArea>
          </div>
        )}
      </div>

      {/* Port Popup - Wert, KO oder IKO erstellen */}
      <Dialog open={!!portPopup} onOpenChange={(open) => !open && setPortPopup(null)}>
        <DialogContent className="sm:max-w-xs max-h-[85vh] overflow-y-auto" onWheel={(e) => e.stopPropagation()}>
          <DialogHeader>
            <DialogTitle className="text-sm">
              {portPopup?.portType === "input" ? "Eingang" : "Ausgang"}: {portPopup?.portKey}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            {/* Full value display */}
            {(() => {
              const block = backendBlocks.find((b) => b.instance_id === portPopup?.instanceId);
              const fullValue = portPopup?.portType === "input"
                ? block?.input_values[portPopup.portKey]
                : block?.output_values[portPopup?.portKey ?? ""];
              const hasVal = fullValue !== undefined && fullValue !== null && fullValue !== "";
              return (
                <div className="rounded border border-border bg-secondary/50 px-3 py-2">
                  <Label className="text-[10px] text-muted-foreground">Aktueller Wert</Label>
                  <div className="text-sm font-mono text-foreground break-all mt-0.5 max-h-32 overflow-y-auto">
                    {hasVal ? String(fullValue) : <span className="text-muted-foreground italic">kein Wert</span>}
                  </div>
                  {portPopup?.portType === "output" && (
                    <p className="text-[10px] text-muted-foreground mt-1">Wird vom Backend berechnet</p>
                  )}
                </div>
              );
            })()}
            {portPopup?.portType === "input" && (
              <div>
                <Label className="text-xs">Wert setzen</Label>
                <div className="flex gap-2 mt-1">
                  <Input
                    className="h-8 text-xs font-mono"
                    value={portValue}
                    onChange={(e) => setPortValue(e.target.value)}
                    placeholder="Wert eingeben..."
                    onKeyDown={(e) => e.key === "Enter" && handlePortValueSave()}
                  />
                  <Button size="sm" className="h-8" onClick={handlePortValueSave}>OK</Button>
                </div>
              </div>
            )}
            <div className="border-t border-border pt-3 space-y-2">
              <Button variant="outline" className="w-full text-xs gap-2" onClick={handlePortConnectKO}>
                <Package className="w-3.5 h-3.5" />
                KO verbinden (Gruppenadresse)
              </Button>
              <Button
                variant="outline"
                className="w-full text-xs gap-2 text-accent border-accent/30 hover:bg-accent/10"
                onClick={handleCreateIKO}
                disabled={createAddressMut.isPending}
              >
                <Zap className="w-3.5 h-3.5" />
                {createAddressMut.isPending ? "Erstelle IKO..." : "IKO erstellen & binden"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* KO Bind Dialog mit Suchfeld + Liste */}
      <Dialog open={!!koDialog?.open} onOpenChange={(open) => !open && setKoDialog(null)}>
        <DialogContent className="sm:max-w-md" onWheel={(e) => e.stopPropagation()}>
          <DialogHeader>
            <DialogTitle>
              KO verbinden – {koDialog?.portType === "input" ? "Eingang" : "Ausgang"} {koDialog?.portKey}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            {currentBlock && (
              <div className="text-[10px] text-muted-foreground">
                Aktuell: {koDialog?.portType === "input"
                  ? currentBlock.input_bindings[koDialog.portKey] || "nicht gebunden"
                  : currentBlock.output_bindings[koDialog?.portKey || ""] || "nicht gebunden"}
              </div>
            )}
            <div>
              <Label className="text-xs">Adresse eingeben oder auswählen</Label>
              <div className="relative mt-1">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
                <Input
                  value={koAddress || koSearch}
                  onChange={(e) => {
                    setKoAddress(e.target.value);
                    setKoSearch(e.target.value);
                  }}
                  placeholder="Suche oder Adresse eingeben..."
                  className="pl-8 h-8 text-xs"
                />
              </div>
            </div>
            {/* Address list */}
            <ScrollArea className="h-48 rounded border border-border">
              <div className="p-1">
                {filteredAddresses.length === 0 && (
                  <p className="text-[10px] text-muted-foreground text-center py-4">Keine Adressen gefunden</p>
                )}
                {filteredAddresses.map((addr) => (
                  <button
                    key={addr.address}
                    className={`w-full text-left px-2 py-1.5 rounded text-xs hover:bg-secondary transition-colors flex items-center gap-2 ${
                      koAddress === addr.address ? "bg-primary/10 text-primary" : "text-foreground"
                    }`}
                    onClick={() => {
                      setKoAddress(addr.address);
                      setKoSearch("");
                    }}
                  >
                    <span className="font-mono text-[10px] shrink-0 w-20">{addr.address}</span>
                    <span className="truncate flex-1">{addr.name || "–"}</span>
                    {addr.is_internal ? (
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-knx-purple/15 text-knx-purple shrink-0">IKO</span>
                    ) : (
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-knx-info/15 text-knx-info shrink-0">KNX</span>
                    )}
                    {addr.group && (
                      <span className="text-[9px] text-muted-foreground shrink-0">{addr.group}</span>
                    )}
                  </button>
                ))}
              </div>
            </ScrollArea>
            <Button onClick={handleBindKO} className="w-full" disabled={bindBlockMut.isPending || !koAddress.trim()}>
              {bindBlockMut.isPending ? "Wird gebunden..." : `KO verbinden: ${koAddress || "..."}`}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default function LogicPage() {
  return (
    <ReactFlowProvider>
      <LogicPageInner />
    </ReactFlowProvider>
  );
}
