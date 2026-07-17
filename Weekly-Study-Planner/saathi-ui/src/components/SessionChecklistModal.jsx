import { tokens, getSubjectPalette } from "../theme.js";
import { Spinner } from "./ui.jsx";
import { useSessionActions } from "../hooks/useSessionActions.js";

function CheckMarkIcon() {
  return (
    <svg width="11" height="9" viewBox="0 0 11 9" fill="none" aria-hidden="true">
      <path
        d="M1.25 4.5 4.1 7.25 9.75 1.5"
        stroke="#fffdf8"
        strokeWidth="1.9"
        strokeLinecap="round"
        strokeLinejoin="round"
        pathLength="1"
        style={{
          strokeDasharray: 1,
          strokeDashoffset: 0,
          animation: "skCheckDraw 180ms cubic-bezier(0.22, 1, 0.36, 1)",
        }}
      />
    </svg>
  );
}

export function SessionChecklistModal({ sessionObj, onClose, onRefresh }) {
  const { session } = sessionObj;
  const {
    contentLoading: subtopicLoading,
    sessionLoading,
    completeSession,
    undoSession,
    skipSession,
    updateContentStatus,
  } = useSessionActions(onRefresh);
  
  const derivedSubject = (session.contents && session.contents[0] && session.contents[0].subjects && session.contents[0].subjects[0]) || "General";
  const palette = getSubjectPalette(derivedSubject);
  const titleToUse = session.title || session.topic;
  
  const allSubs = Array.isArray(session.contents) ? session.contents : [];
  const completedSubs = allSubs.filter(c => c.status === 'done').map(c => c.match_key);
  const subPct = allSubs.length > 0 ? completedSubs.length / allSubs.length : 0;
  const allSubsDone = allSubs.length > 0 && completedSubs.length >= allSubs.length;
  const isCompleted = session.status === 'done';
  const isSkipped = session.status === 'skipped';

  const askHours = (label, suggestedHours = "") => {
    const initialValue = suggestedHours === "" ? "" : String(suggestedHours);
    const raw = window.prompt(
      `${label}\n\nEnter hours as a number like 0.5, 1, 1.25`,
      initialValue,
    );
    if (raw === null) return null;
    const normalized = String(raw).trim();
    if (!normalized) {
      return suggestedHours === "" ? null : Number(suggestedHours);
    }
    const parsed = Number(normalized);
    if (!Number.isFinite(parsed) || parsed < 0) {
      window.alert("Please enter a valid non-negative number of hours.");
      return null;
    }
    return parsed;
  };

  const handleSubtopicClick = (contentKey) => {
    if (subtopicLoading[contentKey]) return;
    const isDone = completedSubs.includes(contentKey);
    if (isDone) {
      updateContentStatus(session.session_id, contentKey, 'pending', 0);
      return;
    }
    const hours = askHours("How much time did this subtopic actually take?", 0.25);
    if (hours === null) return;
    updateContentStatus(session.session_id, contentKey, 'done', hours);
  };

  const doCompleteSession = async () => {
    const hours = askHours("How much time did this full session actually take?", session.estimated_hours);
    if (hours === null) return;
    const res = await completeSession(session.session_id, hours);
    if (res?.ok) {
      onClose();
    }
  };

  const doUndoSession = async () => {
    await undoSession(session.session_id);
  };

  const doSkipSession = async () => {
    const confirmed = window.confirm("Mark this session as skipped?");
    if (!confirmed) return;
    const res = await skipSession(session.session_id);
    if (res?.ok) {
      onClose();
    }
  };

  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(24, 22, 19, 0.22)",
      display: "flex", alignItems: "center", justifyContent: "center",
      zIndex: 2000, animation: "fadeIn 0.25s ease-out", backdropFilter: "blur(10px)",
    }}>
      <div style={{ position: 'absolute', inset: 0 }} onClick={onClose} />
      <div style={{
        position: 'relative', width: 472, background: tokens.bgCard,
        borderRadius: 24, border: `1px solid ${tokens.border}`,
        boxShadow: tokens.shadowXl,
        animation: "modalScaleUp 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards", padding: 32,
        display: "flex", flexDirection: "column", gap: 22,
      }}>
        <style>{`
          @keyframes skCheckDraw {
            from { stroke-dashoffset: 1; }
            to { stroke-dashoffset: 0; }
          }
          @media (prefers-reduced-motion: reduce) {
            @keyframes skCheckDraw {
              from { stroke-dashoffset: 0; }
              to { stroke-dashoffset: 0; }
            }
          }
        `}</style>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
           <div>
             <div style={{ display: 'inline-block', fontSize: 11, fontWeight: 700, padding: "4px 12px", borderRadius: 100, background: palette.bg, color: palette.text || palette.dot, border: `1px solid ${palette.border}`, letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 14 }}>
               {derivedSubject}
             </div>
             <h2 style={{ fontSize: 28, fontWeight: 700, color: tokens.text, lineHeight: 1.08, letterSpacing: "-0.02em" }}>{titleToUse}</h2>
             <div style={{ fontSize: 13, color: tokens.textMuted, marginTop: 10, display: 'flex', gap: 12, alignItems: 'center' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                   <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                   {session.start_time} - {session.end_time}
                </span>
                <span style={{ color: tokens.borderHover }}>|</span>
                <span>{session.estimated_hours}h planned</span>
             </div>
             {/* Allocated badges */}
             {Array.isArray(session.allocated_hours) && session.allocated_hours.length > 0 && (
                <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
                   {session.allocated_hours.map((alloc, i) => (
                      <span key={i} style={{ fontSize: 10, background: tokens.bg, border: `1px solid ${tokens.borderSubtle}`, borderRadius: 8, padding: "3px 8px", color: tokens.textMuted }}>
                         {alloc.chapter}: {alloc.hours}h
                      </span>
                   ))}
                </div>
             )}
           </div>
           <button onClick={onClose} style={{ background: tokens.bg, border: `1px solid ${tokens.border}`, borderRadius: '50%', cursor: 'pointer', color: tokens.textMuted, width: 34, height: 34, display: 'flex', alignItems: 'center', justifyContent: 'center', transition: `all ${tokens.transitionNormal}` }} onMouseEnter={e => { e.currentTarget.style.background = tokens.bgHover; e.currentTarget.style.color = tokens.text; }} onMouseLeave={e => { e.currentTarget.style.background = tokens.bg; e.currentTarget.style.color = tokens.textMuted; }}>✕</button>
        </div>

        {allSubs.length > 0 && (
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: tokens.textMuted, marginBottom: 8 }}>
               <span>Progress</span>
               <span style={{ fontFamily: "'DM Mono', monospace" }}>{Math.round(subPct * 100)}%</span>
            </div>
            <div style={{ width: "100%", height: 4, background: tokens.border, borderRadius: 2, overflow: "hidden" }}>
              <div style={{ height: "100%", width: `${subPct * 100}%`, background: allSubsDone ? tokens.green : palette.dot, borderRadius: 2, transition: "width 0.4s cubic-bezier(0.16, 1, 0.3, 1)" }} />
            </div>
          </div>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: 10, maxHeight: 300, overflowY: "auto", paddingRight: 8 }}>
           {allSubs.length === 0 ? (
             <div style={{ textAlign: "center", padding: "30px 0", color: tokens.textDim, fontSize: 13, border: `1px dashed ${tokens.border}`, borderRadius: 12 }}>No specific contents defined.</div>
           ) : (
             allSubs.map((c, i) => {
               const isDone = completedSubs.includes(c.match_key);
               const isLoading = subtopicLoading[c.match_key];
               return (
                 <button
                   key={c.match_key}
                   type="button"
                   onClick={() => handleSubtopicClick(c.match_key)}
                   style={{
                     display: "flex",
                     alignItems: "center",
                     gap: 14,
                     width: "100%",
                     padding: "14px 16px",
                     borderRadius: 14,
                     border: `1px solid ${isDone ? tokens.greenBorder : tokens.borderSubtle}`,
                     background: isDone ? tokens.doneBg : tokens.bg,
                     cursor: isLoading ? "wait" : "pointer",
                     opacity: isLoading ? 0.6 : 1,
                     transition: `all ${tokens.transitionNormal}`,
                     animation: `fadeUp 0.25s ease ${i * 0.05}s both`,
                     textAlign: "left",
                     boxShadow: isDone ? tokens.shadowDone : "none",
                   }}
                   onMouseEnter={e => {
                     if (!isLoading && !isDone) {
                       e.currentTarget.style.background = tokens.accentMuted;
                       e.currentTarget.style.borderColor = tokens.accentBorder;
                       e.currentTarget.style.transform = "translateY(-1px)";
                     }
                   }}
                   onMouseLeave={e => {
                     if (!isLoading && !isDone) {
                       e.currentTarget.style.background = tokens.bg;
                       e.currentTarget.style.borderColor = tokens.borderSubtle;
                       e.currentTarget.style.transform = "translateY(0)";
                     }
                   }}
                 >
                   <div
                     style={{
                       width: 18,
                       height: 18,
                       borderRadius: 6,
                       border: `1.5px solid ${isDone ? tokens.accentHover : tokens.borderHover}`,
                       background: isDone ? tokens.accent : tokens.bgCard,
                       display: "flex",
                       alignItems: "center",
                       justifyContent: "center",
                       transition: `all ${tokens.transitionNormal}`,
                       flexShrink: 0,
                       boxShadow: isDone ? "0 0 0 4px rgba(140, 153, 236, 0.14)" : "none",
                       transform: isDone ? "scale(1)" : "scale(0.98)",
                     }}
                   >
                     {isLoading ? <Spinner size={10} /> : isDone ? <CheckMarkIcon /> : null}
                   </div>
                   <span
                     style={{
                       fontSize: 14,
                       fontWeight: isDone ? 500 : 600,
                       color: isDone ? tokens.textMuted : tokens.text,
                       textDecoration: isDone ? "line-through" : "none",
                       textDecorationThickness: "1px",
                       transition: `all ${tokens.transitionNormal}`,
                     }}
                   >
                     {c.name}
                   </span>
                 </button>
               );
             })
           )}
        </div>

        <div style={{ marginTop: 8, display: "flex", gap: 12 }}>
          {isCompleted || isSkipped ? (
            <button disabled={sessionLoading} onClick={doUndoSession} style={{ flex: 1, padding: "14px", borderRadius: 12, border: `1px solid ${tokens.border}`, background: tokens.bg, color: tokens.text, fontSize: 14, fontWeight: 600, cursor: sessionLoading ? "wait" : "pointer", opacity: sessionLoading ? 0.7 : 1 }}>
              {sessionLoading ? "Undoing..." : (isSkipped ? "Undo Skip" : "Undo Completion")}
            </button>
          ) : (
            <>
              <button disabled={sessionLoading || isSkipped} onClick={doCompleteSession} style={{ flex: 1, padding: "14px", borderRadius: 12, border: `1px solid ${tokens.greenBorder}`, background: tokens.green, color: "#fffefa", fontSize: 14, fontWeight: 700, cursor: sessionLoading || isSkipped ? "not-allowed" : "pointer", opacity: sessionLoading || isSkipped ? 0.7 : 1, boxShadow: `0 10px 24px rgba(33, 184, 146, 0.18)` }}>
                {sessionLoading ? "Completing..." : "Complete Session ✓"}
              </button>
              <button disabled={sessionLoading || isSkipped} onClick={doSkipSession} style={{ padding: "14px 16px", borderRadius: 12, border: `1px solid ${tokens.redBorder}`, background: tokens.redBg, color: tokens.redText, fontSize: 14, fontWeight: 600, cursor: sessionLoading || isSkipped ? "not-allowed" : "pointer", opacity: sessionLoading || isSkipped ? 0.6 : 1 }}>
                Skip
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
