import { tokens } from "../theme.js";

export function PlanHistoryView({ plans, onRefresh }) {
  const rawPlans = Array.isArray(plans) ? plans : (plans?.plans || []);

  const statusConfig = {
    ACTIVE:   { label: "Active",   dot: tokens.green,  bg: `${tokens.green}18`,   border: `${tokens.green}33`  },
    INACTIVE: { label: "Past",     dot: tokens.indigo, bg: `${tokens.indigo}14`,  border: `${tokens.indigo}33` },
    COMPLETE: { label: "Complete", dot: "#f59e0b",     bg: "rgba(245,158,11,0.1)", border: "rgba(245,158,11,0.3)" },
    UNKNOWN:  { label: "Unknown",  dot: tokens.textDim, bg: tokens.bg, border: tokens.border },
  };

  const formatDate = (d) => {
    if (!d) return "—";
    try { return new Date(d).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }); }
    catch { return d; }
  };

  if (rawPlans.length === 0) {
    return (
      <div style={{ animation: "fadeUp 0.3s ease" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 32 }}>
          <div>
            <h1 style={{ fontSize: 24, fontFamily: "'Fraunces', serif", fontStyle: "italic", color: tokens.text, margin: 0 }}>Plan History</h1>
            <div style={{ fontSize: 13, color: tokens.textMuted, marginTop: 4 }}>All your study plans</div>
          </div>
          <button onClick={onRefresh} style={{ padding: "8px 14px", background: "transparent", border: `1px solid ${tokens.border}`, borderRadius: 8, fontSize: 12, color: tokens.textMuted, cursor: "pointer" }}>↻ Refresh</button>
        </div>
        <div style={{ textAlign: "center", padding: "80px 0", color: tokens.textDim, border: `1px dashed ${tokens.border}`, borderRadius: 16 }}>
          <div style={{ fontSize: 36, marginBottom: 12 }}>📚</div>
          <div style={{ fontSize: 15, marginBottom: 6 }}>No plans yet</div>
          <div style={{ fontSize: 12, color: tokens.textDim }}>Open the AI Agent and ask it to create a study plan!</div>
        </div>
      </div>
    );
  }

  // Deduplicate by plan_id, prefer ACTIVE over INACTIVE
  const seen = new Map();
  for (const p of rawPlans) {
    const key = p.plan_id;
    if (!seen.has(key) || p.status === "ACTIVE") seen.set(key, p);
  }
  const deduped = Array.from(seen.values());

  return (
    <div style={{ animation: "fadeUp 0.3s ease" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 32 }}>
        <div>
          <h1 style={{ fontSize: 24, fontFamily: "'Fraunces', serif", fontStyle: "italic", color: tokens.text, margin: 0 }}>Plan History</h1>
          <div style={{ fontSize: 13, color: tokens.textMuted, marginTop: 4 }}>{deduped.length} plan{deduped.length !== 1 ? "s" : ""} found</div>
        </div>
        <button onClick={onRefresh} style={{ padding: "8px 14px", background: "transparent", border: `1px solid ${tokens.border}`, borderRadius: 8, fontSize: 12, color: tokens.textMuted, cursor: "pointer" }}
          onMouseEnter={e => e.currentTarget.style.borderColor = tokens.borderHover}
          onMouseLeave={e => e.currentTarget.style.borderColor = tokens.border}
        >↻ Refresh</button>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {deduped.map((plan, idx) => {
          const cfg = statusConfig[plan.status] || statusConfig.UNKNOWN;
          return (
            <div key={plan.plan_id} style={{
              background: tokens.bgCard, border: `1px solid ${tokens.border}`, borderRadius: 16,
              padding: "20px 24px", display: "flex", alignItems: "center", gap: 20,
              animation: `fadeUp 0.25s ease ${idx * 0.05}s both`,
              transition: "border-color 0.2s, box-shadow 0.2s",
            }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = tokens.borderHover; e.currentTarget.style.boxShadow = "0 4px 20px rgba(0,0,0,0.06)"; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = tokens.border; e.currentTarget.style.boxShadow = "none"; }}
            >
              {/* Left accent */}
              <div style={{ width: 4, height: 48, borderRadius: 4, background: cfg.dot, flexShrink: 0 }} />

              {/* Main info */}
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
                  <span style={{ fontSize: 15, fontWeight: 500, color: tokens.text }}>{plan.plan_name || "Untitled Plan"}</span>
                  <span style={{ fontSize: 11, fontWeight: 600, padding: "2px 8px", borderRadius: 100, background: cfg.bg, color: cfg.dot, border: `1px solid ${cfg.border}`, letterSpacing: "0.04em" }}>
                    {cfg.label}
                  </span>
                </div>
                <div style={{ display: "flex", gap: 20, fontSize: 12, color: tokens.textMuted }}>
                  <span>📅 {formatDate(plan.start_date)} → {formatDate(plan.planned_end_date)}</span>
                  {plan.estimated_duration > 0 && <span>⏱ {plan.estimated_duration} day{plan.estimated_duration !== 1 ? "s" : ""}</span>}
                  {plan.actual_end_date && <span style={{ color: tokens.green }}>✓ Ended {formatDate(plan.actual_end_date)}</span>}
                </div>
              </div>

              {/* Plan ID badge */}
              <div style={{ fontSize: 10, color: tokens.textDim, fontFamily: "'DM Mono', monospace", padding: "4px 8px", background: tokens.bg, borderRadius: 6, border: `1px solid ${tokens.border}` }}>
                {plan.plan_id}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
