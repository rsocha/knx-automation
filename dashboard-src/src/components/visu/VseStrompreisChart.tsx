import { useMemo } from "react";
import { useGroupAddresses } from "@/hooks/useKnx";
import type { VseWidgetInstance, VseTemplate } from "@/types/vse";

interface Props {
  instance: VseWidgetInstance;
  template: VseTemplate;
}

interface PriceEntry {
  t: number;
  p: number;
}

const BAR_THRESHOLDS = [
  { value: 2, color: "0,237,1" },
  { value: 4, color: "58,249,1" },
  { value: 6, color: "135,250,0" },
  { value: 8, color: "206,251,2" },
  { value: 10, color: "238,255,0" },
  { value: 12, color: "255,222,26" },
  { value: 14, color: "255,167,0" },
  { value: 16, color: "255,141,0" },
  { value: 18, color: "255,116,0" },
  { value: 20, color: "255,77,0" },
  { value: 24, color: "255,0,0" },
  { value: 28, color: "204,0,0" },
  { value: 32, color: "153,0,0" },
  { value: 40, color: "51,0,0" },
];

function getBarColor(value: number): string {
  let color = BAR_THRESHOLDS[0].color;
  for (const t of BAR_THRESHOLDS) {
    if (value >= t.value) color = t.color;
  }
  return color;
}

function getBorderColor(
  value: number,
  thresholdHigh: number,
  thresholdMed: number,
  colorLow: string,
  colorMed: string,
  colorHigh: string
): string {
  if (value >= thresholdHigh) return colorHigh;
  if (value >= thresholdMed) return colorMed;
  return colorLow;
}

function formatPrice(value: number | null, decimals: number): string {
  if (value === null || isNaN(value)) return "--";
  return value.toFixed(decimals).replace(".", ",");
}

function lightenRgb(rgb: string): string {
  const parts = rgb.split(",").map((s) => Math.min(255, parseInt(s.trim()) + 40));
  return `rgb(${parts.join(",")})`;
}

// Generate demo data for preview
function generateDemoData(): PriceEntry[] {
  const now = new Date();
  const start = new Date(now);
  start.setHours(0, 0, 0, 0);
  return Array.from({ length: 24 }, (_, h) => {
    const t = new Date(start);
    t.setHours(h);
    return { t: Math.floor(t.getTime() / 1000), p: 8 + Math.random() * 20 };
  });
}

// Get hour from Unix timestamp
// EPEX data stores local CET/CEST times as UTC timestamps, so we use getUTCHours()
function getDataHour(timestamp: number): number {
  return new Date(timestamp * 1000).getUTCHours();
}

// Get current hour in local timezone
function getCurrentLocalHour(): number {
  return new Date().getHours();
}

