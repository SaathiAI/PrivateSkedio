export const tokens = {
  // Core surfaces — refined dark palette with subtle depth
  bg: "#0a0a0b",
  bgCard: "#111113",
  bgElevated: "#18181b",
  bgHover: "#1f1f23",
  bgActive: "#27272a",

  // Borders — subtle hierarchy
  border: "#27272a",
  borderSubtle: "#1f1f23",
  borderFaint: "rgba(255, 255, 255, 0.04)",
  borderLight: "rgba(255, 255, 255, 0.06)",
  borderHover: "#3f3f46",

  // Text — refined contrast
  text: "#fafafa",
  textSecondary: "#a1a1aa",
  textMuted: "#71717a",
  textDim: "#52525b",

  // Accent — indigo with refined shades
  accent: "#818cf8",
  accentHover: "#6366f1",
  accentMuted: "rgba(129, 140, 248, 0.12)",
  accentBorder: "rgba(129, 140, 248, 0.25)",

  // Semantic colors
  green: "#34d399",
  greenBg: "rgba(52, 211, 153, 0.08)",
  greenBorder: "rgba(52, 211, 153, 0.2)",
  greenText: "#6ee7b7",

  red: "#fb7185",
  redBg: "rgba(251, 113, 133, 0.08)",
  redBorder: "rgba(251, 113, 133, 0.25)",
  redText: "#fda4af",

  yellow: "#fbbf24",
  yellowBg: "rgba(251, 191, 36, 0.08)",
  yellowBorder: "rgba(251, 191, 36, 0.2)",
  yellowText: "#fde68a",

  indigo: "#818cf8",
  indigoBg: "rgba(129, 140, 248, 0.08)",
  indigoBorder: "rgba(129, 140, 248, 0.2)",

  // Overlay / glass — refined blur
  glassBg: "rgba(10, 10, 11, 0.88)",
  glassBorder: "rgba(255, 255, 255, 0.05)",

  // Session states
  skipBg: "rgba(251, 113, 133, 0.06)",
  skipBorder: "rgba(251, 113, 133, 0.18)",
  doneBg: "rgba(34, 197, 94, 0.06)",
  doneBorder: "rgba(34, 197, 94, 0.2)",
  draftBg: "rgba(251, 113, 133, 0.12)",
  draftBorder: "rgba(251, 113, 133, 0.3)",

  // Blocker
  blockerBg: "rgba(161, 161, 170, 0.06)",
  blockerBorder: "rgba(255, 255, 255, 0.04)",
  blockerBorderLeft: "#52525b",

  // Shadows — refined depth system
  shadowSm: "0 1px 2px rgba(0,0,0,0.3), 0 1px 3px rgba(0,0,0,0.15)",
  shadowMd: "0 4px 6px -1px rgba(0,0,0,0.3), 0 2px 4px -1px rgba(0,0,0,0.2)",
  shadowLg: "0 10px 15px -3px rgba(0,0,0,0.4), 0 4px 6px -2px rgba(0,0,0,0.2)",
  shadowXl: "0 20px 25px -5px rgba(0,0,0,0.5), 0 10px 10px -5px rgba(0,0,0,0.3)",

  // Card shadows — subtle inset highlight + soft outer
  shadowCard: "inset 0 1px 0 rgba(255,255,255,0.03), 0 2px 8px rgba(0,0,0,0.25)",
  shadowCardHover: "inset 0 1px 0 rgba(255,255,255,0.05), 0 8px 16px rgba(0,0,0,0.35)",
  shadowDone: "inset 0 1px 0 rgba(34, 197, 94, 0.06), 0 2px 6px rgba(0,0,0,0.2)",
  shadowDoneHover: "0 8px 16px rgba(0,0,0,0.25), 0 0 0 1px rgba(34, 197, 94, 0.2)",

  // Sidebar
  sidebarBg: "#0f0f11",
  sidebarBorder: "#1f1f23",

  // Spacing scale (4px base)
  space1: "4px",
  space2: "8px",
  space3: "12px",
  space4: "16px",
  space5: "20px",
  space6: "24px",
  space8: "32px",
  space10: "40px",
  space12: "48px",

  // Radius
  radiusSm: "6px",
  radiusMd: "8px",
  radiusLg: "12px",
  radiusXl: "16px",
  radiusFull: "9999px",

  // Transitions
  transitionFast: "0.12s cubic-bezier(0.4, 0, 0.2, 1)",
  transitionNormal: "0.2s cubic-bezier(0.4, 0, 0.2, 1)",
  transitionSlow: "0.3s cubic-bezier(0.4, 0, 0.2, 1)",

  // Z-index layers
  zIndexBase: 0,
  zIndexSticky: 10,
  zIndexDrawer: 50,
  zIndexModal: 100,
  zIndexToast: 200,
};

const PALETTE_POOL = [
  { bg: "rgba(168, 85, 247, 0.1)", border: "rgba(168, 85, 247, 0.25)", dot: "#c084fc", text: "#d8b4fe" },
  { bg: "rgba(56, 189, 248, 0.1)", border: "rgba(56, 189, 248, 0.25)", dot: "#38bdf8", text: "#bae6fd" },
  { bg: "rgba(251, 146, 60, 0.1)", border: "rgba(251, 146, 60, 0.25)", dot: "#fb923c", text: "#fed7aa" },
  { bg: "rgba(232, 121, 249, 0.1)", border: "rgba(232, 121, 249, 0.25)", dot: "#e879f9", text: "#f5d0fe" },
  { bg: "rgba(52, 211, 153, 0.1)", border: "rgba(52, 211, 153, 0.25)", dot: "#34d399", text: "#a7f3d0" },
  { bg: "rgba(251, 113, 133, 0.1)", border: "rgba(251, 113, 133, 0.25)", dot: "#fb7185", text: "#fecdd3" },
];

export const getSubjectPalette = (subject = "") => {
  const s = subject || "";
  const hash = s.split("").reduce((acc, ch) => acc + ch.charCodeAt(0), 0);
  return PALETTE_POOL[hash % PALETTE_POOL.length];
};
