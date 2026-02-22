import { KNXStatus, GroupAddress, GroupAddressCreate, KNXSendRequest } from "@/types/knx";

// Configure this to point to your KNX gateway
const API_BASE = localStorage.getItem("knx_api_url") || "http://192.168.0.87:8000/api/v1";

export function getApiBase(): string {
  return localStorage.getItem("knx_api_url") || "http://192.168.0.87:8000/api/v1";
}

export function setApiBase(url: string): void {
  localStorage.setItem("knx_api_url", url);
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const base = getApiBase().replace(/\/+$/, "");
  const res = await fetch(`${base}${path}`, {
    headers: {
      "Content-Type": "application/json",
      "Accept": "application/json",
      "ngrok-skip-browser-warning": "true",
    },
    ...options,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail?.detail || `API Error ${res.status}`);
  }
  return res.json();
}

// Status
export const fetchStatus = () => apiFetch<KNXStatus>("/status");
export const fetchHealth = () => apiFetch<{ status: string }>("/health");

// Group Addresses
export const fetchGroupAddresses = async (internalOnly?: boolean): Promise<GroupAddress[]> => {
  const q = internalOnly !== undefined ? `?internal=${internalOnly}` : "";
  const raw = await apiFetch<any[]>(`/group-addresses${q}`);
  return raw.map((a) => ({
    ...a,
    value: a.last_value ?? a.value ?? undefined,
    group: a.group ?? undefined,
  }));
};

export const fetchGroupAddress = (address: string) =>
  apiFetch<GroupAddress>(`/group-addresses/${encodeURIComponent(address)}`);

export const createGroupAddress = (data: GroupAddressCreate) =>
  apiFetch<GroupAddress>("/group-addresses", {
    method: "POST",
    body: JSON.stringify(data),
  });

