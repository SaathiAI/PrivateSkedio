import assert from "node:assert/strict";
import {
  chatStorageKeyForThread,
  clearClientUserState,
  getOrCreateThreadId,
  loadPersistedMessages,
  threadStorageKeyForUser,
} from "../src/lib/clientState.js";

function createStorage(initial = {}) {
  const data = new Map(Object.entries(initial));
  return {
    getItem(key) {
      return data.has(key) ? data.get(key) : null;
    },
    setItem(key, value) {
      data.set(key, String(value));
    },
    removeItem(key) {
      data.delete(key);
    },
    snapshot() {
      return Object.fromEntries(data.entries());
    },
  };
}

assert.equal(threadStorageKeyForUser("u1"), "saathi_thread_id:u1");
assert.equal(threadStorageKeyForUser(null), "saathi_thread_id:anonymous");
assert.equal(chatStorageKeyForThread("t1"), "chat_t1");

{
  const storage = createStorage();
  let counter = 0;
  const created = getOrCreateThreadId(storage, "u1", () => `thread_${++counter}`);
  const reused = getOrCreateThreadId(storage, "u1", () => `thread_${++counter}`);
  assert.equal(created, "thread_1");
  assert.equal(reused, "thread_1");
  assert.equal(storage.getItem("saathi_thread_id:u1"), "thread_1");
}

{
  const storage = createStorage({
    "saathi_thread_id:u1": "thread_abc",
    "saathi_thread_id": "legacy_thread",
    "chat_thread_abc": JSON.stringify([{ text: "hello" }]),
    "chat_other": JSON.stringify([{ text: "keep" }]),
  });
  clearClientUserState(storage, "u1");
  const snap = storage.snapshot();
  assert.equal(snap["saathi_thread_id:u1"], undefined);
  assert.equal(snap["saathi_thread_id"], undefined);
  assert.equal(snap["chat_thread_abc"], undefined);
  assert.equal(snap["chat_other"], JSON.stringify([{ text: "keep" }]));
}

{
  const storage = createStorage({
    "chat_thread_1": JSON.stringify([{ text: "yo", isUser: true }]),
    "chat_thread_bad": "{oops",
  });
  assert.deepEqual(loadPersistedMessages(storage, "thread_1"), [{ text: "yo", isUser: true }]);
  assert.deepEqual(loadPersistedMessages(storage, "thread_bad"), []);
  assert.deepEqual(loadPersistedMessages(storage, null), []);
}

console.log("client_state: OK");
