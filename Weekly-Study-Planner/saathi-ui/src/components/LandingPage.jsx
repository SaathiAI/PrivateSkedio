import { useMemo, useState } from "react";
import { GoogleSignIn, SignIn, SignUp } from "./Auth.jsx";
import { GlobalStyles } from "./GlobalStyles.jsx";
import { Spinner } from "./ui.jsx";
import { tokens } from "../theme.js";

const featureCards = [
  {
    eyebrow: "Conversation-first",
    title: "Talk normally. SkedioAI turns it into a real study contract.",
    body: "No rigid form filling. You speak naturally, SkedioAI understands the goal, scope, time window, and constraints.",
  },
  {
    eyebrow: "Planner brain",
    title: "Plans stay realistic, not fantasy timetables.",
    body: "Availability, blockers, progress, and required effort are all considered before the schedule gets created.",
  },
  {
    eyebrow: "Progress memory",
    title: "Sessions, checkboxes, and completed work feed back into the next plan.",
    body: "So the system does not keep acting like every week starts from zero.",
  },
];

const workflowSteps = [
  {
    label: "01",
    title: "Tell SkedioAI what you need",
    body: "Exam prep, weekly study, revision sprint, or just help choosing what matters first.",
  },
  {
    label: "02",
    title: "SkedioAI figures out the real contract",
    body: "Scope, effort, available time, blockers, and what is actually feasible.",
  },
  {
    label: "03",
    title: "You get a plan that can actually be followed",
    body: "Then the app tracks sessions, progress, and future changes without losing context.",
  },
];

const appHighlights = [
  "Calendar view with planned sessions",
  "Checklist completion and actual hours",
  "Chat-driven planning and replanning",
  "Saved plan history and progress memory",
];

function SectionTitle({ eyebrow, title, body, align = "left" }) {
  return (
    <div style={{ maxWidth: 720, textAlign: align }}>
      {eyebrow ? (
        <div style={{
          marginBottom: 12,
          fontSize: 11,
          letterSpacing: "0.18em",
          textTransform: "uppercase",
          color: tokens.textDim,
        }}>
          {eyebrow}
        </div>
      ) : null}
      <h2 style={{
        fontFamily: "'Fraunces', serif",
        fontWeight: 400,
        fontSize: "clamp(30px, 4.4vw, 54px)",
        lineHeight: 1.02,
        letterSpacing: "-0.04em",
        color: tokens.text,
        marginBottom: body ? 14 : 0,
      }}>
        {title}
      </h2>
      {body ? (
        <p style={{
          fontSize: 16,
          lineHeight: 1.75,
          color: tokens.textMuted,
          maxWidth: 640,
          margin: align === "center" ? "0 auto" : 0,
        }}>
          {body}
        </p>
      ) : null}
    </div>
  );
}

function MockWindow({ title, children, style }) {
  return (
    <div style={{
      borderRadius: 24,
      border: `1px solid rgba(255,255,255,0.08)`,
      background: "linear-gradient(180deg, rgba(18,18,20,0.98), rgba(11,11,12,0.98))",
      boxShadow: "0 30px 90px rgba(0,0,0,0.42)",
      overflow: "hidden",
      ...style,
    }}>
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "14px 16px",
        borderBottom: `1px solid ${tokens.border}`,
        background: "rgba(255,255,255,0.02)",
      }}>
        <div style={{ display: "flex", gap: 7 }}>
          {["#fb7185", "#fbbf24", "#34d399"].map(color => (
            <span key={color} style={{ width: 9, height: 9, borderRadius: "50%", background: color, display: "inline-block" }} />
          ))}
        </div>
        <div style={{ fontSize: 12, color: tokens.textMuted }}>{title}</div>
        <div style={{ width: 38 }} />
      </div>
      <div style={{ padding: 18 }}>
        {children}
      </div>
    </div>
  );
}

