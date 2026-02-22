import yaml from "js-yaml";

export interface ParsedHACard {
  id: string;
  type: string;
  entity?: string;
  primary?: string;
  secondary?: string;
  icon?: string;
  iconColor?: string;
  layout?: string;
  tapAction?: string;
  badgeIcon?: string;
  badgeColor?: string;
  activeColor?: string;
  inactiveColor?: string;
  children?: ParsedHACard[];
  raw: Record<string, any>;
}

let idCounter = 0;

function extractColor(val: string | undefined): string | undefined {
  if (!val) return undefined;
  // Extract static color from Jinja template
  const colors: Record<string, string> = {
    yellow: "255,193,7",
    green: "76,175,80",
    red: "244,67,54",
    blue: "33,150,243",
    orange: "255,152,0",
    purple: "156,39,176",
    grey: "158,158,158",
    white: "255,255,255",
  };
  const cleaned = val.replace(/\{%.*?%\}/gs, "").trim();
  for (const [name, rgb] of Object.entries(colors)) {
    if (cleaned.includes(name) || val.includes(name)) return rgb;
  }
  return undefined;
}

function extractStaticText(val: string | undefined): string {
  if (!val) return "";
  // Remove Jinja tags, get static parts
  return val
    .replace(/\{%[\s\S]*?%\}/g, "")
    .replace(/\{\{[\s\S]*?\}\}/g, "")
    .replace(/\|/g, "")
    .trim();
}

function parseCard(cardData: Record<string, any>): ParsedHACard {
  const id = `ha-${++idCounter}`;
  const type = cardData.type || "unknown";

  const card: ParsedHACard = {
    id,
    type,
    entity: cardData.entity,
    primary: cardData.primary || cardData.title,
    secondary: extractStaticText(cardData.secondary || cardData.subtitle),
    icon: cardData.icon,
    iconColor: extractColor(cardData.icon_color),
    layout: cardData.layout,
    tapAction: cardData.tap_action?.action,
    badgeIcon: cardData.badge_icon ? extractStaticText(cardData.badge_icon) : undefined,
    badgeColor: extractColor(cardData.badge_color),
    activeColor: extractColor(cardData.icon_color),
    inactiveColor: "158,158,158",
    raw: cardData,
  };

  // Recurse into children
  const childCards = cardData.cards || [];
  if (childCards.length > 0) {
    card.children = childCards.map((c: Record<string, any>) => parseCard(c));
  }

  return card;
}

/**
 * Flatten all leaf cards (non-container) from a parsed tree
 */
function flattenCards(card: ParsedHACard): ParsedHACard[] {
  const isContainer =
    card.type.includes("stack-in-card") ||
    card.type.includes("layout-card") ||
    card.type.includes("vertical-stack") ||
    card.type.includes("horizontal-stack") ||
    card.type.includes("grid");

  if (isContainer && card.children && card.children.length > 0) {
    return card.children.flatMap(flattenCards);
  }
  return [card];
}

export function parseHAYaml(yamlStr: string): ParsedHACard[] {
  idCounter = 0;
  try {
    const parsed = yaml.load(yamlStr) as Record<string, any>;
    if (!parsed || typeof parsed !== "object") return [];

    // Could be a single card or array
    const rootCard = parseCard(parsed);
    return flattenCards(rootCard);
  } catch (err) {
    console.error("YAML parse error:", err);
    return [];
  }
}

/**
 * Map HA card type to VSE template type
 */
export function mapToVseType(card: ParsedHACard): string {
  if (card.type.includes("title")) return "titleCard";
  if (card.tapAction === "toggle") return "switchCard";
  if (card.type.includes("light")) return "switchCard";
  if (card.type.includes("climate")) return "switchCard";
  return "switchCard"; // Default fallback
}

/**
 * Extract suggested variable values from HA card
 */
export function extractVseVariables(card: ParsedHACard): Record<string, any> {
  const vars: Record<string, any> = {};
  if (card.activeColor) vars.var3 = card.activeColor;
  if (card.inactiveColor) vars.var4 = card.inactiveColor;
  if (card.iconColor) {
    vars.var3 = card.iconColor;
  }
  return vars;
}
