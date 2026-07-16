export const tokens = {
  // Core surfaces - warm light product workspace
  bg: "#f7f7f3",
  bgCard: "#fffefa",
  bgElevated: "#f1f0ea",
  bgHover: "#efede6",
  bgActive: "#e9e6dd",

  // Borders - quiet warm structure
  border: "#ded9ce",
  borderSubtle: "#e8e4da",
  borderFaint: "rgba(45, 43, 38, 0.08)",
  borderLight: "rgba(45, 43, 38, 0.12)",
  borderHover: "#c8c1b4",

  // Text — crisp contrast on light surfaces
  text: "#24221e",
  textSecondary: "#555148",
  textMuted: "#767166",
  textDim: "#9b9589",

  // Accent — Skedio lavender-blue
  accent: "#8c99ec",
  accentHover: "#6f7ee4",
  accentMuted: "rgba(140, 153, 236, 0.14)",
  accentBorder: "rgba(140, 153, 236, 0.34)",

  // Semantic colors
  green: "#21b892",
  greenBg: "rgba(33, 184, 146, 0.1)",
  greenBorder: "rgba(33, 184, 146, 0.24)",
  greenText: "#147a63",

  red: "#e85d7a",
  redBg: "rgba(232, 93, 122, 0.1)",
  redBorder: "rgba(232, 93, 122, 0.25)",
  redText: "#a6324d",

  yellow: "#d99021",
  yellowBg: "rgba(217, 144, 33, 0.11)",
  yellowBorder: "rgba(217, 144, 33, 0.25)",
  yellowText: "#8a5a10",

  indigo: "#8c99ec",
  indigoBg: "rgba(140, 153, 236, 0.1)",
  indigoBorder: "rgba(140, 153, 236, 0.24)",

  // Overlay / glass — light blur
  glassBg: "rgba(255, 255, 255, 0.82)",
  glassBorder: "rgba(140, 153, 236, 0.18)",

  // Session states
  skipBg: "rgba(232, 93, 122, 0.08)",
  skipBorder: "rgba(232, 93, 122, 0.22)",
  doneBg: "rgba(33, 184, 146, 0.1)",
  doneBorder: "rgba(33, 184, 146, 0.24)",
  draftBg: "rgba(232, 93, 122, 0.12)",
  draftBorder: "rgba(232, 93, 122, 0.28)",

  // Blocker
  blockerBg: "rgba(88, 97, 116, 0.08)",
  blockerBorder: "rgba(88, 97, 116, 0.14)",
  blockerBorderLeft: "#8a94a8",

  // Shadows — refined depth system
  shadowSm: "0 1px 2px rgba(21, 24, 39, 0.06)",
  shadowMd: "0 8px 18px rgba(76, 88, 132, 0.08)",
  shadowLg: "0 18px 38px rgba(76, 88, 132, 0.11)",
  shadowXl: "0 24px 60px rgba(76, 88, 132, 0.14)",

  // Card shadows — subtle inset highlight + soft outer
  shadowCard: "inset 0 1px 0 rgba(255,255,255,0.8), 0 8px 22px rgba(76, 88, 132, 0.08)",
  shadowCardHover: "inset 0 1px 0 rgba(255,255,255,0.9), 0 14px 32px rgba(76, 88, 132, 0.13)",
  shadowDone: "inset 0 1px 0 rgba(33, 184, 146, 0.08), 0 6px 18px rgba(33, 184, 146, 0.09)",
  shadowDoneHover: "0 12px 28px rgba(33, 184, 146, 0.14), 0 0 0 1px rgba(33, 184, 146, 0.18)",

  // Sidebar
  sidebarBg: "#fbfaf5",
  sidebarBorder: "#ded9ce",

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
  zIndexTooltip: 250,
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
