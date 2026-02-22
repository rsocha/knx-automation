import { useGroupAddresses } from "@/hooks/useKnx";
import type { VseWidgetInstance, VseTemplate } from "@/types/vse";
import MdiIcon from "./MdiIcon";

interface Props {
  instance: VseWidgetInstance;
  template: VseTemplate;
}

function clamp01(x: number) {
  return Math.max(0, Math.min(1, x));
}

function getBorderColor(value: number, thresholdHigh: number, thresholdMed: number) {
  if (value <= 0) return "158,158,158";
  if (value >= thresholdHigh) return "255,235,59";
  if (value >= thresholdMed) return "255,193,7";
  return "76,175,80";
}

export default function VseGaugeBarometer({ instance, template }: Props) {
  const { data: addresses } = useGroupAddresses();

  const vars: Record<string, any> = {
    ...Object.fromEntries(Object.entries(template.variables).map(([k, v]) => [k, v.default])),
    ...instance.variableValues,
  };

  const min = Number(vars.var1) || 960;
  const max = Number(vars.var2) || 1060;
  const ringType: string = vars.var3 || "open";
  const pointerColor: string = vars.var4 || "255,193,7";
  const decimals = Number(vars.var5) || 1;
  const ringColor: string = vars.var6 || "60,60,60";
  const majorTicks = Number(vars.var7) || 10;
  const minorTicks = Number(vars.var8) || 5;
  const showValue = vars.var9 === "1" || vars.var9 === true;
  const showUnit = vars.var10 === "1" || vars.var10 === true;
  const gaugeSize = Number(vars.var11) || 90;
  const ringWidth = Number(vars.var12) || 6;
  const pointerWidth = Number(vars.var13) || 1.5;
  const pointerLengthPct = Number(vars.var14) || 85;
  const labelText = vars.var15 && vars.var15 !== "-" ? vars.var15 : "";
  const labelIcon = vars.var16 && vars.var16 !== "-" ? vars.var16 : "";
  const gaugeIcon: string = vars.var17 || "";
  const thresholdHigh = Number(vars.var18) || 2000;
  const thresholdMed = Number(vars.var19) || 500;
  const labelOpacity = Math.max(0, Math.min(100, Number(vars.var20) || 70)) / 100;
  const unitText: string = vars.unit || "mbar";

  // Read KO values
  const ko1Addr = instance.koBindings["ko1"];
  const ko2Addr = instance.koBindings["ko2"];
  const ga1 = addresses?.find((a) => a.address === ko1Addr);
  const ga2 = addresses?.find((a) => a.address === ko2Addr);

  const value = ga1?.value != null ? parseFloat(ga1.value) : min + (max - min) * 0.5;
  // KO2: Use null check instead of NaN to properly handle value=0
  const hasValue2 = ga2?.value != null && ga2.value !== "";
  const value2 = hasValue2 ? parseFloat(ga2.value) : NaN;

  const hasLabel = labelText !== "" || labelIcon !== "";
  const borderColor = getBorderColor(isNaN(value) ? 0 : value, thresholdHigh, thresholdMed);

  // Gauge angles
  let startAngle: number, totalAngle: number;
  if (ringType === "full") { startAngle = -90; totalAngle = 360; }
  else if (ringType === "half") { startAngle = -180; totalAngle = 180; }
  else { startAngle = -225; totalAngle = 270; }

  const cx = 50, cy = 50, radius = 44, labelRadius = 29;

  // Compute tick data
  const totalTickCount = minorTicks > 0 ? majorTicks * minorTicks : majorTicks;
  const minorInterval = minorTicks > 0 ? minorTicks : 1;

  const ticks: JSX.Element[] = [];
  for (let j = 0; j <= totalTickCount; j++) {
    const pct = j / totalTickCount;
    const angle = startAngle + pct * totalAngle;
    const rad = (angle * Math.PI) / 180;
    const isMajor = j % minorInterval === 0;
    if (minorTicks === 0 && !isMajor) continue;

    const tickOuter = radius + ringWidth / 2 - 1;
    const tickInner = isMajor ? radius - ringWidth / 2 - 2 : radius - ringWidth / 2 + 1;
    const sw = isMajor ? 1.5 : 0.75;
    const sc = isMajor ? "rgba(255,255,255,0.5)" : "rgba(255,255,255,0.25)";

    ticks.push(
      <line key={`t${j}`}
        x1={cx + tickOuter * Math.cos(rad)} y1={cy + tickOuter * Math.sin(rad)}
        x2={cx + tickInner * Math.cos(rad)} y2={cy + tickInner * Math.sin(rad)}
        stroke={sc} strokeWidth={sw} strokeLinecap="round"
      />
    );

    if (isMajor) {
      const majorIdx = j / minorInterval;
      const labelVal = min + (majorIdx / majorTicks) * (max - min);
      const lx = cx + labelRadius * Math.cos(rad);
      const ly = cy + labelRadius * Math.sin(rad);
      ticks.push(
        <text key={`l${j}`} x={lx} y={ly} fill="rgba(255,255,255,0.6)" fontSize={5} textAnchor="middle" dominantBaseline="middle">
          {Math.round(labelVal)}
        </text>
      );
    }
  }

  // Ring arc
  const arcLength = (totalAngle / 360) * 2 * Math.PI * radius;
  const totalCirc = 2 * Math.PI * radius;

  // Red zone segments (last 30%)
  const zoneStartPct = 70;
  const maxOpacity = 0.28;
  const zoneAngleStart = startAngle + (zoneStartPct / 100) * totalAngle;
  const zoneTotalAngle = startAngle + totalAngle - zoneAngleStart;
  const numSegments = 10;
  const segmentAngle = zoneTotalAngle / numSegments;

  const redZone: JSX.Element[] = [];
  for (let s = 0; s < numSegments; s++) {
    const t = s / (numSegments - 1);
    const eased = t * t * t;
    const opacity = maxOpacity * eased;
    const segStart = zoneAngleStart + s * segmentAngle;
    const segEnd = segStart + segmentAngle + 0.5;
    const startRad = (segStart * Math.PI) / 180;
    const endRad = (segEnd * Math.PI) / 180;
    const x1 = cx + radius * Math.cos(startRad);
    const y1 = cy + radius * Math.sin(startRad);
    const x2 = cx + radius * Math.cos(endRad);
    const y2 = cy + radius * Math.sin(endRad);
    redZone.push(
      <path key={`rz${s}`}
        d={`M ${x1.toFixed(2)} ${y1.toFixed(2)} A ${radius} ${radius} 0 0 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`}
        fill="none" stroke={`rgba(255,82,82,${opacity.toFixed(3)})`} strokeWidth={ringWidth} strokeLinecap="butt"
      />
    );
  }

  // Main pointer
  const pct = clamp01((value - min) / (max - min));
  const pAngle = startAngle + pct * totalAngle;
  const pRad = (pAngle * Math.PI) / 180;
  const pLen = radius * (pointerLengthPct / 100);
  const px = cx + pLen * Math.cos(pRad);
  const py = cy + pLen * Math.sin(pRad);
  const tailLen = 8;
  const tailX = cx - tailLen * Math.cos(pRad);
  const tailY = cy - tailLen * Math.sin(pRad);

  // KO2 reference pointer (white, thinner, shorter)
  let refPointer: JSX.Element | null = null;
  if (!isNaN(value2)) {
    const p2 = clamp01((value2 - min) / (max - min));
    const a2 = startAngle + p2 * totalAngle;
    const r2 = (a2 * Math.PI) / 180;
    let len2 = radius * ((pointerLengthPct - 12) / 100);
    len2 = Math.max(radius * 0.55, len2);
    const startOff = 4.2;
    const w = Math.max(0.7, pointerWidth * 0.75);
    refPointer = (
      <line
        x1={cx + startOff * Math.cos(r2)} y1={cy + startOff * Math.sin(r2)}
        x2={cx + len2 * Math.cos(r2)} y2={cy + len2 * Math.sin(r2)}
        stroke="rgba(255,255,255,0.85)" strokeWidth={w} strokeLinecap="round"
      />
    );
  }

  return (
    <div
      style={{
        width: template.width,
        height: template.height,
        borderRadius: 12,
        border: `1.5px solid rgba(${borderColor}, 0.45)`,
        background: "rgba(20,20,20,0.6)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: 4,
        boxSizing: "border-box",
        overflow: "hidden",
        position: "relative",
      }}
    >
      {/* Label */}
      {hasLabel && (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 4, marginBottom: 2, maxWidth: "95%" }}>
          {labelIcon && (
            <span style={{ fontSize: 14, opacity: 1, lineHeight: 1 }}>{labelIcon}</span>
          )}
          {labelText && (
            <span style={{ fontSize: 12, fontWeight: 500, color: `rgba(255,255,255,${labelOpacity})`, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {labelText}
            </span>
          )}
        </div>
      )}

      {/* Gauge SVG */}
      <div style={{ position: "relative", width: `${gaugeSize}%`, flex: 1, maxHeight: `calc(100% - ${hasLabel ? "20px" : "0px"})` }}>
        <svg viewBox="0 0 100 100" style={{ width: "100%", height: "100%" }}>
          {/* Base ring */}
          <circle
            cx={cx} cy={cy} r={radius} fill="none"
            stroke={`rgb(${ringColor})`} strokeWidth={ringWidth}
            strokeDasharray={`${arcLength} ${totalCirc}`} strokeDashoffset={0}
            strokeLinecap="butt"
            transform={`rotate(${startAngle} ${cx} ${cy})`}
          />
          {/* Red zone */}
          {redZone}
          {/* Ticks & labels */}
          {ticks}
          {/* KO2 reference pointer (white) */}
          {refPointer}
          {/* Main pointer */}
          <line
            x1={tailX} y1={tailY} x2={px} y2={py}
            stroke={`rgb(${pointerColor})`} strokeWidth={pointerWidth} strokeLinecap="butt"
            style={{ filter: `drop-shadow(0 0 3px rgba(${pointerColor},0.5))` }}
          />
          {/* Center dot */}
          <circle cx={cx} cy={cy} r={3} fill={`rgb(${pointerColor})`} />
          <circle cx={cx} cy={cy} r={1.2} fill="rgba(30,30,30,0.9)" />
        </svg>

        {/* Gauge icon overlay */}
        {gaugeIcon && gaugeIcon !== "-" && (
          <div style={{ position: "absolute", left: "50%", top: "35%", transform: "translate(-50%,-50%)", pointerEvents: "none", opacity: 0.3 }}>
            <MdiIcon name={gaugeIcon} size={30} />
          </div>
        )}

        {/* Value + Unit */}
        {(showValue || showUnit) && (
          <div style={{ position: "absolute", bottom: "2%", left: 0, width: "100%", textAlign: "center", pointerEvents: "none" }}>
            {showValue && (
              <div style={{ fontSize: 16, fontWeight: 600, color: "rgba(255,255,255,0.9)", lineHeight: 1.2 }}>
                {isNaN(value) ? "--" : value.toFixed(decimals)}
              </div>
            )}
            {showUnit && (
              <div style={{ fontSize: 12, color: "rgba(255,255,255,0.5)", marginTop: 2 }}>
                {unitText}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
