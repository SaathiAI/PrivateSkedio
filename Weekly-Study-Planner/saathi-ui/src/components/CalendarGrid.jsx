import { useMemo, useState, useEffect, useRef } from "react";
import { tokens } from "../theme.js";

function parseDateAtNoon(dateStr) {
  return new Date(`${dateStr}T12:00:00`);
}

function formatDateKey(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function addDays(date, amount) {
  const next = new Date(date);
  next.setDate(next.getDate() + amount);
  return next;
}

function startOfWeek(date) {
  const next = new Date(date);
  const weekday = next.getDay();
  const diff = weekday === 0 ? -6 : 1 - weekday;
  next.setDate(next.getDate() + diff);
  next.setHours(12, 0, 0, 0);
  return next;
}

function startOfMonth(date) {
  return new Date(date.getFullYear(), date.getMonth(), 1, 12, 0, 0, 0);
}

function clampDay(year, monthIndex, day) {
  return Math.min(day, new Date(year, monthIndex + 1, 0).getDate());
}

function buildMiniMonth(date) {
  const monthStart = startOfMonth(date);
  const gridStart = startOfWeek(monthStart);
  return Array.from({ length: 42 }, (_, index) => {
    const cellDate = addDays(gridStart, index);
    return {
      date: cellDate,
      key: formatDateKey(cellDate),
      inMonth: cellDate.getMonth() === monthStart.getMonth(),
    };
  });
}

function ChevronIcon({ direction = "left" }) {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <path
        d={direction === "left" ? "M8.75 3.25 5 7l3.75 3.75" : "M5.25 3.25 9 7l-3.75 3.75"}
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

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

function getCalendarPalette(subject = "") {
  const key = subject.toLowerCase();
  if (key.includes("math")) {
    return { bg: "rgba(33, 184, 146, 0.12)", border: "rgba(33, 184, 146, 0.42)", text: "#147a63" };
  }
  if (key.includes("science")) {
    return { bg: "rgba(217, 144, 33, 0.13)", border: "rgba(217, 144, 33, 0.36)", text: "#8a5a10" };
  }
  if (key.includes("english")) {
    return { bg: "rgba(140, 153, 236, 0.16)", border: "rgba(140, 153, 236, 0.42)", text: "#5f69c8" };
  }
  if (key.includes("social")) {
    return { bg: "rgba(86, 173, 196, 0.14)", border: "rgba(86, 173, 196, 0.38)", text: "#2f7890" };
  }
  return { bg: tokens.bgElevated, border: tokens.borderHover, text: tokens.textSecondary };
}

export function CalendarGrid({
  allDays,
  today,
  onSessionClick,
  onEmptyAction,
  externalEvents = [],
  draftMode = false,
}) {
  const baseHour = 8;
  const endHour = 19;
  const pixelsPerHour = 72;
  const hours = Array.from({ length: endHour - baseHour + 1 }, (_, i) => baseHour + i);

  const [currentTime, setCurrentTime] = useState(new Date());
  const [jumpOpen, setJumpOpen] = useState(false);
  const referenceDate = useMemo(() => {
    if (today) return parseDateAtNoon(today);
    if (allDays?.[0]?.date) return parseDateAtNoon(allDays[0].date);
    return new Date();
  }, [allDays, today]);
  const [focusDate, setFocusDate] = useState(referenceDate);

  useEffect(() => {
    setFocusDate(referenceDate);
  }, [referenceDate]);
  const jumpRef = useRef(null);

  const dayMap = useMemo(() => {
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

    return dayMap;
  }, [allDays, externalEvents]);

  const weekStart = useMemo(() => startOfWeek(focusDate), [focusDate]);
  const displayDays = useMemo(() => {
    return Array.from({ length: 7 }, (_, index) => {
      const date = addDays(weekStart, index);
      const key = formatDateKey(date);
      return dayMap.get(key) || { date: key, sessions: [] };
    });
  }, [dayMap, weekStart]);

  useEffect(() => {
    const interval = setInterval(() => setCurrentTime(new Date()), 60000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!jumpOpen) return undefined;
    const handleOutside = (event) => {
      if (jumpRef.current && !jumpRef.current.contains(event.target)) {
        setJumpOpen(false);
      }
    };
    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, [jumpOpen]);

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
  const calendarHeight = (endHour - baseHour + 1) * pixelsPerHour;
  const currentTimeBeforeRange = currentTimePixels < 0;
  const currentTimeAfterRange = currentTimePixels > calendarHeight;
  const currentTimeMarkerPixels = currentTimeBeforeRange
    ? 0
    : currentTimeAfterRange
      ? calendarHeight
      : currentTimePixels;
  const markerNearBottom = currentTimeMarkerPixels > calendarHeight - 22;
  const todayColumnIndex = displayDays.findIndex(day => day.date === today);
  const showCurrentTime = todayColumnIndex !== -1;
  const weekEnd = useMemo(() => addDays(weekStart, 6), [weekStart]);
  const monthLabel = weekStart.toLocaleDateString("en-US", { month: "long" });
  const rangeLabel = `${weekStart.toLocaleDateString("en-US", { month: "short", day: "numeric" })} - ${weekEnd.toLocaleDateString("en-US", { month: "short", day: "numeric" })}, ${weekEnd.getFullYear()}`;
  const jumpMonthLabel = focusDate.toLocaleDateString("en-US", { month: "long", year: "numeric" });
  const miniMonthDays = useMemo(() => buildMiniMonth(focusDate), [focusDate]);
  const weekdayLabels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const selectedFocusKey = formatDateKey(focusDate);

  const jumpToToday = () => setFocusDate(parseDateAtNoon(today || formatDateKey(new Date())));
  const stepWeek = (direction) => setFocusDate(prev => addDays(prev, direction * 7));
  const stepMiniMonth = (direction) => {
    setFocusDate(prev => {
      const nextMonth = prev.getMonth() + direction;
      const year = prev.getFullYear() + Math.floor(nextMonth / 12);
      const monthIndex = ((nextMonth % 12) + 12) % 12;
      const day = clampDay(year, monthIndex, prev.getDate());
      return new Date(year, monthIndex, day, 12, 0, 0, 0);
    });
  };
  const controlButtonStyle = {
    height: 32,
    minWidth: 32,
    borderRadius: 9,
    border: `1px solid ${tokens.borderSubtle}`,
    background: tokens.bgCard,
    color: tokens.textSecondary,
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    cursor: "pointer",
    fontFamily: "inherit",
    fontSize: 12,
    fontWeight: 600,
    transition: `all ${tokens.transitionFast}`,
    boxShadow: tokens.shadowSm,
  };

  return (
    <div style={{
      background: tokens.bgCard,
      display: "flex",
      flexDirection: "column",
      height: "100%",
      width: "100%",
      flex: 1,
      overflow: "hidden",
    }}>
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 16,
        padding: "18px 20px 14px",
        borderBottom: `1px solid ${tokens.borderSubtle}`,
        background: tokens.bgCard,
        flexShrink: 0,
      }}>
        <div style={{
          display: "grid",
          gap: 4,
        }}>
          <div style={{
            fontSize: 12,
            lineHeight: 1.2,
            fontWeight: 700,
            color: tokens.textMuted,
            letterSpacing: "0.08em",
            textTransform: "uppercase",
          }}>
            {monthLabel}
          </div>
          <div style={{
            fontSize: 24,
            lineHeight: 1,
            fontWeight: 800,
            color: tokens.text,
            letterSpacing: "-0.01em",
          }}>
            {rangeLabel}
          </div>
          <div style={{ fontSize: 12, color: tokens.textMuted, fontWeight: 600 }}>
            Week view
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12, position: "relative" }} ref={jumpRef}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <button type="button" onClick={() => stepWeek(-1)} style={controlButtonStyle} aria-label="Previous week">
              <ChevronIcon direction="left" />
            </button>
            <button type="button" onClick={jumpToToday} style={{ ...controlButtonStyle, paddingInline: 12, minWidth: 62 }}>
              Today
            </button>
            <button type="button" onClick={() => stepWeek(1)} style={controlButtonStyle} aria-label="Next week">
              <ChevronIcon direction="right" />
            </button>
          </div>
          <button
            type="button"
            onClick={() => setJumpOpen(prev => !prev)}
            style={{ ...controlButtonStyle, paddingInline: 12, minWidth: 118, justifyContent: "space-between", gap: 10 }}
            aria-label="Open jump calendar"
          >
            <span>{jumpMonthLabel}</span>
            <ChevronIcon direction={jumpOpen ? "left" : "right"} />
          </button>
          {jumpOpen && (
            <div
              style={{
                position: "absolute",
                top: "calc(100% + 10px)",
                right: 0,
                width: 272,
                borderRadius: 16,
                border: `1px solid ${tokens.borderSubtle}`,
                background: tokens.bgCard,
                boxShadow: tokens.shadowLg,
                padding: 14,
                zIndex: 40,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
                <button type="button" onClick={() => stepMiniMonth(-1)} style={controlButtonStyle} aria-label="Previous month">
                  <ChevronIcon direction="left" />
                </button>
                <div style={{ fontSize: 13, fontWeight: 700, color: tokens.text }}>
                  {jumpMonthLabel}
                </div>
                <button type="button" onClick={() => stepMiniMonth(1)} style={controlButtonStyle} aria-label="Next month">
                  <ChevronIcon direction="right" />
                </button>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 6, marginBottom: 8 }}>
                {weekdayLabels.map(label => (
                  <div key={label} style={{ textAlign: "center", fontSize: 10, fontWeight: 700, color: tokens.textDim, paddingBlock: 4 }}>
                    {label}
                  </div>
                ))}
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 6 }}>
                {miniMonthDays.map(({ date, key, inMonth }) => {
                  const isToday = key === today;
                  const isSelected = key === selectedFocusKey;
                  return (
                    <button
                      key={key}
                      type="button"
                      onClick={() => {
                        setFocusDate(date);
                        setJumpOpen(false);
                      }}
                      style={{
                        height: 32,
                        borderRadius: 10,
                        border: `1px solid ${isSelected ? tokens.accentBorder : "transparent"}`,
                        background: isSelected ? tokens.accentMuted : isToday ? tokens.redBg : "transparent",
                        color: !inMonth ? tokens.textDim : isToday ? tokens.redText : tokens.text,
                        fontSize: 12,
                        fontWeight: isSelected || isToday ? 700 : 600,
                        cursor: "pointer",
                        fontFamily: "inherit",
                      }}
                    >
                      {date.getDate()}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      <div style={{
        display: "flex",
        borderBottom: `1px solid ${tokens.borderSubtle}`,
        background: tokens.bgCard,
        flexShrink: 0,
      }}>
        <div style={{ width: 64, flexShrink: 0, borderRight: `1px solid ${tokens.borderSubtle}` }} />
        {displayDays.map(day => {
          const isToday = day.date === today;
          const d = new Date(day.date + "T12:00:00");
          const weekday = d.toLocaleDateString("en-US", { weekday: "short" });
          const dateNum = d.getDate();
          return (
            <div key={day.date} style={{
              flex: 1, minWidth: 128, padding: "13px 0 12px", textAlign: "center",
              borderRight: `1px solid ${tokens.borderFaint}`,
              background: "transparent",
              position: "relative",
            }}>
              <div style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                fontSize: 14,
                fontWeight: 700,
                color: isToday ? tokens.text : tokens.textSecondary,
              }}>
                <span>{weekday}</span>
                {isToday ? (
                  <span style={{
                    background: tokens.red,
                    color: tokens.bgCard,
                    borderRadius: "50%",
                    width: 26,
                    height: 26,
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    boxShadow: `0 0 0 3px ${tokens.redBg}`,
                  }}>
                    {dateNum}
                  </span>
                ) : <span>{dateNum}</span>}
              </div>
            </div>
          );
        })}
      </div>

      <div style={{ flex: 1, position: "relative", overflow: "auto" }}>
        <div style={{ display: "flex", position: "relative", height: calendarHeight }}>
          
          {/* Y-axis Hours */}
          <div style={{
            width: 64, flexShrink: 0, borderRight: `1px solid ${tokens.borderSubtle}`,
            position: "sticky", left: 0, background: tokens.bgCard, zIndex: 15
          }}>
            {hours.map((hour, index) => (
              <div
                key={hour}
                style={{
                  height: pixelsPerHour,
                  paddingRight: 10,
                  textAlign: "right",
                  position: "relative",
                  overflow: "visible",
                }}
              >
                <div
                  style={{
                    position: "absolute",
                    right: 10,
                    top: index === 0 ? 2 : -6,
                    fontSize: 12,
                    fontWeight: 500,
                    color: tokens.textDim,
                    lineHeight: 1,
                    background: tokens.bgCard,
                    paddingInline: 2,
                  }}
                >
                  {hour === 12 ? '12 PM' : hour > 12 ? `${hour - 12} PM` : `${hour} AM`}
                </div>
              </div>
            ))}
          </div>

          {/* Horizontal Grid lines */}
          <div style={{ position: "absolute", top: 0, left: 64, right: 0, bottom: 0, pointerEvents: "none", zIndex: 1 }}>
            {hours.map(hour => (
              <div key={hour} style={{
                position: "absolute", top: (hour - baseHour) * pixelsPerHour, left: 0, right: 0,
                height: 1, borderTop: `1px solid ${tokens.borderFaint}`
              }} />
            ))}
          </div>

          {showCurrentTime && (
            <div style={{
              position: "absolute",
              top: currentTimeMarkerPixels,
              left: 0,
              right: 0,
              height: 24,
              zIndex: 30,
              pointerEvents: "none",
              opacity: currentTimeBeforeRange || currentTimeAfterRange ? 0.92 : 1,
            }}>
              <div style={{
                position: "absolute",
                top: markerNearBottom ? 9 : 11,
                left: 64,
                right: 0,
                display: "flex",
                alignItems: "center",
                height: 2,
              }}>
                {displayDays.map((day) => {
                  const isTodayColumn = day.date === today;
                  return (
                    <div
                      key={`${day.date}-time-line`}
                      style={{
                        flex: 1,
                        height: 2,
                        background: isTodayColumn ? "rgba(232, 93, 122, 0.94)" : "rgba(232, 93, 122, 0.28)",
                        boxShadow: isTodayColumn ? "0 0 10px rgba(232, 93, 122, 0.24)" : "none",
                      }}
                    />
                  );
                })}
              </div>
              <div style={{
                position: "absolute",
                top: markerNearBottom ? 6 : 8,
                left: 64,
                right: 0,
                display: "flex",
                alignItems: "center",
                height: 8,
                filter: "blur(4px)",
              }}>
                {displayDays.map((day) => {
                  const isTodayColumn = day.date === today;
                  return (
                    <div
                      key={`${day.date}-time-glow`}
                      style={{
                        flex: 1,
                        height: 8,
                        background: isTodayColumn ? "rgba(232, 93, 122, 0.16)" : "rgba(232, 93, 122, 0.05)",
                      }}
                    />
                  );
                })}
              </div>
              <div style={{
                position: "absolute",
                left: 59,
                top: markerNearBottom ? 3 : 5,
                width: 12,
                height: 12,
                borderRadius: "50%",
                background: tokens.red,
                boxShadow: `0 0 0 4px ${tokens.redBg}, 0 0 14px rgba(232, 93, 122, 0.5)`,
              }} />
            </div>
          )}

          {/* Day Columns */}
          {displayDays.map(day => {
            const isToday = day.date === today;
            return (
              <div key={day.date} style={{
                flex: 1, minWidth: 128, borderRight: `1px solid ${tokens.borderFaint}`,
                position: "relative", zIndex: 5,
                background: isToday ? "rgba(140, 153, 236, 0.045)" : "transparent",
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
                  const palette = getCalendarPalette(derivedSubject);
                  const isDone = s.status === 'done';
                  const isSkipped = s.status === 'skipped';
                  const titleToUse = String(s.title || s.topic || "Calendar event");
                  const isDraftSession = draftMode && !s.isBlocker;
                  
                  const boxStyles = s.isBlocker ? {
                    position: "absolute", top: top + 1, height: height - 2, left: 5, right: 5,
                    borderRadius: 6, padding: "7px 9px",
                    background: titleToUse.includes("Lunch") ? tokens.yellowBg : tokens.blockerBg,
                    border: `1px solid ${titleToUse.includes("Lunch") ? tokens.yellowBorder : tokens.blockerBorder}`,
                    color: tokens.text, display: "flex", flexDirection: "column", overflow: "hidden",
                    cursor: "default", zIndex: 2
                  } : {
                    position: "absolute",
                    top: top + 1, height: height - 2,
                    left: 5, right: 5,
                    borderRadius: 6,
                    padding: "7px 9px",
                    background: isDone
                      ? tokens.doneBg
                      : (isSkipped ? tokens.skipBg : palette.bg),
                    border: `1px solid ${isDraftSession ? tokens.draftBorder : (isDone ? tokens.doneBorder : (isSkipped ? tokens.skipBorder : palette.border))}`,
                    opacity: isSkipped ? 0.6 : (isDone ? 0.8 : 1),
                    display: "flex", flexDirection: "column",
                    overflow: "hidden", cursor: "pointer",
                    transition: `all ${tokens.transitionNormal}`,
                    boxShadow: isDraftSession ? `0 0 0 1px ${tokens.draftBorder}` : "none",
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
                               ? `0 0 0 1px ${tokens.draftBorder}, 0 8px 18px rgba(76, 88, 132, 0.12)`
                               : "0 8px 18px rgba(76, 88, 132, 0.12)";
                             e.currentTarget.style.zIndex = 25; 
                           }
                         }}
                         onMouseLeave={e => { 
                           if(!s.isBlocker) {
                             e.currentTarget.style.transform = "none"; 
                             e.currentTarget.style.boxShadow = isDraftSession
                               ? `0 0 0 1px ${tokens.draftBorder}`
                               : "none";
                             e.currentTarget.style.zIndex = 3; 
                           }
                         }}
                    >
                       <div style={{
                         fontSize: 10, fontWeight: 750,
                         color: s.isBlocker ? tokens.textMuted : (isDone ? tokens.green : palette.text),
                         marginBottom: 4, letterSpacing: "0.04em", textTransform: "uppercase",
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
                         fontSize: 13, lineHeight: 1.25, fontWeight: 750,
                         color: s.isBlocker ? tokens.textMuted : (isDone ? tokens.textDim : tokens.text),
                         textDecoration: isDone ? "line-through" : "none",
                       }}>
                          {titleToUse}
                       </div>

                       {!s.isBlocker && (
                         <div style={{
                           fontSize: 11, marginTop: "auto", fontWeight: 600,
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
