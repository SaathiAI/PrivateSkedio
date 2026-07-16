import { useCallback, useEffect, useState } from "react";
import { useAuth } from "./Auth.jsx";
import { tokens } from "../theme.js";
import { calendarApi } from "../lib/calendarApi.js";
import { emailApi } from "../lib/emailApi.js";
import { getProfileInitials, getProfileLabel } from "../lib/userHelpers.js";

const DEV_FRONTEND_ONLY = import.meta.env.DEV && import.meta.env.VITE_USE_REAL_BACKEND !== "1";

export function SettingsView({ onBack, initialSection = "profile", onSectionChange, onOpenPastPlans }) {
  const { user, supabase, isDevAdmin, signOutDevAdmin } = useAuth();
  const activeSection = initialSection || "profile";
  const [calendarStatus, setCalendarStatus] = useState(null);
  const [calendarError, setCalendarError] = useState("");
  const [calendarCheckedAt, setCalendarCheckedAt] = useState(null);
  const [emailStatus, setEmailStatus] = useState(null);
  const [emailError, setEmailError] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [confirmDisconnect, setConfirmDisconnect] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const [logoutError, setLogoutError] = useState("");

  const profileLabel = getProfileLabel(user);
  const profileInitials = getProfileInitials(user);

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
    if (DEV_FRONTEND_ONLY) {
      setCalendarStatus({ connected: false });
      setCalendarCheckedAt(new Date());
      return;
    }
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
    if (DEV_FRONTEND_ONLY) {
      setEmailStatus({ ready: false, recipient: user?.email || "preview@skedio.local" });
      setEmailError("");
      return;
    }
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
  }, [user?.email]);

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
    setDisconnecting(true);
    setCalendarError("");
    try {
      await calendarApi.disconnect();
      setCalendarStatus({ connected: false });
      setCalendarCheckedAt(new Date());
      setConfirmDisconnect(false);
    } catch (error) {
      setCalendarError(error.message || "Calendar disconnect failed");
    }
    setDisconnecting(false);
  };

  const handleLogout = async () => {
    setSigningOut(true);
    setLogoutError("");
    try {
      if (isDevAdmin) {
        signOutDevAdmin?.();
      } else if (supabase) {
        await supabase.auth.signOut({ scope: "local" });
      }
    } catch (error) {
      setLogoutError(error.message || "Could not log out");
    } finally {
      setSigningOut(false);
    }
  };

  return (
    <div>
      <button
        type="button"
        onClick={onBack}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 8,
          background: tokens.bgCard,
          border: `1px solid ${tokens.border}`,
          borderRadius: tokens.radiusFull,
          padding: "9px 13px",
          color: tokens.textSecondary,
          cursor: "pointer",
          fontSize: 13,
          fontFamily: "inherit",
          marginBottom: 22,
        }}
      >
        <ChevronLeftIcon />
        Back to planner
      </button>

        <main style={{
          minHeight: 620,
          background: tokens.bgCard,
          border: `1px solid ${tokens.border}`,
          borderRadius: 26,
          boxShadow: tokens.shadowCard,
          padding: 28,
          animation: "fadeUp 0.2s ease",
        }}>
          {activeSection === "profile" && (
            <SettingsSection
              title="Profile"
              description="Your visible study identity and account scope."
            >
              <div style={{ display: "grid", gridTemplateColumns: "120px minmax(0, 1fr)", gap: 24, alignItems: "center" }}>
                <div style={{
                  width: 96,
                  height: 96,
                  borderRadius: 30,
                  background: "linear-gradient(135deg, #bcc2f4 0%, #ffffff 48%, #9ead78 100%)",
                  border: `1px solid ${tokens.border}`,
                  color: tokens.text,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 30,
                  fontWeight: 800,
                  boxShadow: tokens.shadowMd,
                }}>
                  {profileInitials}
                </div>
                <div>
                  <div style={{ fontSize: 28, fontWeight: 800, color: tokens.text, marginBottom: 6 }}>
                    {profileLabel}
                  </div>
                  <div style={{ fontSize: 14, color: tokens.textSecondary, marginBottom: 16 }}>
                    {user?.email || "Signed in account"}
                  </div>
                  <StatusLine tone="success" text="Authenticated workspace" />
                  <StatusLine tone="default" text="Plans, progress, and review threads are scoped to this account" />
                </div>
              </div>
            </SettingsSection>
          )}

          {activeSection === "settings" && (
            <SettingsSection
              title="Settings"
              description="Workspace actions and account controls live here, away from the primary planner navigation."
            >
              <div style={{ display: "grid", gap: 14 }}>
                <ActionRow
                  title="Past plans"
                  description="Review previous weekly plans and restore context without crowding the sidebar."
                  actionLabel="Open"
                  onClick={onOpenPastPlans}
                />
                <ActionRow
                  title="Integrations"
                  description="Connect Calendar and email so planning can account for real blockers."
                  actionLabel="Manage"
                  onClick={() => onSectionChange?.("integrations")}
                />
                <PreferenceRow
                  title="Planner starts first"
                  description="Keep the weekly planner as the first surface after sign-in."
                  value="Enabled"
                />
                <section style={{
                  display: "flex",
                  justifyContent: "space-between",
                  gap: 18,
                  alignItems: "center",
                  padding: 16,
                  borderRadius: 16,
                  border: `1px solid ${tokens.redBorder}`,
                  background: tokens.redBg,
                }}>
                  <div>
                    <div style={{ fontSize: 15, fontWeight: 700, color: tokens.redText, marginBottom: 4 }}>Log out</div>
                    <div style={{ fontSize: 13, color: tokens.textSecondary }}>End this local session on the current device.</div>
                    {logoutError && <div style={{ marginTop: 8, fontSize: 12, color: tokens.redText }}>{logoutError}</div>}
                  </div>
                  <SmallButton danger onClick={handleLogout} disabled={signingOut}>
                    {signingOut ? "Logging out..." : "Log out"}
                  </SmallButton>
                </section>
              </div>
            </SettingsSection>
          )}

          {activeSection === "security" && (
            <SettingsSection
              title="Security"
              description="A compact view of how this workspace stays locked to your current account and device."
            >
              <div style={{ display: "grid", gap: 14 }}>
                <PreferenceRow
                  title="Signed-in email"
                  description="The account currently allowed to open this planner workspace."
                  value={user?.email || "Local session"}
                />
                <PreferenceRow
                  title="Session scope"
                  description="This session only affects the current browser on this device."
                  value="Local only"
                />
                <PreferenceRow
                  title="Planner access"
                  description="Preview mode keeps frontend work unblocked while backend auth is disabled."
                  value={isDevAdmin ? "Sample admin" : "Authenticated"}
                />
                <section style={{
                  padding: 16,
                  borderRadius: 16,
                  border: `1px solid ${tokens.border}`,
                  background: tokens.bgElevated,
                }}>
                  <div style={{ fontSize: 15, fontWeight: 700, color: tokens.text, marginBottom: 4 }}>
                    Account protection
                  </div>
                  <div style={{ fontSize: 13, color: tokens.textSecondary, lineHeight: 1.6 }}>
                    Password resets, 2-step verification, and provider-level security stay managed through your authentication provider.
                  </div>
                </section>
              </div>
            </SettingsSection>
          )}

          {activeSection === "billing" && (
            <SettingsSection
              title="Billing"
              description="Plan access and billing signals, kept lightweight for now while the workspace shell is taking shape."
            >
              <div style={{ display: "grid", gap: 14 }}>
                <PreferenceRow
                  title="Current plan"
                  description="This preview workspace is running on the internal product shell."
                  value="Pro preview"
                />
                <PreferenceRow
                  title="Renewal state"
                  description="No live billing provider is connected in this frontend preview."
                  value="Not connected"
                />
                <section style={{
                  padding: 16,
                  borderRadius: 16,
                  border: `1px solid ${tokens.border}`,
                  background: tokens.bgElevated,
                }}>
                  <div style={{ fontSize: 15, fontWeight: 700, color: tokens.text, marginBottom: 4 }}>
                    Billing setup
                  </div>
                  <div style={{ fontSize: 13, color: tokens.textSecondary, lineHeight: 1.6, marginBottom: 14 }}>
                    When billing is wired up, plan management, invoices, and renewal controls can live here without changing the sidebar structure again.
                  </div>
                  <span style={{
                    display: "inline-flex",
                    alignItems: "center",
                    padding: "7px 10px",
                    borderRadius: tokens.radiusFull,
                    background: tokens.accentMuted,
                    border: `1px solid ${tokens.accentBorder}`,
                    color: tokens.text,
                    fontSize: 12,
                    fontWeight: 700,
                  }}>
                    Placeholder section
                  </span>
                </section>
              </div>
            </SettingsSection>
          )}

          {activeSection === "integrations" && (
            <section>
              <div style={{
                display: "flex",
                alignItems: "flex-start",
                justifyContent: "space-between",
                gap: 18,
                marginBottom: 26,
              }}>
                <div>
                  <div style={{ fontSize: 30, lineHeight: 1.1, fontWeight: 800, color: tokens.text, marginBottom: 8 }}>
                    Integrations and connected apps
                  </div>
                  <p style={{ fontSize: 14, color: tokens.textSecondary, lineHeight: 1.55, maxWidth: 640 }}>
                    Connect the channels SkedioAI uses to understand your day and bring you back to the plan.
                  </p>
                </div>
                <button
                  type="button"
                  style={{
                    border: `1px solid ${tokens.border}`,
                    background: tokens.bgCard,
                    borderRadius: 9,
                    padding: "10px 12px",
                    color: tokens.text,
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 8,
                    fontSize: 13,
                    fontWeight: 650,
                    fontFamily: "inherit",
                    cursor: "pointer",
                  }}
                >
                  <PlusIcon />
                  Custom integration
                </button>
              </div>

              <div style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 16,
                marginBottom: 18,
              }}>
                <div style={{
                  display: "inline-flex",
                  border: `1px solid ${tokens.border}`,
                  borderRadius: 9,
                  overflow: "hidden",
                  background: tokens.bgCard,
                }}>
                  {["All integrations", "Productivity", "Communication"].map((label, index) => (
                    <span
                      key={label}
                      style={{
                        padding: "9px 13px",
                        fontSize: 12,
                        color: index === 0 ? tokens.text : tokens.textSecondary,
                        fontWeight: index === 0 ? 750 : 600,
                        background: index === 0 ? tokens.bgElevated : "transparent",
                        borderRight: index < 2 ? `1px solid ${tokens.border}` : "none",
                      }}
                    >
                      {label}
                    </span>
                  ))}
                </div>
                <div style={{
                  width: 220,
                  border: `1px solid ${tokens.border}`,
                  borderRadius: 9,
                  background: tokens.bgCard,
                  padding: "9px 12px",
                  display: "flex",
                  alignItems: "center",
                  gap: 9,
                  color: tokens.textMuted,
                  fontSize: 13,
                }}>
                  <SearchGlyph />
                  Search
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 16 }}>
                <IntegrationTile
                  title="Email"
                  domain={user?.email || "mail.google.com"}
                  description="Send review links, missed-session alerts, and plan summaries to the right inbox."
                  connected={Boolean(emailStatus?.ready)}
                  icon={<MailIntegrationIcon />}
                  actionLabel="View integration"
                >
                  {(emailError || emailStatus?.lookup_error || emailStatus?.ready === false) && (
                    <InlineNotice tone="warning">
                      {emailError || emailStatus?.lookup_error || "Email delivery needs backend SMTP configuration."}
                    </InlineNotice>
                  )}
                </IntegrationTile>

                <IntegrationTile
                  title="Google Calendar"
                  domain={calendarStatus?.connected ? calendarStatus.calendar_id || "calendar.google.com" : "calendar.google.com"}
                  description="Read blockers and sync study sessions around real-life events in your calendar."
                  connected={Boolean(calendarStatus?.connected)}
                  icon={<CalendarIntegrationIcon />}
                  actionLabel={calendarStatus?.connected ? "Manage calendar" : connecting ? "Redirecting..." : "View integration"}
                  onAction={DEV_FRONTEND_ONLY ? undefined : calendarStatus?.connected ? refreshCalendarStatus : handleConnect}
                  disabled={connecting || disconnecting}
                >
                  {calendarCheckedAt && (
                    <p style={{ ...copyStyle, fontSize: 12, marginBottom: calendarError ? 10 : 0 }}>
                      Checked {calendarCheckedAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </p>
                  )}
                  {calendarError && <InlineNotice tone="danger">{calendarError}</InlineNotice>}
                  {calendarStatus?.connected && (
                    <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 12 }}>
                      {confirmDisconnect ? (
                        <>
                          <SmallButton danger onClick={handleDisconnect} disabled={disconnecting}>
                            {disconnecting ? "Disconnecting..." : "Confirm disconnect"}
                          </SmallButton>
                          <SmallButton onClick={() => setConfirmDisconnect(false)} disabled={disconnecting}>
                            Cancel
                          </SmallButton>
                        </>
                      ) : (
                        <SmallButton danger onClick={() => setConfirmDisconnect(true)} disabled={disconnecting}>
                          Disconnect
                        </SmallButton>
                      )}
                    </div>
                  )}
                </IntegrationTile>
              </div>
            </section>
          )}
        </main>
    </div>
  );
}

