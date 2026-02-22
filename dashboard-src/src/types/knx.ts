// KNX API types

export interface KNXStatus {
  knx_connected: boolean;
  gateway_ip: string;
  connection_type: string;
  group_address_count: number;
}

export interface GroupAddress {
  address: string;
  name: string;
  description?: string;
  dpt?: string;
  value?: string;
  is_internal?: boolean;
  group?: string;
  last_updated?: string;
}

export interface GroupAddressCreate {
  address: string;
  name: string;
  description?: string;
  dpt?: string;
  is_internal?: boolean;
  initial_value?: string;
  group?: string;
}

export interface KNXSendRequest {
  address: string;
  value: number | string | boolean;
}

export interface VisuPage {
  page_id: string;
  name: string;
  description?: string;
  widgets?: VisuWidget[];
}

export interface VisuWidget {
  id: string;
  type: string;
  label?: string;
  statusAddress?: string;
  sendAddress?: string;
  unit?: string;
  x?: number;
  y?: number;
  w?: number;
  h?: number;
}
