/**
 * Deterministic Creator Theme Generator
 * Generates consistent, curated accent palettes for connected creators
 * without requiring any database storage or backend changes.
 */

export interface CreatorPalette {
  name: string;
  primary: string;
  secondary: string;
  soft: string;
  glow: string;
  border: string;
  badgeBg: string;
}

export const CREATOR_PALETTES: CreatorPalette[] = [
  // PALETTE A — ICE BLUE
  {
    name: "Ice Blue",
    primary: "#7DD3FC",
    secondary: "#38BDF8",
    soft: "#BAE6FD",
    glow: "rgba(56, 189, 248, 0.12)",
    border: "rgba(125, 211, 252, 0.25)",
    badgeBg: "rgba(56, 189, 248, 0.10)",
  },
  // PALETTE B — CYAN
  {
    name: "Cyan",
    primary: "#67E8F9",
    secondary: "#22D3EE",
    soft: "#CFFAFE",
    glow: "rgba(34, 211, 238, 0.12)",
    border: "rgba(103, 232, 249, 0.25)",
    badgeBg: "rgba(34, 211, 238, 0.10)",
  },
  // PALETTE C — LIGHT PURPLE
  {
    name: "Light Purple",
    primary: "#C4B5FD",
    secondary: "#A78BFA",
    soft: "#DDD6FE",
    glow: "rgba(167, 139, 250, 0.12)",
    border: "rgba(196, 181, 253, 0.25)",
    badgeBg: "rgba(167, 139, 250, 0.10)",
  },
  // PALETTE D — VIOLET
  {
    name: "Violet",
    primary: "#DDD6FE",
    secondary: "#8B5CF6",
    soft: "#EDE9FE",
    glow: "rgba(139, 92, 246, 0.12)",
    border: "rgba(221, 214, 254, 0.25)",
    badgeBg: "rgba(139, 92, 246, 0.10)",
  },
  // PALETTE E — MINT GREEN
  {
    name: "Mint Green",
    primary: "#86EFAC",
    secondary: "#4ADE80",
    soft: "#DCFCE7",
    glow: "rgba(74, 222, 128, 0.12)",
    border: "rgba(134, 239, 172, 0.25)",
    badgeBg: "rgba(74, 222, 128, 0.10)",
  },
  // PALETTE F — TEAL
  {
    name: "Teal",
    primary: "#5EEAD4",
    secondary: "#2DD4BF",
    soft: "#CCFBF1",
    glow: "rgba(45, 212, 191, 0.12)",
    border: "rgba(94, 234, 212, 0.25)",
    badgeBg: "rgba(45, 212, 191, 0.10)",
  },
  // PALETTE G — SKY BLUE
  {
    name: "Sky Blue",
    primary: "#93C5FD",
    secondary: "#60A5FA",
    soft: "#DBEAFE",
    glow: "rgba(96, 165, 250, 0.12)",
    border: "rgba(147, 197, 253, 0.25)",
    badgeBg: "rgba(96, 165, 250, 0.10)",
  },
  // PALETTE H — ROSE
  {
    name: "Rose",
    primary: "#FDA4AF",
    secondary: "#FB7185",
    soft: "#FFE4E6",
    glow: "rgba(251, 113, 133, 0.12)",
    border: "rgba(253, 164, 175, 0.25)",
    badgeBg: "rgba(251, 113, 133, 0.10)",
  },
];

/** Consistent non-secret analytics semantic tokens */
export const ANALYTICS_SEMANTICS = {
  views: "#7DD3FC",       // light blue
  watchTime: "#C4B5FD",   // light purple
  subscribers: "#86EFAC", // mint green
  retention: "#67E8F9",   // cyan fallback
  engagement: "#FDA4AF",  // soft pink/rose
  success: "#86EFAC",     // low risk / good
  warning: "#FCD34D",     // amber / medium risk
  danger: "#FDA4AF",      // soft coral / high drop-off
  info: "#7DD3FC",        // informational
  brand: "#ff1f3d",       // RetainAI core red
  neutral: "#FFFFFF",     // primary text
  muted: "rgba(255, 255, 255, 0.60)",
};

/** Deterministic string hash (djb2-like) */
function hashString(input: string): number {
  let hash = 5381;
  for (let i = 0; i < input.length; i++) {
    hash = ((hash << 5) + hash) + input.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

/**
 * Generates a stable, curated creator theme based on a stable channel/user ID.
 * The same creator will receive the exact same palette on every visit.
 */
export function generateCreatorTheme(identifier?: string | null): CreatorPalette {
  if (!identifier || identifier.trim() === "") {
    return CREATOR_PALETTES[0]; // Default to Ice Blue
  }
  const hash = hashString(identifier.trim());
  const index = hash % CREATOR_PALETTES.length;
  return CREATOR_PALETTES[index];
}

/**
 * Returns inline CSS variables for the creator theme to be applied to dashboard root
 */
export function getCreatorCssVariables(palette: CreatorPalette): React.CSSProperties {
  return {
    "--creator-primary": palette.primary,
    "--creator-secondary": palette.secondary,
    "--creator-soft": palette.soft,
    "--creator-glow": palette.glow,
    "--creator-border": palette.border,
    "--creator-badge-bg": palette.badgeBg,
  } as React.CSSProperties;
}
