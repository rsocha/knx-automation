import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { Input } from "@/components/ui/input";
import { useLogicStore } from "@/stores/logicStore";

export interface KONodeData {
  instanceId: string;
  address: string;
  label: string;
  value: string;
  direction: "input" | "output"; // input = sends to block, output = receives from block
}

type KONodeProps = NodeProps & { data: KONodeData };

function KONode({ data, selected }: KONodeProps) {
  const updateKO = useLogicStore((s) => s.updateKOValue);

  return (
    <div
      className={`bg-card border-2 border-accent rounded-lg shadow-lg min-w-[140px] ${
        selected ? "ring-2 ring-accent" : ""
      }`}
    >
      <div className="px-2 py-1.5 bg-accent/10 rounded-t-md border-b border-border flex items-center gap-1.5">
        <div className="w-2 h-2 rounded-full bg-accent shrink-0" />
        <span className="text-[10px] font-mono text-accent font-semibold truncate">{data.address}</span>
      </div>
      <div className="px-2 py-1.5 flex items-center gap-1">
        {data.direction === "input" && (
          <Handle
            type="target"
            position={Position.Left}
            id="ko-in"
            className="!w-2.5 !h-2.5 !bg-accent !border-accent/50 !-left-1.5"
            style={{ top: "auto" }}
          />
        )}
        <span className="text-[10px] text-muted-foreground truncate flex-1">{data.label}</span>
        <Input
          className="h-5 text-[10px] px-1 py-0 bg-secondary border-border font-mono w-14"
          value={data.value}
          onChange={(e) => updateKO(data.instanceId, e.target.value)}
          placeholder="Wert"
        />
        {data.direction === "output" && (
          <Handle
            type="source"
            position={Position.Right}
            id="ko-out"
            className="!w-2.5 !h-2.5 !bg-primary !border-primary/50 !-right-1.5"
            style={{ top: "auto" }}
          />
        )}
      </div>
    </div>
  );
}

export default memo(KONode);
