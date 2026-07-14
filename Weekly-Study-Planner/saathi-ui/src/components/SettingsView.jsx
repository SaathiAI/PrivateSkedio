import { useCallback, useEffect, useState } from "react";
import { useAuth } from "./Auth.jsx";
import { tokens } from "../theme.js";
import { calendarApi } from "../lib/calendarApi.js";
import { emailApi } from "../lib/emailApi.js";

export function SettingsView({ onBack }) {
  const { user } = useAuth();
  const [calendarStatus, setCalendarStatus] = useState(null);
  const [calendarError, setCalendarError] = useState("");
  const [calendarCheckedAt, setCalendarCheckedAt] = useState(null);
  const [emailStatus, setEmailStatus] = useState(null);
  const [emailError, setEmailError] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);

  const refreshCalendarStatus = useCallback(async () => {
    setCalendarError("");
    try {
      setCalendarStatus(await calendarApi.status());
      setCalendarCheckedAt(new Date());
    } catch (error) {
      setCalendarStatus({ connected: false });
      setCalendarError(error.message || "Calendar status check failed");
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    calendarApi.status()
      .then(status => {
        if (cancelled) return;
        setCalendarStatus(status);
        setCalendarCheckedAt(new Date());
      })
      .catch(error => {
        if (cancelled) return;
        setCalendarStatus({ connected: false });
        setCalendarError(error.message || "Calendar status check failed");
      });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    emailApi.status()
      .then(status => {
        if (cancelled) return;
        setEmailStatus(status);
        setEmailError("");
      })
      .catch(error => {
        if (cancelled) return;
        setEmailStatus({ ready: false });
        setEmailError(error.message || "Email status check failed");
      });
    return () => { cancelled = true; };
  }, []);

  const handleConnect = async () => {
    setConnecting(true);
    setCalendarError("");
    try {
      const authUrl = await calendarApi.connectUrl();
      if (authUrl) {
        window.location.href = authUrl;
      } else {
        setConnecting(false);
      }
    } catch (error) {
      setCalendarError(error.message || "Could not start Google Calendar connection");
      setConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    if (!window.confirm("Disconnect Google Calendar?")) return;
    setDisconnecting(true);
    setCalendarError("");
    try {
      await calendarApi.disconnect();
      setCalendarStatus({ connected: false });
      setCalendarCheckedAt(new Date());
    } catch (error) {
      setCalendarError(error.message || "Calendar disconnect failed");
    }
    setDisconnecting(false);
  };

  return (
    <div style={{ padding: "0" }}>
      <div style={{ maxWidth: 980 }}>
        <button onClick={onBack} style={{
          display: "flex", alignItems: "center", gap: 6,
          background: "transparent", border: `1px solid ${tokens.border}`, borderRadius: 7,
          padding: "6px 12px", color: tokens.textMuted, cursor: "pointer",
          fontSize: 12, fontFamily: "inherit", marginBottom: 32,
        }}
          onMouseEnter={e => { e.target.style.color = tokens.text; e.target.style.borderColor = tokens.borderHover; }}
          onMouseLeave={e => { e.target.style.color = tokens.textMuted; e.target.style.borderColor = tokens.border; }}
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M9 11L5 7l4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Back
        </button>

        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 11, color: tokens.textMuted, letterSpacing: "0.16em", textTransform: "uppercase", marginBottom: 10 }}>Settings</div>
          <h1 style={{ fontSize: 38, fontFamily: "'Fraunces', serif", fontWeight: 400, color: tokens.text, marginBottom: 10 }}>Connections</h1>
          <p style={{ fontSize: 14, color: tokens.textMuted, lineHeight: 1.7, maxWidth: 650 }}>
            Account identity, calendar reality, and alert channels stay wired here so SkedioAI can stay conversational without losing the hard truth.
          </p>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 16, marginTop: 24 }}>
        <div style={{
          border: `1px solid ${tokens.border}`, borderRadius: 12, padding: "22px",
          background: tokens.bgCard,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 16 }}>
            <div style={{
              width: 46, height: 46, borderRadius: 10,
              background: "#101010", border: `1px solid ${tokens.borderHover}`,
              color: tokens.text,
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="5" width="18" height="14" rx="2" />
                <path d="m3 7 9 6 9-6" />
              </svg>
            </div>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 15, fontWeight: 600, color: tokens.text }}>Email Authentication</div>
              <div style={{ fontSize: 12, color: tokens.textMuted, marginTop: 3, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {user?.email || "Signed in account"}
              </div>
            </div>
            <div style={{ marginLeft: "auto", padding: "5px 9px", borderRadius: 999, background: tokens.greenBg, border: `1px solid ${tokens.greenBorder}`, color: tokens.green, fontSize: 11, fontWeight: 700 }}>
              Active
            </div>
          </div>

          <div style={{ fontSize: 13, color: tokens.textMuted, lineHeight: 1.65, marginBottom: 18 }}>
            Your account owns the active plan, checklist truth, progress history, and SkedioAI chat thread.
          </div>

          <div style={{ display: "grid", gap: 8 }}>
            {[
              "Bearer auth enabled",
              "Plan progress saved to your account",
              emailStatus?.ready ? "Email alerts can use this identity" : "Email alerts still need backend wiring",
            ].map(item => (
              <div key={item} style={{ display: "flex", alignItems: "center", gap: 8, color: tokens.textMuted, fontSize: 12 }}>
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: tokens.green, flexShrink: 0 }} />
                {item}
              </div>
            ))}
          </div>
        </div>

        {/* Google Calendar */}
        <div style={{
          border: `1px solid ${calendarStatus?.connected ? tokens.greenBorder : tokens.border}`, borderRadius: 12, padding: "22px",
          background: tokens.bgCard,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 16 }}>
            <div style={{
              width: 46, height: 46, borderRadius: 10,
              background: "#101010", border: `1px solid ${tokens.borderHover}`,
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
                <rect x="2" y="4" width="18" height="16" rx="2" stroke="#4285F4" strokeWidth="1.5"/>
                <path d="M2 8h18" stroke="#4285F4" strokeWidth="1.5"/>
                <path d="M7 2v4M15 2v4" stroke="#4285F4" strokeWidth="1.5" strokeLinecap="round"/>
                <rect x="6" y="11" width="3" height="3" rx="0.5" fill="#34A853"/>
                <rect x="11" y="11" width="3" height="3" rx="0.5" fill="#4285F4"/>
                <rect x="6" y="15" width="3" height="3" rx="0.5" fill="#FBBC05"/>
                <rect x="11" y="15" width="3" height="3" rx="0.5" fill="#EA4335"/>
              </svg>
            </div>
            <div>
              <div style={{ fontSize: 15, fontWeight: 600, color: tokens.text }}>Google Calendar</div>
              <div style={{ fontSize: 12, color: tokens.textMuted, marginTop: 2 }}>
                {calendarStatus === null ? "Checking..." :
                  calendarStatus?.connected
                    ? `Connected · ${calendarStatus.calendar_id || "primary"}`
                    : "Not connected"}
              </div>
              {calendarCheckedAt && (
                <div style={{ fontSize: 11, color: tokens.textDim, marginTop: 2 }}>
                  Checked {calendarCheckedAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                </div>
              )}
            </div>
            <div style={{ marginLeft: "auto", padding: "5px 9px", borderRadius: 999, background: calendarStatus?.connected ? tokens.greenBg : tokens.yellowBg, border: `1px solid ${calendarStatus?.connected ? tokens.greenBorder : tokens.yellowBorder}`, color: calendarStatus?.connected ? tokens.green : tokens.yellow, fontSize: 11, fontWeight: 700 }}>
              {calendarStatus === null ? "Checking" : calendarStatus?.connected ? "Synced" : "Optional"}
            </div>
          </div>

          <div style={{ fontSize: 13, color: tokens.textMuted, lineHeight: 1.6, marginBottom: 20 }}>
            {calendarStatus?.connected
              ? "SkedioAI can read non-study blockers, create study events, and update completion state when plan progress changes."
              : "Connect Calendar when you want SkedioAI to see real blockers and sync study sessions into your day."}
          </div>

          {calendarError && (
            <div style={{
              padding: "10px 12px", borderRadius: 8,
              background: tokens.redBg, border: `1px solid ${tokens.red}`,
              color: tokens.red, fontSize: 12, lineHeight: 1.45, marginBottom: 14,
            }}>
              {calendarError}
            </div>
          )}

          {calendarStatus === null ? (
            <div style={{ height: 40 }} />
          ) : calendarStatus?.connected ? (
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <button
                onClick={refreshCalendarStatus}
                disabled={disconnecting}
                style={{
                  padding: "10px 18px", borderRadius: 8, fontSize: 13,
                  border: `1px solid ${tokens.border}`, background: tokens.bg,
                  color: tokens.text, cursor: disconnecting ? "wait" : "pointer",
                  fontFamily: "inherit",
                }}
              >
                Refresh Status
              </button>
              <button
                onClick={handleDisconnect}
                disabled={disconnecting}
                style={{
                  padding: "10px 18px", borderRadius: 8, fontSize: 13,
                  border: `1px solid #fecaca`, background: tokens.redBg,
                  color: tokens.red, cursor: disconnecting ? "wait" : "pointer",
                  fontFamily: "inherit", opacity: disconnecting ? 0.5 : 1,
                }}
              >
                {disconnecting ? "Disconnecting..." : "Disconnect"}
              </button>
            </div>
          ) : (
            <button
              onClick={handleConnect}
              disabled={connecting}
              style={{
                padding: "10px 18px", borderRadius: 8, fontSize: 13, fontWeight: 500,
                border: "none", background: tokens.text,
                color: tokens.bgCard, cursor: connecting ? "wait" : "pointer",
                fontFamily: "inherit", opacity: connecting ? 0.5 : 1,
              }}
            >
              {connecting ? "Redirecting..." : "Connect Calendar"}
            </button>
          )}
        </div>
        <div style={{
          border: `1px solid ${tokens.border}`, borderRadius: 12, padding: "22px",
          background: tokens.bgCard,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 16 }}>
            <div style={{
              width: 46, height: 46, borderRadius: 10,
              background: "#101010", border: `1px solid ${tokens.borderHover}`,
              display: "flex", alignItems: "center", justifyContent: "center", color: tokens.text,
            }}>
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" />
                <path d="M13.73 21a2 2 0 0 1-3.46 0" />
              </svg>
            </div>
            <div>
              <div style={{ fontSize: 15, fontWeight: 600, color: tokens.text }}>Email Alerts</div>
              <div style={{ fontSize: 12, color: tokens.textMuted, marginTop: 2 }}>Missed sessions and conflict summaries</div>
            </div>
            <div style={{
              marginLeft: "auto",
              padding: "5px 9px",
              borderRadius: 999,
              background: emailStatus?.ready ? tokens.greenBg : tokens.yellowBg,
              border: `1px solid ${emailStatus?.ready ? tokens.greenBorder : tokens.yellowBorder}`,
              color: emailStatus?.ready ? tokens.green : tokens.yellow,
              fontSize: 11,
              fontWeight: 700,
            }}>
              {emailStatus === null ? "Checking" : emailStatus?.ready ? "Ready" : "Setup"}
            </div>
          </div>

          <div style={{ fontSize: 13, color: tokens.textMuted, lineHeight: 1.65, marginBottom: 18 }}>
            {emailStatus?.ready
              ? "Alerts are handled by the monitor layer for missed sessions, failed auto-reschedules, and important schedule changes."
              : "Email sign-in is active, but alert delivery depends on backend SMTP and monitor configuration."}
          </div>

          {(emailError || emailStatus?.lookup_error || emailStatus?.ready === false) && (
            <div style={{
              padding: "10px 12px",
              borderRadius: 8,
              background: tokens.yellowBg,
              border: `1px solid ${tokens.yellowBorder}`,
              color: tokens.yellow,
              fontSize: 12,
              lineHeight: 1.45,
              marginBottom: 14,
            }}>
              {emailError || emailStatus?.lookup_error || (
                emailStatus?.smtp_configured
                  ? "Recipient lookup is not ready."
                  : "GMAIL_USER and GMAIL_APP_PASSWORD are required for alert delivery."
              )}
            </div>
          )}

          <div style={{ padding: 12, borderRadius: 8, background: "#101010", border: `1px solid ${tokens.border}`, fontSize: 12, color: tokens.textMuted, overflow: "hidden", textOverflow: "ellipsis" }}>
            Recipient: <span style={{ color: tokens.text }}>{emailStatus?.recipient || user?.email || "current account"}</span>
          </div>
        </div>
        </div>
      </div>
    </div>
  );
}
