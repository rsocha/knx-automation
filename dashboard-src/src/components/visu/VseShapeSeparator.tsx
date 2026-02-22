import type { VseWidgetInstance, VseTemplate } from "@/types/vse";

interface Props {
  instance: VseWidgetInstance;
  template: VseTemplate;
}

export default function VseShapeSeparator({ instance, template }: Props) {
  const vars: Record<string, any> = {
    ...Object.fromEntries(Object.entries(template.variables).map(([k, v]) => [k, v.default])),
    ...instance.variableValues,
  };

  // Parse variables
  const shape = vars.var1 || "line"; // line, rectangle, circle
  const color = vars.var2 || "255,255,255";
  const opacity = Number(vars.var3) || 40;
  const size = Number(vars.var4) || 2;
  const borderRadius = Number(vars.var5) || 0;
  const showBorder = vars.var6 === "1" || vars.var6 === true;
  const borderColor = vars.var7 || "255,255,255";
  const borderOpacity = Number(vars.var8) || 30;

  const baseStyle: React.CSSProperties = {
    width: template.width,
    height: template.height,
    boxSizing: "border-box",
  };

  if (shape === "line") {
    // Horizontal or vertical line depending on aspect ratio
    const isHorizontal = template.width >= template.height;
    return (
      <div
        style={{
          ...baseStyle,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <div
          style={{
            width: isHorizontal ? "100%" : size,
            height: isHorizontal ? size : "100%",
            background: `rgba(${color}, ${opacity / 100})`,
            borderRadius: size / 2,
          }}
        />
      </div>
    );
  }

  if (shape === "circle") {
    const diameter = Math.min(template.width, template.height);
    return (
      <div
        style={{
          ...baseStyle,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <div
          style={{
            width: diameter,
            height: diameter,
            borderRadius: "50%",
            background: `rgba(${color}, ${opacity / 100})`,
            border: showBorder ? `${size}px solid rgba(${borderColor}, ${borderOpacity / 100})` : "none",
          }}
        />
      </div>
    );
  }

  // Default: rectangle
  return (
    <div
      style={{
        ...baseStyle,
        background: `rgba(${color}, ${opacity / 100})`,
        borderRadius,
        border: showBorder ? `${size}px solid rgba(${borderColor}, ${borderOpacity / 100})` : "none",
      }}
    />
  );
}
