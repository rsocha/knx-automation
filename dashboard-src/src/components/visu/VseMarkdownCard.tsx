import type { VseWidgetInstance, VseTemplate } from "@/types/vse";
import MdiIcon from "./MdiIcon";

interface Props {
  instance: VseWidgetInstance;
  template: VseTemplate;
}

export default function VseMarkdownCard({ instance, template }: Props) {
  const vars = {
    ...Object.fromEntries(Object.entries(template.variables).map(([k, v]) => [k, v.default])),
    ...instance.variableValues,
  };

  const icon = vars.var1 || "⚡";
  const subtitle = vars.var2 || "";
  const titleSize = parseFloat(vars.var3) || 1.3;
  const subtitleSize = parseFloat(vars.var4) || 0.85;
  const titleWeight = vars.var5 || "600";
  const subtitleWeight = vars.var6 || "400";
  const titleOpacity = parseFloat(vars.var7) || 0.95;
  const subtitleOpacity = parseFloat(vars.var8) || 0.7;
  const paddingTop = Number(vars.var9) || 12;
  const paddingRight = Number(vars.var10) || 10;
  const paddingBottom = Number(vars.var11) || 8;
  const paddingLeft = Number(vars.var12) || 10;
  const borderRadiusTL = Number(vars.var13) || 16;
  const borderRadiusTR = Number(vars.var14) || 16;
  const borderRadiusBR = Number(vars.var15) || 0;
  const borderRadiusBL = Number(vars.var16) || 0;

  // Check if icon is an emoji (starts with non-ASCII) or MDI icon name
  const isEmoji = /^[\u{1F300}-\u{1FAFF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/u.test(icon);

  return (
    <div
      style={{
        width: template.width,
        height: template.height,
        padding: `${paddingTop}px ${paddingRight}px ${paddingBottom}px ${paddingLeft}px`,
        borderRadius: `${borderRadiusTL}px ${borderRadiusTR}px ${borderRadiusBR}px ${borderRadiusBL}px`,
        background: "rgba(255,255,255,0.06)",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        gap: 4,
      }}
    >
      {/* Title row with icon */}
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        {isEmoji ? (
          <span style={{ fontSize: `${titleSize * 1.2}em` }}>{icon}</span>
        ) : (
          <MdiIcon name={icon} size={titleSize * 20} color="rgba(255,255,255,0.9)" />
        )}
        <span
          style={{
            fontSize: `${titleSize}em`,
            fontWeight: titleWeight,
            opacity: titleOpacity,
            color: "#fff",
          }}
        >
          {instance.label}
        </span>
      </div>

      {/* Subtitle */}
      {subtitle && (
        <span
          style={{
            fontSize: `${subtitleSize}em`,
            fontWeight: subtitleWeight,
            opacity: subtitleOpacity,
            color: "#fff",
            marginLeft: isEmoji ? titleSize * 1.2 * 16 + 8 : titleSize * 20 + 8,
          }}
        >
          {subtitle}
        </span>
      )}
    </div>
  );
}
