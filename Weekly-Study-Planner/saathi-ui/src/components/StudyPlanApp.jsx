import { useCallback, useEffect, useMemo, useState } from "react";
import { AuthGate, DefaultLoginScreen, useAuth } from "./Auth.jsx";
import { CalendarGrid } from "./CalendarGrid.jsx";
import { ChatPanel } from "./ChatPanel.jsx";
import { DashboardTabV2 } from "./Dashboard.jsx";
import { ViewErrorBoundary } from "./ErrorBoundary.jsx";
import { GlobalStyles } from "./GlobalStyles.jsx";
import { KnowledgeGraphModal } from "./KnowledgeGraph.jsx";
import { PlanHistoryView } from "./PlanHistoryView.jsx";
import { ProfileDashboardModal } from "./ProfileDashboardModal.jsx";
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
  { key: "overview", label: "Overview", icon: GridIcon },
  { key: "planner", label: "Planner", icon: CalendarIcon },
  { key: "progress", label: "Progress", icon: FocusIcon },
  { key: "archive", label: "Plan archive", icon: ArchiveIcon },
  { key: "connections", label: "Connections", icon: LinkIcon },
];

function formatDisplayDate(dateValue) {
  return new Date(`${dateValue}T12:00:00`).toLocaleDateString("en-US", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
}

function formatShortDate(dateValue) {
  return new Date(`${dateValue}T12:00:00`).toLocaleDateString("en-US", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

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

function getPlanWindowLabel(plan) {
  const days = plan?.days || [];
  if (days.length === 0) return "No active schedule";
  const start = formatShortDate(days[0].date);
  const end = formatShortDate(days[days.length - 1].date);
  return `${start} - ${end}`;
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
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        width: "100%",
        display: "flex",
        alignItems: "center",
        gap: 12,
        border: "none",
        background: active ? tokens.bgHover : "transparent",
        color: active ? tokens.text : tokens.textMuted,
        borderRadius: tokens.radiusLg,
        padding: "12px 14px",
        cursor: "pointer",
        fontFamily: "inherit",
        fontSize: 14,
        fontWeight: active ? 600 : 500,
        textAlign: "left",
      }}
    >
      <Icon />
      <span>{label}</span>
    </button>
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
  calendarSync,
  onSessionClick,
  onSyncCalendar,
  onOpenAssistant,
}) {
  const nextSession = getUpcomingSession(visiblePlan);
  const blockersLabel = calendarSync.loading
    ? "Syncing blockers..."
    : calendarSync.error
      ? calendarSync.error
      : `${externalEvents.length} blockers in view`;

  return (
    <div style={{ display: "grid", gap: 20, minHeight: 0 }}>
      <div style={{
        display: "grid",
        gridTemplateColumns: "minmax(0, 1.5fr) repeat(3, minmax(0, 0.8fr))",
        gap: 16,
      }}>
        <SurfaceCard style={{ padding: 22 }}>
          <Eyebrow>Planner</Eyebrow>
          <div style={{
            fontSize: 34,
            lineHeight: 1.05,
            fontFamily: "'Playfair Display', serif",
            color: tokens.text,
            marginBottom: 10,
          }}>
            {getPlanWindowLabel(visiblePlan)}
          </div>
          <div style={{ fontSize: 14, color: tokens.textSecondary, lineHeight: 1.6, marginBottom: 18 }}>
            {draftPlan
              ? "You are viewing a reviewable draft. Nothing commits until you accept it."
              : "This is the live scheduling canvas. External blockers stay muted and study sessions stay readable."}
          </div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <ActionButton onClick={onOpenAssistant}>
              <ChatIcon />
              Open planner assistant
            </ActionButton>
            <ActionButton quiet onClick={onSyncCalendar} disabled={calendarSync.loading}>
              <RefreshIcon />
              {calendarSync.loading ? "Syncing..." : "Refresh blockers"}
            </ActionButton>
          </div>
        </SurfaceCard>
        <MetricTile
          label="Review state"
          value={draftPlan ? "Draft" : "Live"}
          detail={draftPlan ? "Approve or recommend changes from the assistant tray." : "Calendar reflects the current committed schedule."}
          accent={draftPlan ? tokens.red : tokens.accent}
        />
        <MetricTile
          label="Calendar reality"
          value={externalEvents.length}
          detail={blockersLabel}
          accent={tokens.yellow}
        />
        <MetricTile
          label="Next study block"
          value={nextSession ? nextSession.start_time : "--"}
          detail={nextSession ? `${nextSession.subject || "Study"} · ${nextSession.topic || ""}` : "No upcoming session placed yet."}
          accent={tokens.green}
        />
      </div>

      <SurfaceCard style={{
        padding: 0,
        overflow: "hidden",
        minHeight: 720,
        display: "flex",
        flexDirection: "column",
      }}>
        <div style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 16,
          padding: "18px 22px",
          borderBottom: `1px solid ${tokens.border}`,
          background: tokens.glassBg,
        }}>
          <div>
            <div style={{ fontSize: 12, color: tokens.textMuted, marginBottom: 4 }}>
              Week view
            </div>
            <div style={{ fontSize: 16, color: tokens.text, fontWeight: 600 }}>
              Schedule preview with blockers and study sessions
            </div>
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <StatusPill text={draftPlan ? "Draft only" : "Committed plan"} tone={draftPlan ? "warning" : "success"} />
            <StatusPill text={calendarSync.error ? "Sync issue" : "Calendar aware"} tone={calendarSync.error ? "danger" : "default"} />
          </div>
        </div>
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
  const { user, loading: authLoading } = useAuth();
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
  const [activeTab, setActiveTab] = useState("overview");
  const [showAI, setShowAI] = useState(false);
  const [focusMode, setFocusMode] = useState(false);
  const [showProfile, setShowProfile] = useState(false);
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

  const progressTopicCount = useMemo(() => Object.values(progress?.by_subject || {}).reduce(
    (count, items) => count + (Array.isArray(items) ? items.length : 0),
    0,
  ), [progress]);

  const progressDoneCount = useMemo(() => Object.values(progress?.by_subject || {}).reduce(
    (count, items) => count + (Array.isArray(items) ? items.filter(item => item?.status === "done").length : 0),
    0,
  ), [progress]);

  const visiblePlan = draftPlan || plan;
  const nextSession = getUpcomingSession(visiblePlan);

  const fetchAllPlans = async () => {
    try {
      setPlans(await planApi.listAll());
    } catch {
      // non-critical
    }
  };

  const fetchProgress = async () => {
    try {
      setProgress(await planApi.getProgress());
    } catch {
      setProgress({ by_subject: {} });
    }
  };

  const fetchStats = async () => {
    try {
      setStats(await statsApi.dashboard());
    } catch {
      // non-critical
    }
  };

  const fetchExternalEvents = async () => {
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
    const stop = startTimer("workspace:bootstrap");
    const data = await planApi.bootstrap();
    stop();
    setPlan(data.plan);
    setProgress(data.progress || { by_subject: {} });
    setStats(data.stats || null);
  };

  const hydrateCoreWorkspace = async () => {
    setLoading(true);
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
      setActiveTab("connections");
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
    setShowAI(true);
  }, []);

  const openPlanner = useCallback(() => {
    setActiveTab("planner");
  }, []);

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
        <aside style={{
          width: 248,
          borderRight: `1px solid ${tokens.sidebarBorder}`,
          background: tokens.sidebarBg,
          display: "flex",
          flexDirection: "column",
          padding: "18px 16px 16px",
          flexShrink: 0,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 26 }}>
            <div style={{
              width: 36,
              height: 36,
              borderRadius: "50%",
              background: "linear-gradient(135deg, #ddd3ff 0%, #b9afff 100%)",
              color: tokens.bg,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}>
              <CapIcon />
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
              <span style={{
                fontSize: 22,
                fontFamily: "'Playfair Display', serif",
                fontWeight: 600,
                color: tokens.text,
              }}>
                skedio
              </span>
              <span style={{ fontSize: 12, color: tokens.textDim, letterSpacing: "0.12em", textTransform: "uppercase" }}>
                AI
              </span>
            </div>
          </div>

          <div style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            borderRadius: tokens.radiusXl,
            border: `1px solid ${tokens.border}`,
            padding: "12px 14px",
            color: tokens.textMuted,
            marginBottom: 22,
          }}>
            <SearchIcon />
            <span style={{ flex: 1 }}>Search</span>
            <span style={{ fontSize: 11, color: tokens.textDim }}>⌘ K</span>
          </div>

          <div style={{ fontSize: 11, color: tokens.textDim, letterSpacing: "0.16em", textTransform: "uppercase", marginBottom: 12 }}>
            Workspace
          </div>
          <nav style={{ display: "grid", gap: 6 }}>
            {NAV_ITEMS.map(item => (
              <SidebarNavButton
                key={item.key}
                label={item.label}
                icon={item.icon}
                active={activeTab === item.key}
                onClick={() => setActiveTab(item.key)}
              />
            ))}
            <SidebarNavButton
              label="Knowledge map"
              icon={KnowledgeIcon}
              active={showGraph}
              onClick={() => setShowGraph(true)}
            />
          </nav>

          <div style={{ marginTop: 24, borderTop: `1px solid ${tokens.borderSubtle}`, paddingTop: 24 }}>
            <div style={{ fontSize: 11, color: tokens.textDim, letterSpacing: "0.16em", textTransform: "uppercase", marginBottom: 12 }}>
              Assistant
            </div>
            <ActionButton onClick={openAssistant} style={{ width: "100%", justifyContent: "center" }}>
              <ChatIcon />
              Open planner tray
            </ActionButton>
          </div>

          <div style={{ marginTop: "auto", paddingTop: 20 }}>
            <div style={{
              borderTop: `1px solid ${tokens.borderSubtle}`,
              paddingTop: 14,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 12,
            }}>
              <button
                type="button"
                onClick={() => setShowProfile(true)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  background: "transparent",
                  border: "none",
                  padding: 0,
                  cursor: "pointer",
                  minWidth: 0,
                  textAlign: "left",
                  color: "inherit",
                }}
                title={profileLabel}
              >
                <div style={{
                  width: 34,
                  height: 34,
                  borderRadius: "50%",
                  background: "#d8c6a9",
                  color: tokens.bg,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontWeight: 700,
                  flexShrink: 0,
                }}>
                  {profileInitials}
                </div>
                <div style={{ minWidth: 0 }}>
                  <div style={{ color: tokens.text, fontSize: 14, fontWeight: 600 }}>Maya Chen</div>
                  <div style={{ color: tokens.textDim, fontSize: 11 }}>Exams · {stats?.days_until_exam ?? 28} days</div>
                </div>
              </button>
              <button
                type="button"
                onClick={() => setFocusMode(prev => !prev)}
                style={{
                  border: `1px solid ${tokens.border}`,
                  background: "transparent",
                  color: focusMode ? tokens.text : tokens.textMuted,
                  borderRadius: tokens.radiusFull,
                  width: 36,
                  height: 36,
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: "pointer",
                }}
                title="Focus mode"
              >
                <FocusIcon />
              </button>
            </div>
          </div>
        </aside>

        <main style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", position: "relative" }}>
          <header style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            gap: 20,
            padding: "18px 26px",
            borderBottom: `1px solid ${tokens.borderSubtle}`,
          }}>
            <div>
              <div style={{ fontSize: 11, color: tokens.textDim, letterSpacing: "0.18em", textTransform: "uppercase", marginBottom: 8 }}>
                {formatDisplayDate(today)}
              </div>
              <div style={{ fontSize: 16, color: tokens.textSecondary }}>
                {visiblePlan?.days?.length
                  ? `${getPlanWindowLabel(visiblePlan)} · ${nextSession ? `next session at ${nextSession.start_time}` : "schedule loaded"}`
                  : "Your workspace is waiting for the next draft."}
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
              <button
                type="button"
                onClick={openAssistant}
                style={{
                  border: `1px solid ${tokens.border}`,
                  background: "transparent",
                  color: tokens.textMuted,
                  borderRadius: tokens.radiusMd,
                  padding: "10px 14px",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 8,
                  cursor: "pointer",
                  fontFamily: "inherit",
                  fontWeight: 600,
                }}
              >
                <ChatIcon />
                Planner assistant
              </button>
              <button
                type="button"
                onClick={() => setFocusMode(prev => !prev)}
                style={{
                  border: `1px solid ${focusMode ? tokens.accentBorder : tokens.border}`,
                  background: focusMode ? tokens.accentMuted : "transparent",
                  color: tokens.text,
                  borderRadius: tokens.radiusMd,
                  padding: "10px 14px",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 8,
                  cursor: "pointer",
                  fontFamily: "inherit",
                  fontWeight: 600,
                }}
              >
                <FocusIcon />
                Focus mode
              </button>
            </div>
          </header>

          <div style={{
            flex: 1,
            minHeight: 0,
            overflowY: "auto",
            padding: focusMode ? "18px 18px 28px" : "26px",
            background: tokens.bg,
          }}>
            <ViewErrorBoundary resetKey={activeTab}>
              {activeTab === "overview" && (
                <OverviewTab
                  visiblePlan={visiblePlan}
                  draftPlan={draftPlan}
                  stats={stats}
                  progress={progress}
                  externalEvents={externalEvents}
                  onOpenPlanner={openPlanner}
                  onOpenAssistant={openAssistant}
                  onOpenGraph={() => setShowGraph(true)}
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

              {activeTab === "connections" && (
                <div style={{ paddingTop: 6 }}>
                  <SettingsView onBack={() => setActiveTab("overview")} />
                </div>
              )}
            </ViewErrorBoundary>
          </div>

          {showAI && (
            <div
              style={{
                position: "absolute",
                inset: 0,
                background: "rgba(6,6,8,0.58)",
                backdropFilter: "blur(8px)",
                WebkitBackdropFilter: "blur(8px)",
                zIndex: tokens.zIndexDrawer,
                display: "flex",
                justifyContent: "center",
                alignItems: "flex-start",
                padding: "20px 20px 32px",
              }}
              onClick={() => setShowAI(false)}
            >
              <div
                style={{
                  width: "min(1040px, 100%)",
                  height: "min(78vh, 860px)",
                  animation: "modalScaleUp 0.24s cubic-bezier(0.16, 1, 0.3, 1)",
                }}
                onClick={event => event.stopPropagation()}
              >
                <ChatPanel
                  threadId={threadId}
                  onClose={() => setShowAI(false)}
                  onPlanCommitted={handleRefreshAll}
                  onDraftStateChange={handleDraftStateChange}
                  devToolsEnabled={devToolsEnabled}
                  onLoadDevDraftPreview={handleLoadDevDraftPreview}
                  onClearDevDraftPreview={handleClearDevDraftPreview}
                  devPreviewNonce={devPreviewNonce}
                  devReviewPreviewPayload={devReviewPreviewPayload}
                  emailReviewRequest={emailReviewRequest}
                  isEmbedded={true}
                />
              </div>
            </div>
          )}
        </main>

        {showProfile && (
          <ProfileDashboardModal stats={stats} onClose={() => setShowProfile(false)} userId={userId} />
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

function FocusIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="7" />
      <circle cx="12" cy="12" r="2.5" />
    </svg>
  );
}

function ArchiveIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 8h16" />
      <rect x="3" y="4" width="18" height="4" rx="1.5" />
      <path d="M6 8v10a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V8" />
      <path d="M10 12h4" />
    </svg>
  );
}

function LinkIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10 13a5 5 0 0 0 7.07 0l2.83-2.83a5 5 0 0 0-7.07-7.07L11 4.93" />
      <path d="M14 11a5 5 0 0 0-7.07 0L4.1 13.83a5 5 0 0 0 7.07 7.07L13 19.07" />
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

function ChatIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="7" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}

function RefreshIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 2v6h-6" />
      <path d="M3 12a9 9 0 0 1 15-6.7L21 8" />
      <path d="M3 22v-6h6" />
      <path d="M21 12a9 9 0 0 1-15 6.7L3 16" />
    </svg>
  );
}

function CapIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="m2 9 10-5 10 5-10 5Z" />
      <path d="M6 11.5V16c0 1.7 2.7 3 6 3s6-1.3 6-3v-4.5" />
    </svg>
  );
}
