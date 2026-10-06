import { useCallback, useEffect, useState } from "react";

/**
 * useState mirrored into localStorage.
 *
 * ResearchOS persists saved papers / analyses / recent searches locally so the
 * Workspace is useful before the database phase lands. Reads and writes are
 * defensive: private-mode browsers and corrupted values must never crash the UI.
 */
export function useLocalStorageState(key, initialValue) {
  const [value, setValue] = useState(() => {
    if (typeof window === "undefined") return initialValue;
    try {
      const raw = window.localStorage.getItem(key);
      return raw ? JSON.parse(raw) : initialValue;
    } catch {
      return initialValue;
    }
  });

  useEffect(() => {
    try {
      window.localStorage.setItem(key, JSON.stringify(value));
    } catch {
      /* storage unavailable (private mode / quota) — keep in-memory state */
    }
  }, [key, value]);

  const update = useCallback((next) => {
    setValue((previous) => (typeof next === "function" ? next(previous) : next));
  }, []);

  return [value, update];
}
