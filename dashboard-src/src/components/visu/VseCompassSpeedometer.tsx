import { useGroupAddresses } from "@/hooks/useKnx";
import type { VseWidgetInstance, VseTemplate } from "@/types/vse";

interface Props {
  instance: VseWidgetInstance;
  template: VseTemplate;
}

function clamp(val: number, min: number, max: number) {
  return Math.max(min, Math.min(max, val));
}

function getBorderColor(value: number, thresholdHigh: number, thresholdMed: number, colors: {high: string, med: string, low: string, off: string}) {
  if (value <= 0) return colors.off;
  if (value >= thresholdHigh) return colors.high;
  if (value >= thresholdMed) return colors.med;
  return colors.low;
}

function degToCardinal(deg: number): string {
  const directions = ["N", "NNO", "NO", "ONO", "O", "OSO", "SO", "SSO", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
  const index = Math.round(((deg % 360) + 360) % 360 / 22.5) % 16;
  return directions[index];
}

export default function VseCompassSpeedometer({ instance, template }: Props) {
  const { data: addresses } = useGroupAddresses();

  const vars: Record<string, any> = {
    ...Object.fromEntries(Object.entries(template.variables).map(([k, v]) => [k, v.default])),
    ...instance.variableValues,
  };

  // Parse variables
  const testSpeed = Number(vars.var1) || 0;
  const testDirection = Number(vars.var2) || 0;
  const decimals = Number(vars.var3) || 1;
  const activeColor = vars.var4 || "100,149,237";
  const inactiveColor = vars.var5 || "100,100,100";
  const showDirection = vars.var6 === "1" || vars.var6 === true;
  const compassSize = Number(vars.var7) || 95;
  const thresholdHigh = Number(vars.var8) || 2000;
  const thresholdMed = Number(vars.var9) || 500;
  const colorHigh = vars.var10 || "255,235,59";
  const colorMed = vars.var11 || "255,193,7";
  const colorLow = vars.var12 || "76,175,80";
  const colorOff = vars.var13 || "158,158,158";
  const testDirectionGray = Number(vars.var14) || 0;
  const unit = vars.unit || "km/h";

  // Read KO values
  const ko1Addr = instance.koBindings["ko1"];
  const ko2Addr = instance.koBindings["ko2"];
  const ko3Addr = instance.koBindings["ko3"];
  
  const ga1 = addresses?.find((a) => a.address === ko1Addr);
  const ga2 = addresses?.find((a) => a.address === ko2Addr);
  const ga3 = addresses?.find((a) => a.address === ko3Addr);

  // Use KO values or test values
  const speed = ga1?.value != null ? parseFloat(ga1.value) : testSpeed;
  const directionBlue = ga2?.value != null ? parseFloat(ga2.value) : testDirection;
  const directionGray = ga3?.value != null ? parseFloat(ga3.value) : testDirectionGray;

  const borderColor = getBorderColor(speed, thresholdHigh, thresholdMed, {
    high: colorHigh,
    med: colorMed,
    low: colorLow,
    off: colorOff
  });

  const cx = 100;
  const cy = 100;
  const radius = 85;
  const innerRadius = 60;

  // Cardinal directions
  const cardinals = [
    { label: "N", angle: 0 },
    { label: "O", angle: 90 },
    { label: "S", angle: 180 },
    { label: "W", angle: 270 },
  ];

  // Tick marks
  const ticks: JSX.Element[] = [];
  for (let i = 0; i < 36; i++) {
    const angle = i * 10;
    const rad = ((angle - 90) * Math.PI) / 180;
    const isMajor = i % 9 === 0; // Every 90 degrees
    const isMinor = i % 3 === 0; // Every 30 degrees
    
    const outerR = radius - 2;
    const innerR = isMajor ? radius - 12 : isMinor ? radius - 8 : radius - 5;
    
    ticks.push(
      <line
        key={`tick-${i}`}
        x1={cx + outerR * Math.cos(rad)}
        y1={cy + outerR * Math.sin(rad)}
        x2={cx + innerR * Math.cos(rad)}
        y2={cy + innerR * Math.sin(rad)}
        stroke={isMajor ? "rgba(255,255,255,0.8)" : "rgba(255,255,255,0.3)"}
        strokeWidth={isMajor ? 2 : 1}
      />
    );
  }

  // Draw pointer (arrow shape)
  const drawPointer = (angle: number, color: string, key: string) => {
    const rad = ((angle - 90) * Math.PI) / 180;
    const tipR = radius - 15;
    const baseR = 15;
    const width = 8;
    
    // Arrow tip
    const tipX = cx + tipR * Math.cos(rad);
    const tipY = cy + tipR * Math.sin(rad);
    
    // Arrow base center
    const baseX = cx + baseR * Math.cos(rad);
    const baseY = cy + baseR * Math.sin(rad);
    
    // Perpendicular for arrow width
    const perpRad = rad + Math.PI / 2;
    const leftX = baseX + width * Math.cos(perpRad);
    const leftY = baseY + width * Math.sin(perpRad);
    const rightX = baseX - width * Math.cos(perpRad);
    const rightY = baseY - width * Math.sin(perpRad);
    
    return (
      <polygon
        key={key}
        points={`${tipX},${tipY} ${leftX},${leftY} ${rightX},${rightY}`}
        fill={`rgb(${color})`}
        stroke={`rgba(${color},0.8)`}
        strokeWidth={1}
        style={{ filter: `drop-shadow(0 0 4px rgba(${color},0.5))` }}
      />
    );
  };

  return (
    <div
      style={{
        width: template.width,
        height: template.height,
        borderRadius: 12,
        border: `2px solid rgba(${borderColor}, 0.5)`,
        background: "rgba(20,20,20,0.85)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <svg
        viewBox="0 0 200 200"
        style={{
          width: `${compassSize}%`,
          height: `${compassSize}%`,
        }}
      >
        {/* Outer ring */}
        <circle
          cx={cx}
          cy={cy}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.15)"
          strokeWidth={3}
        />
        
        {/* Inner circle */}
        <circle
          cx={cx}
          cy={cy}
          r={innerRadius}
          fill="rgba(0,0,0,0.3)"
          stroke="rgba(255,255,255,0.1)"
          strokeWidth={1}
        />

        {/* Tick marks */}
        {ticks}

        {/* Cardinal labels */}
        {cardinals.map((c) => {
          const rad = ((c.angle - 90) * Math.PI) / 180;
          const labelR = radius - 22;
          return (
            <text
              key={c.label}
              x={cx + labelR * Math.cos(rad)}
              y={cy + labelR * Math.sin(rad)}
              fill="rgba(255,255,255,0.9)"
              fontSize={14}
              fontWeight={700}
              textAnchor="middle"
              dominantBaseline="middle"
            >
              {c.label}
            </text>
          );
        })}

        {/* Gray pointer (ko3) */}
        {drawPointer(directionGray, inactiveColor, "gray-pointer")}
        
        {/* Blue pointer (ko2) */}
        {drawPointer(directionBlue, activeColor, "blue-pointer")}

        {/* Center dot */}
        <circle cx={cx} cy={cy} r={6} fill="rgba(255,255,255,0.9)" />
        <circle cx={cx} cy={cy} r={3} fill="rgba(30,30,30,0.9)" />

        {/* Speed display */}
        <text
          x={cx}
          y={cy + 30}
          fill="rgba(255,255,255,0.95)"
          fontSize={22}
          fontWeight={700}
          textAnchor="middle"
          dominantBaseline="middle"
        >
          {speed.toFixed(decimals)}
        </text>
        <text
          x={cx}
          y={cy + 48}
          fill="rgba(255,255,255,0.6)"
          fontSize={11}
          textAnchor="middle"
          dominantBaseline="middle"
        >
          {unit}
        </text>

        {/* Direction text */}
        {showDirection && (
          <text
            x={cx}
            y={cy - 25}
            fill={`rgb(${activeColor})`}
            fontSize={12}
            fontWeight={600}
            textAnchor="middle"
            dominantBaseline="middle"
          >
            {degToCardinal(directionBlue)} {Math.round(directionBlue)}°
          </text>
        )}
      </svg>
    </div>
  );
}
