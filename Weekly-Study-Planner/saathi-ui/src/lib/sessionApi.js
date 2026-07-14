import { API, authPost } from "./api.js";

export const sessionApi = {
  complete(sessionId, actualHours) {
    return authPost(`${API}/session/complete`, {
      session_id: sessionId,
      actual_hours: actualHours,
    });
  },

  updateContent(sessionId, contentMatchKey, status, timeSpent = 0) {
    return authPost(`${API}/session/complete`, {
      session_id: sessionId,
      content_updates: [{
        content_match_key: contentMatchKey,
        status,
        time_spent: timeSpent || 0,
      }],
    });
  },

  undo(sessionId) {
    return authPost(`${API}/session/undo`, {
      session_id: sessionId,
    });
  },

  skip(sessionId) {
    return authPost(`${API}/session/skip`, {
      session_id: sessionId,
    });
  },
};
