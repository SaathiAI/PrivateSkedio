export const threadStorageKeyForUser = (userId) => `saathi_thread_id:${userId || "anonymous"}`;

export const chatStorageKeyForThread = (threadId) => `chat_${threadId}`;

export function getOrCreateThreadId(storage, userId, createThreadId) {
  const storageKey = threadStorageKeyForUser(userId);
  const existing = storage.getItem(storageKey);
  if (existing) return existing;
  const nextThreadId = createThreadId();
  storage.setItem(storageKey, nextThreadId);
  return nextThreadId;
}

export function setThreadIdForUser(storage, userId, threadId) {
  const storageKey = threadStorageKeyForUser(userId);
  storage.setItem(storageKey, threadId);
}

export function clearClientUserState(storage, userId) {
  const scopedThreadKey = threadStorageKeyForUser(userId);
  const threadId = storage.getItem(scopedThreadKey);
  storage.removeItem(scopedThreadKey);
  storage.removeItem("saathi_thread_id");
  if (threadId) {
    storage.removeItem(chatStorageKeyForThread(threadId));
  }
}

export function loadPersistedMessages(storage, threadId) {
  if (!threadId) return [];
  try {
    const raw = storage.getItem(chatStorageKeyForThread(threadId)) || "[]";
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}
