import { authFetch } from "../components/Auth.jsx";

export { authFetch };

export const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

const REQUEST_TIMEOUT_MS = import.meta.env.DEV ? 3000 : 15000;
const BACKEND_WAKE_TIMEOUT_MS = import.meta.env.DEV ? 0 : 65000;
const BACKEND_WAKE_RETRY_MS = 2500;

const sleep = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));


export const requestWithTimeout = async (
  url,
  options = {},
  timeoutMs = REQUEST_TIMEOUT_MS,
) => {
  const runAttempt = async () => {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
    try {
      return await authFetch(url, { ...options, signal: controller.signal });
    } finally {
      window.clearTimeout(timeoutId);
    }
  };

  try {
    return await runAttempt();
  } catch (error) {
    const shouldWarmRetry =
      error?.name === "AbortError" ||
      error?.message === "Failed to fetch" ||
      error instanceof TypeError;

    if (shouldWarmRetry) {
      if (import.meta.env.DEV) {
        throw error;
      }
      await waitForBackendReady();
      return runAttempt();
    }
    throw error;
  }
};

export const waitForBackendReady = async ({
  timeoutMs = BACKEND_WAKE_TIMEOUT_MS,
  retryMs = BACKEND_WAKE_RETRY_MS,
} = {}) => {
  const deadline = Date.now() + timeoutMs;
  let lastError = null;

  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${API}/health`, {
        method: "GET",
        cache: "no-store",
      });
      if (response.ok) {
        return true;
      }
      lastError = new Error(`Health check failed with status ${response.status}`);
    } catch (error) {
      lastError = error;
    }

    await sleep(retryMs);
  }

  throw lastError || new Error("Backend is still waking up");
};

export const authPost = async (url, body) => {
  return requestWithTimeout(url, {
    method: "POST",
    body: JSON.stringify(body),
  });
};

export const authGet = async (url) => {
  return requestWithTimeout(url, { method: "GET" });
};

export const readApiJson = async (response, fallback = {}) => {
  try {
    return await response.json();
  } catch {
    return fallback;
  }
};

export const apiErrorMessage = async (response, fallback) => {
  const data = await readApiJson(response, {});
  return data.detail || data.message || fallback;
};

export const buildQuery = (params) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  });
  return query.toString();
};
