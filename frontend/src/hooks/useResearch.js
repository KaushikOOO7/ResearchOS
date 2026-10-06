import { useCallback, useEffect, useRef, useState } from "react";

import { searchResearch } from "../services/api";

/**
 * Research search state machine.
 *
 * status: idle | loading | success | empty | error
 * Every terminal state is explicit so the UI can render all five states the
 * brief requires (idle, loading, success, empty, error + retry).
 */
export function useResearch() {
  const [state, setState] = useState({
    status: "idle",
    query: "",
    data: null,
    error: null,
  });
  const [elapsed, setElapsed] = useState(0);
  const timer = useRef(null);
  const requestId = useRef(0);

  const stopTimer = useCallback(() => {
    if (timer.current) {
      clearInterval(timer.current);
      timer.current = null;
    }
  }, []);

  useEffect(() => stopTimer, [stopTimer]);

  const search = useCallback(
    async (query, options = {}) => {
      const trimmed = (query || "").trim();
      if (trimmed.length < 3) {
        setState({
          status: "error",
          query: trimmed,
          data: null,
          error: {
            message:
              "Please describe your research idea with at least 3 characters so ResearchOS can search meaningfully.",
            code: "invalid_query",
          },
        });
        return null;
      }

      const currentRequest = ++requestId.current;
      stopTimer();
      setElapsed(0);
      setState({ status: "loading", query: trimmed, data: null, error: null });
      timer.current = setInterval(() => setElapsed((value) => value + 1), 1000);

      try {
        const data = await searchResearch(trimmed, options);
        if (currentRequest !== requestId.current) return null; // superseded
        setState({
          status: data.papers?.length ? "success" : "empty",
          query: trimmed,
          data,
          error: null,
        });
        return data;
      } catch (error) {
        if (currentRequest !== requestId.current) return null;
        setState({ status: "error", query: trimmed, data: null, error });
        return null;
      } finally {
        if (currentRequest === requestId.current) {
          stopTimer();
        }
      }
    },
    [stopTimer],
  );

  const retry = useCallback(
    (options = {}) => search(state.query, options),
    [search, state.query],
  );

  const reset = useCallback(() => {
    requestId.current += 1;
    stopTimer();
    setState({ status: "idle", query: "", data: null, error: null });
  }, [stopTimer]);

  return { ...state, elapsed, search, retry, reset };
}