export default function VseStrompreisChart({ instance, template }: Props) {
  const { data: addresses } = useGroupAddresses();

  const vars = {
    ...Object.fromEntries(Object.entries(template.variables).map(([k, v]) => [k, v.default])),
    ...instance.variableValues,
  };

  const title = vars.var1 || "Stundenpreise heute";
  const decimals = Number(vars.var2) || 2;
  const transparent = vars.var3 === "1" || vars.var3 === true;
  const borderRadius = Number(vars.var4) || 16;
  const nowLabel = vars.var5 || "Jetzt";
  const nowColor = vars.var6 || "52,152,219";
  const thresholdHigh = Number(vars.var7) || 20;
  const thresholdMed = Number(vars.var8) || 15;
  const colorLow = vars.var9 || "76,175,80";
  const colorMed = vars.var10 || "255,193,7";
  const colorHigh = vars.var11 || "244,67,54";
  const showGlow = vars.var12 === "1" || vars.var12 === true;
  // Zeitzonen-Offset: 0 = EPEX Daten in lokaler Zeit, 1 = Daten in UTC
  const dataIsUTC = vars.var13 === "1" || vars.var13 === true || Number(vars.var13) === 1;

  // Parse JSON price data from KO
  const statusAddr = instance.koBindings["ko1"];
  const ga = addresses?.find((a) => a.address === statusAddr);

  const priceData = useMemo<PriceEntry[]>(() => {
    if (!ga?.value) return generateDemoData();
    try {
      const parsed = JSON.parse(ga.value);
      if (Array.isArray(parsed) && parsed.length > 0) return parsed;
    } catch {}
    return generateDemoData();
  }, [ga?.value]);

  // Process data
  // EPEX data usually has timestamps where the hour component represents local CET time
  // but stored as if it were UTC. So we use getUTCHours() to extract the "local" hour.
  const currentHour = getCurrentLocalHour();
  const hourlyPrices: Record<number, number> = {};
  let minPrice = Infinity, maxPrice = -Infinity, minHour = -1, maxHour = -1;

  for (const entry of priceData) {
    if (entry.t === undefined || entry.p === undefined) continue;
    // Use UTC hours for EPEX data (already represents local time)
    const hour = dataIsUTC ? new Date(entry.t * 1000).getHours() : getDataHour(entry.t);
    if (hourlyPrices[hour] === undefined) {
      hourlyPrices[hour] = entry.p;
      if (entry.p < minPrice) { minPrice = entry.p; minHour = hour; }
      if (entry.p > maxPrice) { maxPrice = entry.p; maxHour = hour; }
    }
  }

  const currentPrice = hourlyPrices[currentHour] ?? 15;
  if (minPrice === Infinity) minPrice = 12;
  if (maxPrice === -Infinity) maxPrice = 16;

  const yMax = Math.ceil(maxPrice);
  const yMin = Math.floor(minPrice);
  const yRange = Math.max(yMax - yMin, 1);
  const ySteps = Math.min(yRange, 5);

  const borderColor = getBorderColor(currentPrice, thresholdHigh, thresholdMed, colorLow, colorMed, colorHigh);

  return (
    <div
      style={{
        width: template.width,
        height: template.height,
        borderRadius,
        border: `1.5px solid rgba(${borderColor}, 0.45)`,
        background: transparent ? "transparent" : "rgba(255,255,255,0.06)",
        boxShadow: showGlow
          ? `0 8px 22px rgba(0,0,0,0.24), 0 0 18px rgba(${borderColor}, 0.14)`
          : "0 4px 12px rgba(0,0,0,0.15)",
        fontFamily: "sans-serif",
        color: "#fff",
        padding: "8px 16px 16px 16px",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      {/* Title */}
      <div style={{ fontSize: 14, fontWeight: 400, opacity: 0.8, marginBottom: 8 }}>{title}</div>

      {/* Header: Aktuell / Min / Max */}
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
        <PriceLabel label="Aktuell" price={currentPrice} decimals={decimals} />
        <PriceLabel label="Min" price={minPrice} decimals={decimals} align="center" />
        <PriceLabel label="Max" price={maxPrice} decimals={decimals} align="right" />
      </div>

      {/* Chart */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0, position: "relative" }}>
        <div style={{ flex: 1, display: "flex", minHeight: 0, position: "relative" }}>
          {/* Y axis */}
          <div style={{ width: 28, display: "flex", flexDirection: "column", justifyContent: "space-between", paddingRight: 4, fontSize: 10, opacity: 0.5, marginLeft: 4 }}>
            {Array.from({ length: ySteps + 1 }, (_, i) => {
              const val = yMin + (yRange / ySteps) * (ySteps - i);
              return <span key={i} style={{ textAlign: "right" }}>{Math.round(val)}</span>;
            })}
          </div>

          {/* Chart area */}
          <div style={{ flex: 1, position: "relative" }}>
            {/* Grid lines */}
            {Array.from({ length: ySteps + 1 }, (_, i) => (
              <div
                key={i}
                style={{
                  position: "absolute", left: 0, right: 0,
                  bottom: `${(i / ySteps) * 100}%`,
                  borderBottom: "1px dashed rgba(255,255,255,0.15)",
                }}
              />
            ))}

            {/* Bars */}
            <div style={{ position: "absolute", left: 0, right: 20, top: 25, bottom: 25, display: "flex", alignItems: "flex-end", gap: 2 }}>
              {Array.from({ length: 24 }, (_, hour) => {
                const price = hourlyPrices[hour];
                const hasPrice = price !== undefined && !isNaN(price);
                const barHeight = hasPrice ? Math.max(0, Math.min(100, ((price - yMin) / yRange) * 100)) : 0;
                const barColor = hasPrice ? getBarColor(price) : "128,128,128";
                const isNow = hour === currentHour;
                const isMax = hour === maxHour && hasPrice;
                const isMin = hour === minHour && hasPrice;

                return (
                  <div key={hour} style={{ flex: 1, height: "100%", position: "relative", display: "flex", flexDirection: "column", justifyContent: "flex-end", alignItems: "center" }}>
                    {/* Now marker */}
                    {isNow && (
                      <>
                        <div style={{ position: "absolute", top: -25, bottom: -25, left: "50%", transform: "translateX(-50%)", borderLeft: `2px dashed rgba(${nowColor}, 0.8)`, zIndex: 20, pointerEvents: "none" }} />
                        <div style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)", fontSize: 10, fontWeight: 600, color: "#fff", whiteSpace: "nowrap", background: `rgba(${nowColor}, 1)`, padding: "2px 6px", borderRadius: 4, zIndex: 25, boxShadow: "0 2px 4px rgba(0,0,0,0.3)" }}>{nowLabel}</div>
                      </>
                    )}

                    {/* Max tooltip */}
                    {isMax && (
                      <div style={{ position: "absolute", bottom: `${barHeight}%`, left: "50%", transform: "translate(-50%, -100%)", display: "flex", flexDirection: "column", alignItems: "center", zIndex: 10 }}>
                        <div style={{ background: `rgba(${nowColor}, 1)`, color: "#fff", padding: "2px 6px", borderRadius: 4, fontSize: 9, whiteSpace: "nowrap" }}>{formatPrice(price, decimals)}</div>
                        <div style={{ width: 8, height: 8, borderRadius: "50%", border: `2px solid rgb(${barColor})`, marginTop: 2 }} />
                      </div>
                    )}

                    {/* Bar */}
                    {hasPrice && (
                      <div style={{
                        width: "100%", maxWidth: 20,
                        height: `${barHeight}%`,
                        background: `linear-gradient(to top, rgb(${barColor}), ${lightenRgb(barColor)})`,
                        borderRadius: "3px 3px 0 0",
                        minHeight: 2,
                      }} />
                    )}

                    {/* Min tooltip */}
                    {isMin && (
                      <div style={{ position: "absolute", bottom: 0, left: "50%", transform: "translate(-50%, 100%)", display: "flex", flexDirection: "column", alignItems: "center", zIndex: 10 }}>
                        <div style={{ width: 8, height: 8, borderRadius: "50%", border: `2px solid rgb(${barColor})`, marginBottom: 2 }} />
                        <div style={{ background: `rgba(${nowColor}, 1)`, color: "#fff", padding: "2px 6px", borderRadius: 4, fontSize: 9, whiteSpace: "nowrap" }}>{formatPrice(price, decimals)}</div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* X axis */}
        <div style={{ display: "flex", marginLeft: 32, marginRight: 20, marginTop: 6, borderTop: "1px solid rgba(255,255,255,0.2)", paddingTop: 4 }}>
          {Array.from({ length: 24 }, (_, h) => (
            <div key={h} style={{ flex: 1, textAlign: "center", fontSize: 8, opacity: 0.5 }}>
              {h % 3 === 0 ? `${String(h).padStart(2, "0")}:00` : ""}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function PriceLabel({ label, price, decimals, align = "left" }: { label: string; price: number; decimals: number; align?: string }) {
  const color = getBarColor(price);
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: align === "center" ? "center" : align === "right" ? "flex-end" : "flex-start" }}>
      <div>
        <span style={{ color: `rgb(${color})`, fontSize: 22, fontWeight: 600 }}>{formatPrice(price, decimals)}</span>
        <span style={{ color: `rgb(${color})`, fontSize: 12, opacity: 0.8 }}>ct/kWh</span>
      </div>
      <span style={{ opacity: 0.5, fontSize: 11 }}>{label}</span>
    </div>
  );
}
