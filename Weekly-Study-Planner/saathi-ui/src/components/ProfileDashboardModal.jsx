import { useState } from "react";
import { useAuth } from "./Auth.jsx";
import { clearClientUserState } from "../lib/clientState.js";
import { getProfileInitials } from "../lib/userHelpers.js";
import { startTimer } from "../lib/perf.js";
import { DashboardTabV2 } from "./Dashboard.jsx";
import { tokens } from "../theme.js";

export function ProfileDashboardModal({ stats, onClose, userId }) {
  const { user, supabase } = useAuth();
  const [signingOut, setSigningOut] = useState(false);
  const [signOutError, setSignOutError] = useState("");
  const profileInitials = getProfileInitials(user);
  const handleSignOut = async () => {
    if (!supabase || signingOut) return;
    setSigningOut(true);
    setSignOutError("");
    try {
      clearClientUserState(localStorage, userId);
      const stop = startTimer('auth:signOut(profile)');
      const { error } = await supabase.auth.signOut({ scope: "local" });
      stop();
      if (error) throw error;
      onClose();
    } catch (error) {
      setSignOutError(error.message || "Sign out failed");
    } finally {
      setSigningOut(false);
    }
  };

  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(26,25,23,0.3)",
      display: "flex", alignItems: "center", justifyContent: "center",
      zIndex: 3000, animation: "fadeIn 0.15s ease", backdropFilter: "blur(4px)",
    }}>
      <div style={{
        background: tokens.bg, border: `1px solid ${tokens.border}`,
        borderRadius: 24, width: "90vw", maxWidth: 1000, maxHeight: "90vh", overflowY: "auto",
        boxShadow: "0 24px 60px rgba(0,0,0,0.1)", animation: "fadeUp 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
      }}>
        <div style={{ position: "sticky", top: 0, background: tokens.bg, zIndex: 10, padding: "24px 32px", borderBottom: `1px solid ${tokens.border}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <h2 style={{ fontSize: 24, fontFamily: "'Fraunces', serif", fontWeight: 400, color: tokens.text, margin: 0 }}>Account</h2>
            <div style={{ fontSize: 12, color: tokens.textMuted, marginTop: 4 }}>{user?.email || "Signed in account"}</div>
          </div>
          <button onClick={onClose} style={{ background: "transparent", border: `1px solid ${tokens.border}`, borderRadius: '50%', width: 36, height: 36, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: "pointer", color: tokens.textMuted }}>
             ✕
          </button>
        </div>
        <div style={{ padding: 32, display: "grid", gridTemplateColumns: "minmax(280px, 0.8fr) minmax(0, 1.4fr)", gap: 20 }}>
          <div style={{
            border: `1px solid ${tokens.border}`,
            background: tokens.bgCard,
            borderRadius: 14,
            padding: 22,
            alignSelf: "start",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 18 }}>
              <div style={{
                width: 48,
                height: 48,
                borderRadius: "50%",
                background: `linear-gradient(135deg, ${tokens.indigo}, #7c3aed)`,
                color: "white",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 14,
                fontWeight: 800,
                flexShrink: 0,
              }}>
                {profileInitials}
              </div>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 15, color: tokens.text, fontWeight: 700, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {user?.email || "Signed in"}
                </div>
                <div style={{ fontSize: 12, color: tokens.textMuted, marginTop: 3 }}>
                  SkedioAI account
                </div>
              </div>
            </div>

            <div style={{ display: "grid", gap: 10, marginBottom: 18 }}>
              <div style={{ padding: 12, borderRadius: 9, background: tokens.bg, border: `1px solid ${tokens.border}` }}>
                <div style={{ fontSize: 10, color: tokens.textDim, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 5 }}>User ID</div>
                <div style={{ fontSize: 12, color: tokens.textMuted, fontFamily: "'DM Mono', monospace", overflow: "hidden", textOverflow: "ellipsis" }}>{userId || "unknown"}</div>
              </div>
              <div style={{ padding: 12, borderRadius: 9, background: tokens.bg, border: `1px solid ${tokens.border}` }}>
                <div style={{ fontSize: 10, color: tokens.textDim, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 5 }}>Session</div>
                <div style={{ fontSize: 12, color: tokens.green }}>Authenticated</div>
              </div>
            </div>

            {signOutError && (
              <div style={{
                padding: "10px 12px",
                borderRadius: 8,
                background: tokens.redBg,
                border: `1px solid ${tokens.red}`,
                color: tokens.red,
                fontSize: 12,
                marginBottom: 12,
              }}>
                {signOutError}
              </div>
            )}

            <button
              onClick={handleSignOut}
              disabled={signingOut}
              style={{
                width: "100%",
                padding: "12px 14px",
                borderRadius: 9,
                border: `1px solid ${tokens.red}`,
                background: tokens.redBg,
                color: tokens.red,
                cursor: signingOut ? "wait" : "pointer",
                fontFamily: "inherit",
                fontSize: 14,
                fontWeight: 700,
                opacity: signingOut ? 0.65 : 1,
              }}
            >
              {signingOut ? "Signing out..." : "Log out"}
            </button>
          </div>

          <div style={{ minWidth: 0 }}>
            <DashboardTabV2 stats={stats} examDate={stats?.exam_date} daysUntilExam={stats?.days_until_exam} />
          </div>
        </div>
      </div>
    </div>
  );
}