const copyStyle = {
  fontSize: 13,
  color: tokens.textSecondary,
  lineHeight: 1.65,
  marginBottom: 16,
};

function SettingsSection({ title, description, children }) {
  return (
    <section>
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontSize: 34, lineHeight: 1.1, fontWeight: 800, color: tokens.text, marginBottom: 8 }}>
          {title}
        </div>
        <p style={{ fontSize: 15, color: tokens.textSecondary, lineHeight: 1.6, maxWidth: 680 }}>
          {description}
        </p>
      </div>
      {children}
    </section>
  );
}

function PreferenceRow({ title, description, value }) {
  return (
    <div style={{
      display: "flex",
      justifyContent: "space-between",
      gap: 18,
      alignItems: "center",
      padding: 16,
      borderRadius: 16,
      border: `1px solid ${tokens.border}`,
      background: tokens.bgElevated,
    }}>
      <div>
        <div style={{ fontSize: 15, fontWeight: 700, color: tokens.text, marginBottom: 4 }}>{title}</div>
        <div style={{ fontSize: 13, color: tokens.textSecondary }}>{description}</div>
      </div>
      <span style={{
        padding: "7px 10px",
        borderRadius: tokens.radiusFull,
        background: tokens.accentMuted,
        border: `1px solid ${tokens.accentBorder}`,
        color: tokens.text,
        fontSize: 12,
        fontWeight: 700,
        flexShrink: 0,
      }}>
        {value}
      </span>
    </div>
  );
}

