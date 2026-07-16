import { useEffect, useRef, useState } from "react";
import { tokens } from "../theme.js";
import { chatApi } from "../lib/chatApi.js";
import { startTimer } from "../lib/perf.js";
import {
  chatStorageKeyForThread,
  loadPersistedMessages,
} from "../lib/clientState.js";

export function ChatPanel({
  onClose,
  threadId,
  onPlanCommitted,
  onDraftStateChange,
  devToolsEnabled = false,
  onLoadDevDraftPreview,
  onClearDevDraftPreview,
  devPreviewNonce = 0,
  devReviewPreviewPayload = null,
  emailReviewRequest = null,
  drawerWidth = 380,
  onDrawerWidthChange,
  isEmbedded = false,
  queuedPrompt = null,
}) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [changeMode, setChangeMode] = useState(false);
  const [loading, setLoading] = useState(false);
  const [resetting, setResetting] = useState(false);
  const endRef = useRef(null);
  const lastEmailReviewNonceRef = useRef(null);
  const lastQueuedPromptNonceRef = useRef(null);

  useEffect(() => {
    if (!threadId) {
      setMessages([]);
      return;
    }
    setMessages(loadPersistedMessages(localStorage, threadId));
  }, [threadId]);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  useEffect(() => {
    if (!emailReviewRequest?.nonce || !threadId) return;
    if (emailReviewRequest.threadId !== threadId) return;
    if (lastEmailReviewNonceRef.current === emailReviewRequest.nonce) return;

    lastEmailReviewNonceRef.current = emailReviewRequest.nonce;
    let cancelled = false;

    const runEmailReviewFlow = async () => {
      setLoading(true);
      try {
        const action = emailReviewRequest.action || "open";
        const data = action === "open"
          ? await chatApi.pendingReview(threadId)
          : await chatApi.action(action, threadId);

        if (cancelled) return;

        const assistantMessage = buildAssistantMessage(data);
        persistMessages([assistantMessage]);
        onDraftStateChange?.(data.draft_plan || null);
        if (data.plan_committed) {
          onDraftStateChange?.(null);
          onPlanCommitted?.();
        }
        if (action === "request_changes") {
          setChangeMode(true);
        }
      } catch {
        if (cancelled) return;
        persistMessages([
          {
            text: "I couldn't load that review link properly.",
            isUser: false,
            actions: [],
            actionGroups: [],
          },
        ]);
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    runEmailReviewFlow();
    return () => {
      cancelled = true;
    };
  }, [emailReviewRequest, threadId]);

  useEffect(() => {
    if (!devPreviewNonce) return;

    const previewMessage = buildAssistantMessage(devReviewPreviewPayload || {
      reply: "Planner draft ready. I mapped the sessions onto the calendar and parked the plan in review mode. Nothing is saved yet.",
      actions: [
        { id: "approve_plan", label: "Approve plan" },
        { id: "request_changes", label: "Request changes" },
        { id: "cancel_plan", label: "Cancel plan" },
      ],
    });

    const nextMessages = [...messages, { ...previewMessage, devPreview: true }];
    persistMessages(nextMessages);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [devPreviewNonce]);

  const planActionMeta = {
    approve_plan: {
      eyebrow: "Verified draft",
      detail: "Save this exact plan to your schedule.",
      tone: "primary",
    },
    request_changes: {
      eyebrow: "Adjust",
      detail: "Tell SkedioAI what should change first.",
      tone: "secondary",
    },
    cancel_plan: {
      eyebrow: "Later",
      detail: "Keep chatting without saving this draft.",
      tone: "quiet",
    },
  };

  const buildActionGroups = (pendingUi, legacyActions = []) => {
    if (pendingUi?.type === "plan_review") {
      const coreItems = Array.isArray(pendingUi.actions)
        ? pendingUi.actions.map(action => ({
            id: action.id,
            label: action.label,
          }))
        : [];
      return [
        coreItems.length > 0 ? {
          key: "core",
          title: "Choose next step",
          subtitle: "Nothing is saved until you approve it.",
          items: coreItems,
        } : null,
      ].filter(Boolean);
    }

    if (!Array.isArray(legacyActions) || legacyActions.length === 0) return [];
    return [
      {
        key: "legacy",
        title: "Actions",
        subtitle: "",
        items: legacyActions,
      },
    ];
  };

  const buildAssistantMessage = (payload) => {
    const pendingUi = payload?.pending_ui || null;
    const actions = Array.isArray(payload?.actions) ? payload.actions : [];
    return {
      text: payload?.reply || "...",
      isUser: false,
      actions,
      pendingUi,
      actionGroups: buildActionGroups(pendingUi, actions),
      debugPayload: payload || null,
    };
  };

  const persistMessages = (nextMessages) => {
    setMessages(nextMessages);
    if (!threadId) return;
    localStorage.setItem(chatStorageKeyForThread(threadId), JSON.stringify(nextMessages));
  };

  const handleResetChat = async () => {
    if (!threadId || loading || resetting) return;
    setResetting(true);
    try {
      await chatApi.reset(threadId);
      localStorage.removeItem(chatStorageKeyForThread(threadId));
      setMessages([]);
      onDraftStateChange?.(null);
      setChangeMode(false);
    } catch (error) {
      console.error("Failed to reset chat", error);
    } finally {
      setResetting(false);
    }
  };

  const sendPromptText = async (userMsg) => {
    if (!userMsg.trim() || loading) return;
    const assistantIndex = messages.length + 1;
    const newMsgs = [
      ...messages,
      { text: userMsg, isUser: true },
      { text: "", isUser: false, actions: [] },
    ];
    persistMessages(newMsgs);
    setLoading(true);
    try {
      const uiContext = changeMode ? { source: "pending_plan_review" } : null;
      const stop = startTimer('chat:sendStream');
      const data = await chatApi.sendStream(userMsg, threadId, {
        onChunk: (chunk) => {
          setMessages(prev => {
            const next = [...prev];
            const current = next[assistantIndex] || { text: "", isUser: false, actions: [] };
            next[assistantIndex] = {
              ...current,
              text: `${current.text || ""}${chunk}`,
              isUser: false,
            };
            if (threadId) localStorage.setItem(chatStorageKeyForThread(threadId), JSON.stringify(next));
            return next;
          });
        },
      }, uiContext);
      stop();
      setChangeMode(false);
      setMessages(prev => {
        const next = [...prev];
        next[assistantIndex] = {
          ...buildAssistantMessage(data),
        };
        if (threadId) localStorage.setItem(chatStorageKeyForThread(threadId), JSON.stringify(next));
        return next;
      });
      onDraftStateChange?.(data.draft_plan || null);
      // Auto-refresh immediately when plan committed
      if (data.plan_committed) {
        onDraftStateChange?.(null);
        onPlanCommitted();
      }
    } catch {
      const errored = [
        ...newMsgs.slice(0, assistantIndex),
        { text: "Something went wrong.", isUser: false, actions: [], actionGroups: [] },
      ];
      persistMessages(errored);
    } finally { setLoading(false); }
  };

  useEffect(() => {
    if (!queuedPrompt?.nonce || !threadId) return;
    if (lastQueuedPromptNonceRef.current === queuedPrompt.nonce) return;
    if (loading) return;

    lastQueuedPromptNonceRef.current = queuedPrompt.nonce;
    void sendPromptText(queuedPrompt.text);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queuedPrompt, threadId, loading]);

  const send = async (e) => {
    e.preventDefault();
    if (!input.trim() || loading) return;
    const userMsg = input.trim();
    setInput("");
    await sendPromptText(userMsg);
  };

  const handleAction = async (messageIndex, actionId) => {
    if (loading) return;
    const targetMessage = messages[messageIndex];

    if (targetMessage?.devPreview) {
      const cleared = messages.map((msg, i) => (
        i === messageIndex ? { ...msg, actions: [], actionGroups: [] } : msg
      ));

      if (actionId === "request_changes") {
        persistMessages([
          ...cleared,
          {
            text: "Dev preview kept open. Change requests are a UI-only preview right now, so the draft stays on the calendar.",
            isUser: false,
          },
        ]);
        return;
      }

      if (actionId === "approve_plan") {
        onDraftStateChange?.(null);
        persistMessages([
          ...cleared,
          {
            text: "Dev preview approved locally. I cleared the draft styling, but this did not commit anything to the backend.",
            isUser: false,
          },
        ]);
        return;
      }

      if (actionId === "cancel_plan") {
        onDraftStateChange?.(null);
        persistMessages([
          ...cleared,
          {
            text: "Dev preview dismissed. The draft sessions are removed from the calendar.",
            isUser: false,
          },
        ]);
        return;
      }
    }

    const cleared = messages.map((msg, i) => (
      i === messageIndex ? { ...msg, actions: [], actionGroups: [] } : msg
    ));

    if (actionId === "request_changes") {
      const nextMessages = [
        ...cleared,
        { text: "What should I change in the draft plan?", isUser: false },
      ];
      setChangeMode(true);
      persistMessages(nextMessages);
      return;
    }

    if (actionId === "cancel_plan") {
      onDraftStateChange?.(null);
    }

    setLoading(true);
    persistMessages(cleared);
    try {
      const data = await chatApi.action(actionId, threadId);
      const withReply = [...cleared, buildAssistantMessage(data)];
      persistMessages(withReply);
      onDraftStateChange?.(data.draft_plan || null);
      if (data.plan_committed) {
        onDraftStateChange?.(null);
        onPlanCommitted();
      }
    } catch {
      setMessages(p => [...p, { text: "Something went wrong.", isUser: false }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={isEmbedded ? {
      height: "100%",
      minHeight: 0,
      background: tokens.bgCard,
      border: `1px solid ${tokens.border}`,
      borderRadius: 20,
      display: "flex",
      flexDirection: "column",
      overflow: "hidden",
      boxShadow: "0 24px 60px rgba(0,0,0,0.38)",
    } : {
      position: "fixed", top: 0, right: 0, bottom: 0, width: 420,
      background: tokens.bgCard, borderLeft: `1px solid ${tokens.borderSubtle}`,
      display: "flex", flexDirection: "column", zIndex: tokens.zIndexModal,
      animation: "slideRight 0.25s cubic-bezier(0.16, 1, 0.3, 1)", boxShadow: "-4px 0 24px rgba(0,0,0,0.25)",
    }}>
      {/* Header */}
      <div style={{
        padding: isEmbedded ? "18px 22px" : `${tokens.space4} ${tokens.space5}`,
        borderBottom: `1px solid ${tokens.borderSubtle}`,
        display: "flex", alignItems: "center", justifyContent: "space-between",
        background: isEmbedded ? "rgba(17,17,19,0.92)" : "transparent",
        flexShrink: 0,
      }}>
        <div>
          <div style={{
            fontSize: isEmbedded ? 20 : 16,
            fontFamily: "'Playfair Display', serif",
            fontWeight: 500,
            color: tokens.text,
          }}>{isEmbedded ? "Planner assistant" : "SkedioAI"}</div>
          <div style={{ fontSize: 11, color: tokens.textDim, marginTop: 3 }}>
            {isEmbedded ? "Review drafts, request changes, and keep the schedule honest." : "Study companion"}
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: tokens.space2 }}>
          {!isEmbedded && typeof onDrawerWidthChange === "function" && (
            <div style={{ display: "flex", alignItems: "center", gap: tokens.space2 }}>
              <input
                type="range"
                min="320"
                max="640"
                step="20"
                value={drawerWidth}
                onChange={e => onDrawerWidthChange(e.target.value)}
                style={{
                  width: 80,
                  accentColor: tokens.accent,
                  cursor: "pointer",
                }}
                aria-label="Adjust chat drawer width"
              />
            </div>
          )}
          {devToolsEnabled && (
            <>
              <button
                type="button"
                onClick={onLoadDevDraftPreview}
                style={{
                  background: tokens.redBg,
                  border: `1px solid ${tokens.redBorder}`,
                  borderRadius: tokens.radiusFull,
                  padding: `${tokens.space1} ${tokens.space3}`,
                  color: tokens.redText,
                  cursor: "pointer",
                  fontSize: 11,
                  fontWeight: 500,
                  fontFamily: "inherit",
                }}
              >
                Draft
              </button>
              <button
                type="button"
                onClick={onClearDevDraftPreview}
                style={{
                  background: "transparent",
                  border: `1px solid ${tokens.border}`,
                  borderRadius: tokens.radiusFull,
                  padding: `${tokens.space1} ${tokens.space3}`,
                  color: tokens.textMuted,
                  cursor: "pointer",
                  fontSize: 11,
                  fontWeight: 500,
                  fontFamily: "inherit",
                }}
              >
                Clear
              </button>
            </>
          )}
          <button
            type="button"
            disabled={!threadId || loading || resetting}
            onClick={handleResetChat}
            style={{
              background: "transparent",
              border: `1px solid ${tokens.border}`,
              borderRadius: tokens.radiusFull,
              padding: `${tokens.space1} ${tokens.space3}`,
              color: tokens.textMuted,
              cursor: !threadId || loading || resetting ? "not-allowed" : "pointer",
              fontSize: 11,
              fontWeight: 500,
              fontFamily: "inherit",
              opacity: !threadId || loading || resetting ? 0.5 : 1,
            }}
          >
            {resetting ? "Resetting..." : "New"}
          </button>
          <button onClick={onClose} aria-label="Close chat" style={{
            background: "transparent", border: `1px solid ${tokens.border}`,
            borderRadius: tokens.radiusSm,
            padding: `${tokens.space1} ${tokens.space2}`,
            color: tokens.textMuted, cursor: "pointer", fontSize: 11,
            fontFamily: "inherit", fontWeight: 500,
            transition: `all ${tokens.transitionFast}`,
          }}
            onMouseEnter={e => { e.currentTarget.style.background = tokens.bgHover; e.currentTarget.style.color = tokens.text; }}
            onMouseLeave={e => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = tokens.textMuted; }}
          >esc</button>
        </div>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, minHeight: 0, overflowY: "auto", padding: isEmbedded ? "20px 22px 0" : `${tokens.space5} ${tokens.space5} 0` }}>
        {messages.length === 0 && (
          <div style={{ textAlign: "center", padding: isEmbedded ? "84px 0" : "60px 0" }}>
            <div style={{
              fontSize: isEmbedded ? 30 : 20,
              fontFamily: "'Playfair Display', serif",
              color: tokens.textDim,
              marginBottom: tokens.space3,
            }}>
              {isEmbedded ? "What should we do with the week?" : "What would you like to study?"}
            </div>
            <div style={{ fontSize: 13, color: tokens.textMuted, lineHeight: 1.8 }}>
              {isEmbedded ? (
                <>
                  Review a draft<br />Reschedule around blockers<br />Adjust the plan without losing the thread
                </>
              ) : (
                <>
                  Reschedule sessions<br />Add or remove topics<br />Adjust your plan
                </>
              )}
            </div>
          </div>
        )}
        {messages.map((msg, i) => (
          (() => {
            const effectiveActionGroups = Array.isArray(msg.actionGroups) && msg.actionGroups.length > 0
              ? msg.actionGroups
              : buildActionGroups(msg.pendingUi, msg.actions);
            return (
          <div key={i} style={{ display: "flex", justifyContent: msg.isUser ? "flex-end" : "flex-start", marginBottom: 10, animation: "fadeUp 0.15s ease" }}>
            <div style={{ maxWidth: "82%" }}>
              <div style={{
                padding: "10px 14px", borderRadius: 10,
                background: msg.isUser ? tokens.text : tokens.bg,
                color: msg.isUser ? tokens.bgCard : tokens.text,
                fontSize: 14, lineHeight: 1.55, whiteSpace: "pre-wrap",
                border: msg.isUser ? "none" : `1px solid ${tokens.border}`,
              }}>{msg.text}</div>
              {!msg.isUser && effectiveActionGroups.length > 0 && (
                <div style={{
                  marginTop: 8,
                  border: `1px solid ${tokens.border}`,
                  borderRadius: 10,
                  background: tokens.bgCard,
                  overflow: "hidden",
                  boxShadow: "0 10px 28px rgba(0,0,0,0.04)",
                }}>
                  <div style={{
                    padding: "9px 11px",
                    borderBottom: `1px solid ${tokens.border}`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                          gap: 12,
                  }}>
                    <div>
                      <div style={{ fontSize: 11, color: tokens.text, fontWeight: 600 }}>
                        {msg.pendingUi?.type === "plan_review" ? "Plan review ready" : "Ready for your call"}
                      </div>
                      <div style={{ fontSize: 11, color: tokens.textMuted, marginTop: 2 }}>
                        {msg.pendingUi?.type === "plan_review"
                          ? "Choose a final action or try a guided tweak."
                          : "Nothing is saved until you choose."}
                      </div>
                      {msg.pendingUi?.type === "plan_review" && (
                        <div
                          style={{
                            marginTop: 8,
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 6,
                            padding: "5px 8px",
                            borderRadius: 999,
                            background: `${tokens.redBg}18`,
                            color: tokens.text,
                            border: `1px solid ${tokens.border}`,
                            fontSize: 10,
                            fontWeight: 700,
                            letterSpacing: "0.06em",
                            textTransform: "uppercase",
                          }}
                        >
                          <span
                            style={{
                              width: 6,
                              height: 6,
                              borderRadius: "50%",
                              background: tokens.red,
                              boxShadow: `0 0 0 3px ${tokens.red}22`,
                            }}
                          />
                          Draft only
                        </div>
                      )}
                    </div>
                    <div style={{
                      width: 7,
                      height: 7,
                      borderRadius: "50%",
                      background: tokens.green,
                      boxShadow: `0 0 0 3px ${tokens.green}22`,
                      flexShrink: 0,
                    }} />
                  </div>

                  <div style={{ padding: 7, display: "grid", gap: 8 }}>
                    {effectiveActionGroups.map((group, groupIndex) => (
                      <div key={group.key || groupIndex} style={{ display: "grid", gap: 6 }}>
                        {(group.title || group.subtitle) && (
                          <div style={{ padding: "2px 4px 0" }}>
                            {group.title && (
                              <div style={{ fontSize: 11, fontWeight: 600, color: tokens.text }}>
                                {group.title}
                              </div>
                            )}
                            {group.subtitle && (
                              <div style={{ fontSize: 11, color: tokens.textMuted, marginTop: 2 }}>
                                {group.subtitle}
                              </div>
                            )}
                          </div>
                        )}
                        {group.items.map(action => {
                      const meta = planActionMeta[action.id] || {};
                      const isPrimary = meta.tone === "primary";
                      const isQuiet = meta.tone === "quiet";
                      const isSuggestion = Boolean(action.reason);
                      return (
                        <button
                          key={action.id}
                          type="button"
                          disabled={loading}
                          onClick={() => handleAction(i, action.id)}
                          style={{
                            width: "100%",
                            border: `1px solid ${
                              isPrimary
                                ? tokens.text
                                : isSuggestion
                                  ? tokens.borderHover
                                  : tokens.border
                            }`,
                            background: isPrimary
                              ? tokens.text
                              : isSuggestion
                                ? `${tokens.indigo}10`
                                : tokens.bg,
                            color: isPrimary ? tokens.bgCard : isQuiet ? tokens.textMuted : tokens.text,
                            borderRadius: 8,
                            padding: "9px 10px",
                            cursor: loading ? "wait" : "pointer",
                            fontFamily: "inherit",
                            textAlign: "left",
                            transition: "transform 0.15s ease, border-color 0.15s ease, background 0.15s ease",
                            opacity: loading ? 0.68 : 1,
                          }}
                          onMouseEnter={e => {
                            if (loading) return;
                            e.currentTarget.style.transform = "translateY(-1px)";
                            e.currentTarget.style.borderColor = isPrimary ? tokens.text : tokens.borderHover;
                          }}
                          onMouseLeave={e => {
                            e.currentTarget.style.transform = "translateY(0)";
                            e.currentTarget.style.borderColor = isPrimary
                              ? tokens.text
                              : isSuggestion
                                ? tokens.borderHover
                                : tokens.border;
                          }}
                        >
                          <div style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            gap: 10,
                          }}>
                            <div>
                              <div style={{ fontSize: 13, fontWeight: 600 }}>
                                {action.label}
                              </div>
                              <div style={{
                                fontSize: 11,
                                color: isPrimary ? "rgba(255,255,255,0.72)" : tokens.textMuted,
                                marginTop: 2,
                                lineHeight: 1.35,
                              }}>
                                {action.reason || meta.detail}
                              </div>
                            </div>
                            <span style={{
                              fontSize: 10,
                              color: isPrimary ? "rgba(255,255,255,0.72)" : tokens.textMuted,
                              textTransform: "uppercase",
                              letterSpacing: "0.08em",
                              flexShrink: 0,
                            }}>
                              {action.reason ? "Suggestion" : meta.eyebrow}
                            </span>
                          </div>
                        </button>
                      );
                    })}
                      </div>
                    ))}
                  </div>
                  {devToolsEnabled && msg.debugPayload && (
                    <details
                      style={{
                        borderTop: `1px solid ${tokens.border}`,
                        background: tokens.bg,
                      }}
                    >
                      <summary
                        style={{
                          cursor: "pointer",
                          listStyle: "none",
                          padding: "10px 11px",
                          fontSize: 11,
                          color: tokens.textMuted,
                          userSelect: "none",
                        }}
                      >
                        Dev payload
                      </summary>
                      <pre
                        style={{
                          margin: 0,
                          padding: "0 11px 11px",
                          fontSize: 11,
                          lineHeight: 1.5,
                          color: tokens.textMuted,
                          whiteSpace: "pre-wrap",
                          wordBreak: "break-word",
                          overflowX: "auto",
                        }}
                      >
                        {JSON.stringify(msg.debugPayload, null, 2)}
                      </pre>
                    </details>
                  )}
                </div>
              )}
            </div>
          </div>
            );
          })()
        ))}
        {loading && (
          <div style={{ display: "flex", gap: 5, padding: "10px 0", marginBottom: 10 }}>
            {[0, 0.15, 0.3].map((d, i) => (
              <div key={i} style={{ width: 7, height: 7, borderRadius: "50%", background: tokens.textDim, animation: `pulse 1.2s infinite ${d}s` }} />
            ))}
          </div>
        )}
        <div ref={endRef} style={{ height: 20 }} />
      </div>

      {/* Input */}
      <form onSubmit={send} style={{
        padding: isEmbedded ? "18px 22px 22px" : `${tokens.space4} ${tokens.space5}`,
        borderTop: `1px solid ${tokens.borderSubtle}`,
        display: "flex", gap: tokens.space2,
        flexShrink: 0,
      }}>
        <input
          type="text" value={input} onChange={e => setInput(e.target.value)}
          placeholder={changeMode ? "What should change?" : "Ask SkedioAI..."} disabled={loading} autoFocus
          style={{
            flex: 1, background: tokens.bg, border: `1px solid ${tokens.border}`,
            borderRadius: tokens.radiusMd, padding: `${tokens.space3} ${tokens.space4}`,
            color: tokens.text, fontSize: 13, outline: "none", fontFamily: "inherit",
            transition: `border-color ${tokens.transitionFast}`,
          }}
        />
        <button type="submit" disabled={!input.trim() || loading} style={{
          background: input.trim() && !loading ? tokens.accent : tokens.bgHover,
          border: "none", borderRadius: tokens.radiusMd,
          padding: `${tokens.space3} ${tokens.space4}`,
          color: input.trim() && !loading ? tokens.bg : tokens.textDim,
          cursor: input.trim() && !loading ? "pointer" : "not-allowed",
          fontSize: 14, fontFamily: "inherit", fontWeight: 500,
          transition: `all ${tokens.transitionFast}`,
        }}>↑</button>
      </form>
    </div>
  );
}
