import { useCallback, useEffect, useRef, useState } from "react";
import { AuthGate, DefaultLoginScreen, useAuth } from "./Auth.jsx";
import { CalendarGrid } from "./CalendarGrid.jsx";
import { ChatPanel } from "./ChatPanel.jsx";
import { DashboardTabV2 } from "./Dashboard.jsx";
import { ViewErrorBoundary } from "./ErrorBoundary.jsx";
import { GlobalStyles } from "./GlobalStyles.jsx";
import { KnowledgeGraphModal } from "./KnowledgeGraph.jsx";
import { PlanHistoryView } from "./PlanHistoryView.jsx";
import { SettingsView } from "./SettingsView.jsx";
import { startTimer } from "../lib/perf.js";
import { SessionChecklistModal } from "./SessionChecklistModal.jsx";
import { Spinner, Toast } from "./ui.jsx";
import { calendarApi } from "../lib/calendarApi.js";
import { planApi } from "../lib/planApi.js";
import { statsApi } from "../lib/statsApi.js";
import { normalizePlan } from "../lib/planAdapter.js";
import { getOrCreateThreadId, setThreadIdForUser } from "../lib/clientState.js";
import { getProfileInitials, getProfileLabel } from "../lib/userHelpers.js";
import { tokens } from "../theme.js";

