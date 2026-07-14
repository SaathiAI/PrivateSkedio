import { useCallback, useState } from "react";
import { sessionApi } from "../lib/sessionApi.js";
import { startTimer } from "../lib/perf.js";

export function useSessionActions(onRefresh) {
  const [sessionLoading, setSessionLoading] = useState(false);
  const [contentLoading, setContentLoading] = useState({});

  const refreshIfOk = useCallback(async (response) => {
    if (response?.ok && onRefresh) {
      await onRefresh();
    }
    return response;
  }, [onRefresh]);

  const completeSession = useCallback(async (sessionId, hours) => {
    setSessionLoading(true);
    try {
      const stop = startTimer('session:complete');
      const res = await sessionApi.complete(sessionId, hours);
      stop();
      return await refreshIfOk(res);
    } catch (error) {
      console.error(error);
      return null;
    } finally {
      setSessionLoading(false);
    }
  }, [refreshIfOk]);

  const undoSession = useCallback(async (sessionId) => {
    setSessionLoading(true);
    try {
      const stop = startTimer('session:undo');
      const res = await sessionApi.undo(sessionId);
      stop();
      return await refreshIfOk(res);
    } catch (error) {
      console.error(error);
      return null;
    } finally {
      setSessionLoading(false);
    }
  }, [refreshIfOk]);

  const skipSession = useCallback(async (sessionId) => {
    setSessionLoading(true);
    try {
      const stop = startTimer('session:skip');
      const res = await sessionApi.skip(sessionId);
      stop();
      return await refreshIfOk(res);
    } catch (error) {
      console.error(error);
      return null;
    } finally {
      setSessionLoading(false);
    }
  }, [refreshIfOk]);

  const updateContentStatus = useCallback(async (sessionId, contentKey, status, hours = 0) => {
    setContentLoading(prev => ({ ...prev, [contentKey]: true }));
    try {
      const stop = startTimer('session:updateContent');
      const res = await sessionApi.updateContent(sessionId, contentKey, status, hours);
      stop();
      return await refreshIfOk(res);
    } catch (error) {
      console.error(error);
      return null;
    } finally {
      setContentLoading(prev => ({ ...prev, [contentKey]: false }));
    }
  }, [refreshIfOk]);

  return {
    sessionLoading,
    contentLoading,
    completeSession,
    undoSession,
    skipSession,
    updateContentStatus,
  };
}
