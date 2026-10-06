import { useCallback, useEffect, useState } from "react";

import Footer from "./components/layout/Footer";
import Header from "./components/layout/Header";
import AboutPage from "./pages/AboutPage";
import PapersPage from "./pages/PapersPage";
import ResearchPage from "./pages/ResearchPage";
import WorkspacePage from "./pages/WorkspacePage";
import { useHealth } from "./hooks/useHealth";
import { usePaperAnalysis } from "./hooks/usePaperAnalysis";
import { useResearch } from "./hooks/useResearch";
import { useWorkspace } from "./hooks/useWorkspace";

/**
 * ResearchOS application shell.
 *
 * Holds the shared state (research results, AI analysis, local workspace) and
 * switches between the four product views. No router dependency is needed for
 * four views, which keeps the bundle small.
 */
export default function App() {
  const [view, setView] = useState("research");

  const health = useHealth();
  const research = useResearch();
  const analysis = usePaperAnalysis();
  const workspace = useWorkspace();

  const { recordSearch } = workspace;

  // Record successful searches in the workspace history.
  useEffect(() => {
    if (research.status === "success" && research.data?.query) {
      recordSearch(research.data.query, research.data.stats?.returned ?? 0);
    }
  }, [research.status, research.data, recordSearch]);

  const handleSearch = useCallback(
    async (query, options) => {
      setView("research");
      analysis.clear();
      await research.search(query, options);
    },
    [analysis, research],
  );

  const handleAnalyze = useCallback(
    async (paper) => {
      setView("research");
      await analysis.analyze(paper);
      // Bring the analysis dashboard into view once the result is rendered.
      requestAnimationFrame(() => {
        document.getElementById("analysis-anchor")?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      });
    },
    [analysis],
  );

  const handleOpenSavedAnalysis = useCallback(
    (paper, savedAnalysis, metadata) => {
      // Show the stored analysis exactly as it was produced (no silent
      // re-run): the user can press "Re-run AI" in the workspace list.
      setView("research");
      analysis.hydrate(paper, savedAnalysis, metadata);
      requestAnimationFrame(() => {
        document.getElementById("analysis-anchor")?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      });
    },
    [analysis],
  );

  const handleNavigate = useCallback(
    (nextView, query) => {
      setView(nextView);
      if (query) {
        handleSearch(query, {});
      }
      window.scrollTo({ top: 0, behavior: "smooth" });
    },
    [handleSearch],
  );

  const handleReanalyze = useCallback(
    (paper) => {
      handleAnalyze(paper);
    },
    [handleAnalyze],
  );

  return (
    <div className="app">
      <a className="skip-link" href="#main">
        Skip to content
      </a>

      <Header
        view={view}
        onNavigate={handleNavigate}
        health={health}
        savedCount={workspace.savedPapers.length}
        analysisCount={workspace.savedAnalyses.length}
      />

      <main className="app-main" id="main">
        {view === "research" && (
          <ResearchPage
            research={research}
            analysis={analysis}
            workspace={workspace}
            health={health}
            onAnalyze={handleAnalyze}
            onOpenAnalysis={handleAnalyze}
          />
        )}

        {view === "papers" && (
          <PapersPage
            workspace={workspace}
            onAnalyze={handleAnalyze}
            onOpenAnalysis={handleAnalyze}
            onNavigate={handleNavigate}
          />
        )}

        {view === "workspace" && (
          <WorkspacePage
            workspace={workspace}
            onNavigate={handleNavigate}
            onOpenAnalysis={handleOpenSavedAnalysis}
            onReanalyze={handleReanalyze}
          />
        )}

        {view === "about" && <AboutPage health={health} />}

        <div id="analysis-anchor" />
      </main>

      <Footer health={health} onNavigate={handleNavigate} />
    </div>
  );
}
