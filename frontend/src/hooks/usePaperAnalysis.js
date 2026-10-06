import { useCallback, useEffect, useRef, useState } from "react";

import { analyzePaper } from "../services/api";

/**
 * AI analysis state machine.
 *
 * Tracks which paper is being analysed so paper cards can show a per-card
 * loading state, and exposes the structured analysis + provenance metadata
 * returned by the backend.
 */
export function usePaperAnalysis() {
  const [state, setState] = useState({
    status: "idle", // idle | loading | success | error
    paper: null,
    analysis: null,
    metadata: null,
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

  const analyze = useCallback(
    async (paper) => {
      if (!paper?.title) return null;
      if (!paper.pdf_url && !paper.abstract) {
        setState({
          status: "error",
          paper,
          analysis: null,
          metadata: null,
          error: {
            message:
              "This paper has no PDF link and no abstract, so there is nothing to analyse. Try the source page instead.",
            code: "no_content",
          },
        });
        return null;
      }

      const currentRequest = ++requestId.current;
      stopTimer();
      setElapsed(0);
      setState({
        status: "loading",
        paper,
        analysis: null,
        metadata: null,
        error: null,
      });
      timer.current = setInterval(() => setElapsed((value) => value + 1), 1000);

      try {
        const data = await analyzePaper(paper);
        if (currentRequest !== requestId.current) return null;
        setState({
          status: "success",
          paper,
          analysis: data.analysis,
          metadata: data.metadata,
          error: null,
        });
        return data;
      } catch (error) {
        if (currentRequest !== requestId.current) return null;
        setState({
          status: "error",
          paper,
          analysis: null,
          metadata: null,
          error,
        });
        return null;
      } finally {
        if (currentRequest === requestId.current) stopTimer();
      }
    },
    [stopTimer],
  );

  const retry = useCallback(() => {
    if (state.paper) return analyze(state.paper);
    return null;
  }, [analyze, state.paper]);

  /**
   * Display a stored analysis (from the workspace) without re-calling the AI.
   * Kept explicit so the UI never pretends a fresh model run happened.
   */
  const hydrate = useCallback(
    (paper, analysis, metadata) => {
      requestId.current += 1;
      stopTimer();
      setElapsed(0);
      setState({ status: "success", paper, analysis, metadata, error: null });
    },
    [stopTimer],
  );

  const clear = useCallback(() => {
    requestId.current += 1;
    stopTimer();
    setState({
      status: "idle",
      paper: null,
      analysis: null,
      metadata: null,
      error: null,
    });
  }, [stopTimer]);

  return { ...state, elapsed, analyze, retry, hydrate, clear };
}
