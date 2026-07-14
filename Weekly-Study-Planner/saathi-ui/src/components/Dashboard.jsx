import React, { useState, useEffect } from "react";
import { tokens } from "../theme.js";
import { backlogApi } from "../lib/backlogApi.js";
import { planApi } from "../lib/planApi.js";
import {
  normalizeAllocationSummary,
  normalizeChapterBacklog,
} from "../lib/dashboardAdapters.js";

export function DashboardTabV2({ stats, examDate, daysUntilExam }) {
  const hoursStudied = stats?.hours_studied || 0;
  const hoursTarget = stats?.hours_target || 0;
  const hoursRemaining = stats?.hours_remaining || 0;
  const subtopicsDone = stats?.subtopics_done || 0;
  const totalSubtopics = stats?.total_subtopics || 0;
  const sessionsDone = stats?.sessions_completed || 0;
  const totalSessions = stats?.total_sessions || 0;
  const dailyHours = stats?.daily_hours || [];
  const topicBreakdown = stats?.topic_breakdown || [];
  
  const [allocation, setAllocation] = useState([]);
  const [backlog, setBacklog] = useState({ chapters: {} });

  useEffect(() => {
    planApi.allocationSummary()
      .then(d => setAllocation(normalizeAllocationSummary(d))).catch(console.error);
    backlogApi.chapters()
      .then(d => setBacklog({ chapters: normalizeChapterBacklog(d) })).catch(console.error);
  }, []);
  
  const pctDone = hoursTarget > 0 ? Math.round((hoursStudied / hoursTarget) * 100) : 0;
  const subtopicPct = totalSubtopics > 0 ? Math.round((subtopicsDone / totalSubtopics) * 100) : 0;
  
  const chartColors = [tokens.green, tokens.indigo, tokens.yellow, "#f472b6"];
  const maxDayHours = Math.max(...dailyHours.map(d => d.hours), 1);
  
  const gaugeTotal = 157;
  const gaugeCurrent = (pctDone / 100) * gaugeTotal;

  return (
    <div style={{ animation: "fadeUp 0.3s ease" }}>
      {examDate && daysUntilExam !== null && (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", background: tokens.redBg, border: `1px solid ${tokens.border}`, borderRadius: 12, padding: "16px 20px", marginBottom: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ fontSize: 24 }}>🎯</div>
            <div>
              <div style={{ fontSize: 11, color: tokens.red, letterSpacing: "0.1em", textTransform: "uppercase" }}>Exam Countdown</div>
              <div style={{ fontSize: 13, color: tokens.text, fontWeight: 500 }}>{examDate}</div>
            </div>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: 32, fontFamily: "'Fraunces', serif", fontWeight: 400, color: tokens.red }}>{daysUntilExam}</div>
            <div style={{ fontSize: 11, color: tokens.red }}>days left</div>
          </div>
        </div>
      )}
      
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 24 }}>
        <div style={{ background: tokens.bgCard, border: `1px solid ${tokens.border}`, borderRadius: 12, padding: 20, display: "flex", flexDirection: "column", boxShadow: "0 2px 8px rgba(0,0,0,0.2)" }}>
          <div style={{ fontSize: 13, fontWeight: 500, color: tokens.text, marginBottom: 12 }}>Focus Time</div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", position: "relative", marginBottom: 10 }}>
            <svg width="120" height="70" viewBox="0 0 80 50">
              <path d="M 15 45 A 25 25 0 0 1 65 45" fill="none" stroke={tokens.bgHover} strokeWidth="6" strokeLinecap="round" />
              <path d="M 15 45 A 25 25 0 0 1 65 45" fill="none" stroke={tokens.green} strokeWidth="6" strokeLinecap="round" strokeDasharray={`${gaugeCurrent} ${gaugeTotal}`} strokeDashoffset="0" />
            </svg>
            <div style={{ position: "absolute", bottom: 0, display: "flex", flexDirection: "column", alignItems: "center" }}>
              <div style={{ fontSize: 26, fontFamily: "'Fraunces', serif", fontWeight: 400, color: tokens.text }}>{hoursStudied}<span style={{fontSize: 14, color: tokens.textMuted}}>h</span></div>
            </div>
          </div>
          <div style={{ textAlign: "center", fontSize: 11, color: tokens.textMuted }}>{pctDone}% of {hoursTarget}h goal</div>
        </div>
        
        <div style={{ background: tokens.bgCard, border: `1px solid ${tokens.border}`, borderRadius: 12, padding: 20, display: "flex", flexDirection: "column", justifyContent: "space-between", boxShadow: "0 2px 8px rgba(0,0,0,0.2)" }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 500, color: tokens.text, marginBottom: 8 }}>Remaining Study</div>
            <div style={{ fontSize: 32, fontFamily: "'Fraunces', serif", fontWeight: 400, color: tokens.text }}>{hoursRemaining}h</div>
          </div>
          <div style={{ fontSize: 11, color: tokens.textMuted, padding: "6px 10px", background: tokens.bgHover, borderRadius: 6, display: "inline-block", alignSelf: "flex-start" }}>across {(totalSessions - sessionsDone)} sessions</div>
        </div>
        
        <div style={{ background: tokens.bgCard, border: `1px solid ${tokens.border}`, borderRadius: 12, padding: 20, display: "flex", flexDirection: "column", justifyContent: "space-between", boxShadow: "0 2px 8px rgba(0,0,0,0.2)" }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 500, color: tokens.text, marginBottom: 8 }}>Subtopics Done</div>
            <div style={{ fontSize: 32, fontFamily: "'Fraunces', serif", fontWeight: 400, color: tokens.text }}>{subtopicsDone}</div>
          </div>
          <div style={{ width: "100%", height: 4, background: tokens.bgHover, borderRadius: 2, overflow: "hidden" }}>
             <div style={{ height: "100%", width: `${subtopicPct}%`, background: tokens.yellow, borderRadius: 2 }} />
          </div>
          <div style={{ fontSize: 11, color: tokens.textMuted }}>{subtopicPct}% of {totalSubtopics} max</div>
        </div>
        
        <div style={{ background: tokens.bgCard, border: `1px solid ${tokens.border}`, borderRadius: 12, padding: 20, display: "flex", flexDirection: "column", justifyContent: "space-between", boxShadow: "0 2px 8px rgba(0,0,0,0.2)" }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 500, color: tokens.text, marginBottom: 8 }}>Sessions Run</div>
            <div style={{ fontSize: 32, fontFamily: "'Fraunces', serif", fontWeight: 400, color: tokens.text }}>{sessionsDone}</div>
          </div>
          <div style={{ fontSize: 11, color: tokens.textMuted, padding: "6px 10px", background: tokens.indigoBg, borderRadius: 6, display: "inline-block", alignSelf: "flex-start" }}>
            <span style={{ color: tokens.indigo }}>{sessionsDone}/{totalSessions}</span> complete
          </div>
        </div>
      </div>
      
      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 16, marginBottom: 24 }}>
        <div style={{ background: tokens.bgCard, border: `1px solid ${tokens.border}`, borderRadius: 12, padding: 24, boxShadow: "0 2px 8px rgba(0,0,0,0.2)" }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: tokens.text, marginBottom: 24 }}>Daily Focus Time</div>
          <div style={{ display: "flex", alignItems: "flex-end", gap: 8, height: 160, paddingBottom: 10, borderBottom: `1px solid ${tokens.bgHover}`, position: "relative" }}>
            <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 1, background: tokens.bgHover }}></div>
            <div style={{ position: "absolute", top: 80, left: 0, right: 0, height: 1, background: tokens.bgHover }}></div>
            
            {dailyHours.length === 0 ? (
              <div style={{ color: tokens.textMuted, fontSize: 13, width: "100%", textAlign: "center", alignSelf: "center" }}>No data yet</div>
            ) : dailyHours.slice(-7).map((d, i) => {
               const dayHeight = Math.max((d.hours / maxDayHours) * 140, 4);
               return (
                <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 4, position: "relative", zIndex: 1 }}>
                  <div style={{ width: "100%", borderRadius: "4px 4px 0 0", background: i === dailyHours.slice(-7).length - 1 ? tokens.green : tokens.borderHover, height: dayHeight, transition: "height 0.4s ease", opacity: 0.8 }} />
                </div>
               );
            })}
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8 }}>
             {dailyHours.slice(-7).map((d, i) => (
               <div key={i} style={{ flex: 1, textAlign: "center", fontSize: 11, color: tokens.textMuted }}>{d.date?.slice(-2) || "-"}</div>
             ))}
          </div>
        </div>
        
        <div style={{ background: tokens.bgCard, border: `1px solid ${tokens.border}`, borderRadius: 12, padding: 24, boxShadow: "0 2px 8px rgba(0,0,0,0.2)" }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: tokens.text, marginBottom: 20 }}>Time Breakdown</div>
          {topicBreakdown.length === 0 ? (
            <div style={{ color: tokens.textMuted, fontSize: 13, textAlign: "center", padding: "40px 0" }}>No data yet</div>
          ) : (
            <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
              <svg width="120" height="120" viewBox="0 0 120 120">
                {(() => {
                  const total = topicBreakdown.reduce((a, t) => a + t.hours, 0);
                  let offset = 0;
                  return topicBreakdown.map((t, i) => {
                    const pct = total > 0 ? (t.hours / total) * 100 : 0;
                    const dash = (pct / 100) * 251.2;
                    const color = chartColors[i % chartColors.length];
                    const result = (
                      <React.Fragment key={i}>
                        <circle cx="60" cy="60" r="40" fill="none" stroke={tokens.bgHover} strokeWidth="16" />
                        <circle cx="60" cy="60" r="40" fill="none" stroke={color} strokeWidth="16" strokeDasharray={`${dash} 251.2`} strokeDashoffset={`${-offset}`} strokeLinecap="butt" transform="rotate(-90 60 60)" />
                      </React.Fragment>
                    );
                    offset += dash;
                    return result;
                  });
                })()}
                <circle cx="60" cy="60" r="28" fill={tokens.bgCard} />
                <text x="60" y="66" textAnchor="middle" fontSize="18" fontWeight="500" fill={tokens.text}>{hoursStudied}h</text>
              </svg>
              <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 12 }}>
                {topicBreakdown.slice(0, 4).map((t, i) => (
                  <div key={i} style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <div style={{ width: 10, height: 10, borderRadius: 3, background: chartColors[i % chartColors.length] }} />
                      <span style={{ fontSize: 12, color: tokens.textMuted, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 90 }}>{t.topic}</span>
                    </div>
                    <span style={{ fontSize: 12, fontWeight: 500, color: tokens.text }}>{t.hours}h</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {/* Allocation Summary Card */}
        <div style={{ background: tokens.bgCard, border: `1px solid ${tokens.border}`, borderRadius: 12, padding: 24, boxShadow: "0 2px 8px rgba(0,0,0,0.2)" }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: tokens.text, marginBottom: 16 }}>Allocation Summary</div>
          {allocation.length === 0 ? (
            <div style={{ color: tokens.textMuted, fontSize: 13 }}>No allocation data</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {allocation.map((alloc, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingBottom: 8, borderBottom: `1px solid ${tokens.bgHover}` }}>
                  <div>
                    <div style={{ fontSize: 13, color: tokens.text, fontWeight: 500 }}>{alloc.chapter}</div>
                    <div style={{ fontSize: 11, color: tokens.textMuted }}>{alloc.subject}</div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: 12, color: tokens.text }}>{alloc.completed_hours}h / {alloc.estimated_hours}h target</div>
                    <div style={{ fontSize: 11, color: tokens.textDim }}>{alloc.scheduled_hours}h scheduled</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Chapter Backlog Card */}
        <div style={{ background: tokens.bgCard, border: `1px solid ${tokens.border}`, borderRadius: 12, padding: 24, boxShadow: "0 2px 8px rgba(0,0,0,0.2)" }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: tokens.text, marginBottom: 16 }}>Chapter Backlog</div>
          {(!backlog.chapters || Object.keys(backlog.chapters).length === 0) ? (
            <div style={{ color: tokens.textMuted, fontSize: 13 }}>No backlog items</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
               {Object.entries(backlog.chapters).map(([chapterName, items], i) => (
                  <div key={i} style={{ marginBottom: 8 }}>
                    <div style={{ fontSize: 13, color: tokens.text, fontWeight: 600, marginBottom: 4 }}>{chapterName}</div>
                    {(Array.isArray(items) ? items : []).map((item, j) => (
                      <div key={j} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "4px 0", borderBottom: `1px solid ${tokens.bgHover}` }}>
                        <span style={{ fontSize: 12, color: tokens.textMuted }}>{item.name}</span>
                        <span style={{ fontSize: 11, padding: "2px 6px", borderRadius: 4, background: item.status === "done" ? tokens.greenBg : tokens.bgHover, color: item.status === "done" ? tokens.green : tokens.textDim }}>
                           {item.status}
                        </span>
                      </div>
                    ))}
                  </div>
               ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
