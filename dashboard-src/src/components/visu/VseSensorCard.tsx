import { useGroupAddresses } from "@/hooks/useKnx";
import type { VseWidgetInstance, VseTemplate } from "@/types/vse";
import MdiIcon from "./MdiIcon";

interface Props {
  instance: VseWidgetInstance;
  template: VseTemplate;
}

export default function VseSensorCard({ instance, template }: Props) {
  const { data: addresses } = useGroupAddresses();

  const vars: Record<string, any> = {
    ...Object.fromEntries(Object.entries(template.variables).map(([k, v]) => [k, v.default])),
    ...instance.variableValues,
  };

  const iconName = vars.var1 || "thermometer";
  const label = vars.var2 || "Sensor";
  const decimals = Number(vars.var3) ?? 1;
  const iconSize = Number(vars.var4) || 24;
  const labelSize = vars.var5 || "0.85";
  const labelOpacity = vars.var7 || "0.7";
  const valueSize = vars.var8 || "1.1";
  const valueOpacity = vars.var10 || "0.9";
  const iconColor = vars.var11 || "100,181,246";
  const borderRadius = Number(vars.var12) || 16;
  const borderOpacity = Number(vars.var13) ?? 30;
  const borderColor = vars.var14 || "255,255,255";
  const borderWidth = Number(vars.var15) || 1;
  const bgColor = vars.var16 || "30,30,35";
  const bgOpacity = Number(vars.var17) ?? 90;
  const unitText = vars.unit || "°C";

  const ko1Addr = instance.koBindings["ko1"];
  const ga = addresses?.find((a) => a.address === ko1Addr);
  const value = ga?.value != null ? parseFloat(ga.value) : 0;

  // Use instance size overrides or template defaults
  const w = instance.widthOverride ?? template.width;
  const h = instance.heightOverride ?? template.height;

  return (
    <div
      style={{
        width: w,
        height: h,
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "8px 14px",
        borderRadius,
        border: `${borderWidth}px solid rgba(${borderColor},${borderOpacity / 100})`,
        background: `rgba(${bgColor},${bgOpacity / 100})`,
        boxSizing: "border-box",
        overflow: "hidden",
      }}
    >
      {/* Icon */}
      <div style={{ flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <MdiIcon name={iconName} size={iconSize} color={`rgb(${iconColor})`} />
      </div>

      {/* Text */}
      <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", minWidth: 0 }}>
        <div
          style={{
            fontSize: `${labelSize}em`,
            fontWeight: 500,
            color: `rgba(255,255,255,${labelOpacity})`,
            lineHeight: 1.2,
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {label}
        </div>
        <div
          style={{
            fontSize: `${valueSize}em`,
            fontWeight: 600,
            color: `rgba(255,255,255,${valueOpacity})`,
            lineHeight: 1.2,
          }}
        >
          {isNaN(value) ? "--" : value.toFixed(decimals)} {unitText}
        </div>
      </div>
    </div>
  );
}
