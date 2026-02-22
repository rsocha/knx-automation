import { useState } from "react";
import { DEVICE_PRESETS, type DevicePreset } from "@/types/vse";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
  children: React.ReactNode;
}

export default function DeviceFrame({ children }: Props) {
  const [deviceId, setDeviceId] = useState("iphone17pro");
  const [rotated, setRotated] = useState(false);

  const device = DEVICE_PRESETS.find((d) => d.id === deviceId) || DEVICE_PRESETS[0];
  const w = rotated ? device.height : device.width;
  const h = rotated ? device.width : device.height;

  // Scale to fit within container
  const maxW = 500;
  const maxH = 700;
  const scale = Math.min(1, maxW / w, maxH / h);

  return (
    <div className="flex flex-col items-center gap-3">
      {/* Device selector */}
      <div className="flex items-center gap-2">
        <Select value={deviceId} onValueChange={setDeviceId}>
          <SelectTrigger className="h-8 w-52 text-xs bg-secondary border-border">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {DEVICE_PRESETS.map((d) => (
              <SelectItem key={d.id} value={d.id}>
                {d.icon} {d.name} ({d.width}×{d.height})
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          variant="ghost"
          size="sm"
          className="h-8 w-8 p-0"
          onClick={() => setRotated(!rotated)}
          title="Drehen"
        >
          <RotateCcw className="w-3.5 h-3.5" />
        </Button>
      </div>

      {/* Device frame */}
      <div
        className="relative bg-black rounded-[2.5rem] p-3 shadow-2xl"
        style={{
          width: w * scale + 24,
          height: h * scale + 24,
        }}
      >
        {/* Notch */}
        <div className="absolute top-2 left-1/2 -translate-x-1/2 w-24 h-5 bg-black rounded-b-xl z-10" />

        {/* Screen */}
        <div
          className="bg-background rounded-[2rem] overflow-hidden relative"
          style={{
            width: w * scale,
            height: h * scale,
          }}
        >
          <div
            style={{
              width: w,
              height: h,
              transform: `scale(${scale})`,
              transformOrigin: "top left",
            }}
            className="overflow-auto"
          >
            {children}
          </div>
        </div>

        {/* Home indicator */}
        <div className="absolute bottom-1.5 left-1/2 -translate-x-1/2 w-28 h-1 bg-gray-600 rounded-full" />
      </div>

      <span className="text-[10px] text-muted-foreground">
        {device.name} – {w}×{h}px {rotated ? "(Querformat)" : ""}
      </span>
    </div>
  );
}
