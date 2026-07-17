import { useEffect, useMemo, useState } from "react";
import { tokens } from "../theme.js";
import { backlogApi } from "../lib/backlogApi.js";
import { planApi } from "../lib/planApi.js";
import {
  normalizeAllocationSummary,
  normalizeChapterBacklog,
} from "../lib/dashboardAdapters.js";

function DashboardSection({ title, subtitle, actions, children, style }) {
  return (
    <section
      style={{
        background: tokens.bgCard,
        border: `1px solid ${tokens.border}`,
        borderRadius: 20,
        boxShadow: tokens.shadowCard,
        padding: 24,
        ...style,
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16, marginBottom: 18 }}>
        <div>
          <div style={{ fontSize: 15, fontWeight: 700, color: tokens.text, marginBottom: 4 }}>{title}</div>
          {subtitle ? (
            <div style={{ fontSize: 12, lineHeight: 1.55, color: tokens.textMuted, maxWidth: 420 }}>{subtitle}</div>
          ) : null}
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}

function DashboardStat({ label, value, detail, tone = "accent", delay = 0 }) {
  const toneMap = {
    accent: {
      badge: tokens.accentMuted,
      border: tokens.accentBorder,
      ink: tokens.accentHover,
    },
    success: {
      badge: tokens.greenBg,
      border: tokens.greenBorder,
      ink: tokens.greenText,
    },
    warning: {
      badge: tokens.yellowBg,
      border: tokens.yellowBorder,
      ink: tokens.yellowText,
    },
    danger: {
      badge: tokens.redBg,
      border: tokens.redBorder,
      ink: tokens.redText,
    },
  };

  const palette = toneMap[tone] || toneMap.accent;

  return (
    <div
      style={{
        background: tokens.bgCard,
        border: `1px solid ${tokens.border}`,
        borderRadius: 18,
        boxShadow: tokens.shadowCard,
        padding: 20,
        minHeight: 148,
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        animation: `fadeUp 0.45s cubic-bezier(0.22, 1, 0.36, 1) ${delay}ms both`,
      }}
    >
      <div
        style={{
          width: 16,
          height: 16,
          borderRadius: 999,
          background: palette.badge,
          border: `1px solid ${palette.border}`,
        }}
      />
      <div>
        <div style={{ fontSize: 12, color: tokens.textMuted, marginBottom: 10 }}>{label}</div>
        <div
          style={{
            fontSize: 38,
            lineHeight: 0.98,
            fontFamily: "'Fraunces', serif",
            color: tokens.text,
            marginBottom: 8,
          }}
        >
          {value}
        </div>
        <div style={{ fontSize: 12, lineHeight: 1.55, color: palette.ink }}>{detail}</div>
      </div>
    </div>
  );
}

function AnimatedProgressLine({ points, width = 720, height = 250 }) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const id = window.setTimeout(() => setMounted(true), 80);
    return () => window.clearTimeout(id);
  }, []);

  const padding = { top: 16, right: 18, bottom: 32, left: 16 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;
  const maxValue = Math.max(...points.map(point => point.value), 1);

  const coordinates = points.map((point, index) => {
    const x = padding.left + ((chartWidth / Math.max(points.length - 1, 1)) * index);
    const y = padding.top + chartHeight - ((point.value / maxValue) * chartHeight);
    return { ...point, x, y };
  });

  const linePath = coordinates.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");
  const areaPath = `${linePath} L ${coordinates[coordinates.length - 1]?.x ?? padding.left} ${padding.top + chartHeight} L ${coordinates[0]?.x ?? padding.left} ${padding.top + chartHeight} Z`;
  const pathLength = Math.max(points.length * 96, 240);

  return (
    <div style={{ position: "relative" }}>
      <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
        <defs>
          <linearGradient id="skedio-dashboard-area" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="rgba(140, 153, 236, 0.22)" />
            <stop offset="100%" stopColor="rgba(140, 153, 236, 0.02)" />
          </linearGradient>
          <filter id="skedio-dashboard-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {[0.25, 0.5, 0.75, 1].map(step => (
          <line
            key={step}
            x1={padding.left}
            x2={width - padding.right}
            y1={padding.top + chartHeight * step}
            y2={padding.top + chartHeight * step}
            stroke={tokens.borderSubtle}
            strokeWidth="1"
          />
        ))}

        <path d={areaPath} fill="url(#skedio-dashboard-area)" opacity={mounted ? 1 : 0} style={{ transition: "opacity 500ms ease" }} />

        <path
          d={linePath}
          fill="none"
          stroke={tokens.accent}
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
          filter="url(#skedio-dashboard-glow)"
          style={{
            strokeDasharray: pathLength,
            strokeDashoffset: mounted ? 0 : pathLength,
            transition: "stroke-dashoffset 1200ms cubic-bezier(0.22, 1, 0.36, 1)",
          }}
        />

        {coordinates.map((point, index) => (
          <g
            key={point.label}
            style={{
              opacity: mounted ? 1 : 0,
              transform: mounted ? "translateY(0px)" : "translateY(6px)",
              transition: `opacity 320ms ease ${180 + index * 70}ms, transform 420ms cubic-bezier(0.22, 1, 0.36, 1) ${180 + index * 70}ms`,
            }}
          >
            <circle cx={point.x} cy={point.y} r="5.5" fill={tokens.bgCard} stroke={tokens.accent} strokeWidth="2.5" />
            <circle cx={point.x} cy={point.y} r="2.25" fill={tokens.accent} />
            <text x={point.x} y={height - 8} textAnchor="middle" fontSize="11" fill={tokens.textMuted}>
              {point.label}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}

function SubjectProgressList({ topicBreakdown }) {
  const total = topicBreakdown.reduce((sum, item) => sum + (item.hours || 0), 0);
  const palette = [tokens.accent, tokens.green, tokens.yellow, tokens.red];

  if (topicBreakdown.length === 0) {
    return <div style={{ fontSize: 13, color: tokens.textMuted }}>Progress will appear here once study hours start landing against subjects.</div>;
  }

  return (
    <div style={{ display: "grid", gap: 14 }}>
      {topicBreakdown.slice(0, 5).map((item, index) => {
        const pct = total > 0 ? Math.round(((item.hours || 0) / total) * 100) : 0;
        const color = palette[index % palette.length];

        return (
          <div key={`${item.topic}-${index}`}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 8 }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: tokens.text, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {item.topic}
                </div>
                <div style={{ fontSize: 11, color: tokens.textMuted }}>{item.hours || 0} hours recorded</div>
              </div>
              <div style={{ fontSize: 12, fontWeight: 700, color }}>{pct}%</div>
            </div>
            <div style={{ height: 7, borderRadius: 999, background: tokens.bgHover, overflow: "hidden" }}>
              <div
                style={{
                  width: `${pct}%`,
                  height: "100%",
                  borderRadius: 999,
                  background: color,
                  transition: "width 800ms cubic-bezier(0.22, 1, 0.36, 1)",
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function AllocationList({ allocation }) {
  if (allocation.length === 0) {
    return <div style={{ fontSize: 13, color: tokens.textMuted }}>Allocation detail will show once plan targets sync into the dashboard.</div>;
  }

  return (
    <div style={{ display: "grid", gap: 12 }}>
      {allocation.slice(0, 4).map((item, index) => {
        const estimated = Number(item.estimated_hours || 0);
        const completed = Number(item.completed_hours || 0);
        const pct = estimated > 0 ? Math.min(100, Math.round((completed / estimated) * 100)) : 0;

        return (
          <div
            key={`${item.chapter}-${index}`}
            style={{
              padding: 14,
              borderRadius: 14,
              background: index === 0 ? tokens.accentMuted : tokens.bg,
              border: `1px solid ${index === 0 ? tokens.accentBorder : tokens.borderSubtle}`,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 8 }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: tokens.text, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {item.chapter || "Untitled chapter"}
                </div>
                <div style={{ fontSize: 11, color: tokens.textMuted }}>{item.subject || "Subject stream"}</div>
              </div>
              <div style={{ fontSize: 12, fontWeight: 700, color: tokens.text }}>{completed}h / {estimated}h</div>
            </div>
            <div style={{ height: 6, borderRadius: 999, background: "rgba(36, 34, 30, 0.08)", overflow: "hidden", marginBottom: 8 }}>
              <div style={{ width: `${pct}%`, height: "100%", borderRadius: 999, background: tokens.accent }} />
            </div>
            <div style={{ fontSize: 11, color: tokens.textMuted }}>{item.scheduled_hours || 0} hours already scheduled</div>
          </div>
        );
      })}
    </div>
  );
}

function BacklogList({ chapters }) {
  const entries = Object.entries(chapters || {}).flatMap(([chapter, items]) =>
    (Array.isArray(items) ? items : []).map(item => ({
      chapter,
      name: item?.name || "Unnamed item",
      status: String(item?.status || "unknown").toLowerCase(),
    })),
  );

  const sortedEntries = entries.sort((a, b) => {
    const order = { pending: 0, unknown: 1, done: 2 };
    return (order[a.status] ?? 3) - (order[b.status] ?? 3);
  });

  if (sortedEntries.length === 0) {
    return <div style={{ fontSize: 13, color: tokens.textMuted }}>No backlog pressure right now. This is exactly the kind of calm we like.</div>;
  }

  return (
    <div style={{ display: "grid", gap: 12 }}>
      {sortedEntries.slice(0, 5).map((entry, index) => {
        const isDone = entry.status === "done";
        return (
          <div
            key={`${entry.chapter}-${entry.name}-${index}`}
            style={{
              padding: 14,
              borderRadius: 14,
              background: isDone ? tokens.greenBg : index === 0 ? tokens.redBg : tokens.bg,
              border: `1px solid ${isDone ? tokens.greenBorder : index === 0 ? tokens.redBorder : tokens.borderSubtle}`,
              display: "flex",
              alignItems: "flex-start",
              justifyContent: "space-between",
              gap: 12,
            }}
          >
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: tokens.text, marginBottom: 4 }}>{entry.name}</div>
              <div style={{ fontSize: 11, color: tokens.textMuted }}>{entry.chapter}</div>
            </div>
            <div
              style={{
                fontSize: 11,
                fontWeight: 700,
                borderRadius: 999,
                padding: "5px 9px",
                background: isDone ? tokens.greenBg : entry.status === "pending" ? tokens.redBg : tokens.bgHover,
                color: isDone ? tokens.greenText : entry.status === "pending" ? tokens.redText : tokens.textMuted,
                border: `1px solid ${isDone ? tokens.greenBorder : entry.status === "pending" ? tokens.redBorder : tokens.borderSubtle}`,
                textTransform: "capitalize",
                flexShrink: 0,
              }}
            >
              {entry.status}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function formatExamWindow(daysUntilExam, examDate) {
  if (!examDate && daysUntilExam == null) return "No exam deadline synced yet";
  if (daysUntilExam == null) return examDate;
  if (daysUntilExam <= 0) return `Exam window is here${examDate ? ` · ${examDate}` : ""}`;
  return `${daysUntilExam} days until the next exam${examDate ? ` · ${examDate}` : ""}`;
}

export function DashboardTabV2({ stats, examDate, daysUntilExam }) {
  const hoursStudied = Number(stats?.hours_studied || 0);
  const hoursTarget = Number(stats?.hours_target || 0);
  const hoursRemaining = Number(stats?.hours_remaining || 0);
  const subtopicsDone = Number(stats?.subtopics_done || 0);
  const totalSubtopics = Number(stats?.total_subtopics || 0);
  const sessionsDone = Number(stats?.sessions_completed || 0);
  const totalSessions = Number(stats?.total_sessions || 0);
  const dailyHours = Array.isArray(stats?.daily_hours) ? stats.daily_hours : [];
  const topicBreakdown = Array.isArray(stats?.topic_breakdown) ? stats.topic_breakdown : [];

  const [allocation, setAllocation] = useState([]);
  const [backlog, setBacklog] = useState({ chapters: {} });

  useEffect(() => {
    let cancelled = false;

    planApi
      .allocationSummary()
      .then(data => {
        if (!cancelled) setAllocation(normalizeAllocationSummary(data));
      })
      .catch(() => {
        if (!cancelled) setAllocation([]);
      });

    backlogApi
      .chapters()
      .then(data => {
        if (!cancelled) setBacklog({ chapters: normalizeChapterBacklog(data) });
      })
      .catch(() => {
        if (!cancelled) setBacklog({ chapters: {} });
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const percentToGoal = hoursTarget > 0 ? Math.round((hoursStudied / hoursTarget) * 100) : 0;
  const pendingSessions = Math.max(totalSessions - sessionsDone, 0);
  const subtopicPercent = totalSubtopics > 0 ? Math.round((subtopicsDone / totalSubtopics) * 100) : 0;

  const chartPoints = useMemo(() => {
    const labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

    if (dailyHours.length === 0) {
      return labels.map((label, index) => ({
        label,
        value: [1.2, 2.8, 2.1, 3.4, 2.6, 4.1, 3.2][index],
      }));
    }

    const recent = dailyHours.slice(-7);
    return recent.map((item, index) => ({
      label: item?.date
        ? new Date(`${item.date}T12:00:00`).toLocaleDateString("en-US", { weekday: "short" })
        : labels[index] || `Day ${index + 1}`,
      value: Number(item?.hours || 0),
    }));
  }, [dailyHours]);

  const strongestDay = useMemo(() => {
    return chartPoints.reduce((best, point) => (point.value > (best?.value ?? -1) ? point : best), null);
  }, [chartPoints]);

  return (
    <div style={{ display: "grid", gap: 18, animation: "fadeUp 0.32s ease" }}>
      <section
        style={{
          background: "linear-gradient(180deg, rgba(255,255,250,0.98) 0%, rgba(248,247,242,0.98) 100%)",
          border: `1px solid ${tokens.border}`,
          borderRadius: 24,
          boxShadow: tokens.shadowCard,
          padding: 24,
        }}
      >
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 18, flexWrap: "wrap" }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 11, letterSpacing: "0.16em", textTransform: "uppercase", color: tokens.accent, marginBottom: 10 }}>
              Dashboard
            </div>
            <div style={{ fontSize: 42, lineHeight: 0.98, fontFamily: "'Fraunces', serif", color: tokens.text, marginBottom: 10 }}>
              Study momentum at a glance
            </div>
            <div style={{ fontSize: 14, lineHeight: 1.65, color: tokens.textSecondary, maxWidth: 620 }}>
              Track what has moved, what is slipping, and where the next useful hour should land.
            </div>
          </div>
          <div
            style={{
              padding: "11px 14px",
              borderRadius: 16,
              background: daysUntilExam != null && daysUntilExam <= 7 ? tokens.redBg : tokens.accentMuted,
              border: `1px solid ${daysUntilExam != null && daysUntilExam <= 7 ? tokens.redBorder : tokens.accentBorder}`,
              minWidth: 220,
            }}
          >
            <div style={{ fontSize: 11, letterSpacing: "0.14em", textTransform: "uppercase", color: daysUntilExam != null && daysUntilExam <= 7 ? tokens.redText : tokens.accentHover, marginBottom: 6 }}>
              Exam window
            </div>
            <div style={{ fontSize: 13, lineHeight: 1.55, color: tokens.text }}>
              {formatExamWindow(daysUntilExam, examDate)}
            </div>
          </div>
        </div>
      </section>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 16 }}>
        <DashboardStat
          label="Study hours logged"
          value={`${hoursStudied}h`}
          detail={hoursTarget > 0 ? `${percentToGoal}% of the current goal is already real.` : "Hours will stack here as sessions complete."}
          tone="accent"
          delay={0}
        />
        <DashboardStat
          label="Sessions completed"
          value={sessionsDone}
          detail={totalSessions > 0 ? `${pendingSessions} sessions still waiting in the week.` : "No sessions have been scheduled yet."}
          tone="success"
          delay={60}
        />
        <DashboardStat
          label="Pending load"
          value={`${hoursRemaining}h`}
          detail={pendingSessions > 0 ? `Spread across ${pendingSessions} remaining sessions.` : "Nothing is hanging loose right now."}
          tone="warning"
          delay={120}
        />
        <DashboardStat
          label="Subtopics secured"
          value={subtopicsDone}
          detail={totalSubtopics > 0 ? `${subtopicPercent}% of the tracked subtopics are done.` : "Checklist progress will surface once topics are being marked done."}
          tone="danger"
          delay={180}
        />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.5fr) minmax(320px, 0.9fr)", gap: 16 }}>
        <DashboardSection
          title="Weekly progress"
          subtitle="A quick read of how study hours are building through the current week."
          actions={
            <div
              style={{
                borderRadius: 999,
                border: `1px solid ${tokens.borderSubtle}`,
                background: tokens.bg,
                padding: "7px 10px",
                fontSize: 11,
                fontWeight: 700,
                color: tokens.textMuted,
                whiteSpace: "nowrap",
              }}
            >
              Strongest day: {strongestDay?.label || "Thu"}
            </div>
          }
        >
          <AnimatedProgressLine points={chartPoints} />
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 12, marginTop: 8 }}>
            <div style={{ padding: 14, borderRadius: 14, background: tokens.bg, border: `1px solid ${tokens.borderSubtle}` }}>
              <div style={{ fontSize: 11, color: tokens.textMuted, marginBottom: 6 }}>Current pace</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: tokens.text }}>{hoursStudied}h</div>
            </div>
            <div style={{ padding: 14, borderRadius: 14, background: tokens.bg, border: `1px solid ${tokens.borderSubtle}` }}>
              <div style={{ fontSize: 11, color: tokens.textMuted, marginBottom: 6 }}>Goal pressure</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: tokens.text }}>{percentToGoal}%</div>
            </div>
            <div style={{ padding: 14, borderRadius: 14, background: tokens.bg, border: `1px solid ${tokens.borderSubtle}` }}>
              <div style={{ fontSize: 11, color: tokens.textMuted, marginBottom: 6 }}>Best day so far</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: tokens.text }}>{strongestDay?.label || "Thu"}</div>
            </div>
          </div>
        </DashboardSection>

        <DashboardSection
          title="Subject mix"
          subtitle="The split of recorded effort across the subjects currently taking time."
        >
          <SubjectProgressList topicBreakdown={topicBreakdown} />
        </DashboardSection>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 16 }}>
        <DashboardSection
          title="Allocation summary"
          subtitle="How the active plan is distributing hours against chapter targets."
        >
          <AllocationList allocation={allocation} />
        </DashboardSection>

        <DashboardSection
          title="Backlog pressure"
          subtitle="The chapters and carry-forward work that still want another pass."
        >
          <BacklogList chapters={backlog.chapters} />
        </DashboardSection>
      </div>
    </div>
  );
}