export const updateGroupAddress = (address: string, data: Partial<GroupAddressCreate>) =>
  apiFetch<GroupAddress>(`/group-addresses/${encodeURIComponent(address)}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });

export const deleteGroupAddress = (address: string) =>
  apiFetch<{ status: string }>(`/group-addresses/${encodeURIComponent(address)}`, {
    method: "DELETE",
  });

// KNX Send - WICHTIG: Query-Parameter, nicht JSON Body!
export const sendKnxCommand = async (data: KNXSendRequest) => {
  const base = getApiBase().replace(/\/+$/, "");
  const url = `${base}/knx/send?group_address=${encodeURIComponent(data.address)}&value=${encodeURIComponent(String(data.value))}`;
  
  const res = await fetch(url, { 
    method: "POST",
    headers: {
      "ngrok-skip-browser-warning": "true",
    },
  });
  
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail?.detail || `KNX Send Error ${res.status}`);
  }
  
  return res.json() as Promise<{ status: string; address: string; value: any }>;
};

// ============ Logic API ============

export interface BackendBlock {
  instance_id: string;
  block_type: string;
  block_id: number;
  name: string;
  page_id: string | null;
  inputs: Record<string, { config: { name: string; type: string; default?: any }; value: any; binding: string | null }>;
  outputs: Record<string, { config: { name: string; type: string; default?: any }; value: any; binding: string | null }>;
  input_values: Record<string, any>;
  output_values: Record<string, any>;
  input_bindings: Record<string, string>;
  output_bindings: Record<string, string>;
  enabled: boolean;
}

export interface BackendPageRaw {
  id: string;
  name: string;
  description: string;
  blocks: any[];
  created_at: string;
}

export interface BackendPage {
  page_id: string;
  name: string;
  description: string;
  block_count: number;
}

// Logic Pages
const mapPage = (raw: BackendPageRaw): BackendPage => ({
  page_id: raw.id,
  name: raw.name,
  description: raw.description,
  block_count: raw.blocks?.length ?? 0,
});

// Logic Blocks
export const fetchLogicBlocks = () => apiFetch<BackendBlock[]>("/logic/blocks");

export const fetchLogicBlock = (instanceId: string) =>
  apiFetch<BackendBlock>(`/logic/blocks/${instanceId}`);

export const fetchLogicBlockDebug = (instanceId: string) =>
  apiFetch<{
    instance_id: string;
    input_values: Record<string, any>;
    output_values: Record<string, any>;
    input_bindings: Record<string, string>;
    output_bindings: Record<string, string>;
    enabled: boolean;
  }>(`/logic/blocks/${instanceId}/debug`);

export const createLogicBlock = (blockType: string, pageId?: string) =>
  apiFetch<BackendBlock>("/logic/blocks", {
    method: "POST",
    body: JSON.stringify({ block_type: blockType, page_id: pageId || null }),
  });

export const deleteLogicBlock = (instanceId: string) =>
  apiFetch<{ status: string }>(`/logic/blocks/${instanceId}`, { method: "DELETE" });

export const bindLogicBlock = (instanceId: string, data: { input_key?: string; output_key?: string; address: string }) =>
  apiFetch<{ status: string; address: string }>(`/logic/blocks/${instanceId}/bind`, {
    method: "POST",
    body: JSON.stringify(data),
  });

export const unbindLogicBlock = (instanceId: string, data: { input_key?: string; output_key?: string }) =>
  apiFetch<{ status: string }>(`/logic/blocks/${instanceId}/unbind`, {
    method: "POST",
    body: JSON.stringify(data),
  });

export const setLogicBlockInput = (instanceId: string, inputKey: string, value: string) =>
  apiFetch<{ status: string }>(`/logic/blocks/${instanceId}/input/${inputKey}`, {
    method: "POST",
    body: JSON.stringify({ value }),
  });

export const triggerLogicBlock = (instanceId: string) =>
  apiFetch<{ status: string }>(`/logic/blocks/${instanceId}/trigger`, { method: "POST" });

// Logic Pages
export const fetchLogicPages = async (): Promise<BackendPage[]> => {
  const raw = await apiFetch<BackendPageRaw[]>("/logic/pages");
  return raw.map(mapPage);
};

export const createLogicPage = (name: string, pageId?: string) =>
  apiFetch<BackendPage>("/logic/pages", {
    method: "POST",
    body: JSON.stringify({ name, page_id: pageId || null }),
  });

export const deleteLogicPage = (pageId: string) =>
  apiFetch<{ status: string }>(`/logic/pages/${pageId}`, { method: "DELETE" });

// Available block types
export const fetchAvailableBlocks = () =>
  apiFetch<Array<{ type: string; name: string; category: string; description: string; inputs: Record<string, any>; outputs: Record<string, any> }>>("/logic/blocks/available");

// Block positions
export const fetchBlockPositions = () => apiFetch<Record<string, { x: number; y: number }>>("/logic/positions");

export const saveBlockPositions = (positions: Record<string, { x: number; y: number }>) =>
  apiFetch<{ status: string }>("/logic/positions", {
    method: "POST",
    body: JSON.stringify(positions),
  });

// Logic status
export const fetchLogicStatus = () =>
  apiFetch<{ blocks_count: number; pages_count: number; available_types: string[]; running: boolean }>("/logic/status");

// ============ Visu Rooms API ============

export interface VisuRoom {
  id: string;
  name: string;
  category: string;
  widgets: any[];
}

export const fetchVisuRooms = () => apiFetch<VisuRoom[]>("/visu/rooms");

export const saveVisuRooms = (rooms: VisuRoom[]) =>
  apiFetch<{ status: string; count: number }>("/visu/rooms", {
    method: "POST",
    body: JSON.stringify(rooms),
  });

export const exportVisuConfig = () => {
  const base = getApiBase().replace(/\/+$/, "");
  window.open(`${base}/visu/export`, "_blank");
};

export const importVisuConfig = async (file: File): Promise<{ status: string; rooms: number }> => {
  const base = getApiBase().replace(/\/+$/, "");
  const formData = new FormData();
  formData.append("file", file);
  
  const res = await fetch(`${base}/visu/import`, {
    method: "POST",
    headers: {
      "ngrok-skip-browser-warning": "true",
    },
    body: formData,
  });
  
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail?.detail || `Import Error ${res.status}`);
  }
  
  return res.json();
};

// ============ License API ============

export interface LicenseStatus {
  licensed: boolean;
  email?: string;
  expires?: string;
  days_left?: number;
  key_preview?: string;
  error?: string;
}

export interface LicenseActivation {
  status: string;
  email: string;
  expires: string;
  days_left: number;
}

export const fetchLicenseStatus = () => apiFetch<LicenseStatus>("/license/status");

export const activateLicense = async (key: string, email: string): Promise<LicenseActivation> => {
  const base = getApiBase().replace(/\/+$/, "");
  const url = `${base}/license/activate?key=${encodeURIComponent(key)}&email=${encodeURIComponent(email)}`;
  
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "ngrok-skip-browser-warning": "true",
    },
  });
  
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail?.detail || `Activation Error ${res.status}`);
  }
  
  return res.json();
};
