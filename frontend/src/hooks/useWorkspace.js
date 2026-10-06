import { useCallback, useMemo } from "react";

import { useLocalStorageState } from "./useLocalStorageState";

const MAX_RECENT_SEARCHES = 12;

/**
 * Local research workspace: saved papers, saved analyses and recent searches.
 *
 * Persisted in the browser for now; the backend keeps the same shape so the
 * PostgreSQL-backed workspace (Phase 6-7) can replace this hook without
 * touching the components.
 */
export function useWorkspace() {
  const [savedPapers, setSavedPapers] = useLocalStorageState("researchos.savedPapers", []);
  const [savedAnalyses, setSavedAnalyses] = useLocalStorageState("researchos.savedAnalyses", []);
  const [recentSearches, setRecentSearches] = useLocalStorageState("researchos.recentSearches", []);

  const savedPaperIds = useMemo(
    () => new Set(savedPapers.map((paper) => paper.id)),
    [savedPapers],
  );
  const savedAnalysisIds = useMemo(
    () => new Set(savedAnalyses.map((entry) => entry.paper?.id).filter(Boolean)),
    [savedAnalyses],
  );

  const toggleSavePaper = useCallback(
    (paper) => {
      setSavedPapers((previous) => {
        const exists = previous.some((item) => item.id === paper.id);
        if (exists) return previous.filter((item) => item.id !== paper.id);
        return [{ ...paper, saved_at: new Date().toISOString() }, ...previous].slice(0, 100);
      });
    },
    [setSavedPapers],
  );

  const removeSavedPaper = useCallback(
    (paperId) => setSavedPapers((previous) => previous.filter((item) => item.id !== paperId)),
    [setSavedPapers],
  );

  const saveAnalysis = useCallback(
    (paper, analysis, metadata) => {
      setSavedAnalyses((previous) => {
        const entry = {
          paper,
          analysis,
          metadata,
          saved_at: new Date().toISOString(),
        };
        const withoutCurrent = previous.filter((item) => item.paper?.id !== paper.id);
        return [entry, ...withoutCurrent].slice(0, 50);
      });
    },
    [setSavedAnalyses],
  );

  const removeSavedAnalysis = useCallback(
    (paperId) => setSavedAnalyses((previous) => previous.filter((item) => item.paper?.id !== paperId)),
    [setSavedAnalyses],
  );

  const recordSearch = useCallback(
    (query, paperCount) => {
      const entry = {
        query,
        paper_count: paperCount,
        searched_at: new Date().toISOString(),
      };
      setRecentSearches((previous) =>
        [
          entry,
          ...previous.filter((item) => item.query.toLowerCase() !== query.toLowerCase()),
        ].slice(0, MAX_RECENT_SEARCHES),
      );
    },
    [setRecentSearches],
  );

  const clearSavedPapers = useCallback(() => setSavedPapers([]), [setSavedPapers]);

  const clearSavedAnalyses = useCallback(() => setSavedAnalyses([]), [setSavedAnalyses]);

  const clearRecentSearches = useCallback(() => setRecentSearches([]), [setRecentSearches]);

  const clearWorkspace = useCallback(() => {
    setSavedPapers([]);
    setSavedAnalyses([]);
    setRecentSearches([]);
  }, [setSavedPapers, setSavedAnalyses, setRecentSearches]);

  return {
    savedPapers,
    savedAnalyses,
    recentSearches,
    savedPaperIds,
    savedAnalysisIds,
    toggleSavePaper,
    removeSavedPaper,
    saveAnalysis,
    removeSavedAnalysis,
    recordSearch,
    clearSavedPapers,
    clearSavedAnalyses,
    clearRecentSearches,
    clearWorkspace,
  };
}
