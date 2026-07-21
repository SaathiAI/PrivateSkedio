import { useEffect, useState } from "react";
import "./LandingPage.css";
import { OrbitingCircles } from "./orbiting-circles";

const weekDays = [
  { day: "Tue", date: "21", active: true },
  { day: "Wed", date: "22" },
  { day: "Thu", date: "23" },
  { day: "Fri", date: "24" },
  { day: "Sat", date: "25" },
];

const sessions = [
  { day: 0, top: 30, height: 74, title: "Math sprint", meta: "09:30 - 11:00", tone: "green", delay: "0ms" },
  { day: 1, top: 44, height: 52, title: "Science recap", meta: "10:15 - 11:15", tone: "amber", delay: "110ms" },
  { day: 2, top: 132, height: 70, title: "Polynomial practice", meta: "14:00 - 15:15", tone: "violet", delay: "220ms" },
  { day: 3, top: 28, height: 78, title: "Focus block", meta: "09:30 - 11:00", tone: "green", delay: "330ms" },
  { day: 4, top: 132, height: 70, title: "Review and recall", meta: "14:00 - 15:15", tone: "violet", delay: "440ms" },
];

const features = [
  {
    label: "Intake",
    title: "Talk like a person.",
    body: "SkedioAI turns messy goals into a planning contract: subject, deadline, scope, available hours, and real constraints.",
  },
  {
    label: "Planner",
    title: "Drafts that respect reality.",
    body: "Sessions land around calendar blockers, lunch, sleep, progress pressure, and the time that is actually available.",
  },
  {
    label: "Memory",
    title: "The week learns back.",
    body: "Checklist completion, skipped work, and active-plan history feed the next revision instead of disappearing.",
  },
];

const dashboardRows = [
  ["Polynomials", "Core theory", "72%", "violet"],
  ["Quadratics", "Practice set", "54%", "green"],
  ["Electricity", "Recall pass", "38%", "amber"],
  ["English", "Review notes", "64%", "rose"],
];

const emailLines = [
  "Your revised July study plan is ready for review.",
  "SkedioAI protected lunch, Daily Standup, and the Friday blocker before placing the next focus blocks.",
  "Please approve the draft or send changes before it is committed to Google Calendar.",
];

const scheduleScores = [
  ["Tue 09:30", "Best focus fit", "96"],
  ["Wed 14:00", "After school", "78"],
  ["Fri 16:30", "Light review", "66"],
];

const checklistItems = [
  "Revise factorisation rules",
  "Solve mixed theorem problems",
  "Mark weak derivations",
  "Write a 5-line recap",
];

const storyCards = [
  {
    label: "01",
    title: "Messy intent becomes a contract.",
    body: "The assistant extracts subject, deadline, effort, weak areas, and the kind of week the student can actually survive.",
    meta: "Conversation",
  },
  {
    label: "02",
    title: "Calendar reality shapes the draft.",
    body: "Lunch, school blocks, standups, sleep, and recovery windows become hard edges before any session is placed.",
    meta: "Scheduling",
  },
  {
    label: "03",
    title: "Every tick changes tomorrow.",
    body: "A checked item updates progress, backlog pressure, and what the next revision knows about the student's truth.",
    meta: "Memory",
  },
  {
    label: "04",
    title: "The week closes with a review.",
    body: "SkedioAI sends a clean plan review, waits for approval, then commits the schedule back into the calendar.",
    meta: "Loop",
  },
];

const rescheduleDays = ["Tue 21", "Wed 22", "Thu 23", "Fri 24"];

const fixedBlocks = [
  { day: 0, top: 82, height: 46, title: "School", meta: "08:00 - 08:45" },
  { day: 1, top: 190, height: 54, title: "Lunch", meta: "11:30" },
  { day: 2, top: 238, height: 54, title: "Standup", meta: "12:30" },
  { day: 3, top: 178, height: 48, title: "Project call", meta: "11:15 - 12:00" },
];

