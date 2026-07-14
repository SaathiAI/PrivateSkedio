import { tokens, getSubjectPalette } from "../theme.js";
import { Spinner } from "./ui.jsx";
import { useSessionActions } from "../hooks/useSessionActions.js";

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
      position: "fixed", inset: 0, background: "rgba(10, 10, 15, 0.6)",
      display: "flex", alignItems: "center", justifyContent: "center",
      zIndex: 2000, animation: "fadeIn 0.25s ease-out", backdropFilter: "blur(12px)",
    }}>
      <div style={{ position: 'absolute', inset: 0 }} onClick={onClose} />
      <div style={{
        position: 'relative', width: 460, background: `${tokens.bgCard}ee`,
        borderRadius: 24, border: `1px solid rgba(255, 255, 255, 0.08)`,
        boxShadow: "0 30px 80px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.02) inset", 
        animation: "modalScaleUp 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards", padding: 36,
        display: "flex", flexDirection: "column", gap: 24, backdropFilter: "blur(20px)"
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
           <div>
             <div style={{ display: 'inline-block', fontSize: 11, fontWeight: 700, padding: "4px 12px", borderRadius: 100, background: `linear-gradient(135deg, ${palette.bg}, transparent)`, color: palette.dot, border: `1px solid ${palette.border}`, letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 14 }}>
               {derivedSubject}
             </div>
             <h2 style={{ fontSize: 26, fontWeight: 500, color: tokens.text, fontFamily: "'Fraunces', serif", fontStyle: "italic", lineHeight: 1.1, letterSpacing: "-0.01em" }}>{titleToUse}</h2>
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
                      <span key={i} style={{ fontSize: 10, background: "rgba(255,255,255,0.03)", border: `1px solid rgba(255,255,255,0.08)`, borderRadius: 6, padding: "2px 8px", color: tokens.textMuted }}>
                         {alloc.chapter}: {alloc.hours}h
                      </span>
                   ))}
                </div>
             )}
           </div>
           <button onClick={onClose} style={{ background: tokens.bg, border: `1px solid ${tokens.border}`, borderRadius: '50%', cursor: 'pointer', color: tokens.textMuted, width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'all 0.2s' }} onMouseEnter={e => { e.currentTarget.style.background = tokens.border; e.currentTarget.style.color = tokens.text; }} onMouseLeave={e => { e.currentTarget.style.background = tokens.bg; e.currentTarget.style.color = tokens.textMuted; }}>✕</button>
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
                 <div key={c.match_key} onClick={() => handleSubtopicClick(c.match_key)} style={{ display: "flex", alignItems: "center", gap: 14, padding: "14px 16px", borderRadius: 12, border: `1px solid ${isDone ? tokens.greenBorder : 'rgba(255,255,255,0.05)'}`, background: isDone ? `${tokens.green}15` : 'rgba(255,255,255,0.02)', cursor: isLoading ? "wait" : "pointer", opacity: isLoading ? 0.6 : 1, transition: "all 0.25s cubic-bezier(0.16, 1, 0.3, 1)", animation: `fadeUp 0.25s ease ${i * 0.05}s both` }} onMouseEnter={e => { if (!isLoading && !isDone) { e.currentTarget.style.background = 'rgba(255,255,255,0.05)'; e.currentTarget.style.transform = "translateY(-2px)"; e.currentTarget.style.boxShadow = "0 8px 20px rgba(0,0,0,0.2)"; } }} onMouseLeave={e => { if (!isLoading && !isDone) { e.currentTarget.style.background = 'rgba(255,255,255,0.02)'; e.currentTarget.style.transform = "translateY(0)"; e.currentTarget.style.boxShadow = "none"; } }}>
                   <div style={{ width: 22, height: 22, borderRadius: "50%", border: `2px solid ${isDone ? tokens.green : 'rgba(255,255,255,0.2)'}`, background: isDone ? tokens.green : "transparent", display: "flex", alignItems: "center", justifyContent: "center", transition: "all 0.25s cubic-bezier(0.16, 1, 0.3, 1)", flexShrink: 0 }}>
                     {isLoading ? <Spinner size={12} /> : isDone && (
                       <svg width="12" height="9" viewBox="0 0 12 9" fill="none" style={{ animation: "popIn 0.3s cubic-bezier(0.16, 1, 0.3, 1)" }}><path d="M1.5 4.5L4.5 7.5L10.5 1.5" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
                     )}
                   </div>
                   <span style={{ fontSize: 14, color: isDone ? tokens.textMuted : tokens.text, textDecoration: isDone ? "line-through" : "none", transition: "all 0.25s" }}>{c.name}</span>
                 </div>
               );
             })
           )}
        </div>

        <div style={{ marginTop: 8, display: "flex", gap: 12 }}>
          {isCompleted || isSkipped ? (
            <button disabled={sessionLoading} onClick={doUndoSession} style={{ flex: 1, padding: "14px", borderRadius: 12, border: `1px solid ${tokens.border}`, background: tokens.bg, color: tokens.text, fontSize: 14, fontWeight: 500, cursor: sessionLoading ? "wait" : "pointer", opacity: sessionLoading ? 0.7 : 1 }}>
              {sessionLoading ? "Undoing..." : (isSkipped ? "Undo Skip" : "Undo Completion")}
            </button>
          ) : (
            <>
              <button disabled={sessionLoading || isSkipped} onClick={doCompleteSession} style={{ flex: 1, padding: "14px", borderRadius: 12, border: "none", background: tokens.green, color: "#000", fontSize: 14, fontWeight: 600, cursor: sessionLoading || isSkipped ? "not-allowed" : "pointer", opacity: sessionLoading || isSkipped ? 0.7 : 1, boxShadow: `0 4px 16px ${tokens.green}66` }}>
                {sessionLoading ? "Completing..." : "Complete Session ✓"}
              </button>
              <button disabled={sessionLoading || isSkipped} onClick={doSkipSession} style={{ padding: "14px 16px", borderRadius: 12, border: `1px solid rgba(251, 113, 133, 0.25)`, background: "rgba(251, 113, 133, 0.08)", color: "#fecdd3", fontSize: 14, fontWeight: 500, cursor: sessionLoading || isSkipped ? "not-allowed" : "pointer", opacity: sessionLoading || isSkipped ? 0.6 : 1 }}>
                Skip
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
