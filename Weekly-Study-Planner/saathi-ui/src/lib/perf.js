/**
 * Lightweight performance timing utility.
 * Logs timing to console in dev, no-op in production.
 */

const isDev = import.meta.env.DEV;

export function startTimer(label) {
  if (!isDev) return () => 0;
  const start = performance.now();
  return () => {
    const duration = performance.now() - start;
    console.log(`[perf] ${label}: ${duration.toFixed(1)}ms`);
    return duration;
  };
}

export function measureAsync(label, fn) {
  return async (...args) => {
    const stop = startTimer(label);
    try {
      const result = await fn(...args);
      stop();
      return result;
    } catch (err) {
      stop();
      throw err;
    }
  };
}