function ActionRow({ title, description, actionLabel, onClick }) {
  return (
    <div style={{
      display: "flex",
      justifyContent: "space-between",
      gap: 18,
      alignItems: "center",
      padding: 16,
      borderRadius: 16,
      border: `1px solid ${tokens.border}`,
      background: tokens.bgElevated,
    }}>
      <div>
        <div style={{ fontSize: 15, fontWeight: 700, color: tokens.text, marginBottom: 4 }}>{title}</div>
        <div style={{ fontSize: 13, color: tokens.textSecondary }}>{description}</div>
      </div>
      <SmallButton onClick={onClick} disabled={!onClick}>
        {actionLabel}
      </SmallButton>
    </div>
  );
}

function IntegrationTile({ title, domain, description, connected, icon, actionLabel, onAction, disabled = false, children }) {
  return (
    <section style={{
      minHeight: 190,
      border: `1px solid ${tokens.border}`,
      borderRadius: 12,
      background: tokens.bgCard,
      overflow: "hidden",
      display: "flex",
      flexDirection: "column",
    }}>
      <div style={{ padding: 18, display: "grid", gridTemplateColumns: "minmax(0, 1fr) 54px", gap: 16 }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 16, fontWeight: 800, color: tokens.text, marginBottom: 3 }}>{title}</div>
          <div style={{ fontSize: 12, color: tokens.textMuted, marginBottom: 18, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {domain}
          </div>
          <p style={{ fontSize: 13, color: tokens.textSecondary, lineHeight: 1.55, margin: 0 }}>
            {description}
          </p>
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          {icon}
        </div>
      </div>

      {children && (
        <div style={{ padding: "0 18px 14px" }}>
          {children}
        </div>
      )}

      <div style={{
        marginTop: "auto",
        borderTop: `1px solid ${tokens.borderSubtle}`,
        padding: 14,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 12,
      }}>
        <button
          type="button"
          onClick={onAction}
          disabled={disabled}
          style={{
            border: `1px solid ${tokens.border}`,
            background: tokens.bgCard,
            color: tokens.text,
            borderRadius: 8,
            padding: "8px 11px",
            fontSize: 12,
            fontWeight: 700,
            fontFamily: "inherit",
            cursor: disabled ? "wait" : "pointer",
            opacity: disabled ? 0.65 : 1,
          }}
        >
          {actionLabel}
        </button>
        <span style={{
          width: 32,
          height: 18,
          borderRadius: 999,
          background: connected ? tokens.accent : "#e7e7e2",
          border: `1px solid ${connected ? tokens.accentHover : tokens.border}`,
          position: "relative",
          flexShrink: 0,
        }}>
          <span style={{
            position: "absolute",
            top: 2,
            left: connected ? 16 : 2,
            width: 12,
            height: 12,
            borderRadius: "50%",
            background: "#fffefa",
            boxShadow: "0 1px 2px rgba(36,34,30,0.18)",
          }} />
        </span>
      </div>
    </section>
  );
}

function IntegrationCard({ title, subtitle, status, tone, children }) {
  const isSuccess = tone === "success";
  return (
    <section style={{
      border: `1px solid ${isSuccess ? tokens.greenBorder : tokens.border}`,
      borderRadius: 18,
      padding: 20,
      background: isSuccess ? "linear-gradient(180deg, #ffffff 0%, rgba(33,184,146,0.06) 100%)" : tokens.bgElevated,
    }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 14, marginBottom: 16 }}>
        <div style={{
          width: 44,
          height: 44,
          borderRadius: 15,
          background: isSuccess ? tokens.greenBg : tokens.accentMuted,
          border: `1px solid ${isSuccess ? tokens.greenBorder : tokens.accentBorder}`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: isSuccess ? tokens.greenText : tokens.accentHover,
          flexShrink: 0,
        }}>
          {isSuccess ? <CheckIcon /> : <LinkGlyph />}
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 16, fontWeight: 800, color: tokens.text, marginBottom: 3 }}>{title}</div>
          <div style={{ fontSize: 12, color: tokens.textMuted }}>{subtitle}</div>
        </div>
        <span style={{
          marginLeft: "auto",
          padding: "6px 9px",
          borderRadius: tokens.radiusFull,
          background: isSuccess ? tokens.greenBg : tokens.yellowBg,
          border: `1px solid ${isSuccess ? tokens.greenBorder : tokens.yellowBorder}`,
          color: isSuccess ? tokens.greenText : tokens.yellowText,
          fontSize: 11,
          fontWeight: 800,
          flexShrink: 0,
        }}>
          {status}
        </span>
      </div>
      {children}
    </section>
  );
}