const candidateBlocks = [
  {
    day: 0,
    top: 152,
    height: 86,
    title: "Quadratics sprint",
    meta: "09:30 - 11:00",
    tone: "green",
    delay: "0ms",
    tasks: ["Revise discriminant rules", "Solve 6 mixed equations", "Mark one weak method"],
  },
  {
    day: 1,
    top: 266,
    height: 92,
    title: "Polynomials practice",
    meta: "14:00 - 15:20",
    tone: "violet",
    delay: "180ms",
    tasks: ["Factor theorem examples", "Remainder theorem drill", "Save 3 exam-style misses"],
  },
  {
    day: 2,
    top: 122,
    height: 78,
    title: "Electricity recall",
    meta: "09:15 - 10:15",
    tone: "amber",
    delay: "360ms",
    tasks: ["Rewrite Ohm's law notes", "Practice circuit diagrams", "Check units before answers"],
  },
  {
    day: 3,
    top: 276,
    height: 82,
    title: "English review",
    meta: "14:30 - 15:45",
    tone: "rose",
    delay: "540ms",
    tasks: ["Recall quote bank", "Tighten intro paragraph", "Review teacher feedback"],
  },
];

function SnapText({ children }) {
  return (
    <span className="lp-snap-text">
      {children.split(" ").map((word, index) => (
        <span
          className="lp-snap-word"
          style={{
            "--word": index,
            "--scatter-x": `${((index % 5) - 2) * 11}px`,
            "--scatter-y": `${((index % 4) - 1.5) * 10}px`,
            "--scatter-rotate": `${((index % 6) - 2.5) * 3.5}deg`,
          }}
          key={`${word}-${index}`}
        >
          {word}
        </span>
      ))}
    </span>
  );
}

function LogoMark({ small = false }) {
  return (
    <svg className={small ? "lp-logo is-small" : "lp-logo"} viewBox="0 0 64 64" aria-hidden="true">
      <path d="M32 28 20 16M32 28l12-12M32 28v17" />
      <path d="M32 45c-4 4-8 5-13 5M32 45c4 4 8 5 13 5M32 45c-1 5-3 8-7 11M32 45c1 5 3 8 7 11" className="thin" />
      <path d="M32 57c-2.2-2.8-2.2-4.9 0-7.4 2.2 2.5 2.2 4.6 0 7.4Z" className="root" />
      <path d="M32 5c5 5.2 5 10.3 0 15.5C27 15.3 27 10.2 32 5Z" className="leaf top" />
      <path d="M16 17c5.5.8 8.5 3.8 9.2 9.2C19.8 25.5 16.8 22.5 16 17Z" className="leaf" />
      <path d="M48 17c-.8 5.5-3.8 8.5-9.2 9.2C39.5 20.8 42.5 17.8 48 17Z" className="leaf" />
      <path d="M11 30c4.4-.7 7.4.9 9.1 4.8C15.8 35.4 12.8 33.8 11 30Z" className="leaf pale" />
      <path d="M53 30c-1.8 3.8-4.8 5.4-9.1 4.8C45.6 30.9 48.6 29.3 53 30Z" className="leaf pale" />
      <path d="M24 30c3.1.6 4.8 2.4 5.2 5.5C26.1 34.9 24.4 33.1 24 30Z" className="leaf small" />
      <path d="M40 30c-.4 3.1-2.1 4.9-5.2 5.5C35.2 32.4 36.9 30.6 40 30Z" className="leaf small" />
    </svg>
  );
}

function GmailLogo() {
  return (
    <svg className="lp-brand-logo" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#4285F4" d="M8.5 12.5v24.8c0 1.5 1.2 2.7 2.7 2.7h6.1V24.6L8.5 18v-5.5Z" />
      <path fill="#34A853" d="M30.7 40h6.1c1.5 0 2.7-1.2 2.7-2.7V12.5L30.7 18v22Z" />
      <path fill="#EA4335" d="M17.3 24.6 24 29.6l6.7-5V18L24 23l-6.7-5v6.6Z" />
      <path fill="#FBBC05" d="M30.7 18 39.5 12.5v-.6c0-2.9-3.3-4.6-5.7-2.9l-3.1 2.3V18Z" />
      <path fill="#C5221F" d="M8.5 11.9v6.1l8.8 6.6V18L14.2 15.7c-2.4-1.8-5.7-.1-5.7-3.8Z" />
    </svg>
  );
}

