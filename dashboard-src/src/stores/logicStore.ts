import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface LogicBlockPort {
  key: string;
  name: string;
  type: string;
  default?: any;
}

export interface LogicBlockDef {
  id: string;
  blockId: number;
  name: string;
  description: string;
  version: string;
  author: string;
  category: string;
  inputs: LogicBlockPort[];
  outputs: LogicBlockPort[];
  sourceCode: string;
}

export interface LogicPage {
  id: string;
  name: string;
  description?: string;
}

export interface LogicNodeInstance {
  instanceId: string;
  blockId: string;
  pageId: string;
  x: number;
  y: number;
  inputValues: Record<string, any>;
  outputValues: Record<string, any>;
}

export interface KOInstance {
  instanceId: string;
  address: string;
  label: string;
  value: string;
  direction: "input" | "output";
  pageId: string;
  x: number;
  y: number;
}

export interface LogicConnection {
  id: string;
  sourceInstanceId: string;
  sourcePort: string;
  targetInstanceId: string;
  targetPort: string;
}

interface LogicStore {
  pages: LogicPage[];
  blocks: LogicBlockDef[];
  instances: LogicNodeInstance[];
  connections: LogicConnection[];
  koInstances: KOInstance[];
  addPage: (page: LogicPage) => void;
  removePage: (id: string) => void;
  renamePage: (id: string, name: string) => void;
  addBlock: (block: LogicBlockDef) => void;
  removeBlock: (id: string) => void;
  addInstance: (inst: LogicNodeInstance) => void;
  removeInstance: (id: string) => void;
  updateInstancePosition: (id: string, x: number, y: number) => void;
  setInputValue: (instanceId: string, port: string, value: any) => void;
  setOutputValue: (instanceId: string, port: string, value: any) => void;
  addConnection: (conn: LogicConnection) => void;
  removeConnection: (id: string) => void;
  addKO: (ko: KOInstance) => void;
  removeKO: (id: string) => void;
  updateKOValue: (instanceId: string, value: string) => void;
  updateKOPosition: (id: string, x: number, y: number) => void;
}

