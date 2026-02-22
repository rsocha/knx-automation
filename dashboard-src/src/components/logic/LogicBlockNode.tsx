import { memo, useCallback } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { LogicBlockPort } from "@/stores/logicStore";
import { Link } from "lucide-react";

export interface LogicBlockNodeData {
  label: string;
  category: string;
  instanceId: string;
  blockId: string;
  version?: string;
  inputs: LogicBlockPort[];
  outputs: LogicBlockPort[];
  inputValues: Record<string, any>;
  outputValues: Record<string, any>;
  inputBindings?: Record<string, string>;
  outputBindings?: Record<string, string>;
  onConnectKO?: (nodeId: string, portKey: string, portType: "input" | "output") => void;
}

type LogicBlockNodeProps = NodeProps & { data: LogicBlockNodeData };

function LogicBlockNode({ data, selected }: LogicBlockNodeProps) {
  const categoryColors: Record<string, string> = {
    Audio: "border-knx-purple",
    Licht: "border-knx-warning",
    Klima: "border-accent",
    default: "border-primary",
  };

  const borderClass = categoryColors[data.category] || categoryColors.default;

  const hasValue = (v: any) => v !== undefined && v !== null && v !== "";

  const handlePortClick = useCallback(
    (portKey: string, portType: "input" | "output") => {
      data.onConnectKO?.(data.instanceId, portKey, portType);
    },
    [data]
  );

  return (
    <div
      className={`bg-card border-2 ${borderClass} rounded-lg shadow-lg min-w-[280px] ${
        selected ? "ring-2 ring-primary" : ""
      }`}
    >
      {/* Header */}
      <div className="px-3 py-2 bg-secondary rounded-t-md border-b border-border">
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-mono text-muted-foreground">#{data.blockId}</span>
          <span className="text-xs font-semibold text-foreground truncate">{data.label}</span>
          {data.version && (
            <span className="text-[9px] font-mono text-muted-foreground ml-auto shrink-0">v{data.version}</span>
          )}
        </div>
        {data.category && <div className="text-[10px] text-muted-foreground">{data.category}</div>}
      </div>

      {/* Ports */}
      <div className="flex">
        {/* Inputs */}
        <div className="flex-1 py-1.5">
          {data.inputs.map((port) => {
            const binding = data.inputBindings?.[port.key];
            const value = data.inputValues[port.key];
            return (
              <div key={port.key} className="relative flex items-center gap-1 pl-2 pr-1 py-1 group">
                <Handle
                  type="target"
                  position={Position.Left}
                  id={`in-${port.key}`}
                  className="!w-2.5 !h-2.5 !bg-accent !border-accent/50 !-left-1.5"
                  style={{ top: "auto" }}
                />
                <button
                  className="w-4 h-4 flex items-center justify-center rounded hover:bg-accent/20 opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
                  onClick={() => handlePortClick(port.key, "input")}
                  title="Wert/KO setzen"
                >
                  <Link className="w-2.5 h-2.5 text-accent" />
                </button>
              <div className="flex flex-col flex-1 min-w-0">
                  <span className="text-[10px] text-foreground truncate leading-tight">
                    <span className="font-mono text-muted-foreground">{port.key}</span> {port.name}
                  </span>
                  <div className="flex items-center gap-1">
                    <span
                      className={`text-[9px] font-mono truncate max-w-[60px] px-1 rounded cursor-pointer ${
                        hasValue(value)
                          ? "border-[1.5px] border-yellow-500 text-foreground"
                          : "text-muted-foreground"
                      }`}
                      title={hasValue(value) ? String(value) : undefined}
                      onClick={() => hasValue(value) && handlePortClick(port.key, "input")}
                    >
                      {hasValue(value) ? String(value) : "–"}
                    </span>
                  </div>
                  {binding && (
                    <span className="text-[8px] text-accent font-mono truncate" title={binding}>
                      → {binding}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Divider */}
        <div className="w-px bg-border" />

        {/* Outputs */}
        <div className="flex-1 py-1.5">
          {data.outputs.map((port) => {
            const binding = data.outputBindings?.[port.key];
            const value = data.outputValues?.[port.key];
            return (
              <div key={port.key} className="relative flex items-center justify-end gap-1 pr-2 pl-1 py-1 group">
              <div className="flex flex-col flex-1 min-w-0 items-end">
                  <span className="text-[10px] text-foreground truncate leading-tight">
                    {port.name} <span className="font-mono text-muted-foreground">{port.key}</span>
                  </span>
                  <div className="flex items-center gap-1">
                    <span
                      className={`text-[9px] font-mono truncate max-w-[60px] px-1 rounded cursor-pointer ${
                        hasValue(value)
                          ? "border-[1.5px] border-yellow-500 text-foreground"
                          : "text-muted-foreground"
                      }`}
                      title={hasValue(value) ? String(value) : undefined}
                      onClick={() => hasValue(value) && handlePortClick(port.key, "output")}
                    >
                      {hasValue(value) ? String(value) : "–"}
                    </span>
                  </div>
                  {binding && (
                    <span className="text-[8px] text-primary font-mono truncate" title={binding}>
                      → {binding}
                    </span>
                  )}
                </div>
                <button
                  className="w-4 h-4 flex items-center justify-center rounded hover:bg-primary/20 opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
                  onClick={() => handlePortClick(port.key, "output")}
                  title="KO verbinden"
                >
                  <Link className="w-2.5 h-2.5 text-primary" />
                </button>
                <Handle
                  type="source"
                  position={Position.Right}
                  id={`out-${port.key}`}
                  className="!w-2.5 !h-2.5 !bg-primary !border-primary/50 !-right-1.5"
                  style={{ top: "auto" }}
                />
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default memo(LogicBlockNode);