function AuthCard() {
  const [mode, setMode] = useState("signup");

  const subtitle = useMemo(() => (
    mode === "signup"
      ? "Create your account and start building plans, tracking sessions, and syncing your study flow."
      : "Sign in to continue your active plan, progress memory, and study coach thread."
  ), [mode]);

  return (
    <div style={{
      width: "min(100%, 420px)",
      borderRadius: 28,
      border: `1px solid rgba(255,255,255,0.08)`,
      background: "linear-gradient(180deg, rgba(17,17,19,0.96), rgba(13,13,14,0.98))",
      boxShadow: "0 28px 80px rgba(0,0,0,0.45)",
      overflow: "hidden",
    }}>
      <div style={{ padding: "24px 24px 20px", borderBottom: `1px solid ${tokens.border}` }}>
        <div style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 10,
          padding: "8px 12px",
          borderRadius: 999,
          background: "rgba(129,140,248,0.08)",
          border: "1px solid rgba(129,140,248,0.18)",
          color: tokens.accent,
          fontSize: 12,
          marginBottom: 18,
        }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: tokens.accent, display: "inline-block" }} />
          Live planning workspace
        </div>
        <h3 style={{
          fontFamily: "'Fraunces', serif",
          fontWeight: 400,
          fontSize: 34,
          lineHeight: 1.02,
          letterSpacing: "-0.04em",
          marginBottom: 10,
          color: tokens.text,
        }}>
          Start with SkedioAI.
        </h3>
        <p style={{ color: tokens.textMuted, fontSize: 15, lineHeight: 1.7 }}>
          {subtitle}
        </p>
      </div>

      <div style={{ padding: 24 }}>
        <div style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 8,
          padding: 5,
          borderRadius: 14,
          background: "#121214",
          border: `1px solid ${tokens.border}`,
          marginBottom: 20,
        }}>
          <button
            onClick={() => setMode("signup")}
            style={{
              padding: "11px 12px",
              borderRadius: 10,
              border: "none",
              cursor: "pointer",
              fontWeight: 700,
              fontSize: 13,
              background: mode === "signup" ? tokens.text : "transparent",
              color: mode === "signup" ? tokens.bg : tokens.textMuted,
              transition: "all 0.2s ease",
            }}
          >
            Create account
          </button>
          <button
            onClick={() => setMode("signin")}
            style={{
              padding: "11px 12px",
              borderRadius: 10,
              border: "none",
              cursor: "pointer",
              fontWeight: 700,
              fontSize: 13,
              background: mode === "signin" ? tokens.text : "transparent",
              color: mode === "signin" ? tokens.bg : tokens.textMuted,
              transition: "all 0.2s ease",
            }}
          >
            Sign in
          </button>
        </div>

        {mode === "signup" ? <SignUp /> : <SignIn />}

        <div style={{
          display: "flex",
          alignItems: "center",
          gap: 16,
          margin: "24px 0 20px",
          color: tokens.textDim,
          fontSize: 11,
          letterSpacing: "0.14em",
        }}>
          <div style={{ height: 1, flex: 1, background: tokens.border }} />
          <span>OR CONTINUE WITH</span>
          <div style={{ height: 1, flex: 1, background: tokens.border }} />
        </div>

        <GoogleSignIn />
      </div>
    </div>
  );
}

