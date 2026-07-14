import { tokens } from "../theme.js";

export function Spinner({ size = 16 }) {
  return (
    <div style={{
      width: size, height: size, borderRadius: "50%",
      border: `2px solid ${tokens.border}`, borderTopColor: tokens.accent,
      animation: "spin 0.6s linear infinite", flexShrink: 0,
    }} />
  );
}

export function IconButton({ title, active, children, onClick, style }) {
  return (
    <button
      title={title}
      className="sidebar-icon-btn"
      onClick={onClick}
      style={{
        color: active ? tokens.text : tokens.textMuted,
        background: active ? tokens.accentMuted : "transparent",
        ...style,
      }}
    >
      {children}
    </button>
  );
}

export function StatusBadge({ children, background, border, color, style }) {
  return (
    <div style={{
      padding: `${tokens.space1} ${tokens.space3}`,
      borderRadius: tokens.radiusFull,
      background,
      border: `1px solid ${border}`,
      color,
      fontSize: 11,
      fontWeight: 500,
      ...style,
    }}>
      {children}
    </div>
  );
}

export function Toast({ children }) {
  if (!children) return null;
  return (
    <div style={{
      position: "fixed", bottom: 24, left: "50%", transform: "translateX(-50%)",
      background: tokens.bgElevated, color: tokens.text,
      padding: `${tokens.space3} ${tokens.space5}`,
      borderRadius: tokens.radiusLg,
      fontSize: 13, fontWeight: 500,
      zIndex: tokens.zIndexToast,
      animation: "fadeUp 0.2s cubic-bezier(0.16, 1, 0.3, 1)",
      boxShadow: tokens.shadowXl,
      border: `1px solid ${tokens.borderSubtle}`,
    }}>{children}</div>
  );
}