const generateThreadId = () => `thread_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

const NAV_ITEMS = [
  { key: "planner", label: "Planner", icon: CalendarIcon },
  { key: "overview", label: "Dashboard", icon: GridIcon },
  { key: "knowledge", label: "Knowledge graph", icon: KnowledgeIcon },
];

const DEV_FRONTEND_ONLY = import.meta.env.DEV && import.meta.env.VITE_USE_REAL_BACKEND !== "1";

const buildDevWorkspace = (today) => {
  const start = new Date(`${today}T12:00:00`);
  const days = Array.from({ length: 5 }, (_, index) => {
    const date = new Date(start);
    date.setDate(start.getDate() + index);
    const dateValue = date.toISOString().split("T")[0];
    return {
      date: dateValue,
      capacity_hours: 5,
      total_hours: index === 2 ? 3 : 4,
      sessions: [
        {
          session_id: `dev-${index}-math`,
          title: index === 0 ? "Algebra revision" : "Focused study block",
          subject: index % 2 === 0 ? "Mathematics" : "Science",
          topic: index % 2 === 0 ? "Quadratic equations" : "Light and electricity",
          start_time: "09:30",
          end_time: "11:00",
          status: index === 0 ? "done" : "pending",
          completed: index === 0,
          contents: [
            {
              name: index % 2 === 0 ? "Formula practice" : "Concept notes",
              status: index === 0 ? "done" : "pending",
              subjects: [index % 2 === 0 ? "Mathematics" : "Science"],
              match_key: `dev-content-${index}-a`,
            },
          ],
        },
        {
          session_id: `dev-${index}-review`,
          title: "Review and recall",
          subject: index % 2 === 0 ? "English" : "Social Science",
          topic: index % 2 === 0 ? "Writing practice" : "History notes",
          start_time: "14:00",
          end_time: "15:15",
          status: "pending",
          completed: false,
          contents: [
            {
              name: "Active recall",
              status: "pending",
              subjects: [index % 2 === 0 ? "English" : "Social Science"],
              match_key: `dev-content-${index}-b`,
            },
          ],
        },
      ],
    };
  });

  return {
    plan: normalizePlan({
      plan_id: "dev-front-end-plan",
      status: "active",
      days,
    }),
    progress: {
      by_subject: {
        Mathematics: [{ status: "done" }, { status: "pending" }, { status: "pending" }],
        Science: [{ status: "pending" }, { status: "pending" }],
        English: [{ status: "pending" }],
      },
    },
    stats: {
      hours_studied: 6.5,
      total_sessions: 10,
      days_until_exam: 28,
    },
  };
};

function flattenSessions(plan) {
  return (plan?.days || [])
    .flatMap(day => (day.sessions || []).map(session => ({
      ...session,
      date: day.date,
    })))
    .sort((a, b) => `${a.date}${a.start_time}`.localeCompare(`${b.date}${b.start_time}`));
}

function getUpcomingSession(plan) {
  const now = new Date();
  return flattenSessions(plan).find(session => {
    const endAt = new Date(`${session.date}T${session.end_time || session.start_time || "00:00"}:00`);
    return endAt >= now;
  }) || null;
}

function getGreeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

function subjectProgressEntries(progress) {
  return Object.entries(progress?.by_subject || {}).map(([subject, items]) => {
    const safeItems = Array.isArray(items) ? items : [];
    const done = safeItems.filter(item => item?.status === "done").length;
    return {
      subject,
      done,
      total: safeItems.length,
      pct: safeItems.length > 0 ? Math.round((done / safeItems.length) * 100) : 0,
    };
  });
}

function SurfaceCard({ children, style }) {
  return (
    <section
      style={{
        background: tokens.bgCard,
        border: `1px solid ${tokens.border}`,
        borderRadius: tokens.radiusXl,
        boxShadow: tokens.shadowCard,
        ...style,
      }}
    >
      {children}
    </section>
  );
}

function Eyebrow({ children, color = tokens.accent }) {
  return (
    <div style={{
      fontSize: 11,
      letterSpacing: "0.18em",
      textTransform: "uppercase",
      color,
      marginBottom: 12,
    }}>
      {children}
    </div>
  );
}

function ActionButton({ children, onClick, quiet = false, style, disabled = false }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      style={{
        border: quiet ? `1px solid ${tokens.border}` : `1px solid ${tokens.accentBorder}`,
        background: quiet ? "transparent" : tokens.accentMuted,
        color: quiet ? tokens.textMuted : tokens.text,
        borderRadius: tokens.radiusFull,
        padding: "11px 16px",
        fontSize: 13,
        fontWeight: 600,
        fontFamily: "inherit",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.6 : 1,
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        ...style,
      }}
    >
      {children}
    </button>
  );
}

function MetricTile({ label, value, detail, accent = tokens.accent }) {
  return (
    <SurfaceCard style={{ padding: 22 }}>
      <div style={{
        width: 18,
        height: 18,
        borderRadius: 999,
        background: `${accent}22`,
        border: `1px solid ${accent}44`,
        marginBottom: 16,
      }} />
      <div style={{ fontSize: 12, color: tokens.textMuted, marginBottom: 10 }}>{label}</div>
      <div style={{
        fontSize: 34,
        lineHeight: 1,
        fontFamily: "'Playfair Display', serif",
        color: tokens.text,
        marginBottom: 8,
      }}>
        {value}
      </div>
      <div style={{ fontSize: 13, color: tokens.textMuted, lineHeight: 1.6 }}>{detail}</div>
    </SurfaceCard>
  );
}

function SidebarNavButton({ label, active, onClick, icon: Icon }) {
  const iconNode = Icon();
  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={active ? "page" : undefined}
      className="sk-sidebar-item"
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 0,
        border: `1px solid ${active ? tokens.accentBorder : "transparent"}`,
        background: active ? tokens.accentMuted : "transparent",
        color: active ? tokens.text : tokens.textMuted,
        borderRadius: 12,
        width: "100%",
        height: 42,
        padding: 0,
        cursor: "pointer",
        fontFamily: "inherit",
        fontSize: 14,
        fontWeight: active ? 600 : 500,
        textAlign: "left",
        position: "relative",
      }}
      title={label}
    >
      <span className="sk-sidebar-icon" aria-hidden="true">{iconNode}</span>
      <span className="sk-sidebar-label">{label}</span>
    </button>
  );
}

function YggdrasilLogo({ size = 42, awake = false }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      aria-hidden="true"
      className={`sk-logo-mark ${awake ? "is-awake" : ""}`}
    >
      <g className="sk-logo-wood">
        <path
          d="M32 28 20 16M32 28l12-12M32 28v17"
          stroke="#151827"
          strokeWidth="5.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="M32 45c-4 4-8 5-13 5M32 45c4 4 8 5 13 5M32 45c-1 5-3 8-7 11M32 45c1 5 3 8 7 11"
          stroke="#151827"
          strokeWidth="2.8"
          strokeLinecap="round"
        />
      </g>
      <path
        className="sk-logo-root-core"
        d="M32 57c-2.2-2.8-2.2-4.9 0-7.4 2.2 2.5 2.2 4.6 0 7.4Z"
        fill="#8C99EC"
        stroke="#151827"
        strokeWidth="1.6"
      />
      <g className="sk-logo-leaf sk-logo-leaf-top">
        <path d="M32 5c5 5.2 5 10.3 0 15.5C27 15.3 27 10.2 32 5Z" fill="#9EAD78" />
      </g>
      <g className="sk-logo-leaf sk-logo-leaf-left">
        <path d="M16 17c5.5.8 8.5 3.8 9.2 9.2C19.8 25.5 16.8 22.5 16 17Z" fill="#8D9F68" />
      </g>
      <g className="sk-logo-leaf sk-logo-leaf-right">
        <path d="M48 17c-.8 5.5-3.8 8.5-9.2 9.2C39.5 20.8 42.5 17.8 48 17Z" fill="#8D9F68" />
      </g>
      <g className="sk-logo-leaf sk-logo-leaf-outer-left">
        <path d="M11 30c4.4-.7 7.4.9 9.1 4.8C15.8 35.4 12.8 33.8 11 30Z" fill="#BCC2F4" />
      </g>
      <g className="sk-logo-leaf sk-logo-leaf-outer-right">
        <path d="M53 30c-1.8 3.8-4.8 5.4-9.1 4.8C45.6 30.9 48.6 29.3 53 30Z" fill="#BCC2F4" />
      </g>
      <g className="sk-logo-leaf sk-logo-leaf-inner-left">
        <path d="M24 30c3.1.6 4.8 2.4 5.2 5.5C26.1 34.9 24.4 33.1 24 30Z" fill="#9EAD78" />
      </g>
      <g className="sk-logo-leaf sk-logo-leaf-inner-right">
        <path d="M40 30c-.4 3.1-2.1 4.9-5.2 5.5C35.2 32.4 36.9 30.6 40 30Z" fill="#9EAD78" />
      </g>
    </svg>
  );
}

function OverviewTab({
  visiblePlan,
  draftPlan,
  stats,
  progress,
  externalEvents,
  onOpenPlanner,
  onOpenAssistant,
  onOpenGraph,
}) {
  const nextSession = getUpcomingSession(visiblePlan);
  const weeklyHours = stats?.hours_studied || 0;
  const totalSessions = stats?.total_sessions || flattenSessions(visiblePlan).length;
  const doneSessions = stats?.sessions_completed || 0;
  const progressEntries = subjectProgressEntries(progress).slice(0, 3);

  return (
    <div style={{ display: "grid", gap: 24 }}>
      <SurfaceCard style={{ padding: 42 }}>
        <Eyebrow>Your study desk</Eyebrow>
        <div style={{
          display: "flex",
          justifyContent: "space-between",
          gap: 24,
          alignItems: "flex-start",
          flexWrap: "wrap",
        }}>
          <div style={{ maxWidth: 720 }}>
            <h1 style={{
              fontSize: "clamp(48px, 6vw, 72px)",
              lineHeight: 0.96,
              fontFamily: "'Playfair Display', serif",
              fontWeight: 600,
              color: tokens.text,
              marginBottom: 18,
            }}>
              {getGreeting()}, Maya.
            </h1>
            <p style={{
              fontSize: 24,
              color: tokens.textSecondary,
              lineHeight: 1.5,
              maxWidth: 760,
            }}>
              {nextSession
                ? `Your next session is ${nextSession.topic || nextSession.subject || "ready"} at ${nextSession.start_time}. The week already knows what matters.`
                : "Your workspace is ready. Build the next draft, protect your time, and keep the week clean."}
            </p>
          </div>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            <ActionButton onClick={onOpenPlanner}>
              <CalendarIcon />
              Open planner
            </ActionButton>
            <ActionButton quiet onClick={onOpenAssistant}>
              <ChatIcon />
              Open assistant
            </ActionButton>
          </div>
        </div>
      </SurfaceCard>

      <div style={{
        display: "grid",
        gridTemplateColumns: "minmax(0, 1.7fr) minmax(300px, 0.95fr)",
        gap: 24,
      }}>
        <SurfaceCard style={{ padding: 26 }}>
          <Eyebrow>Today's next session</Eyebrow>
          <div style={{
            display: "flex",
            justifyContent: "space-between",
            gap: 24,
            alignItems: "flex-start",
            flexWrap: "wrap",
          }}>
            <div>
              <div style={{
                fontSize: 48,
                lineHeight: 1.02,
                fontFamily: "'Playfair Display', serif",
                color: tokens.text,
                marginBottom: 12,
              }}>
                {nextSession?.topic || "No session placed yet"}
              </div>
              <div style={{ fontSize: 18, color: tokens.textSecondary, marginBottom: 28 }}>
                {nextSession
                  ? `${nextSession.subject || "Study"} · ${nextSession.start_time}-${nextSession.end_time}`
                  : "Open the planner assistant to build or revise a draft."}
              </div>
            </div>
            <StatusPill
              text={draftPlan ? "Draft review ready" : "Schedule active"}
              tone={draftPlan ? "warning" : "default"}
            />
          </div>
          <div style={{
            paddingTop: 18,
            borderTop: `1px solid ${tokens.borderSubtle}`,
            display: "flex",
            justifyContent: "space-between",
            gap: 16,
            flexWrap: "wrap",
            color: tokens.textMuted,
            fontSize: 14,
          }}>
            <span>{externalEvents.length} external blockers protected</span>
            <button
              type="button"
              onClick={onOpenPlanner}
              style={{
                border: "none",
                background: "transparent",
                color: tokens.accent,
                fontFamily: "inherit",
                fontSize: 14,
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              See day plan
            </button>
          </div>
        </SurfaceCard>

        <SurfaceCard style={{ padding: 26 }}>
          <Eyebrow>Weekly momentum</Eyebrow>
          <div style={{
            fontSize: 58,
            lineHeight: 1,
            fontFamily: "'Playfair Display', serif",
            color: tokens.text,
            marginBottom: 12,
          }}>
            {weeklyHours}h
          </div>
          <div style={{ fontSize: 18, color: tokens.textSecondary, marginBottom: 20 }}>
            {doneSessions} of {totalSessions || 0} sessions completed
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(10, 1fr)", gap: 6 }}>
            {Array.from({ length: 10 }).map((_, index) => {
              const filled = index < Math.min(10, Math.round(((doneSessions || 0) / Math.max(totalSessions || 1, 1)) * 10));
              return (
                <div
                  key={index}
                  style={{
                    height: 6,
                    borderRadius: 999,
                    background: filled ? tokens.accent : tokens.bgHover,
                  }}
                />
              );
            })}
          </div>
        </SurfaceCard>
      </div>

      <div style={{
        display: "grid",
        gridTemplateColumns: "minmax(0, 1.4fr) minmax(300px, 1fr)",
        gap: 24,
      }}>
        <SurfaceCard style={{ padding: 26 }}>
          <Eyebrow>Plan status</Eyebrow>
          <div style={{
            fontSize: 44,
            lineHeight: 1.06,
            fontFamily: "'Playfair Display', serif",
            color: tokens.text,
            marginBottom: 14,
          }}>
            {draftPlan ? "Revision draft ready" : visiblePlan?.days?.length ? "Current plan in motion" : "No active plan yet"}
          </div>
          <p style={{ fontSize: 18, color: tokens.textSecondary, lineHeight: 1.6, marginBottom: 22 }}>
            {draftPlan
              ? "A revised schedule is waiting for your call. Review it in the planner assistant before anything gets committed."
              : visiblePlan?.days?.length
                ? "Your current week is loaded, blockers are visible, and the assistant can revise the schedule whenever the week shifts."
                : "Start with the assistant and SkedioAI will map your week into the calendar."}
          </p>
          <ActionButton quiet onClick={onOpenAssistant}>
            <ChatIcon />
            {draftPlan ? "Review draft" : "Talk to assistant"}
          </ActionButton>
        </SurfaceCard>

        <SurfaceCard style={{ padding: 26 }}>
          <Eyebrow>Learning map</Eyebrow>
          <div style={{
            fontSize: 42,
            lineHeight: 1.05,
            fontFamily: "'Playfair Display', serif",
            color: tokens.text,
            marginBottom: 14,
          }}>
            {progressEntries.reduce((count, item) => count + Math.max(item.total - item.done, 0), 0)} concepts need attention
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 22 }}>
            {progressEntries.length > 0 ? progressEntries.map(item => (
              <span
                key={item.subject}
                style={{
                  padding: "7px 10px",
                  borderRadius: tokens.radiusFull,
                  border: `1px solid ${tokens.border}`,
                  color: tokens.textSecondary,
                  fontSize: 12,
                }}
              >
                {item.subject}
              </span>
            )) : (
              <span style={{ color: tokens.textMuted, fontSize: 14 }}>Progress signals will show up here once sessions start landing.</span>
            )}
          </div>
          <button
            type="button"
            onClick={onOpenGraph}
            style={{
              border: "none",
              background: "transparent",
              color: "#d9ec7e",
              fontFamily: "inherit",
              fontSize: 14,
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            Open knowledge map
          </button>
        </SurfaceCard>
      </div>
    </div>
  );
}

function PlannerTab({
  visiblePlan,
  draftPlan,
  today,
  externalEvents,
  onSessionClick,
}) {
  return (
    <div style={{ minHeight: "calc(100dvh - 150px)" }}>
      <SurfaceCard style={{
        padding: 0,
        overflow: "hidden",
        minHeight: "calc(100dvh - 166px)",
        display: "flex",
        flexDirection: "column",
        borderRadius: 14,
      }}>
        <div style={{ flex: 1, minHeight: 0 }}>
          <CalendarGrid
            allDays={visiblePlan?.days || []}
            today={today}
            onSessionClick={onSessionClick}
            externalEvents={externalEvents}
            draftMode={Boolean(draftPlan)}
          />
        </div>
      </SurfaceCard>
    </div>
  );
}

function ProgressTab({ stats, progress, onOpenGraph }) {
  const entries = subjectProgressEntries(progress);

  return (
    <div style={{ display: "grid", gap: 24 }}>
      <SurfaceCard style={{ padding: 36 }}>
        <Eyebrow>Progress</Eyebrow>
        <div style={{
          fontSize: "clamp(42px, 5vw, 68px)",
          lineHeight: 0.98,
          fontFamily: "'Playfair Display', serif",
          color: tokens.text,
          marginBottom: 16,
        }}>
          Measure the work that matters.
        </div>
        <p style={{ fontSize: 22, color: tokens.textSecondary, lineHeight: 1.55, maxWidth: 780 }}>
          A clean record of sessions, completed topics, and the weak spots that deserve another pass.
        </p>
      </SurfaceCard>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 16 }}>
        <MetricTile
          label="Studied this cycle"
          value={`${stats?.hours_studied || 0}h`}
          detail="Focus time tracked from completed sessions."
          accent="#e8c78a"
        />
        <MetricTile
          label="Sessions completed"
          value={stats?.sessions_completed || 0}
          detail="Each finished block feeds the rhythm view and progress memory."
          accent="#d9ec7e"
        />
        <MetricTile
          label="Subtopics mastered"
          value={stats?.subtopics_done || 0}
          detail="Knowledge moves when the checklist truth gets updated."
          accent={tokens.accent}
        />
      </div>

      <SurfaceCard style={{ padding: 26 }}>
        <DashboardTabV2 stats={stats} examDate={stats?.exam_date} daysUntilExam={stats?.days_until_exam} />
      </SurfaceCard>

      <SurfaceCard style={{ padding: 28 }}>
        <Eyebrow>Current contract</Eyebrow>
        <div style={{
          fontSize: 42,
          lineHeight: 1.06,
          fontFamily: "'Playfair Display', serif",
          color: tokens.text,
          marginBottom: 20,
        }}>
          Subject progress
        </div>
        <div style={{ display: "grid", gap: 18 }}>
          {entries.length > 0 ? entries.map(item => (
            <div key={item.subject}>
              <div style={{
                display: "flex",
                justifyContent: "space-between",
                gap: 12,
                marginBottom: 8,
                fontSize: 14,
              }}>
                <span style={{ color: tokens.text }}>{item.subject}</span>
                <span style={{ color: tokens.textMuted }}>{item.done} / {item.total}</span>
              </div>
              <div style={{
                height: 6,
                borderRadius: 999,
                background: tokens.bgHover,
                overflow: "hidden",
              }}>
                <div style={{
                  width: `${item.pct}%`,
                  height: "100%",
                  background: item.subject === "Mathematics" ? "#d9ec7e" : item.subject === "Physics" ? tokens.accent : "#dcc7a5",
                  borderRadius: 999,
                }} />
              </div>
            </div>
          )) : (
            <div style={{ color: tokens.textMuted, fontSize: 14 }}>
              Progress bars will show up after the first sessions and subtopic checklists start moving.
            </div>
          )}
        </div>
        <div style={{ marginTop: 22 }}>
          <ActionButton quiet onClick={onOpenGraph}>
            <KnowledgeIcon />
            Open knowledge map
          </ActionButton>
        </div>
      </SurfaceCard>
    </div>
  );
}

function StatusPill({ text, tone = "default" }) {
  const toneMap = {
    default: {
      background: tokens.accentMuted,
      border: tokens.accentBorder,
      color: tokens.text,
    },
    success: {
      background: tokens.greenBg,
      border: tokens.greenBorder,
      color: tokens.greenText,
    },
    warning: {
      background: tokens.redBg,
      border: tokens.redBorder,
      color: tokens.redText,
    },
    danger: {
      background: tokens.redBg,
      border: tokens.redBorder,
      color: tokens.redText,
    },
  };

  const current = toneMap[tone] || toneMap.default;
  return (
    <span style={{
      display: "inline-flex",
      alignItems: "center",
      gap: 6,
      padding: "8px 12px",
      borderRadius: tokens.radiusFull,
      border: `1px solid ${current.border}`,
      background: current.background,
      color: current.color,
      fontSize: 12,
      fontWeight: 700,
    }}>
      <span style={{
        width: 6,
        height: 6,
        borderRadius: "50%",
        background: current.color,
      }} />
      {text}
    </span>
  );
}

export function StudyPlanApp() {
  const { user, loading: authLoading, supabase, isDevAdmin, signOutDevAdmin } = useAuth();
  const sidebarRef = useRef(null);
  const userId = user?.id || null;
  const [toast, setToast] = useState(null);
  const [plans, setPlans] = useState([]);
  const [plan, setPlan] = useState(null);
  const [progress, setProgress] = useState({ by_subject: {} });
  const [loading, setLoading] = useState(true);
  const [bootMessage, setBootMessage] = useState("Waking up SkedioAI...");
  const [stats, setStats] = useState(null);
  const [calendarSync, setCalendarSync] = useState({
    loading: false,
    error: "",
    checkedAt: null,
  });
  const [activeTab, setActiveTab] = useState("planner");
  const [showAI, setShowAI] = useState(false);
  const [assistantWidth, setAssistantWidth] = useState(520);
  const [logoAwake, setLogoAwake] = useState(false);
  const [assistantLauncherInput, setAssistantLauncherInput] = useState("");
  const [queuedAssistantPrompt, setQueuedAssistantPrompt] = useState(null);
  const [launcherCenterX, setLauncherCenterX] = useState(null);
  const [settingsSection, setSettingsSection] = useState("profile");
  const [sidebarSettingsOpen, setSidebarSettingsOpen] = useState(false);
  const [showGraph, setShowGraph] = useState(false);
  const [selectedSessionOverlay, setSelectedSessionOverlay] = useState(null);
  const [threadId, setThreadId] = useState(null);
  const [externalEvents, setExternalEvents] = useState([]);
  const [draftPlan, setDraftPlan] = useState(null);
  const [devPreviewNonce, setDevPreviewNonce] = useState(0);
  const [devReviewPreviewPayload, setDevReviewPreviewPayload] = useState(null);
  const [emailReviewRequest, setEmailReviewRequest] = useState(null);

  const today = new Date().toISOString().split("T")[0];
  const devToolsEnabled = import.meta.env.DEV || new URLSearchParams(window.location.search).has("devtools");

  useEffect(() => {
    if (!userId) {
      setThreadId(null);
      return;
    }
    try {
      const params = new URLSearchParams(window.location.search);
      const reviewThread = params.get("review_thread");
      const nextThreadId = reviewThread || getOrCreateThreadId(localStorage, userId, generateThreadId);
      if (reviewThread) {
        setThreadIdForUser(localStorage, userId, reviewThread);
      }
      setThreadId(nextThreadId);
    } catch {
      setThreadId(generateThreadId());
    }
  }, [userId]);

  const profileLabel = getProfileLabel(user);
  const profileInitials = getProfileInitials(user);

  const visiblePlan = draftPlan || plan;

  const fetchAllPlans = async () => {
    if (DEV_FRONTEND_ONLY) {
      setPlans([buildDevWorkspace(today).plan]);
      return;
    }
    try {
      setPlans(await planApi.listAll());
    } catch {
      // non-critical
    }
  };

  const fetchProgress = async () => {
    if (DEV_FRONTEND_ONLY) {
      setProgress(buildDevWorkspace(today).progress);
      return;
    }
    try {
      setProgress(await planApi.getProgress());
    } catch {
      setProgress({ by_subject: {} });
    }
  };

  const fetchStats = async () => {
    if (DEV_FRONTEND_ONLY) {
      setStats(buildDevWorkspace(today).stats);
      return;
    }
    try {
      setStats(await statsApi.dashboard());
    } catch {
      // non-critical
    }
  };

  const fetchExternalEvents = async () => {
    if (DEV_FRONTEND_ONLY) {
      setExternalEvents([
        {
          id: "dev-blocker-1",
          date: today,
          title: "School assembly",
          start_time: "12:00",
          end_time: "12:45",
        },
      ]);
      setCalendarSync({ loading: false, error: "", checkedAt: new Date() });
      return;
    }
    setCalendarSync(prev => ({ ...prev, loading: true, error: "" }));
    try {
      const start = new Date();
      start.setDate(start.getDate() - 2);
      const end = new Date();
      end.setDate(end.getDate() + 10);
      const startStr = start.toISOString().split("T")[0];
      const endStr = end.toISOString().split("T")[0];
      const stop = startTimer("workspace:externalEvents");
      const events = await calendarApi.externalEvents(startStr, endStr);
      stop();
      setExternalEvents(events);
      setCalendarSync({ loading: false, error: "", checkedAt: new Date() });
    } catch (error) {
      setExternalEvents([]);
      setCalendarSync({
        loading: false,
        error: error.message || "Calendar blockers unavailable",
        checkedAt: new Date(),
      });
    }
  };

  const fetchWorkspaceBootstrap = async () => {
    if (DEV_FRONTEND_ONLY) {
      const data = buildDevWorkspace(today);
      setPlan(data.plan);
      setProgress(data.progress);
      setStats(data.stats);
      return;
    }
    const stop = startTimer("workspace:bootstrap");
    const data = await planApi.bootstrap();
    stop();
    setPlan(data.plan);
    setProgress(data.progress || { by_subject: {} });
    setStats(data.stats || null);
  };

  const hydrateCoreWorkspace = async () => {
    setLoading(true);
    if (DEV_FRONTEND_ONLY) {
      setBootMessage("Loading frontend preview...");
      const data = buildDevWorkspace(today);
      setPlan(data.plan);
      setProgress(data.progress);
      setStats(data.stats);
      setExternalEvents([
        {
          id: "dev-blocker-1",
          date: today,
          title: "School assembly",
          start_time: "12:00",
          end_time: "12:45",
        },
      ]);
      setCalendarSync({ loading: false, error: "", checkedAt: new Date() });
      setLoading(false);
      return;
    }
    setBootMessage("Waking up SkedioAI...");
    try {
      setBootMessage("Loading your study plan...");
      await fetchWorkspaceBootstrap();
      fetchExternalEvents();
    } catch (error) {
      setToast(error.message || "Backend is still waking up");
      setTimeout(() => setToast(null), 5000);
    } finally {
      setLoading(false);
    }
  };

  const handleRefreshAll = () => {
    setLoading(true);
    Promise.resolve(fetchWorkspaceBootstrap()).finally(() => setLoading(false));
    fetchExternalEvents();
  };

  useEffect(() => {
    hydrateCoreWorkspace();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (activeTab === "archive" && plans.length === 0) {
      fetchAllPlans();
    }
  }, [activeTab, plans.length]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const calendarStatus = params.get("calendar_status");
    const calendarMessage = params.get("calendar_message");
    const reviewThread = params.get("review_thread");
    const reviewAction = params.get("review_action");
    if (calendarStatus) {
      window.history.replaceState({}, "", "/");
      setActiveTab("settings");
      setSettingsSection("integrations");
      if (calendarStatus === "connected") {
        setToast("Calendar connected! ✓");
        fetchExternalEvents();
      } else {
        setToast(calendarMessage || "Calendar connection failed");
      }
      setTimeout(() => setToast(null), 5000);
      return;
    }

    if (reviewThread && userId && threadId === reviewThread) {
      setActiveTab("planner");
      setShowAI(true);
      setEmailReviewRequest({
        threadId: reviewThread,
        action: reviewAction || "open",
        nonce: `${reviewThread}:${reviewAction || "open"}:${Date.now()}`,
      });
      window.history.replaceState({}, "", "/");
    }
  }, [threadId, userId]);

  useEffect(() => {
    const node = sidebarRef.current;
    if (!node) return undefined;

    const updateLauncherCenter = () => {
      const rect = node.getBoundingClientRect();
      const dockEdge = rect.right;
      setLauncherCenterX(dockEdge + ((window.innerWidth - dockEdge) / 2));
    };

    updateLauncherCenter();

    const observer = new ResizeObserver(() => {
      updateLauncherCenter();
    });
    observer.observe(node);
    window.addEventListener("resize", updateLauncherCenter);

    return () => {
      observer.disconnect();
      window.removeEventListener("resize", updateLauncherCenter);
    };
  }, []);

  const handleSessionToggle = useCallback((session, apiData, newSubtopicsCompleted, newCompleted) => {
    setPlan(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        days: prev.days.map(day => ({
          ...day,
          sessions: day.sessions.map(s => s.session_id === session.session_id
            ? {
                ...s,
                completed: newCompleted,
                subtopics_completed: newSubtopicsCompleted,
                actual_hours: apiData.actual_hours ?? s.actual_hours,
              }
            : s),
        })),
      };
    });
    fetchProgress();
    fetchStats();
  }, []);

  const handleSubtopicToggle = useCallback((sessionId, newSubtopicsCompleted, date) => {
    setPlan(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        days: prev.days.map(day => ({
          ...day,
          sessions: day.sessions.map(s => s.session_id === sessionId && day.date === date
            ? { ...s, subtopics_completed: newSubtopicsCompleted }
            : s),
        })),
      };
    });
    fetchProgress();
  }, []);

  const handleCalendarSessionClick = (session, date) => {
    setSelectedSessionOverlay({ session, date });
  };

  const handleDraftStateChange = useCallback((nextDraftPlan) => {
    setDraftPlan(normalizePlan(nextDraftPlan));
  }, []);

  const handleLoadDevDraftPreview = useCallback(async () => {
    const { debugPlannerReviewPayload, buildPlannerReviewPreviewPayload } = await import("../dev/plannerDraftPreview.js");
    const previewPayload = debugPlannerReviewPayload(
      buildPlannerReviewPreviewPayload(today),
    );
    setActiveTab("planner");
    setShowAI(true);
    setDraftPlan(normalizePlan(previewPayload.draft_plan));
    setDevReviewPreviewPayload(previewPayload);
    setDevPreviewNonce(prev => prev + 1);
  }, [today]);

  const handleClearDevDraftPreview = useCallback(() => {
    setDraftPlan(null);
    setDevReviewPreviewPayload(null);
  }, []);

  const openAssistant = useCallback(() => {
    setQueuedAssistantPrompt(null);
    setShowAI(true);
  }, []);

  const closeAssistant = useCallback(() => {
    setQueuedAssistantPrompt(null);
    setShowAI(false);
  }, []);

  const handleAssistantLauncherSubmit = useCallback((event) => {
    event.preventDefault();
    const prompt = assistantLauncherInput.trim();
    if (!prompt) {
      setShowAI(true);
      return;
    }
    setQueuedAssistantPrompt({
      text: prompt,
      nonce: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    });
    setAssistantLauncherInput("");
    setLogoAwake(true);
    setShowAI(true);
  }, [assistantLauncherInput]);

  const openPlanner = useCallback(() => {
    setActiveTab("planner");
  }, []);

  const openSettings = useCallback((section = "profile") => {
    setSidebarSettingsOpen(true);
    setSettingsSection(section);
    setActiveTab("settings");
  }, []);

  const handleSidebarLogout = useCallback(async () => {
    try {
      if (isDevAdmin) {
        signOutDevAdmin?.();
        return;
      }
      if (supabase) {
        await supabase.auth.signOut({ scope: "local" });
      }
    } catch (error) {
      setToast(error?.message || "Could not log out");
      setTimeout(() => setToast(null), 5000);
    }
  }, [isDevAdmin, signOutDevAdmin, supabase]);

  const beginAssistantResize = useCallback((event) => {
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = assistantWidth;
    const onMove = (moveEvent) => {
      const delta = startX - moveEvent.clientX;
      const nextWidth = Math.min(760, Math.max(380, startWidth + delta));
      setAssistantWidth(nextWidth);
    };
    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }, [assistantWidth]);

  if (authLoading || (loading && plans.length === 0)) {
    return (
      <div style={{ minHeight: "100vh", background: tokens.bg, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <GlobalStyles />
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16 }}>
          <div style={{
            width: 48,
            height: 48,
            borderRadius: tokens.radiusXl,
            background: tokens.accentMuted,
            border: `1px solid ${tokens.accentBorder}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}>
            <Spinner size={20} />
          </div>
          <div style={{ fontSize: 13, color: tokens.textMuted, letterSpacing: "0.01em" }}>{bootMessage}</div>
        </div>
      </div>
    );
  }

  return (
    <AuthGate fallback={<DefaultLoginScreen />}>
      <GlobalStyles />
      <div style={{ display: "flex", minHeight: "100vh", background: tokens.bg, color: tokens.text }}>
        <aside ref={sidebarRef} className="sk-app-sidebar">
          <button
            type="button"
            onClick={() => {
              setLogoAwake(prev => !prev);
              setActiveTab("planner");
            }}
            className="sk-sidebar-brand"
            aria-pressed={logoAwake}
            aria-label="Open planner"
          >
            <span className="sk-sidebar-logo">
              <YggdrasilLogo size={38} awake={logoAwake} />
            </span>
            <span className="sk-sidebar-brand-copy">
              <span className="sk-sidebar-brand-title">SkedioAI</span>
              <span className="sk-sidebar-brand-subtitle">study planner</span>
            </span>
          </button>

          <nav aria-label="Primary" className="sk-sidebar-nav">
            {NAV_ITEMS.map(item => (
              <SidebarNavButton
                key={item.key}
                label={item.label}
                icon={item.icon}
                active={
                  activeTab === item.key
                  || (item.key === "knowledge" && showGraph)
                }
                onClick={() => setActiveTab(item.key)}
              />
            ))}
            <div className={`sk-sidebar-settings-group ${sidebarSettingsOpen ? "is-open" : ""}`}>
              <button
                type="button"
                onClick={() => {
                  setSidebarSettingsOpen(prev => {
                    const nextOpen = !prev;
                    if (nextOpen) {
                      setActiveTab("settings");
                      setSettingsSection(currentSection => currentSection || "profile");
                    }
                    return nextOpen;
                  });
                }}
                className="sk-sidebar-item sk-sidebar-settings-trigger"
                aria-expanded={sidebarSettingsOpen}
                aria-current={activeTab === "settings" ? "page" : undefined}
                title="Settings"
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 0,
                  border: `1px solid ${activeTab === "settings" ? tokens.accentBorder : "transparent"}`,
                  background: activeTab === "settings" ? tokens.accentMuted : "transparent",
                  color: activeTab === "settings" ? tokens.text : tokens.textMuted,
                  borderRadius: 12,
                  width: "100%",
                  height: 42,
                  padding: 0,
                  cursor: "pointer",
                  fontFamily: "inherit",
                  fontSize: 14,
                  fontWeight: activeTab === "settings" ? 600 : 500,
                  textAlign: "left",
                  position: "relative",
                }}
              >
                <span className="sk-sidebar-icon" aria-hidden="true"><SettingsIcon /></span>
                <span className="sk-sidebar-label">Settings</span>
                <span className="sk-sidebar-expand-mark" aria-hidden="true">
                  {sidebarSettingsOpen ? "-" : "+"}
                </span>
              </button>
              <div className="sk-sidebar-settings-children">
                {[
                  ["profile", "Profile"],
                  ["security", "Security"],
                  ["integrations", "Integrations"],
                  ["billing", "Billing"],
                  ["archive", "Past plans"],
                  ["logout", "Log out"],
                ].map(([section, label]) => {
                  const activeChild =
                    (section === "archive" && activeTab === "archive")
                    || (section !== "archive" && section !== "logout" && activeTab === "settings" && settingsSection === section);
                  return (
                    <button
                      key={`${section}-${label}`}
                      type="button"
                      onClick={() => {
                        if (section === "archive") {
                          setSidebarSettingsOpen(true);
                          setActiveTab("archive");
                          fetchAllPlans();
                          return;
                        }
                        if (section === "logout") {
                          handleSidebarLogout();
                          return;
                        }
                        openSettings(section);
                      }}
                      aria-current={activeChild ? "page" : undefined}
                      className="sk-sidebar-settings-child"
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
            </div>
          </nav>

          <div className="sk-sidebar-bottom">
              <button
                type="button"
                onClick={() => openSettings("profile")}
                className="sk-sidebar-profile"
                style={{
                  background: activeTab === "settings" && settingsSection === "profile" ? tokens.accentMuted : tokens.bgElevated,
                  border: `1px solid ${activeTab === "settings" && settingsSection === "profile" ? tokens.accentBorder : tokens.border}`,
                }}
                title={profileLabel}
              >
                <div style={{
                  width: 32,
                  height: 32,
                  borderRadius: "50%",
                  background: "#e887ad",
                  color: "#fffefa",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 14,
                  fontWeight: 700,
                  flexShrink: 0,
                }}>
                  {profileInitials}
                </div>
                <span className="sk-sidebar-user-copy">
                  <span className="sk-sidebar-user-name">{profileLabel}</span>
                  <span className="sk-sidebar-user-meta">Profile</span>
                </span>
              </button>
          </div>
        </aside>

        <main style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", position: "relative" }}>
          <div style={{
            flex: 1,
            minHeight: 0,
            display: "flex",
            background: tokens.bg,
            position: "relative",
          }}>
            <div style={{
              flex: "1 1 auto",
              minWidth: 0,
              minHeight: 0,
              overflowY: "auto",
              padding: showAI ? "26px 10px 26px 10px" : "26px 16px 26px 10px",
              background: tokens.bg,
            }}>
              <ViewErrorBoundary resetKey={activeTab}>
              {activeTab === "overview" && (
                <DashboardTabV2
                  stats={stats}
                  examDate={stats?.exam_date}
                  daysUntilExam={stats?.days_until_exam}
                />
              )}

              {activeTab === "planner" && (
                <PlannerTab
                  visiblePlan={visiblePlan}
                  draftPlan={draftPlan}
                  today={today}
                  externalEvents={externalEvents}
                  calendarSync={calendarSync}
                  onSessionClick={handleCalendarSessionClick}
                  onSyncCalendar={fetchExternalEvents}
                  onOpenAssistant={openAssistant}
                />
              )}

              {activeTab === "progress" && (
                <ProgressTab
                  stats={stats}
                  progress={progress}
                  onOpenGraph={() => setShowGraph(true)}
                />
              )}

              {activeTab === "knowledge" && (
                <SurfaceCard style={{ padding: 36, minHeight: "calc(100vh - 170px)" }}>
                  <Eyebrow color={tokens.greenText}>Knowledge graph</Eyebrow>
                  <div style={{
                    fontSize: 54,
                    lineHeight: 1,
                    color: tokens.text,
                    marginBottom: 16,
                    fontWeight: 700,
                  }}>
                    Your learning map stays rooted here.
                  </div>
                  <p style={{ fontSize: 18, color: tokens.textSecondary, lineHeight: 1.65, maxWidth: 760, marginBottom: 24 }}>
                    Open the graph view to inspect subjects, chapters, subtopics, and progress relationships without turning the planner into a noisy dashboard.
                  </p>
                  <ActionButton onClick={() => setShowGraph(true)}>
                    <KnowledgeIcon />
                    Open graph surface
                  </ActionButton>
                </SurfaceCard>
              )}

              {activeTab === "archive" && (
                <div style={{ paddingTop: 4 }}>
                  <PlanHistoryView
                    plans={plans}
                    onRefresh={handleRefreshAll}
                    today={today}
                    onSessionToggle={handleSessionToggle}
                    onSubtopicToggle={handleSubtopicToggle}
                  />
                </div>
              )}

              {activeTab === "settings" && (
                <div style={{ paddingTop: 6, animation: "settingsSlideIn 0.24s cubic-bezier(0.16, 1, 0.3, 1)" }}>
                  <SettingsView
                    onBack={() => setActiveTab("planner")}
                    initialSection={settingsSection}
                    onSectionChange={setSettingsSection}
                    onOpenPastPlans={() => {
                      setActiveTab("archive");
                      fetchAllPlans();
                    }}
                  />
                </div>
              )}
              </ViewErrorBoundary>
            </div>

          </div>

          {!showAI && (
            <form
              onSubmit={handleAssistantLauncherSubmit}
              className="sk-ai-launcher"
              style={{
                position: "fixed",
                left: launcherCenterX ?? window.innerWidth / 2,
                bottom: 24,
                transform: "translateX(-50%)",
                width: "min(560px, calc(100% - 96px))",
                height: 58,
                borderRadius: 20,
                border: `1px solid ${tokens.accentBorder}`,
                background: "rgba(255, 255, 250, 0.94)",
                backdropFilter: "blur(18px)",
                WebkitBackdropFilter: "blur(18px)",
                boxShadow: "0 20px 52px rgba(76, 88, 132, 0.18)",
                zIndex: tokens.zIndexSticky,
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "8px 10px 8px 14px",
              }}
            >
              <div style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: 34, height: 34, flexShrink: 0 }}>
                <YggdrasilLogo size={30} awake={logoAwake} />
              </div>
              <input
                type="text"
                value={assistantLauncherInput}
                onChange={event => setAssistantLauncherInput(event.target.value)}
                onFocus={() => setLogoAwake(true)}
                placeholder="Ask SkedioAI about your plan, blockers, or next study move..."
                aria-label="Ask SkedioAI"
                style={{
                  flex: 1,
                  minWidth: 0,
                  border: "none",
                  outline: "none",
                  background: "transparent",
                  color: tokens.text,
                  fontSize: 13,
                  fontFamily: "inherit",
                }}
              />
              <button
                type="submit"
                aria-label={assistantLauncherInput.trim() ? "Send message to SkedioAI" : "Open SkedioAI assistant"}
                style={{
                  width: 40,
                  height: 40,
                  borderRadius: 14,
                  border: `1px solid ${assistantLauncherInput.trim() ? tokens.accentBorder : tokens.border}`,
                  background: assistantLauncherInput.trim() ? tokens.accentMuted : tokens.bgCard,
                  color: assistantLauncherInput.trim() ? tokens.accentHover : tokens.textMuted,
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                  cursor: "pointer",
                }}
              >
                <ArrowUpRightIcon />
              </button>
            </form>
          )}

        </main>

        {showAI && (
          <aside
            style={{
              width: assistantWidth,
              minWidth: 380,
              maxWidth: "min(760px, calc(100vw - 220px))",
              height: "calc(100dvh - 28px)",
              margin: "14px 14px 14px 0",
              flex: "0 0 auto",
              position: "sticky",
              top: 14,
              zIndex: 4,
              display: "flex",
              background: "transparent",
              animation: "assistantPanelIn 0.26s cubic-bezier(0.16, 1, 0.3, 1)",
            }}
          >
            <button
              type="button"
              aria-label="Resize assistant panel"
              onMouseDown={beginAssistantResize}
              style={{
                position: "absolute",
                left: -4,
                top: 32,
                bottom: 32,
                width: 10,
                border: "none",
                background: "transparent",
                cursor: "col-resize",
                zIndex: 3,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <span
                aria-hidden="true"
                style={{
                  width: 4,
                  height: 52,
                  borderRadius: 999,
                  background: tokens.borderHover,
                  boxShadow: "0 0 0 2px rgba(255, 254, 250, 0.72)",
                  opacity: 0.7,
                }}
              />
            </button>
            <ChatPanel
              threadId={threadId}
              onClose={closeAssistant}
              onPlanCommitted={handleRefreshAll}
              onDraftStateChange={handleDraftStateChange}
              devToolsEnabled={devToolsEnabled}
              onLoadDevDraftPreview={handleLoadDevDraftPreview}
              onClearDevDraftPreview={handleClearDevDraftPreview}
              devPreviewNonce={devPreviewNonce}
              devReviewPreviewPayload={devReviewPreviewPayload}
              emailReviewRequest={emailReviewRequest}
              isEmbedded={true}
              drawerWidth={assistantWidth}
              onDrawerWidthChange={setAssistantWidth}
              queuedPrompt={queuedAssistantPrompt}
            />
          </aside>
        )}

        {showGraph && (
          <ViewErrorBoundary
            resetKey="knowledge-graph"
            actionLabel="Close Graph"
            onAction={() => setShowGraph(false)}
          >
            <KnowledgeGraphModal onClose={() => setShowGraph(false)} />
          </ViewErrorBoundary>
        )}

        {selectedSessionOverlay && (
          <SessionChecklistModal
            sessionObj={selectedSessionOverlay}
            onClose={() => setSelectedSessionOverlay(null)}
            onRefresh={handleRefreshAll}
          />
        )}

        <Toast>{toast}</Toast>
      </div>
    </AuthGate>
  );
}

function GridIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
    </svg>
  );
}

function CalendarIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="18" rx="2" />
      <line x1="8" y1="2.5" x2="8" y2="6" />
      <line x1="16" y1="2.5" x2="16" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  );
}

function SettingsIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2.75v2.1" />
      <path d="M12 19.15v2.1" />
      <path d="M2.75 12h2.1" />
      <path d="M19.15 12h2.1" />
      <path d="m5.46 5.46 1.48 1.48" />
      <path d="m17.06 17.06 1.48 1.48" />
      <path d="m18.54 5.46-1.48 1.48" />
      <path d="m6.94 17.06-1.48 1.48" />
    </svg>
  );
}

function KnowledgeIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="18" cy="5" r="2.5" />
      <circle cx="6" cy="12" r="2.5" />
      <circle cx="18" cy="19" r="2.5" />
      <path d="M8.3 13.2 15.7 17" />
      <path d="M15.7 7 8.3 10.8" />
    </svg>
  );
}

function ArrowUpRightIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M7 17 17 7" />
      <path d="M8 7h9v9" />
    </svg>
  );
}

function ChatIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  );
}