function GoogleCalendarLogo() {
  return (
    <svg className="lp-brand-logo" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#4285F4" d="M10 7h21.8L38 13.2V38c0 1.7-1.3 3-3 3H10c-1.7 0-3-1.3-3-3V10c0-1.7 1.3-3 3-3Z" />
      <path fill="#34A853" d="M7 18h31v20c0 1.7-1.3 3-3 3H10c-1.7 0-3-1.3-3-3V18Z" />
      <path fill="#FBBC05" d="M31.8 7H35c1.7 0 3 1.3 3 3v8h-6.2V7Z" />
      <path fill="#EA4335" d="M7 13h31v7H7v-7Z" />
      <path fill="#fff" d="M12.5 21h23v16h-23z" />
      <text x="24" y="34" textAnchor="middle" fill="#4285F4" fontSize="13" fontWeight="800" fontFamily="Manrope, Arial, sans-serif">
        31
      </text>
    </svg>
  );
}

function CalendarPreview() {
  return (
    <div className="lp-calendar-preview" aria-label="SkedioAI planner preview">
      <aside className="lp-mini-sidebar">
        <LogoMark small />
        <span className="lp-side-icon is-active">□</span>
        <span className="lp-side-icon">▦</span>
        <span className="lp-side-icon">⌁</span>
        <span className="lp-side-icon">☼</span>
        <span className="lp-avatar">PR</span>
      </aside>
      <div className="lp-calendar-shell">
        <div className="lp-calendar-head">
          <div>
            <span className="lp-kicker">Planner</span>
            <h3>Jul 21 - Jul 27, 2026</h3>
          </div>
          <div className="lp-head-actions">
            <span />
            <span />
            <span />
          </div>
        </div>
        <div className="lp-week">
          {weekDays.map((item) => (
            <div className="lp-day" key={item.day}>
              <span>{item.day}</span>
              <b className={item.active ? "is-today" : ""}>{item.date}</b>
            </div>
          ))}
        </div>
        <div className="lp-grid">
          <div className="lp-now-line" />
          {sessions.map((session) => (
            <div
              className={`lp-session is-${session.tone}`}
              key={`${session.day}-${session.title}`}
              style={{
                "--day": session.day,
                "--top": `${session.top}px`,
                "--height": `${session.height}px`,
                "--delay": session.delay,
              }}
            >
              <strong>{session.title}</strong>
              <span>{session.meta}</span>
            </div>
          ))}
        </div>
        <form className="lp-assistant-bar">
          <LogoMark small />
          <span>Ask SkedioAI to revise around blockers...</span>
          <button type="button" aria-label="Open assistant">↗</button>
        </form>
      </div>
    </div>
  );
}

function DraftSequence() {
  return (
    <div className="lp-draft-stage">
      {[
        ["Calendar truth", "Standup and lunch stay protected."],
        ["Backlog pressure", "Quadratics gets the first focused block."],
        ["Draft plan", "Study slots land one by one."],
      ].map(([title, body], index) => (
        <div className="lp-draft-card" style={{ "--i": index }} key={title}>
          <span>0{index + 1}</span>
          <strong>{title}</strong>
          <p>{body}</p>
        </div>
      ))}
    </div>
  );
}

