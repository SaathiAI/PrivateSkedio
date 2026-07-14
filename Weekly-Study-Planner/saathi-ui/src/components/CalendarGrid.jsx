import { useMemo, useState, useEffect } from "react";
import { tokens, getSubjectPalette } from "../theme.js";

function timeToPixels(timeStr, baseHour = 7, pixelsPerHour = 60) {
  if (!timeStr) return 0;
  const [h, m] = timeStr.split(":").map(Number);
  const totalHours = h + (m / 60);
  return (totalHours - baseHour) * pixelsPerHour;
}

function CheckIcon({ size = 12 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="7" fill={tokens.green} opacity="0.15" />
      <path d="M5 8l2 2 4-4" stroke={tokens.green} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function CalendarGrid({
  allDays,
  today,
  onSessionClick,
  onEmptyAction,
  externalEvents = [],
  draftMode = false,
}) {
  const baseHour = 6;
  const endHour = 23;
  const pixelsPerHour = 80;
  const hours = Array.from({ length: endHour - baseHour + 1 }, (_, i) => baseHour + i);

  const [currentTime, setCurrentTime] = useState(new Date());
  const displayDays = useMemo(() => {
    const dayMap = new Map();

    (allDays || []).forEach(day => {
      if (!day?.date) return;
      dayMap.set(day.date, {
        ...day,
        sessions: Array.isArray(day.sessions) ? day.sessions : [],
      });
    });

    (externalEvents || []).forEach(event => {
      if (!event?.date) return;
      if (!dayMap.has(event.date)) {
        dayMap.set(event.date, { date: event.date, sessions: [] });
      }
    });

    return Array.from(dayMap.values()).sort((a, b) => a.date.localeCompare(b.date));
  }, [allDays, externalEvents]);

  useEffect(() => {
    const interval = setInterval(() => setCurrentTime(new Date()), 60000);
    return () => clearInterval(interval);
  }, []);

  if (displayDays.length === 0) {
    return (
      <div style={{
        display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
        flex: 1, width: "100%", padding: `${tokens.space12} ${tokens.space6}`, textAlign: "center",
      }}>
        <div style={{
          width: 72, height: 72, borderRadius: tokens.radiusXl,
          background: tokens.accentMuted, border: `1px solid ${tokens.accentBorder}`,
          display: "flex", alignItems: "center", justifyContent: "center",
          marginBottom: tokens.space5,
        }}>
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke={tokens.accent} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
            <line x1="16" y1="2" x2="16" y2="6" />
            <line x1="8" y1="2" x2="8" y2="6" />
            <line x1="3" y1="10" x2="21" y2="10" />
          </svg>
        </div>
        <h3 style={{ fontSize: 16, fontWeight: 600, color: tokens.text, marginBottom: tokens.space2 }}>
          No study plan yet
        </h3>
        <p style={{ fontSize: 13, color: tokens.textMuted, maxWidth: 300, lineHeight: 1.6, marginBottom: tokens.space6 }}>
          Generate a personalized plan to see your schedule here. Sessions will be organized across your week.
        </p>
        {onEmptyAction && (
          <button
            onClick={onEmptyAction}
            style={{
              padding: `${tokens.space3} ${tokens.space5}`,
              borderRadius: tokens.radiusMd,
              fontSize: 13, fontWeight: 500,
              border: "none",
              background: tokens.text,
              color: tokens.bg,
              cursor: "pointer",
              fontFamily: "inherit",
              transition: `all ${tokens.transitionNormal}`,
            }}
          >
            Generate Plan
          </button>
        )}
      </div>
    );
  }

  const currentHour = currentTime.getHours();
  const currentMinute = currentTime.getMinutes();
  const currentTotalHours = currentHour + (currentMinute / 60);
  const currentTimePixels = (currentTotalHours - baseHour) * pixelsPerHour;

  return (
    <div style={{
      background: tokens.bg, display: "flex", flexDirection: "column",
      height: "100%", width: "100%", flex: 1, overflow: "auto",
    }}>
      {/* Header axis -> Days */}
      <div style={{
        display: "flex", borderBottom: `1px solid ${tokens.borderSubtle}`,
        position: "sticky", top: 0, background: tokens.glassBg,
        backdropFilter: "blur(12px)", WebkitBackdropFilter: "blur(12px)", zIndex: 20
      }}>
        <div style={{ width: 56, flexShrink: 0, borderRight: `1px solid ${tokens.borderSubtle}` }} />
        {displayDays.map(day => {
          const isToday = day.date === today;
          const d = new Date(day.date + "T12:00:00");
          const weekday = d.toLocaleDateString("en-US", { weekday: "short" });
          const dateNum = d.getDate();
          return (
            <div key={day.date} style={{
              flex: 1, minWidth: 120, padding: `${tokens.space4} 0`, textAlign: "center",
              borderRight: `1px solid ${tokens.borderFaint}`,
              background: isToday
                ? `linear-gradient(180deg, ${tokens.accentMuted} 0%, transparent 100%)`
                : "transparent",
              position: "relative",
            }}>
              {isToday && (
                <div style={{
                  position: "absolute", bottom: 0, left: "25%", right: "25%", height: 2,
                  background: `linear-gradient(90deg, transparent, ${tokens.accent}, transparent)`,
                  borderRadius: 1,
                }} />
              )}
              <div style={{
                fontSize: 10, fontWeight: 600, letterSpacing: "0.08em",
                color: isToday ? tokens.accent : tokens.textDim,
                textTransform: "uppercase",
              }}>
                {weekday}
              </div>
              <div style={{
                fontSize: 20, fontWeight: 600, color: isToday ? tokens.text : tokens.textMuted,
                marginTop: 2,
              }}>
                {isToday ? (
                  <span style={{
                    background: tokens.accent, color: tokens.bg, borderRadius: "50%",
                    width: 32, height: 32, display: "inline-flex", alignItems: "center", justifyContent: "center",
                    boxShadow: `0 0 16px ${tokens.accentBorder}`,
                  }}>
                    {dateNum}
                  </span>
                ) : dateNum}
              </div>
            </div>
          );
        })}
      </div>

      {/* Grid container */}
      <div style={{ flex: 1, position: "relative" }}>
        <div style={{ display: "flex", position: "relative", height: (endHour - baseHour + 1) * pixelsPerHour }}>
          
          {/* Y-axis Hours */}
          <div style={{
            width: 56, flexShrink: 0, borderRight: `1px solid ${tokens.borderSubtle}`,
            position: "sticky", left: 0, background: tokens.bg, zIndex: 15
          }}>
            {hours.map(hour => (
              <div key={hour} style={{
                height: pixelsPerHour, paddingRight: 10, textAlign: "right",
                fontSize: 10, fontWeight: 500, color: tokens.textDim,
                transform: "translateY(-6px)"
              }}>
                {hour === 12 ? '12 PM' : hour > 12 ? `${hour - 12} PM` : `${hour} AM`}
              </div>
            ))}
          </div>

          {/* Horizontal Grid lines */}
          <div style={{ position: "absolute", top: 0, left: 56, right: 0, bottom: 0, pointerEvents: "none", zIndex: 1 }}>
            {hours.map(hour => (
              <div key={hour} style={{
                position: "absolute", top: (hour - baseHour) * pixelsPerHour, left: 0, right: 0,
                height: 1, borderTop: `1px solid ${tokens.borderFaint}`
              }} />
            ))}
          </div>

          {/* Current Time Line */}
          {currentTimePixels >= 0 && currentTimePixels <= (endHour - baseHour + 1) * pixelsPerHour && (
             <div style={{
               position: "absolute", top: currentTimePixels, left: 56, right: 0,
               height: 2, zIndex: 12, pointerEvents: "none",
             }}>
               <div style={{
                 position: "absolute", top: 0, left: 0, right: 0, height: 2,
                 background: tokens.red,
                 boxShadow: `0 0 8px ${tokens.red}88`,
               }} />
               <div style={{
                 position: "absolute", left: -5, top: -4, width: 10, height: 10,
                 borderRadius: "50%", background: tokens.red,
                 boxShadow: `0 0 10px ${tokens.red}88`,
               }} />
             </div>
          )}

          {/* Day Columns */}
          {displayDays.map(day => {
            const isToday = day.date === today;
            return (
              <div key={day.date} style={{
                flex: 1, minWidth: 120, borderRight: `1px solid ${tokens.borderFaint}`,
                position: "relative", zIndex: 5,
                background: isToday
                  ? `linear-gradient(180deg, ${tokens.accentMuted}40 0%, transparent 40%)`
                  : "transparent",
              }}>
                {/* Empty time slot indicators for today */}
                {isToday && hours.filter(h => {
                  const hourStr = `${String(h).padStart(2, "0")}:00`;
                  return !(day.sessions || []).some(s => s.start_time <= hourStr && s.end_time > hourStr);
                }).slice(0, 3).map(h => (
                  <div
                    key={`slot-${h}`}
                    style={{
                      position: "absolute",
                      top: (h - baseHour) * pixelsPerHour + 16,
                      left: 6, right: 6, height: pixelsPerHour - 32,
                      border: `1px dashed ${tokens.borderFaint}`,
                      borderRadius: tokens.radiusMd,
                      pointerEvents: "none",
                      opacity: h < currentHour ? 0.2 : 0.4,
                    }}
                  />
                ))}

                {externalEvents
                  .filter(e => e.date === day.date)
                  .map(e => ({ ...e, subject: "Calendar", isBlocker: true, topic: e.title }))
                  .concat(day.sessions || [])
                  .map((s, idx) => {
                  const top = timeToPixels(s.start_time, baseHour, pixelsPerHour);
                  const bottom = timeToPixels(s.end_time, baseHour, pixelsPerHour);
                  const height = Math.max(bottom - top, 28);
                  
                  const derivedSubject = (s.contents && s.contents[0] && s.contents[0].subjects && s.contents[0].subjects[0]) || "General";
                  const palette = getSubjectPalette(derivedSubject);
                  const isDone = s.status === 'done';
                  const isSkipped = s.status === 'skipped';
                  const titleToUse = String(s.title || s.topic || "Calendar event");
                  const isDraftSession = draftMode && !s.isBlocker;
                  
                  const boxStyles = s.isBlocker ? {
                    position: "absolute", top: top + 1, height: height - 2, left: 5, right: 5,
                    borderRadius: tokens.radiusMd, padding: `${tokens.space2} ${tokens.space3}`,
                    background: titleToUse.includes("Lunch") ? tokens.yellowBg : tokens.blockerBg,
                    border: `1px solid ${tokens.blockerBorder}`,
                    borderLeft: `3px solid ${titleToUse.includes("Lunch") ? tokens.yellow : tokens.blockerBorderLeft}`,
                    color: tokens.text, display: "flex", flexDirection: "column", overflow: "hidden",
                    cursor: "default", zIndex: 2
                  } : {
                    position: "absolute",
                    top: top + 1, height: height - 2,
                    left: 5, right: 5,
                    borderRadius: tokens.radiusMd,
                    padding: `${tokens.space2} ${tokens.space3}`,
                    background: isDone
                      ? tokens.doneBg
                      : (isSkipped ? tokens.skipBg : palette.bg),
                    border: `1px solid ${isDraftSession ? tokens.draftBorder : (isDone ? tokens.doneBorder : (isSkipped ? tokens.skipBorder : palette.border))}`,
                    borderLeft: `3px solid ${isDraftSession ? tokens.red : (isDone ? tokens.green : (isSkipped ? tokens.red : palette.dot))}`,
                    opacity: isSkipped ? 0.6 : (isDone ? 0.8 : 1),
                    display: "flex", flexDirection: "column",
                    overflow: "hidden", cursor: "pointer",
                    transition: `all ${tokens.transitionNormal}`,
                    boxShadow: isDraftSession
                      ? `0 0 0 1px ${tokens.draftBorder}, 0 4px 12px rgba(0,0,0,0.2)`
                      : isDone ? tokens.shadowDone : tokens.shadowCard,
                    zIndex: 3
                  };

                  return (
                    <div key={`${day.date}-${s.start_time}-${idx}`} 
                         style={boxStyles}
                         onClick={(e) => { e.stopPropagation(); if(onSessionClick && !s.isBlocker) onSessionClick(s, day.date); }}
                         onMouseEnter={e => { 
                           if(!s.isBlocker) {
                             e.currentTarget.style.transform = "translateY(-1px)"; 
                             e.currentTarget.style.boxShadow = isDraftSession
                               ? `0 8px 20px rgba(0,0,0,0.25), 0 0 0 1px ${tokens.draftBorder}`
                               : isDone ? tokens.shadowDoneHover : tokens.shadowCardHover;
                             e.currentTarget.style.zIndex = 25; 
                           }
                         }}
                         onMouseLeave={e => { 
                           if(!s.isBlocker) {
                             e.currentTarget.style.transform = "none"; 
                             e.currentTarget.style.boxShadow = isDraftSession
                               ? `0 0 0 1px ${tokens.draftBorder}, 0 4px 12px rgba(0,0,0,0.2)`
                               : isDone ? tokens.shadowDone : tokens.shadowCard;
                             e.currentTarget.style.zIndex = 3; 
                           }
                         }}
                    >
                       <div style={{
                         fontSize: 10, fontWeight: 600,
                         color: s.isBlocker ? tokens.textMuted : (isDone ? tokens.green : palette.text),
                         marginBottom: 2, letterSpacing: "0.05em", textTransform: "uppercase",
                         display: "flex", alignItems: "center", gap: 4,
                       }}>
                         {isDone && <CheckIcon />}
                         {s.isBlocker ? `${s.start_time} - ${s.end_time}` : derivedSubject}
                       </div>

                       {isDraftSession && (
                         <div style={{
                           position: "absolute", top: 6, right: 6,
                           padding: "1px 5px", borderRadius: tokens.radiusFull,
                           fontSize: 9, fontWeight: 600, letterSpacing: "0.05em",
                           color: tokens.redText,
                           background: tokens.draftBg,
                           border: `1px solid ${tokens.draftBorder}`,
                         }}>
                           DRAFT
                         </div>
                       )}

                       {isDone && !s.isBlocker && (
                         <div style={{
                           position: "absolute", top: 6, right: 6,
                           padding: "1px 5px", borderRadius: tokens.radiusFull,
                           fontSize: 9, fontWeight: 600, letterSpacing: "0.05em",
                           color: tokens.green,
                           background: tokens.doneBg,
                           border: `1px solid ${tokens.doneBorder}`,
                         }}>
                           DONE
                         </div>
                       )}

                       <div style={{
                         fontSize: 12, lineHeight: 1.3, fontWeight: s.isBlocker ? 500 : 500,
                         color: s.isBlocker ? tokens.textMuted : (isDone ? tokens.textDim : tokens.text),
                         textDecoration: isDone ? "line-through" : "none",
                       }}>
                          {titleToUse}
                       </div>

                       {!s.isBlocker && (
                         <div style={{
                           fontSize: 10, marginTop: "auto", fontWeight: 500,
                           color: isDone ? tokens.greenText : tokens.textDim,
                         }}>
                            {s.start_time} - {s.end_time}
                         </div>
                       )}
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
