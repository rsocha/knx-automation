import * as mdiIcons from "@mdi/js";

/**
 * Resolve an MDI icon name to its SVG path.
 * Accepts: "lightbulb", "light-bulb", "mdi:lightbulb", "mdiLightbulb"
 */
export function getMdiPath(name: string): string | null {
  if (!name || name === "-") return null;

  let clean = name.replace(/^mdi[:\-]/, "");

  const camel =
    "mdi" +
    clean
      .split(/[-_]/)
      .map((s) => s.charAt(0).toUpperCase() + s.slice(1).toLowerCase())
      .join("");

  const path = (mdiIcons as any)[camel];
  if (path && typeof path === "string") return path;

  const direct = (mdiIcons as any)[name];
  if (direct && typeof direct === "string") return direct;

  const lower = camel.toLowerCase();
  const key = Object.keys(mdiIcons).find((k) => k.toLowerCase() === lower);
  if (key) return (mdiIcons as any)[key];

  return null;
}

interface MdiIconProps {
  name: string;
  size?: number;
  color?: string;
  className?: string;
  style?: React.CSSProperties;
}

export default function MdiIcon({ name, size = 24, color, className, style }: MdiIconProps) {
  const path = getMdiPath(name);
  if (!path) return null;
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      className={className}
      style={{ ...style, fill: color || "currentColor" }}
    >
      <path d={path} />
    </svg>
  );
}
