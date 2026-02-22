import { useMemo } from "react";
import { useGroupAddresses, useSendKnxCommand } from "@/hooks/useKnx";
import { toast } from "sonner";
import MdiIcon from "./MdiIcon";
import type { VseWidgetInstance, VseTemplate } from "@/types/vse";

interface Props {
  instance: VseWidgetInstance;
  template: VseTemplate;
}

/**
 * VseDynamicWidget - Generischer Renderer für benutzerdefinierte Widgets
 * 
 * Rendert Widgets automatisch basierend auf dem JSON-Template ohne
 * dass eine eigene React-Komponente geschrieben werden muss.
 * 
 * Unterstützte Features:
 * - Label-Anzeige
 * - Icon (MDI oder Emoji)
 * - KO-Werte anzeigen (ko1, ko2, ...)
 * - Klick zum Schalten (wenn ko_send definiert)
 * - Anpassbare Farben, Größen, Abstände
 * 
 * Spezielle Variablen im Template:
 * - icon: MDI Icon-Name oder Emoji
 * - icon_size: Größe in px (default: 32)
 * - icon_color: RGB Farbe (default: 255,255,255)
 * - text_color: RGB für Text
 * - bg_color: RGB für Hintergrund
 * - bg_opacity: 0-100 (default: 10)
 * - border_radius: px (default: 12)
 * - border_color: RGB
 * - border_width: px (default: 0)
 * - padding: px (default: 12)
 * - font_size: px für Wert (default: 24)
 * - label_size: px für Label (default: 12)
 * - unit: Einheit für Wert (z.B. "°C", "%")
 * - layout: "vertical" | "horizontal" | "icon-left" | "icon-top" (default: vertical)
 * - clickable: "1" wenn klickbar (Toggle)
 * - value_on: Text bei Wert=1
 * - value_off: Text bei Wert=0
 */
export default function VseDynamicWidget({ instance, template }: Props) {
  const { data: addresses } = useGroupAddresses();
  const send = useSendKnxCommand();

  // Merge default values with instance values
  const vars = useMemo(() => {
    const defaults: Record<string, any> = {};
    if (template.variables) {
      for (const [key, def] of Object.entries(template.variables)) {
        defaults[key] = def.default;
      }
    }
    return { ...defaults, ...instance.variableValues };
  }, [template.variables, instance.variableValues]);

  // Get KO values
  const koValues: Record<string, string | null> = {};
  if (template.inputs) {
    for (const koKey of Object.keys(template.inputs)) {
      const addr = instance.koBindings[koKey];
      if (addr) {
        const ga = addresses?.find((a) => a.address === addr);
        koValues[koKey] = ga?.value ?? null;
      }
    }
  }

  // Primary value (ko1)
  const primaryValue = koValues["ko1"];
  const primaryAddr = instance.koBindings["ko1"];
  const sendAddr = instance.koBindings["ko2"] || primaryAddr;

  // Parse value
  const numValue = primaryValue !== null ? parseFloat(primaryValue) : null;
  const boolValue = primaryValue === "1" || primaryValue === "true" || primaryValue === "True" || primaryValue === "on";

  // Styling from variables
  const icon = vars.icon || vars.var1 || "";
  const iconSize = Number(vars.icon_size || vars.var7) || 32;
  const iconColor = vars.icon_color || vars.var3 || "255,255,255";
  const textColor = vars.text_color || "255,255,255";
  const bgColor = vars.bg_color || vars.var21 || "40,40,40";
  const bgOpacity = (Number(vars.bg_opacity || vars.var22) || 10) / 100;
  const borderRadius = Number(vars.border_radius || vars.var9) || 12;
  const borderColor = vars.border_color || vars.var17 || "";
  const borderWidth = Number(vars.border_width || vars.var19) || 0;
  const padding = Number(vars.padding) || 12;
  const fontSize = Number(vars.font_size || vars.var7) || 24;
  const labelSize = Number(vars.label_size || vars.var12) || 12;
  const unit = vars.unit || "";
  const layout = vars.layout || "vertical";
  const clickable = vars.clickable === "1" || vars.clickable === true;
  const valueOn = vars.value_on || vars.var5 || "An";
  const valueOff = vars.value_off || vars.var6 || "Aus";

  // Format display value
  let displayValue = "–";
  if (primaryValue !== null) {
    if (vars.value_on || vars.value_off) {
      // Boolean text display
      displayValue = boolValue ? valueOn : valueOff;
    } else if (numValue !== null && !isNaN(numValue)) {
      // Numeric display
      const decimals = Number(vars.decimals) || 1;
      displayValue = numValue.toFixed(decimals).replace(".", ",");
    } else {
      displayValue = primaryValue;
    }
  }

  // Check if icon is emoji
  const isEmoji = icon && /^[\u{1F300}-\u{1FAFF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/u.test(icon);

  // Click handler for toggle
  const handleClick = () => {
    if (!clickable || !sendAddr) return;
    
    const newValue = boolValue ? 0 : 1;
    send.mutate(
      { address: sendAddr, value: newValue },
      {
        onSuccess: () => {
          toast.success(`${instance.label}: ${newValue ? valueOn : valueOff}`);
        },
        onError: (err) => {
          toast.error(`Fehler: ${err.message}`);
        },
      }
    );
  };

  // Render icon
  const renderIcon = () => {
    if (!icon) return null;
    
    if (isEmoji) {
      return <span style={{ fontSize: iconSize }}>{icon}</span>;
    }
    
    return (
      <MdiIcon 
        name={icon} 
        size={iconSize} 
        color={`rgb(${boolValue ? vars.icon_color_on || iconColor : iconColor})`} 
      />
    );
  };

  // Layout styles
  const isHorizontal = layout === "horizontal" || layout === "icon-left";
  const isIconTop = layout === "icon-top";

  return (
    <div
      onClick={clickable ? handleClick : undefined}
      style={{
        width: template.width,
        height: template.height,
        borderRadius,
        border: borderWidth > 0 ? `${borderWidth}px solid rgba(${borderColor}, 0.5)` : "none",
        background: `rgba(${bgColor}, ${bgOpacity})`,
        padding,
        display: "flex",
        flexDirection: isHorizontal ? "row" : "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 8,
        cursor: clickable ? "pointer" : "default",
        transition: "all 0.2s ease",
        color: `rgb(${textColor})`,
      }}
      className={clickable ? "hover:scale-[1.02] active:scale-[0.98]" : ""}
    >
      {/* Icon */}
      {icon && (isIconTop || isHorizontal) && renderIcon()}

      {/* Content */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: isHorizontal ? "flex-start" : "center",
          gap: 4,
        }}
      >
        {/* Label */}
        <span
          style={{
            fontSize: labelSize,
            opacity: 0.8,
            fontWeight: 500,
          }}
        >
          {instance.label}
        </span>

        {/* Value */}
        {primaryValue !== null && (
          <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
            {!isIconTop && !isHorizontal && icon && renderIcon()}
            <span
              style={{
                fontSize,
                fontWeight: 600,
              }}
            >
              {displayValue}
            </span>
            {unit && (
              <span style={{ fontSize: fontSize * 0.5, opacity: 0.7 }}>
                {unit}
              </span>
            )}
          </div>
        )}

        {/* Secondary values (ko2, ko3, ...) */}
        {Object.entries(koValues)
          .filter(([k]) => k !== "ko1" && koValues[k] !== null)
          .map(([key, val]) => (
            <span key={key} style={{ fontSize: labelSize, opacity: 0.6 }}>
              {val}
            </span>
          ))}
      </div>
    </div>
  );
}
