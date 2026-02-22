import { useState, useRef, useEffect } from "react";
import { useSendKnxCommand, useGroupAddresses } from "@/hooks/useKnx";
import { toast } from "sonner";
import MdiIcon from "./MdiIcon";
import type { VseWidgetInstance, VseTemplate } from "@/types/vse";

interface Props {
  instance: VseWidgetInstance;
  template: VseTemplate;
}

function parseRgb(rgb: string): string {
  const parts = rgb.split(",").map((s) => s.trim());
  if (parts.length === 3) return `rgb(${parts[0]}, ${parts[1]}, ${parts[2]})`;
  return rgb;
}

function rgbToRgba(rgb: string, alpha: number): string {
  const parts = rgb.split(",").map((s) => s.trim());
  if (parts.length === 3) return `rgba(${parts[0]}, ${parts[1]}, ${parts[2]}, ${alpha})`;
  return rgb;
}

export default function VseSwitchCard({ instance, template }: Props) {
  const { data: addresses } = useGroupAddresses();
  const send = useSendKnxCommand();
  const [localOn, setLocalOn] = useState<boolean | null>(null);
  const lastToggleTime = useRef(0);
  const lastRemoteValue = useRef<string | null>(null);

  const vars = {
    ...Object.fromEntries(Object.entries(template.variables).map(([k, v]) => [k, v.default])),
    ...instance.variableValues,
  };

  // KO bindings
  const statusAddr = instance.koBindings["ko1"];
  const sendAddr = instance.koBindings["ko2"] || statusAddr;
  const ga = addresses?.find((a) => a.address === statusAddr);
  const remoteOn = ga?.value === "True" || ga?.value === "1" || ga?.value === "true" || ga?.value === "on";

  // Track remote changes but ignore updates for 3 seconds after user toggle
  useEffect(() => {
    if (ga?.value !== undefined && ga?.value !== lastRemoteValue.current) {
      const timeSinceToggle = Date.now() - lastToggleTime.current;
      if (timeSinceToggle > 3000) {
        // Only accept remote updates after 3 seconds
        setLocalOn(null);
      }
      lastRemoteValue.current = ga?.value ?? null;
    }
  }, [ga?.value]);

  // Use local state if recently toggled, otherwise use remote
  const isOn = localOn !== null ? localOn : remoteOn;

  // Colors
  const activeColor = vars.var3 || "255,193,7";
  const inactiveColor = vars.var4 || "158,158,158";
  const currentColor = isOn ? activeColor : inactiveColor;

  const badgeActiveColor = vars.var13 || "76,175,80";
  const badgeInactiveColor = vars.var14 || "244,67,54";
  const badgeColor = isOn ? badgeActiveColor : badgeInactiveColor;

  const borderActiveColor = vars.var17 || "255,193,7";
  const borderInactiveColor = vars.var18 || "158,158,158";
  const borderColor = isOn ? borderActiveColor : borderInactiveColor;

  const borderWidth = Number(vars.var19) || 1.5;
  const borderOpacity = (Number(vars.var20) || 45) / 100;
  const borderRadius = Number(vars.var9) || 12;
  const iconSize = Number(vars.var7) || 40;
  const badgeSize = Number(vars.var8) || 18;
  const showGlow = vars.var10 === "1" || vars.var10 === true;
  const labelFontSize = Number(vars.var12) || 12;
  const statusFontSize = Number(vars.var23) || 11;

  const bgColor = vars.var21 || "40,40,40";
  const bgOpacity = (Number(vars.var22) ?? 90) / 100;

  const textOn = vars.var5 || "An";
  const textOff = vars.var6 || "Aus";
  const statusText = isOn ? textOn : textOff;

  // Badge position (relative to icon container)
  const badgeOffsetX = Number(vars.var25) || 0;
  const badgeOffsetY = Number(vars.var26) || 0;
  const showBadge = vars.var27 !== "0" && vars.var27 !== false;

  // Icons
  const mainIconName = vars.var1 || "lightbulb";
  const badgeIconOn = vars.var2 || "power";
  const badgeIconOff = vars.var24 || "power-off";
  const statusIconOn = vars.var15 || "check-bold";
  const statusIconOff = vars.var16 || "pause";

  const toggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    
    if (!sendAddr) {
      toast.error(`Keine Schalt-Adresse (ko2) konfiguriert für "${instance.label}"`);
      console.error("[Switch] No sendAddr configured for", instance.label);
      return;
    }
    
    const newState = !isOn;
    const sendValue = newState ? 1 : 0;
    
    console.log(`[Switch] ${instance.label}: Sending ${sendValue} to ${sendAddr}`);
    
    // Set local state and mark toggle time
    setLocalOn(newState);
    lastToggleTime.current = Date.now();
    
    send.mutate(
      { address: sendAddr, value: sendValue },
      {
        onSuccess: (result) => {
          console.log(`[Switch] ${instance.label}: Send success`, result);
          toast.success(`${instance.label}: ${newState ? "Ein" : "Aus"} → ${sendAddr}`);
        },
        onError: (error) => {
          console.error(`[Switch] ${instance.label}: Send failed`, error);
          toast.error(`${instance.label}: Senden fehlgeschlagen - ${error.message}`);
          // Revert optimistic state
          setLocalOn(null);
        }
      }
    );
  };

  // Use instance size or template defaults
  const w = instance.widthOverride ?? template.width;
  const h = instance.heightOverride ?? template.height;

  return (
    <button
      onClick={toggle}
      className="relative flex flex-col items-center justify-center gap-1 transition-all duration-300 cursor-pointer select-none hover:scale-[1.03] active:scale-[0.97]"
      style={{
        width: w,
        height: h,
        borderRadius,
        border: `${borderWidth}px solid ${rgbToRgba(borderColor, borderOpacity)}`,
        background: `linear-gradient(135deg, ${rgbToRgba(bgColor, bgOpacity)} 0%, ${rgbToRgba(bgColor, bgOpacity * 0.85)} 100%)`,
        boxShadow: showGlow && isOn
          ? `0 0 20px ${rgbToRgba(activeColor, 0.2)}, inset 0 1px 0 rgba(255,255,255,0.05)`
          : "inset 0 1px 0 rgba(255,255,255,0.05)",
        overflow: "hidden",
      }}
    >
      {/* Icon + Badge container */}
      <div 
        className="relative flex items-center justify-center" 
        style={{ 
          width: Math.min(iconSize + badgeSize, w - 20), 
          height: iconSize,
          flexShrink: 0,
        }}
      >
        <MdiIcon
          name={mainIconName}
          size={iconSize}
          color={parseRgb(currentColor)}
        />
        {/* Badge - positioned relative to icon */}
        {showBadge && (
          <div
            className="absolute rounded-full flex items-center justify-center transition-colors duration-300"
            style={{
              width: badgeSize,
              height: badgeSize,
              backgroundColor: parseRgb(badgeColor),
              top: -badgeSize / 3 + badgeOffsetY,
              right: -badgeSize / 3 + badgeOffsetX,
            }}
          >
            <MdiIcon
              name={isOn ? badgeIconOn : badgeIconOff}
              size={badgeSize * 0.6}
              color="white"
            />
          </div>
        )}
      </div>

      {/* Label */}
      <span
        className="font-medium text-neutral-200 truncate px-2"
        style={{ fontSize: labelFontSize, maxWidth: w - 16 }}
      >
        {instance.label}
      </span>

      {/* Status line */}
      <div className="flex items-center gap-1">
        <MdiIcon
          name={isOn ? statusIconOn : statusIconOff}
          size={statusFontSize}
          color={parseRgb(currentColor)}
        />
        <span
          className="font-semibold transition-colors duration-300"
          style={{ fontSize: statusFontSize, color: parseRgb(currentColor) }}
        >
          {statusText}
        </span>
      </div>
    </button>
  );
}
