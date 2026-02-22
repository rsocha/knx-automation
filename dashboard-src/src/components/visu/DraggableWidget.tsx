import { useRef, useCallback, useState } from "react";
import { Pencil } from "lucide-react";
import type { VseWidgetInstance, VseTemplate } from "@/types/vse";
import VseRenderer from "./VseRenderer";
import ResizableWidget from "./ResizableWidget";

interface Props {
  widget: VseWidgetInstance;
  template: VseTemplate;
  editMode: boolean;
  onMove: (x: number, y: number) => void;
  onResize: (w: number, h: number) => void;
  onEdit: () => void;
  onRemove: () => void;
}

export default function DraggableWidget({ widget, template, editMode, onMove, onResize, onEdit, onRemove }: Props) {
  const [dragging, setDragging] = useState(false);
  const startRef = useRef({ mx: 0, my: 0, x: 0, y: 0 });

  const onMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (!editMode) return;
      // Don't drag if clicking buttons or resize handle
      if ((e.target as HTMLElement).closest("[data-widget-control], [data-resize-handle]")) return;
      e.preventDefault();
      startRef.current = { mx: e.clientX, my: e.clientY, x: widget.x, y: widget.y };
      setDragging(true);

      const onMouseMove = (ev: MouseEvent) => {
        const dx = ev.clientX - startRef.current.mx;
        const dy = ev.clientY - startRef.current.my;
        onMove(
          Math.max(0, startRef.current.x + dx),
          Math.max(0, startRef.current.y + dy)
        );
      };

      const onMouseUp = () => {
        setDragging(false);
        window.removeEventListener("mousemove", onMouseMove);
        window.removeEventListener("mouseup", onMouseUp);
      };

      window.addEventListener("mousemove", onMouseMove);
      window.addEventListener("mouseup", onMouseUp);
    },
    [editMode, widget.x, widget.y, onMove]
  );

  return (
    <div
      onMouseDown={onMouseDown}
      style={{
        position: "absolute",
        left: widget.x,
        top: widget.y,
        cursor: editMode ? (dragging ? "grabbing" : "grab") : "default",
        zIndex: dragging ? 50 : 1,
        transition: dragging ? "none" : "box-shadow 0.2s",
        boxShadow: dragging ? "0 8px 24px rgba(0,0,0,0.4)" : "none",
      }}
    >
      {editMode && (
        <div className="absolute -top-2 -right-2 z-10 flex gap-1">
          <button
            data-widget-control
            onClick={onEdit}
            className="w-6 h-6 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-xs hover:scale-110 transition-transform"
          >
            <Pencil className="w-3 h-3" />
          </button>
          <button
            data-widget-control
            onClick={onRemove}
            className="w-6 h-6 rounded-full bg-destructive text-destructive-foreground flex items-center justify-center text-xs hover:scale-110 transition-transform"
          >
            ✕
          </button>
        </div>
      )}
      <ResizableWidget
        width={widget.widthOverride ?? template.width}
        height={widget.heightOverride ?? template.height}
        onResize={onResize}
        editMode={editMode}
      >
        <VseRenderer instance={widget} template={template} />
      </ResizableWidget>
    </div>
  );
}
