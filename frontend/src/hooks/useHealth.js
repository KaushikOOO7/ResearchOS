import { useCallback, useEffect, useState } from "react";

import { getHealth } from "../services/api";

/**
 * Backend health + capability status.
 *
 * Used to show, honestly, whether AI analysis is configured on the server
 * before the user spends time on a paper.
 */
export function useHealth() {
  const [state, setState] = useState({ status: "loading", data: null, error: null });

  // Initial fetch on mount (async, so no synchronous setState in the effect).
  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const data = await getHealth();
        if (!cancelled) setState({ status: "ready", data, error: null });
      } catch (error) {
        if (!cancelled) setState({ status: "unreachable", data: null, error });
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  /** Manual re-check (event handler use only). */
  const refresh = useCallback(async () => {
    setState((previous) => ({ ...previous, status: "loading" }));
    try {
      const data = await getHealth();
      setState({ status: "ready", data, error: null });
      return data;
    } catch (error) {
      setState({ status: "unreachable", data: null, error });
      return null;
    }
  }, []);

  return { ...state, refresh };
}