function StatusLine({ text, tone = "default" }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, color: tokens.textSecondary, fontSize: 13, marginBottom: 8 }}>
      <span style={{
        width: 7,
        height: 7,
        borderRadius: "50%",
        background: tone === "success" ? tokens.green : tokens.accent,
        flexShrink: 0,
      }} />
      {text}
    </div>
  );
}

function InlineNotice({ tone = "warning", children }) {
  const danger = tone === "danger";
  return (
    <div style={{
      padding: "10px 12px",
      borderRadius: 12,
      background: danger ? tokens.redBg : tokens.yellowBg,
      border: `1px solid ${danger ? tokens.redBorder : tokens.yellowBorder}`,
      color: danger ? tokens.redText : tokens.yellowText,
      fontSize: 12,
      lineHeight: 1.45,
      marginBottom: 14,
    }}>
      {children}
    </div>
  );
}

function SmallButton({ children, onClick, disabled = false, primary = false, danger = false }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      style={{
        padding: "10px 14px",
        borderRadius: 12,
        fontSize: 13,
        fontWeight: 700,
        border: primary ? "none" : `1px solid ${danger ? tokens.redBorder : tokens.border}`,
        background: primary ? tokens.accent : danger ? tokens.redBg : tokens.bgCard,
        color: primary ? "#ffffff" : danger ? tokens.redText : tokens.text,
        cursor: disabled ? "wait" : "pointer",
        fontFamily: "inherit",
        opacity: disabled ? 0.6 : 1,
      }}
    >
      {children}
    </button>
  );
}

function ChevronLeftIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <path d="M9 11 5 7l4-4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="m20 6-11 11-5-5" />
    </svg>
  );
}

function LinkGlyph() {
  return (
    <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M10 13a5 5 0 0 0 7.07 0l2.83-2.83a5 5 0 0 0-7.07-7.07L11 4.93" />
      <path d="M14 11a5 5 0 0 0-7.07 0L4.1 13.83a5 5 0 0 0 7.07 7.07L13 19.07" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <path d="M12 5v14" />
      <path d="M5 12h14" />
    </svg>
  );
}

function SearchGlyph() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </svg>
  );
}

function MailIntegrationIcon() {
  return (
    <div style={{
      width: 54,
      height: 54,
      borderRadius: 13,
      background: "#ffffff",
      border: `1px solid ${tokens.border}`,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      boxShadow: "0 10px 24px rgba(36,34,30,0.08)",
    }}>
      <img
        src="https://upload.wikimedia.org/wikipedia/commons/7/7e/Gmail_icon_%282020%29.svg"
        alt=""
        width="38"
        height="38"
        style={{ display: "block" }}
      />
    </div>
  );
}

function CalendarIntegrationIcon() {
  return (
    <div style={{
      width: 54,
      height: 54,
      borderRadius: 13,
      background: "#ffffff",
      border: `1px solid ${tokens.border}`,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      boxShadow: "0 10px 24px rgba(36,34,30,0.08)",
    }}>
      <img
        src="https://upload.wikimedia.org/wikipedia/commons/a/a5/Google_Calendar_icon_%282020%29.svg"
        alt=""
        width="38"
        height="38"
        style={{ display: "block" }}
      />
    </div>
  );
}
