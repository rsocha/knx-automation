import { useState, useEffect } from "react";
import { Input } from "@/components/ui/input";

interface ColorPickerProps {
  value: string; // Format: "R,G,B" e.g. "255,193,7"
  onChange: (value: string) => void;
  className?: string;
}

function rgbToHex(rgb: string): string {
  try {
    const parts = rgb.split(",").map((p) => parseInt(p.trim(), 10));
    if (parts.length !== 3 || parts.some(isNaN)) return "#ffffff";
    return `#${parts.map((p) => Math.max(0, Math.min(255, p)).toString(16).padStart(2, "0")).join("")}`;
  } catch {
    return "#ffffff";
  }
}

function hexToRgb(hex: string): string {
  try {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    if (!result) return "255,255,255";
    return `${parseInt(result[1], 16)},${parseInt(result[2], 16)},${parseInt(result[3], 16)}`;
  } catch {
    return "255,255,255";
  }
}

export default function ColorPicker({ value, onChange, className }: ColorPickerProps) {
  const [localValue, setLocalValue] = useState(value || "255,255,255");

  useEffect(() => {
    if (value && value !== localValue) {
      setLocalValue(value);
    }
  }, [value]);

  const handleColorChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const rgb = hexToRgb(e.target.value);
    setLocalValue(rgb);
    onChange(rgb);
  };

  const handleTextChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setLocalValue(e.target.value);
    // Validate and update only if valid RGB format
    const parts = e.target.value.split(",").map((p) => parseInt(p.trim(), 10));
    if (parts.length === 3 && parts.every((p) => !isNaN(p) && p >= 0 && p <= 255)) {
      onChange(e.target.value);
    }
  };

  const handleBlur = () => {
    // On blur, ensure the value is valid
    const parts = localValue.split(",").map((p) => parseInt(p.trim(), 10));
    if (parts.length === 3 && parts.every((p) => !isNaN(p) && p >= 0 && p <= 255)) {
      const normalized = parts.join(",");
      setLocalValue(normalized);
      onChange(normalized);
    } else {
      // Reset to previous valid value or default
      setLocalValue(value || "255,255,255");
    }
  };

  return (
    <div className={`flex items-center gap-2 ${className || ""}`}>
      {/* Color Preview & Picker */}
      <div className="relative">
        <input
          type="color"
          value={rgbToHex(localValue)}
          onChange={handleColorChange}
          className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
        />
        <div
          className="w-8 h-8 rounded border border-border cursor-pointer shadow-sm"
          style={{ backgroundColor: `rgb(${localValue})` }}
        />
      </div>
      
      {/* RGB Text Input */}
      <Input
        value={localValue}
        onChange={handleTextChange}
        onBlur={handleBlur}
        placeholder="R,G,B"
        className="flex-1 bg-secondary border-border h-7 text-xs font-mono"
      />
    </div>
  );
}
