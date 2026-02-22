import { useState, useCallback, useRef } from "react";

interface Props {
  width: number;
  height: number;
  minWidth?: number;
  minHeight?: number;
  onResize: (w: number, h: number) => void;
  editMode: boolean;
  children: React.ReactNode;
}

export default function ResizableWidget({
  width,
  height,
  minWidth = 60,
  minHeight = 30,
  onResize,
  editMode,
  children,
}: Props) {
  const [dragging, setDragging] = useState(false);
  const startRef = useRef({ x: 0, y: 0, w: 0, h: 0 });

  const onMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (!editMode) return;
      e.preventDefault();
      e.stopPropagation();
      startRef.current = { x: e.clientX, y: e.clientY, w: width, h: height };
      setDragging(true);

      const onMove = (ev: MouseEvent) => {
        const dx = ev.clientX - startRef.current.x;
        const dy = ev.clientY - startRef.current.y;
        const newW = Math.max(minWidth, startRef.current.w + dx);
        const newH = Math.max(minHeight, startRef.current.h + dy);
        onResize(Math.round(newW), Math.round(newH));
      };

      const onUp = () => {
        setDragging(false);
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
      };

      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
    },
    [editMode, width, height, minWidth, minHeight, onResize]
  );

  return (
    <div style={{ position: "relative", width, height }}>
      {children}
      {editMode && (
        <>
          {/* Size label */}
          <div
            style={{
              position: "absolute",
              bottom: -18,
              left: "50%",
              transform: "translateX(-50%)",
              fontSize: 9,
              color: "rgba(255,255,255,0.5)",
              whiteSpace: "nowrap",
              pointerEvents: "none",
            }}
          >
            {width}×{height}
          </div>
          {/* Resize handle */}
          <div
            data-resize-handle
            onMouseDown={onMouseDown}
            style={{
              position: "absolute",
              right: -3,
              bottom: -3,
              width: 14,
              height: 14,
              cursor: "nwse-resize",
              zIndex: 30,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              borderRadius: 3,
              background: dragging ? "hsl(var(--primary))" : "rgba(255,255,255,0.15)",
              border: "1px solid rgba(255,255,255,0.3)",
              transition: "background 0.15s",
            }}
          >
            <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
              <line x1="7" y1="1" x2="1" y2="7" stroke="rgba(255,255,255,0.6)" strokeWidth="1" />
              <line x1="7" y1="4" x2="4" y2="7" stroke="rgba(255,255,255,0.6)" strokeWidth="1" />
            </svg>
          </div>
        </>
      )}
    </div>
  );
}