function StoryStack() {
  return (
    <section className="lp-story-section" id="story">
      <div className="lp-story-copy">
        <span className="lp-kicker">Scroll story</span>
        <h2><SnapText>Watch the study week assemble itself.</SnapText></h2>
        <p>
          The landing now follows the same loop as the product: understand the student,
          respect reality, update memory, then close the week cleanly.
        </p>
      </div>
      <div className="lp-story-stack">
        {storyCards.map((card, index) => (
          <article className="lp-story-card" style={{ "--i": index }} key={card.title}>
            <span>{card.label}</span>
            <small>{card.meta}</small>
            <h3>{card.title}</h3>
            <p>{card.body}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function AutoRescheduleDemo() {
  const [phase, setPhase] = useState("idle");
  const [selectedSlot, setSelectedSlot] = useState(null);
  const showDraft = phase !== "idle";

  useEffect(() => {
    if (phase !== "drafting") {
      return undefined;
    }

    const timer = window.setTimeout(() => setPhase("pending"), 2500);
    return () => window.clearTimeout(timer);
  }, [phase]);

  useEffect(() => {
    if (!showDraft) {
      setSelectedSlot(null);
    }
  }, [showDraft]);

  const startDraft = () => {
    setSelectedSlot(null);
    setPhase("drafting");
  };
  const approveDraft = () => setPhase("approved");
  const replayDraft = () => {
    setSelectedSlot(null);
    setPhase("drafting");
  };
  const activeSlot = selectedSlot === null ? null : candidateBlocks[selectedSlot];

  return (
    <section className={`lp-reschedule-section is-visible is-${phase}`} id="auto-reschedule">
      <div className="lp-section-copy">
        <span className="lp-kicker">Review before commit</span>
        <h2><SnapText>Draft slots float in. One approval commits the plan.</SnapText></h2>
        <p>
          SkedioAI does not silently rewrite the calendar. It proposes the whole
          revised plan, shows exactly where sessions land, then waits for approval.
        </p>
      </div>

      <div className="lp-reschedule-demo">
        <div className="lp-reschedule-calendar" aria-label="Draft study plan preview">
          <div className="lp-reschedule-topbar">
            <div>
              <span>Draft calendar</span>
              <strong>Jul 21 - Jul 24</strong>
            </div>
            <div className="lp-reschedule-state" aria-live="polite">
              {phase === "idle" && "Ready"}
              {phase === "drafting" && "Building draft"}
              {phase === "pending" && "Awaiting approval"}
              {phase === "approved" && "Committed"}
            </div>
          </div>

          <div className="lp-reschedule-days">
            <span />
            {rescheduleDays.map((day, index) => (
              <b className={index === 0 ? "is-today" : ""} key={day}>{day}</b>
            ))}
          </div>

          <div className="lp-reschedule-grid">
            {["8 AM", "10 AM", "12 PM", "2 PM", "4 PM"].map((time) => (
              <span className="lp-reschedule-time" key={time}>{time}</span>
            ))}

            {fixedBlocks.map((block) => (
              <article
                className="lp-reschedule-block is-fixed"
                style={{
                  "--day": block.day,
                  "--top": `${block.top}px`,
                  "--height": `${block.height}px`,
                }}
                key={`${block.day}-${block.title}`}
              >
                <strong>{block.title}</strong>
                <small>{block.meta}</small>
              </article>
            ))}

            {showDraft && candidateBlocks.map((block, index) => (
              <article
                className={`lp-reschedule-block is-candidate is-${block.tone}${selectedSlot === index ? " is-selected" : ""}`}
                style={{
                  "--day": block.day,
                  "--top": `${block.top}px`,
                  "--height": `${block.height}px`,
                  "--delay": block.delay,
                  "--i": index,
                }}
                key={`${block.day}-${block.title}`}
                role="button"
                tabIndex={0}
                onClick={() => setSelectedSlot(index)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    setSelectedSlot(index);
                  }
                }}
              >
                <span>{phase === "approved" ? "Committed" : "Draft"}</span>
                <strong>{block.title}</strong>
                <small>{block.meta}</small>
              </article>
            ))}

            <div className="lp-reschedule-scan" aria-hidden="true" />

            {activeSlot && (
              <div
                className={`lp-slot-readonly is-${activeSlot.tone}`}
                style={{ "--day": activeSlot.day }}
                role="dialog"
                aria-label={`${activeSlot.title} checklist preview`}
              >
                <button type="button" onClick={() => setSelectedSlot(null)} aria-label="Close checklist">×</button>
                <span>{phase === "approved" ? "Committed slot" : "Draft slot"}</span>
                <strong>{activeSlot.title}</strong>
                <small>{activeSlot.meta} · read-only checklist</small>
                <div>
                  {activeSlot.tasks.map((task, index) => (
                    <p style={{ "--i": index }} key={task}>
                      <i aria-hidden="true" />
                      <b>{task}</b>
                    </p>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="lp-reschedule-chat">
          <div className="lp-chat-head">
            <LogoMark small />
            <div>
              <strong>SkedioAI</strong>
              <span>whole-plan approval</span>
            </div>
          </div>

          <div className="lp-reschedule-thread" aria-live="polite">
            {phase === "idle" && (
              <>
                <p className="is-user">Can you rebuild the week around blockers?</p>
                <p className="is-ai">Yes. I will draft the full plan first, then ask before anything is committed.</p>
              </>
            )}
            {phase === "drafting" && (
              <>
                <p className="is-ai">Reading fixed calendar blocks...</p>
                <p className="is-ai">Scoring open gaps by focus quality and deadline pressure...</p>
                <p className="is-ai is-thinking">Placing candidate sessions now.</p>
              </>
            )}
            {phase === "pending" && (
              <>
                <p className="is-ai">Draft ready: 4 sessions placed, no blocker collisions.</p>
                <p className="is-ai">Approve this plan to commit every proposed slot together.</p>
              </>
            )}
            {phase === "approved" && (
              <>
                <p className="is-ai">Approved. I committed the full draft plan to the calendar.</p>
                <p className="is-ai">The next dashboard and review email now use this version.</p>
              </>
            )}
          </div>

          <div className="lp-reschedule-actions">
            {phase === "idle" && <button type="button" onClick={startDraft}>Draft plan</button>}
            {phase === "drafting" && <button type="button" disabled>Drafting...</button>}
            {phase === "pending" && (
              <>
                <button type="button" onClick={approveDraft}>Approve plan</button>
                <button type="button" onClick={replayDraft}>Change it</button>
              </>
            )}
            {phase === "approved" && <button type="button" onClick={replayDraft}>Replay draft</button>}
          </div>
        </div>
      </div>
    </section>
  );
}

function DashboardPreview() {
  return (
    <div className="lp-dashboard-card">
      <div className="lp-panel-title">
        <span>Dashboard</span>
        <b>Study momentum at a glance</b>
      </div>
      <div className="lp-chart">
        <svg viewBox="0 0 520 220" aria-hidden="true">
          <path d="M24 162 C110 138 165 124 220 98 C290 65 342 86 408 126 C450 151 486 143 502 134" />
          <circle cx="24" cy="162" r="6" />
          <circle cx="220" cy="98" r="6" />
          <circle cx="502" cy="134" r="6" />
        </svg>
      </div>
      <div className="lp-subject-list">
        {dashboardRows.map(([topic, detail, pct, tone], index) => (
          <div className="lp-subject-row" style={{ "--row": index }} key={topic}>
            <div>
              <strong>{topic}</strong>
              <span>{detail}</span>
            </div>
            <b>{pct}</b>
            <i className={`is-${tone}`} style={{ "--w": pct }} />
          </div>
        ))}
      </div>
    </div>
  );
}

function KnowledgePreview() {
  const nodes = [
    ["You", 72, 70, "you", "-8px", "9px"],
    ["maths", 53, 55, "subject", "10px", "-8px"],
    ["Quadratics", 31, 35, "chapter", "-6px", "-10px"],
    ["Polynomials", 61, 30, "chapter", "8px", "7px"],
    ["Formula practice", 24, 62, "node", "-10px", "6px"],
    ["Factor theorem", 72, 44, "node", "7px", "-9px"],
  ];

  return (
    <div className="lp-graph-card">
      <div className="lp-graph-bg" />
      <svg className="lp-graph-lines" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        <path d="M72 70 53 55 31 35M53 55 61 30M53 55 24 62M53 55 72 44" />
      </svg>
      {nodes.map(([name, x, y, type, dx, dy], index) => (
        <div
          className={`lp-node is-${type}`}
          style={{ left: `${x}%`, top: `${y}%`, "--i": index, "--dx": dx, "--dy": dy }}
          key={name}
        >
          <span>{name}</span>
        </div>
      ))}
    </div>
  );
}

function SchedulerPreview() {
  return (
    <div className="lp-scheduler-card">
      <div className="lp-panel-title">
        <span>Auto scheduling</span>
        <b>Every slot gets scored before it lands.</b>
      </div>
      <div className="lp-score-list">
        {scheduleScores.map(([time, label, score], index) => (
          <div className="lp-score-row" key={time} style={{ "--i": index, "--score": `${score}%` }}>
            <div>
              <strong>{time}</strong>
              <span>{label}</span>
            </div>
            <b>{score}</b>
            <i />
          </div>
        ))}
      </div>
      <div className="lp-scheduler-result">
        <span>Chosen</span>
        <strong>Tue 09:30 - Mathematics sprint</strong>
        <p>Morning focus, no blocker overlap, enough buffer before lunch.</p>
      </div>
    </div>
  );
}

function ChatPreview() {
  return (
    <div className="lp-chat-card">
      <div className="lp-chat-head">
        <LogoMark small />
        <div>
          <strong>SkedioAI</strong>
          <span>planner assistant</span>
        </div>
      </div>
      <div className="lp-chat-thread">
        <p className="is-user">Can you plan my next study block?</p>
        <p className="is-ai">I can. Your calendar has lunch at 11:30 and a standup at 12:30. I’ll place maths before that.</p>
        <p className="is-user">Keep evenings lighter.</p>
        <p className="is-ai">Done. I’ll use evenings for recall, not heavy problem solving.</p>
      </div>
      <div className="lp-chat-input">
        <span>Ask SkedioAI...</span>
        <button type="button">↑</button>
      </div>
    </div>
  );
}

function ChecklistPreview() {
  const [checkedItems, setCheckedItems] = useState(() => checklistItems.map((_, index) => index < 2));
  const checkedCount = checkedItems.filter(Boolean).length;
  const progress = `${Math.round((checkedCount / checklistItems.length) * 100)}%`;

  return (
    <div className="lp-checklist-card" style={{ "--progress": progress }}>
      <div className="lp-panel-title">
        <span>Session checklist</span>
        <b>Ticking work updates the plan truth.</b>
      </div>
      <div className="lp-check-progress"><i /></div>
      <div className="lp-check-list">
        {checklistItems.map((item, index) => (
          <label className="lp-check-item" style={{ "--i": index }} key={item}>
            <input
              type="checkbox"
              checked={checkedItems[index]}
              onChange={() => {
                setCheckedItems((items) => items.map((value, itemIndex) => itemIndex === index ? !value : value));
              }}
            />
            <span />
            <b>{item}</b>
          </label>
        ))}
      </div>
    </div>
  );
}

function IntegrationPreview() {
  return (
    <div className="lp-integration-orbit-demo" aria-label="Gmail and Google Calendar integration animation">
      <div className="lp-integration-center">
        <LogoMark />
      </div>
      <OrbitingCircles iconSize={112} radius={154} duration={18} delay={0}>
        <div className="lp-orbit-app" aria-label="Gmail">
          <GmailLogo />
        </div>
        <div className="lp-orbit-app" aria-label="Google Calendar">
          <GoogleCalendarLogo />
        </div>
      </OrbitingCircles>
    </div>
  );
}

function EmailPreview() {
  return (
    <div className="lp-email-card">
      <div className="lp-email-top">
        <span>From SkedioAI</span>
        <b>Plan review</b>
      </div>
      <h3>Your week is ready to review</h3>
      {emailLines.map((line) => (
        <p key={line}>{line}</p>
      ))}
      <div className="lp-email-actions">
        <button type="button">Approve plan</button>
        <button type="button">Change it</button>
      </div>
    </div>
  );
}

function LandingFooter() {
  return (
    <footer className="lp-footer">
      <div className="lp-footer-top">
        <a className="lp-brand" href="#landing" aria-label="SkedioAI landing footer">
          <LogoMark small />
          <span>
            <b>SkedioAI</b>
            <small>study planner</small>
          </span>
        </a>
        <div className="lp-footer-links">
          <div>
            <strong>Product</strong>
            <a href="#loop">Planner</a>
            <a href="#signals">Dashboard</a>
            <a href="#integrations">Integrations</a>
          </div>
          <div>
            <strong>Features</strong>
            <a href="#schedule">Auto scheduling</a>
            <a href="#signals">Checklist memory</a>
            <a href="#integrations">Review email</a>
          </div>
          <div>
            <strong>Company</strong>
            <a href="#app">Open app</a>
            <a href="#landing">Privacy</a>
            <a href="#landing">Support</a>
          </div>
        </div>
      </div>
      <div className="lp-footer-close">
        <div className="lp-footer-close-mark" aria-hidden="true">
          <LogoMark />
        </div>
        <div>
          <h2>Make the week readable.</h2>
          <p>Open SkedioAI, connect the calendar, and let the plan bend around the life already there.</p>
        </div>
        <a href="#app">Open the app</a>
      </div>
      <div className="lp-footer-bottom">
        <span>© 2026 SkedioAI</span>
        <span>Calendar-aware study planning</span>
        <span>Built for realistic weekly execution</span>
      </div>
    </footer>
  );
}

export function LandingPage() {
  useEffect(() => {
    const elements = document.querySelectorAll(
      ".lp-section, .lp-split-section, .lp-story-section, .lp-story-card, .lp-reschedule-section, .lp-feature-card, .lp-draft-card, .lp-three-panel > *, .lp-dashboard-card, .lp-graph-card, .lp-integrations-stack > *, .lp-footer"
    );

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.16, rootMargin: "0px 0px -8% 0px" }
    );

    elements.forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, []);

  return (
    <main className="lp-page">
      <div className="lp-noise" aria-hidden="true" />
      <div className="lp-ambient-field" aria-hidden="true" />
      <nav className="lp-nav">
        <a className="lp-brand" href="#landing" aria-label="SkedioAI landing">
          <LogoMark small />
          <span>
            <b>SkedioAI</b>
            <small>study planner</small>
          </span>
        </a>
        <div className="lp-nav-links">
          <a href="#loop">Loop</a>
          <a href="#signals">Signals</a>
          <a href="#integrations">Integrations</a>
        </div>
        <a className="lp-nav-action" href="#app">Open app</a>
      </nav>

      <section className="lp-hero">
        <div className="lp-hero-copy">
          <span className="lp-pill">Calendar-aware study OS</span>
          <h1><SnapText>Plan the week your student can actually follow.</SnapText></h1>
          <p>
            SkedioAI turns syllabus pressure, real calendar blockers, active-plan memory,
            and checklist truth into one clean weekly study flow.
          </p>
          <div className="lp-hero-actions">
            <a href="#app">Start planning</a>
            <a href="#loop">Watch the loop</a>
          </div>
        </div>
      </section>

      <section className="lp-product-theatre" aria-label="SkedioAI product preview">
        <div className="lp-theatre-glow" aria-hidden="true" />
        <div className="lp-floating-chip lp-chip-a">Calendar connected</div>
        <div className="lp-floating-chip lp-chip-b">3 blockers protected</div>
        <CalendarPreview />
      </section>

      <section className="lp-strip" aria-label="Product promise">
        <span>Intake contract</span>
        <span>Calendar blockers</span>
        <span>Draft preview</span>
        <span>Checklist truth</span>
        <span>Review email</span>
      </section>

      <StoryStack />

      <AutoRescheduleDemo />

      <section className="lp-section lp-centered-section" id="loop">
        <div className="lp-section-copy">
          <span className="lp-kicker">The planning loop</span>
          <h2><SnapText>Not a timetable generator. A week operating system.</SnapText></h2>
          <p>
            The assistant captures the real contract first, then the planner places
            work into the calendar only after the constraints make sense.
          </p>
        </div>
        <div className="lp-feature-grid">
          {features.map((feature) => (
            <article className="lp-feature-card" key={feature.title}>
              <span>{feature.label}</span>
              <h3>{feature.title}</h3>
              <p>{feature.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="lp-split-section">
        <div className="lp-section-copy">
          <span className="lp-kicker">Draft preview</span>
          <h2><SnapText>Watch the plan assemble before it commits.</SnapText></h2>
          <p>
            Draft sessions float into place, glow while they are provisional, and
            become durable only after review.
          </p>
        </div>
        <DraftSequence />
      </section>

      <section className="lp-section lp-centered-section" id="schedule">
        <div className="lp-section-copy">
          <span className="lp-kicker">Scheduling intelligence</span>
          <h2><SnapText>It does not just place sessions. It chooses why.</SnapText></h2>
          <p>
            SkedioAI scores candidate slots by focus quality, blocker safety, deadline pressure,
            and workload balance before the plan becomes visible.
          </p>
        </div>
        <div className="lp-three-panel">
          <SchedulerPreview />
          <ChatPreview />
          <ChecklistPreview />
        </div>
      </section>

      <section className="lp-section lp-centered-section" id="signals">
        <div className="lp-section-copy">
          <span className="lp-kicker">Progress signals</span>
          <h2><SnapText>Every checkbox changes what the system knows.</SnapText></h2>
        </div>
        <div className="lp-two-up">
          <DashboardPreview />
          <KnowledgePreview />
        </div>
      </section>

      <section className="lp-split-section" id="integrations">
        <div className="lp-section-copy">
          <span className="lp-kicker">Connected apps</span>
          <h2><SnapText>Gmail and Calendar close the loop.</SnapText></h2>
          <p>
            SkedioAI can read blockers, sync study sessions, and send a clean review
            email when a new plan needs approval.
          </p>
        </div>
        <div className="lp-integrations-stack">
          <IntegrationPreview />
          <div id="demo-email">
            <EmailPreview />
          </div>
        </div>
      </section>
      <LandingFooter />
    </main>
  );
}