/** Parse a Python LogicBlock file to extract INPUTS/OUTPUTS/metadata */
export function parseLogicBlockPython(source: string): Omit<LogicBlockDef, "id"> | null {
  try {
    // Extract class metadata
    const nameMatch = source.match(/^\s*NAME\s*=\s*["'](.+?)["']/m);
    const descMatch = source.match(/^\s*DESCRIPTION\s*=\s*["'](.+?)["']/m);
    const versionMatch = source.match(/^\s*VERSION\s*=\s*["'](.+?)["']/m);
    const authorMatch = source.match(/^\s*AUTHOR\s*=\s*["'](.+?)["']/m);
    const categoryMatch = source.match(/^\s*CATEGORY\s*=\s*["'](.+?)["']/m);
    const idMatch = source.match(/^\s*ID\s*=\s*(\d+)/m);

    // Extract INPUTS dict
    const inputs = extractPorts(source, "INPUTS");
    const outputs = extractPorts(source, "OUTPUTS");

    if (inputs.length === 0 && outputs.length === 0) return null;

    return {
      blockId: idMatch ? parseInt(idMatch[1]) : Date.now(),
      name: nameMatch?.[1] || "Unbekannt",
      description: descMatch?.[1] || "",
      version: versionMatch?.[1] || "1.0",
      author: authorMatch?.[1] || "",
      category: categoryMatch?.[1] || "Allgemein",
      inputs,
      outputs,
      sourceCode: source,
    };
  } catch {
    return null;
  }
}

function extractPorts(source: string, section: string): LogicBlockPort[] {
  // Match INPUTS = { ... } or OUTPUTS = { ... }
  const regex = new RegExp(`${section}\\s*=\\s*\\{([\\s\\S]*?)^\\s*\\}`, "m");
  const match = source.match(regex);
  if (!match) return [];

  const ports: LogicBlockPort[] = [];
  // Match each 'E1': {'name': 'xxx', 'type': 'xxx', ...}
  const portRegex = /['"](\w+)['"]\s*:\s*\{([^}]+)\}/g;
  let m;
  while ((m = portRegex.exec(match[1])) !== null) {
    const key = m[1];
    const body = m[2];
    const nameM = body.match(/['"]name['"]\s*:\s*['"](.+?)['"]/);
    const typeM = body.match(/['"]type['"]\s*:\s*['"](.+?)['"]/);
    const defaultM = body.match(/['"]default['"]\s*:\s*(.+?)(?:,|\s*$)/);
    ports.push({
      key,
      name: nameM?.[1] || key,
      type: typeM?.[1] || "str",
      default: defaultM ? defaultM[1].trim().replace(/['"]/g, "") : undefined,
    });
  }
  return ports;
}

export const useLogicStore = create<LogicStore>()(
  persist(
    (set) => ({
      pages: [{ id: "default", name: "Hauptseite" }],
      blocks: [],
      instances: [],
      connections: [],
      koInstances: [],
      addPage: (page) => set((s) => ({ pages: [...s.pages, page] })),
      removePage: (id) =>
        set((s) => ({
          pages: s.pages.filter((p) => p.id !== id),
          instances: s.instances.filter((i) => i.pageId !== id),
          koInstances: s.koInstances.filter((k) => k.pageId !== id),
          connections: s.connections.filter((c) => {
            const pageInstIds = new Set([
              ...s.instances.filter((i) => i.pageId === id).map((i) => i.instanceId),
              ...s.koInstances.filter((k) => k.pageId === id).map((k) => k.instanceId),
            ]);
            return !pageInstIds.has(c.sourceInstanceId) && !pageInstIds.has(c.targetInstanceId);
          }),
        })),
      renamePage: (id, name) =>
        set((s) => ({ pages: s.pages.map((p) => (p.id === id ? { ...p, name } : p)) })),
      addBlock: (block) => set((s) => ({ blocks: [...s.blocks, block] })),
      removeBlock: (id) =>
        set((s) => ({
          blocks: s.blocks.filter((b) => b.id !== id),
          instances: s.instances.filter((i) => i.blockId !== id),
          connections: s.connections.filter(
            (c) =>
              !s.instances
                .filter((i) => i.blockId === id)
                .some((i) => i.instanceId === c.sourceInstanceId || i.instanceId === c.targetInstanceId)
          ),
        })),
      addInstance: (inst) => set((s) => ({ instances: [...s.instances, inst] })),
      removeInstance: (id) =>
        set((s) => ({
          instances: s.instances.filter((i) => i.instanceId !== id),
          connections: s.connections.filter((c) => c.sourceInstanceId !== id && c.targetInstanceId !== id),
        })),
      updateInstancePosition: (id, x, y) =>
        set((s) => ({
          instances: s.instances.map((i) => (i.instanceId === id ? { ...i, x, y } : i)),
        })),
      setInputValue: (instanceId, port, value) =>
        set((s) => ({
          instances: s.instances.map((i) =>
            i.instanceId === instanceId ? { ...i, inputValues: { ...i.inputValues, [port]: value } } : i
          ),
        })),
      setOutputValue: (instanceId, port, value) =>
        set((s) => ({
          instances: s.instances.map((i) =>
            i.instanceId === instanceId ? { ...i, outputValues: { ...i.outputValues, [port]: value } } : i
          ),
        })),
      addConnection: (conn) => set((s) => ({ connections: [...s.connections, conn] })),
      removeConnection: (id) => set((s) => ({ connections: s.connections.filter((c) => c.id !== id) })),
      addKO: (ko) => set((s) => ({ koInstances: [...s.koInstances, ko] })),
      removeKO: (id) =>
        set((s) => ({
          koInstances: s.koInstances.filter((k) => k.instanceId !== id),
          connections: s.connections.filter((c) => c.sourceInstanceId !== id && c.targetInstanceId !== id),
        })),
      updateKOValue: (instanceId, value) =>
        set((s) => ({
          koInstances: s.koInstances.map((k) => (k.instanceId === instanceId ? { ...k, value } : k)),
        })),
      updateKOPosition: (id, x, y) =>
        set((s) => ({
          koInstances: s.koInstances.map((k) => (k.instanceId === id ? { ...k, x, y } : k)),
        })),
    }),
    { name: "knx-logic-store" }
  )
);
