// VSE (Visual Scene Element) type definitions

export interface VseInput {
  name: string;
  type: string;
  description?: string;
}

export interface VseVariable {
  name: string;
  type: "text" | "number" | "bool" | "icon" | "color";
  default?: any;
  description?: string;
}

export interface VseTemplate {
  id: string;
  name: string;
  description?: string;
  category: string;
  author?: string;
  version?: string;
  width: number;
  height: number;
  render: string;
  inputs: Record<string, VseInput>;
  variables: Record<string, VseVariable>;
}

export interface VseWidgetInstance {
  id: string;
  templateId: string;
  label: string;
  roomId: string;
  // KO bindings: input key -> group address
  koBindings: Record<string, string>;
  // Variable overrides
  variableValues: Record<string, any>;
  // Position on grid
  x: number;
  y: number;
  // Size overrides (optional, defaults to template size)
  widthOverride?: number;
  heightOverride?: number;
}

export interface VisuRoom {
  id: string;
  name: string;
  category: string; // e.g. "Wohnbereich", "Schlafbereich", "Außen"
  icon?: string;
  widgets: VseWidgetInstance[];
}

export interface DevicePreset {
  id: string;
  name: string;
  width: number;
  height: number;
  icon: string;
}

export const DEVICE_PRESETS: DevicePreset[] = [
  { id: "iphone17pro", name: "iPhone 17 Pro", width: 402, height: 874, icon: "📱" },
  { id: "iphone17promax", name: "iPhone 17 Pro Max", width: 440, height: 956, icon: "📱" },
  { id: "ipad", name: "iPad Pro 11\"", width: 834, height: 1194, icon: "📋" },
  { id: "desktop", name: "Desktop 1080p", width: 1920, height: 1080, icon: "🖥️" },
  { id: "custom", name: "Benutzerdefiniert", width: 400, height: 800, icon: "⚙️" },
];
