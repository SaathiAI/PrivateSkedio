import { API, authFetch, authPost, apiErrorMessage } from "./api.js";

const readChatResponse = async (response, fallback) => {
  if (!response.ok) {
    throw new Error(await apiErrorMessage(response, fallback));
  }
  return response.json();
};

export const chatApi = {
  async send(message, threadId, uiContext = null) {
    const response = await authPost(`${API}/chat/send`, {
      message,
      thread_id: threadId,
      ui_context: uiContext,
    });
    return readChatResponse(response, "Chat request failed");
  },

  async action(action, threadId) {
    const response = await authPost(`${API}/chat/action`, {
      action,
      thread_id: threadId,
    });
    return readChatResponse(response, "Plan action failed");
  },

  async pendingReview(threadId) {
    const params = new URLSearchParams({ thread_id: threadId });
    const response = await authFetch(`${API}/chat/pending-review?${params.toString()}`);
    return readChatResponse(response, "Pending review could not be loaded");
  },

  async reset(threadId) {
    const response = await authFetch(`${API}/chat/reset/${encodeURIComponent(threadId)}`, {
      method: "DELETE",
    });
    return readChatResponse(response, "Chat reset failed");
  },

  async sendStream(message, threadId, handlers = {}, uiContext = null) {
    const response = await authFetch(`${API}/chat/send/stream`, {
      method: "POST",
      body: JSON.stringify({
        message,
        thread_id: threadId,
        ui_context: uiContext,
      }),
    });

    if (!response.ok || !response.body) {
      throw new Error(`Streaming chat failed with status ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finalPayload = null;

    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (!line.trim()) {
          continue;
        }

        const event = JSON.parse(line);
        if (event.type === "chunk") {
          handlers.onChunk?.(event.text || "");
          continue;
        }

        if (event.type === "done") {
          finalPayload = event;
          handlers.onDone?.(event);
          continue;
        }

        if (event.type === "error") {
          throw new Error(event.detail || "Streaming chat failed");
        }
      }
    }

    if (!finalPayload) {
      throw new Error("Streaming chat ended without final payload");
    }

    return finalPayload;
  },
};