export function LandingPage() {
  return (
    <div style={{
      minHeight: "100vh",
      background: `
        radial-gradient(circle at top left, rgba(129,140,248,0.18), transparent 28%),
        radial-gradient(circle at 85% 15%, rgba(52,211,153,0.10), transparent 20%),
        linear-gradient(180deg, #080809 0%, #0d0d0d 42%, #090909 100%)
      `,
      color: tokens.text,
    }}>
      <GlobalStyles />

      <div style={{
        position: "relative",
        maxWidth: 1320,
        margin: "0 auto",
        padding: "28px clamp(20px, 4vw, 40px) 80px",
      }}>
        <header style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 20,
          marginBottom: 42,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{
              width: 36,
              height: 36,
              borderRadius: 12,
              background: tokens.text,
              color: tokens.bg,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontWeight: 800,
              fontSize: 15,
              boxShadow: "0 14px 32px rgba(238,238,238,0.14)",
            }}>
              S
            </div>
            <div>
              <div style={{
                fontFamily: "'Fraunces', serif",
                fontStyle: "italic",
                fontSize: 28,
                lineHeight: 1,
              }}>
                SkedioAI
              </div>
              <div style={{ fontSize: 12, color: tokens.textDim, marginTop: 4 }}>
                Your study companion
              </div>
            </div>
          </div>

          <div style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 10,
            padding: "10px 14px",
            borderRadius: 999,
            border: `1px solid rgba(255,255,255,0.08)`,
            background: "rgba(255,255,255,0.03)",
            color: tokens.textMuted,
            fontSize: 13,
          }}>
            Class 10 planning • progress • replanning
          </div>
        </header>

        <section style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1.15fr) minmax(360px, 0.85fr)",
          gap: 28,
          alignItems: "start",
        }}>
          <div>
            <div style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 10,
              padding: "9px 14px",
              borderRadius: 999,
              background: "rgba(255,255,255,0.04)",
              border: `1px solid rgba(255,255,255,0.08)`,
              color: tokens.textMuted,
              fontSize: 13,
              marginBottom: 20,
            }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: tokens.green, display: "inline-block" }} />
              Talk to SkedioAI. Get a plan you can actually follow.
            </div>

            <h1 style={{
              fontFamily: "'Fraunces', serif",
              fontWeight: 400,
              fontSize: "clamp(48px, 8vw, 92px)",
              lineHeight: 0.94,
              letterSpacing: "-0.06em",
              marginBottom: 18,
              maxWidth: 760,
            }}>
              Study planning that feels human, not robotic.
            </h1>

            <p style={{
              maxWidth: 700,
              color: tokens.textMuted,
              fontSize: "clamp(16px, 1.8vw, 19px)",
              lineHeight: 1.82,
              marginBottom: 28,
            }}>
              SkedioAI helps Class 10 students turn messy goals into clear study plans,
              track real progress, respect time limits, and keep the whole system grounded in what actually happened.
            </p>

            <div style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 12,
              marginBottom: 26,
            }}>
              <a
                href="#auth"
                style={{
                  textDecoration: "none",
                  padding: "14px 20px",
                  borderRadius: 14,
                  background: tokens.text,
                  color: tokens.bg,
                  fontWeight: 700,
                  boxShadow: "0 18px 42px rgba(238,238,238,0.10)",
                }}
              >
                Start with SkedioAI
              </a>
              <a
                href="#features"
                style={{
                  textDecoration: "none",
                  padding: "14px 20px",
                  borderRadius: 14,
                  border: `1px solid rgba(255,255,255,0.10)`,
                  background: "rgba(255,255,255,0.03)",
                  color: tokens.text,
                  fontWeight: 600,
                }}
              >
                See how it works
              </a>
            </div>

            <div style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
              gap: 12,
              maxWidth: 740,
            }}>
              {[
                ["Plans that stay realistic", "No fake perfect timetables."],
                ["Progress-aware memory", "Finished work actually matters next time."],
                ["Chat + calendar + checkboxes", "One system instead of ten scattered tools."],
              ].map(([title, body]) => (
                <div
                  key={title}
                  style={{
                    padding: 16,
                    borderRadius: 18,
                    border: `1px solid rgba(255,255,255,0.08)`,
                    background: "rgba(255,255,255,0.03)",
                    backdropFilter: "blur(12px)",
                  }}
                >
                  <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 6 }}>{title}</div>
                  <div style={{ fontSize: 13, lineHeight: 1.65, color: tokens.textMuted }}>{body}</div>
                </div>
              ))}
            </div>
          </div>

          <div id="auth" style={{ display: "flex", justifyContent: "center" }}>
            <AuthCard />
          </div>
        </section>

        <section style={{ marginTop: 72 }}>
          <MockWindow title="SkedioAI workspace preview">
            <div style={{
              display: "grid",
              gridTemplateColumns: "1.2fr 0.8fr",
              gap: 16,
            }}>
              <div style={{
                borderRadius: 18,
                border: `1px solid ${tokens.border}`,
                background: "#111113",
                padding: 16,
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
                  <div>
                    <div style={{ fontSize: 12, color: tokens.textDim, marginBottom: 4 }}>This week</div>
                    <div style={{ fontSize: 24, fontFamily: "'Fraunces', serif", fontWeight: 400 }}>Study calendar</div>
                  </div>
                  <div style={{
                    padding: "6px 10px",
                    borderRadius: 999,
                    background: tokens.indigoBg,
                    border: `1px solid ${tokens.indigoBorder}`,
                    color: tokens.accent,
                    fontSize: 12,
                  }}>
                    Synced plan
                  </div>
                </div>
                <div style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(3, 1fr)",
                  gap: 10,
                }}>
                  {[
                    ["Mon", "Quadratic Equations", "2 sessions"],
                    ["Tue", "Polynomials", "1 deep focus"],
                    ["Wed", "Probability", "Practice + review"],
                    ["Thu", "Weak areas", "Adaptive catch-up"],
                    ["Fri", "Light revision", "Protected buffer"],
                    ["Sat", "Past paper sprint", "Checkpointed"],
                  ].map(([day, title, meta]) => (
                    <div
                      key={day}
                      style={{
                        minHeight: 118,
                        borderRadius: 16,
                        border: `1px solid ${tokens.border}`,
                        background: "#171719",
                        padding: 12,
                      }}
                    >
                      <div style={{ fontSize: 11, color: tokens.textDim, marginBottom: 8 }}>{day}</div>
                      <div style={{ fontSize: 14, fontWeight: 700, lineHeight: 1.35, marginBottom: 8 }}>{title}</div>
                      <div style={{ fontSize: 12, color: tokens.textMuted }}>{meta}</div>
                    </div>
                  ))}
                </div>
              </div>

              <div style={{ display: "grid", gap: 16 }}>
                <div style={{
                  borderRadius: 18,
                  border: `1px solid ${tokens.border}`,
                  background: "#111113",
                  padding: 16,
                }}>
                  <div style={{ fontSize: 12, color: tokens.textDim, marginBottom: 8 }}>Study coach</div>
                  <div style={{ fontSize: 17, fontWeight: 700, marginBottom: 10 }}>Chat that actually remembers your plan</div>
                  <div style={{ color: tokens.textMuted, fontSize: 13, lineHeight: 1.7 }}>
                    SkedioAI asks what matters, checks feasibility, and adjusts the contract before the schedule gets generated.
                  </div>
                </div>

                <div style={{
                  borderRadius: 18,
                  border: `1px solid ${tokens.border}`,
                  background: "#111113",
                  padding: 16,
                }}>
                  <div style={{ fontSize: 12, color: tokens.textDim, marginBottom: 8 }}>Progress memory</div>
                  <div style={{ fontSize: 17, fontWeight: 700, marginBottom: 10 }}>Checkboxes feed the next plan</div>
                  <div style={{ color: tokens.textMuted, fontSize: 13, lineHeight: 1.7 }}>
                    Session completion, actual hours, and weak areas help future plans become smarter instead of repetitive.
                  </div>
                </div>
              </div>
            </div>
          </MockWindow>
        </section>

        <section id="features" style={{ marginTop: 92 }}>
          <SectionTitle
            eyebrow="Why it feels different"
            title="Not just another study planner."
            body="SkedioAI combines conversation, planning logic, progress tracking, and realism checks into one flow."
          />

          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
            gap: 18,
            marginTop: 28,
          }}>
            {featureCards.map((card) => (
              <div
                key={card.title}
                style={{
                  padding: 22,
                  borderRadius: 24,
                  border: `1px solid rgba(255,255,255,0.08)`,
                  background: "linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.02))",
                }}
              >
                <div style={{ fontSize: 11, color: tokens.textDim, letterSpacing: "0.16em", textTransform: "uppercase", marginBottom: 10 }}>
                  {card.eyebrow}
                </div>
                <div style={{ fontSize: 21, lineHeight: 1.22, fontWeight: 700, marginBottom: 10 }}>
                  {card.title}
                </div>
                <div style={{ color: tokens.textMuted, fontSize: 14, lineHeight: 1.75 }}>
                  {card.body}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section style={{ marginTop: 92 }}>
          <SectionTitle
            eyebrow="How it works"
            title="A cleaner path from messy intent to grounded action."
            body="The idea is simple: capture the truth, build a realistic contract, then let the planner turn it into sessions."
          />

          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
            gap: 18,
            marginTop: 28,
          }}>
            {workflowSteps.map((step) => (
              <div
                key={step.label}
                style={{
                  padding: 24,
                  borderRadius: 24,
                  border: `1px solid rgba(255,255,255,0.08)`,
                  background: "rgba(255,255,255,0.03)",
                }}
              >
                <div style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: 42,
                  height: 42,
                  borderRadius: 999,
                  background: tokens.indigoBg,
                  border: `1px solid ${tokens.indigoBorder}`,
                  color: tokens.accent,
                  fontSize: 12,
                  fontWeight: 800,
                  marginBottom: 14,
                }}>
                  {step.label}
                </div>
                <div style={{ fontSize: 20, fontWeight: 700, lineHeight: 1.25, marginBottom: 10 }}>
                  {step.title}
                </div>
                <div style={{ color: tokens.textMuted, fontSize: 14, lineHeight: 1.75 }}>
                  {step.body}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section style={{ marginTop: 92 }}>
          <div style={{
            display: "grid",
            gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)",
            gap: 20,
            alignItems: "stretch",
          }}>
            <MockWindow title="Inside the product">
              <div style={{ display: "grid", gap: 12 }}>
                {appHighlights.map((item, index) => (
                  <div
                    key={item}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 12,
                      padding: "14px 14px",
                      borderRadius: 14,
                      border: `1px solid ${tokens.border}`,
                      background: "#121214",
                    }}
                  >
                    <div style={{
                      width: 30,
                      height: 30,
                      borderRadius: 999,
                      background: index % 2 === 0 ? tokens.indigoBg : tokens.greenBg,
                      border: `1px solid ${index % 2 === 0 ? tokens.indigoBorder : tokens.greenBorder}`,
                      color: index % 2 === 0 ? tokens.accent : tokens.green,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 13,
                      fontWeight: 800,
                      flexShrink: 0,
                    }}>
                      {index + 1}
                    </div>
                    <div style={{ fontSize: 14, color: tokens.text }}>{item}</div>
                  </div>
                ))}
              </div>
            </MockWindow>

            <div style={{
              padding: "28px clamp(20px, 2vw, 30px)",
              borderRadius: 28,
              border: `1px solid rgba(255,255,255,0.08)`,
              background: "linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.02))",
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
            }}>
              <div style={{ fontSize: 11, color: tokens.textDim, letterSpacing: "0.18em", textTransform: "uppercase", marginBottom: 12 }}>
                Built for real usage
              </div>
              <div style={{
                fontFamily: "'Fraunces', serif",
                fontWeight: 400,
                fontSize: "clamp(30px, 4vw, 48px)",
                lineHeight: 1.03,
                letterSpacing: "-0.04em",
                marginBottom: 16,
              }}>
                Your app, your plan, your progress — finally in one place.
              </div>
              <p style={{ color: tokens.textMuted, fontSize: 15, lineHeight: 1.8, marginBottom: 22 }}>
                SkedioAI is not just a pretty planner. It is meant to carry the whole loop:
                intake, planning, progress truth, calendar awareness, and future replanning.
              </p>
              <a
                href="#auth"
                style={{
                  alignSelf: "flex-start",
                  textDecoration: "none",
                  padding: "14px 18px",
                  borderRadius: 14,
                  background: tokens.text,
                  color: tokens.bg,
                  fontWeight: 700,
                }}
              >
                Open the workspace
              </a>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
