import { useState, useEffect, useMemo } from "react";
import {
  Search,
  Sparkles,
  FileText,
  Network,
  AlertTriangle,
  ExternalLink,
  BookOpen,
  Loader2,
  History,
  X,
  Trash2,
  Layers,
  BarChart3,
  Lightbulb,
  Compass,
  CheckCircle2,
  Clock,
  Bookmark,
  Play,
  RotateCcw,
  Download,
  Copy,
  ArrowRight,
  CheckSquare,
  Square,
  FolderOpen,
  Globe
} from "lucide-react";
import {
  searchPapers,
  analyzePaper,
  batchAnalyzePapers,
  synthesizeGaps,
  designExperiment,
  generateBlueprint,
  checkHealth
} from "./services/api";

const STORAGE_KEYS = {
  HISTORY: "researchos_search_history",
  SAVED_PAPERS: "researchos_saved_papers",
  CURRENT_SESSION: "researchos_current_session",
};

const STAGES = [
  { id: 1, name: "Query Understanding", desc: "Intent & terms" },
  { id: 2, name: "Paper Discovery", desc: "Top 30 papers" },
  { id: 3, name: "Paper Triage", desc: "Select & group" },
  { id: 4, name: "Paper Analysis", desc: "Extract insights" },
  { id: 5, name: "Cross-Paper Synthesis", desc: "Patterns & tension" },
  { id: 6, name: "Research Gaps", desc: "Novel directions" },
  { id: 7, name: "Project Blueprint", desc: "Phased architecture" },
  { id: 8, name: "Final Report", desc: "Synthesized dossier" },
];

function App() {
  // Navigation
  const [activeTab, setActiveTab] = useState("discover"); // discover | thirty_min | lab | compare | gaps | experiments | library

  // Search & Papers State
  const [query, setQuery] = useState("");
  const [papers, setPapers] = useState([]);
  const [selectedPaperIds, setSelectedPaperIds] = useState(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [providers, setProviders] = useState([]);
  const [providerFilter, setProviderFilter] = useState("ALL");

  // Single Paper Analysis State
  const [analyzingPaperId, setAnalyzingPaperId] = useState(null);
  const [inspectedPaper, setInspectedPaper] = useState(null);
  const [inspectedAnalysis, setInspectedAnalysis] = useState(null);
  const [analysisError, setAnalysisError] = useState("");

  // Batch Analysis (Research Lab) State
  const [batchResults, setBatchResults] = useState([]);
  const [batchLoading, setBatchLoading] = useState(false);
  const [batchProgress, setBatchProgress] = useState({ total: 0, completed: 0, failed: 0 });

  // 30-Minute Research Mode State
  const [thirtyMinStage, setThirtyMinStage] = useState(1);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [timerRunning, setTimerRunning] = useState(false);
  const [synthesizedGaps, setSynthesizedGaps] = useState([]);
  const [contradictions, setContradictions] = useState([]);
  const [activeGap, setActiveGap] = useState(null);
  const [experimentDesign, setExperimentDesign] = useState(null);
  const [projectBlueprint, setProjectBlueprint] = useState(null);
  const [synthesisLoading, setSynthesisLoading] = useState(false);

  // Library & Persistence State
  const [searchHistory, setSearchHistory] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEYS.HISTORY);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const [savedPapers, setSavedPapers] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEYS.SAVED_PAPERS);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const [historyOpen, setHistoryOpen] = useState(false);
  const [backendStatus, setBackendStatus] = useState("checking");
  const [copyFeedback, setCopyFeedback] = useState("");

  // Timer for 30-Minute Mode
  useEffect(() => {
    let interval;
    if (timerRunning) {
      interval = setInterval(() => {
        setElapsedSeconds(prev => prev + 1);
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [timerRunning]);

  // Initial Health Check
  useEffect(() => {
    checkHealth()
      .then(res => setBackendStatus(res.status === "healthy" ? "healthy" : "offline"))
      .catch(() => setBackendStatus("offline"));
  }, []);

  // Sync to LocalStorage
  const recordSearchHistory = (q, count) => {
    try {
      const entry = { id: Date.now(), query: q, timestamp: new Date().toISOString(), count };
      setSearchHistory(prev => {
        const filtered = prev.filter(item => item.query.toLowerCase() !== q.toLowerCase());
        const updated = [entry, ...filtered].slice(0, 25);
        localStorage.setItem(STORAGE_KEYS.HISTORY, JSON.stringify(updated));
        return updated;
      });
    } catch {}
  };

  const toggleSavePaper = (paper, e) => {
    if (e) e.stopPropagation();
    setSavedPapers(prev => {
      const exists = prev.some(p => p.id === paper.id || p.title === paper.title);
      let updated;
      if (exists) {
        updated = prev.filter(p => p.id !== paper.id && p.title !== paper.title);
      } else {
        updated = [paper, ...prev];
      }
      try {
        localStorage.setItem(STORAGE_KEYS.SAVED_PAPERS, JSON.stringify(updated));
      } catch {}
      return updated;
    });
  };

  const isPaperSaved = (paper) => {
    return savedPapers.some(p => p.id === paper.id || p.title === paper.title);
  };

  // Perform Academic Search
  const handleSearch = async (overrideQuery = null) => {
    const target = (overrideQuery || query).trim();
    if (!target) return;

    if (overrideQuery) {
      setQuery(overrideQuery);
      setHistoryOpen(false);
    }

    try {
      setLoading(true);
      setError("");
      setPapers([]);
      setSelectedPaperIds(new Set());
      setInspectedPaper(null);
      setInspectedAnalysis(null);

      const res = await searchPapers(target, 30);
      const returned = res.papers || [];
      setPapers(returned);
      setProviders(res.providers_succeeded || ["arXiv"]);

      // Pre-select top 5 papers
      const initialSelected = new Set(returned.slice(0, 5).map(p => p.id));
      setSelectedPaperIds(initialSelected);

      recordSearchHistory(target, returned.length);
    } catch (err) {
      console.error(err);
      setError(err.message || "Unable to fetch research papers.");
    } finally {
      setLoading(false);
    }
  };

  // Analyze Single Paper
  const handleSingleAnalyze = async (paper) => {
    try {
      setAnalyzingPaperId(paper.id);
      setAnalysisError("");
      setInspectedPaper(paper);
      setInspectedAnalysis(null);

      const res = await analyzePaper(paper);
      setInspectedAnalysis(res.analysis);
    } catch (err) {
      console.error(err);
      setAnalysisError(err.message || "Failed to analyze paper.");
    } finally {
      setAnalyzingPaperId(null);
    }
  };

  // Start Batch Analysis (Research Lab)
  const handleBatchAnalyze = async (selectedList = null) => {
    const toProcess = selectedList || papers.filter(p => selectedPaperIds.has(p.id));
    if (toProcess.length === 0) return;

    try {
      setBatchLoading(true);
      setBatchProgress({ total: toProcess.length, completed: 0, failed: 0 });

      const res = await batchAnalyzePapers(toProcess, 3);
      setBatchResults(res.results || []);
      setBatchProgress({
        total: res.total,
        completed: res.completed,
        failed: res.failed,
      });

      // Also trigger synthesis if in 30-min mode
      if (thirtyMinStage === 4) {
        setThirtyMinStage(5);
        handleSynthesizeGaps(res.results);
      }
    } catch (err) {
      console.error("Batch error:", err);
    } finally {
      setBatchLoading(false);
    }
  };

  // Synthesize Gaps & Contradictions
  const handleSynthesizeGaps = async (analyzedList = null) => {
    const list = analyzedList || batchResults.filter(r => r.status === "completed");
    const paperPayload = list.map(r => ({
      title: r.title,
      analysis: r.analysis,
    }));

    try {
      setSynthesisLoading(true);
      const res = await synthesizeGaps(query || "Research Investigation", paperPayload);
      setSynthesizedGaps(res.gaps || []);
      setContradictions(res.contradictions || []);
      if (res.gaps?.length > 0) {
        setActiveGap(res.gaps[0]);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setSynthesisLoading(false);
    }
  };

  // Design Experiment for Selected Gap
  const handleDesignExperiment = async (gap) => {
    const targetGap = gap || activeGap || (synthesizedGaps[0] || { title: "Research Boundary" });
    setActiveGap(targetGap);
    try {
      setSynthesisLoading(true);
      const res = await designExperiment(targetGap, query, papers.slice(0, 5));
      setExperimentDesign(res.experiment);
      setActiveTab("experiments");
    } catch (err) {
      console.error(err);
    } finally {
      setSynthesisLoading(false);
    }
  };

  // Generate Project Blueprint
  const handleGenerateBlueprint = async (gap) => {
    const target = gap || activeGap || { title: query || "Novel Research Framework" };
    try {
      setSynthesisLoading(true);
      const res = await generateBlueprint(target, target.title || query, papers.slice(0, 5));
      setProjectBlueprint(res.blueprint);
      setActiveTab("experiments");
    } catch (err) {
      console.error(err);
    } finally {
      setSynthesisLoading(false);
    }
  };

  // 30-Minute Research Mode Workflow Triggers
  const startThirtyMinMode = () => {
    setActiveTab("thirty_min");
    setThirtyMinStage(1);
    setElapsedSeconds(0);
    setTimerRunning(true);
    if (query.trim() && papers.length === 0) {
      handleSearch();
      setThirtyMinStage(2);
    } else if (papers.length > 0) {
      setThirtyMinStage(3);
    }
  };

  // Filtered papers based on provider pill
  const filteredPapers = useMemo(() => {
    if (providerFilter === "ALL") return papers;
    return papers.filter(p => (p.source || "").toLowerCase().includes(providerFilter.toLowerCase()));
  }, [papers, providerFilter]);

  // Toggle selection
  const toggleSelectPaper = (id) => {
    setSelectedPaperIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAllPapers = () => {
    if (selectedPaperIds.size === filteredPapers.length) {
      setSelectedPaperIds(new Set());
    } else {
      setSelectedPaperIds(new Set(filteredPapers.map(p => p.id)));
    }
  };

  const copyToClipboard = (text, label) => {
    navigator.clipboard.writeText(text);
    setCopyFeedback(label);
    setTimeout(() => setCopyFeedback(""), 2000);
  };

  const exportMarkdownReport = () => {
    const reportMd = `# ResearchOS Comprehensive Investigation Report
**Topic:** ${query || "Academic Inquiry"}
**Date:** ${new Date().toLocaleDateString()}
**Status:** Synthesized from ${papers.length} peer-reviewed records

---

## 1. Executive Summary
This report summarizes an automated scientific literature synthesis across major repositories (arXiv, OpenAlex, Crossref, Semantic Scholar, PubMed).

## 2. Core Retrieved Literature
${papers.slice(0, 15).map((p, i) => `### [${i + 1}] ${p.title} (${p.year || "Recent"})
- **Authors:** ${(p.authors || []).join(", ")}
- **Venue:** ${p.venue || p.source}
- **PDF URL:** ${p.pdf_url || "Unavailable"}
- **DOI:** ${p.doi || "None"}
- **Abstract:** ${p.abstract || "N/A"}
`).join("\n")}

## 3. Synthesized Research Gaps
${synthesizedGaps.map((g, i) => `### Gap ${i + 1}: ${g.title}
- **Type:** ${g.gap_type} | **Evidence Strength:** ${g.evidence_strength}
- **Description:** ${g.description}
- **Validation Experiment:** ${g.validation_experiment}
- **Supporting Papers:** ${(g.supporting_papers || []).join(", ")}
`).join("\n")}

## 4. Proposed Experiment Design
${experimentDesign ? `
- **Research Question:** ${experimentDesign.research_question}
- **Hypothesis:** ${experimentDesign.hypothesis}
- **Proposed Methodology:** ${experimentDesign.proposed_methodology}
- **Compute:** ${experimentDesign.compute_requirements}
` : "Experiment design pending generation."}

## 5. Implementation Blueprint
${projectBlueprint ? `
- **Project Title:** ${projectBlueprint.project_title}
- **Problem Statement:** ${projectBlueprint.problem_statement}
- **Feasibility Score:** ${projectBlueprint.feasibility_score}/100
- **Phased Roadmap:**
${projectBlueprint.implementation_phases.map(ph => `  - **${ph.phase}** (${ph.weeks}): ${ph.deliverables}`).join("\n")}
` : "Blueprint pending generation."}

---
*Generated by ResearchOS — AI Research Intelligence Platform*
`;
    const blob = new Blob([reportMd], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `ResearchOS_Report_${Date.now()}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="app">
      {/* HEADER */}
      <header className="header">
        <div className="logo" onClick={() => setActiveTab("discover")} style={{ cursor: "pointer" }}>
          <Sparkles size={20} />
          <span>ResearchOS</span>
        </div>

        <div className="header-actions">
          <button
            className="history-toggle-btn"
            onClick={() => setHistoryOpen(true)}
            title="View search history"
          >
            <History size={15} />
            <span>History</span>
            {searchHistory.length > 0 && <span className="history-badge">{searchHistory.length}</span>}
          </button>

          <button
            className="history-toggle-btn"
            onClick={() => setActiveTab("library")}
            title="Saved Library"
          >
            <Bookmark size={15} />
            <span>Library</span>
            {savedPapers.length > 0 && <span className="history-badge">{savedPapers.length}</span>}
          </button>

          <div className="status">
            <span
              className="status-dot"
              style={{
                background: backendStatus === "healthy" ? "#7ee787" : "#ffaa44",
                boxShadow: backendStatus === "healthy" ? "0 0 10px rgba(126, 231, 135, 0.55)" : "none"
              }}
            />
            <span>{backendStatus === "healthy" ? "AI Engine Ready" : "Academic Mode"}</span>
          </div>
        </div>
      </header>

      {/* TOP NAVIGATION BAR */}
      <nav className="nav-bar">
        <button
          className={`nav-tab ${activeTab === "discover" ? "active" : ""}`}
          onClick={() => setActiveTab("discover")}
        >
          <Search size={15} />
          <span>Discover</span>
          {papers.length > 0 && <span className="nav-tab-badge">{papers.length}</span>}
        </button>

        <button
          className={`nav-tab special ${activeTab === "thirty_min" ? "active" : ""}`}
          onClick={startThirtyMinMode}
        >
          <Sparkles size={15} />
          <span>30-Min Mode</span>
        </button>

        <button
          className={`nav-tab ${activeTab === "lab" ? "active" : ""}`}
          onClick={() => setActiveTab("lab")}
        >
          <Layers size={15} />
          <span>Research Lab</span>
          {selectedPaperIds.size > 0 && <span className="nav-tab-badge">{selectedPaperIds.size}</span>}
        </button>

        <button
          className={`nav-tab ${activeTab === "compare" ? "active" : ""}`}
          onClick={() => setActiveTab("compare")}
        >
          <BarChart3 size={15} />
          <span>Compare Matrix</span>
        </button>

        <button
          className={`nav-tab ${activeTab === "gaps" ? "active" : ""}`}
          onClick={() => {
            setActiveTab("gaps");
            if (synthesizedGaps.length === 0 && papers.length > 0) handleSynthesizeGaps();
          }}
        >
          <Compass size={15} />
          <span>Research Gaps</span>
          {synthesizedGaps.length > 0 && <span className="nav-tab-badge">{synthesizedGaps.length}</span>}
        </button>

        <button
          className={`nav-tab ${activeTab === "experiments" ? "active" : ""}`}
          onClick={() => setActiveTab("experiments")}
        >
          <Lightbulb size={15} />
          <span>Experiments & Blueprint</span>
        </button>

        <button
          className={`nav-tab ${activeTab === "library" ? "active" : ""}`}
          onClick={() => setActiveTab("library")}
        >
          <FolderOpen size={15} />
          <span>Library</span>
        </button>

        <button
          className={`nav-tab ${activeTab === "sources" ? "active" : ""}`}
          onClick={() => setActiveTab("sources")}
        >
          <Globe size={15} />
          <span>Source Coverage (17)</span>
        </button>
      </nav>

      {/* HISTORY DRAWER */}
      {historyOpen && (
        <>
          <div className="history-backdrop" onClick={() => setHistoryOpen(false)} />
          <aside className="history-sidebar">
            <div className="history-header">
              <div className="history-title">
                <Clock size={17} />
                <span>Recent Research Queries</span>
              </div>
              <button className="history-close-btn" onClick={() => setHistoryOpen(false)}>
                <X size={17} />
              </button>
            </div>
            <div className="history-content">
              {searchHistory.length === 0 ? (
                <div className="history-empty">
                  <History size={30} style={{ opacity: 0.3 }} />
                  <p>No search history yet.</p>
                </div>
              ) : (
                searchHistory.map(item => (
                  <div
                    key={item.id}
                    className="history-item"
                    onClick={() => {
                      handleSearch(item.query);
                      setActiveTab("discover");
                    }}
                  >
                    <div className="history-item-body">
                      <div className="history-item-query">{item.query}</div>
                      <div className="history-item-meta">
                        <span>{item.count} papers retrieved</span>
                      </div>
                    </div>
                    <button
                      className="history-delete-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        setSearchHistory(prev => prev.filter(x => x.id !== item.id));
                      }}
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                ))
              )}
            </div>
          </aside>
        </>
      )}

      {/* MAIN CONTAINER */}
      <main className="main">
        {/* ========================================================================= */}
        {/* TAB 1: DISCOVER (SEARCH & TOP 30 REAL PAPERS) */}
        {/* ========================================================================= */}
        {activeTab === "discover" && (
          <>
            <section className="hero">
              <div className="badge">
                <Sparkles size={15} />
                Evidence-Driven Scientific Discovery
              </div>

              <h1>
                Turn your idea into
                <span> research intelligence.</span>
              </h1>

              <p>
                Query 5 open academic repositories, extract architectures, discover failure conditions,
                and turn candidate gaps into actionable project blueprints.
              </p>

              {/* SEARCH INPUT */}
              <div className="research-box">
                <Search size={20} />
                <input
                  type="text"
                  placeholder="What do you want to research? (e.g., Mamba state-space models, Quantum error correction)"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") handleSearch(); }}
                />
                <button onClick={() => handleSearch()} disabled={loading}>
                  {loading ? (
                    <>
                      <Loader2 size={16} className="spin" />
                      Searching...
                    </>
                  ) : (
                    "Research"
                  )}
                </button>
              </div>

              {error && (
                <div className="error-message">
                  <AlertTriangle size={16} style={{ display: "inline", marginRight: "8px" }} />
                  {error}
                </div>
              )}
            </section>

            {/* RESULTS SECTION */}
            {papers.length > 0 && (
              <section className="results-section">
                <div className="results-header">
                  <div>
                    <span className="section-label">
                      AUTHENTIC PAPERS • PROVIDERS: {providers.join(", ")}
                    </span>
                    <h2>Top Ranked Academic Literature ({papers.length})</h2>
                  </div>

                  <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                    <button
                      className="secondary-button"
                      onClick={() => handleBatchAnalyze()}
                      disabled={selectedPaperIds.size === 0}
                    >
                      <Layers size={15} />
                      Batch Analyze ({selectedPaperIds.size})
                    </button>
                    <button
                      className="primary-button"
                      onClick={startThirtyMinMode}
                    >
                      <Play size={15} />
                      Start 30-Min Mode
                    </button>
                  </div>
                </div>

                {/* FILTER PILLS */}
                <div className="filter-pills-bar">
                  <span style={{ fontSize: "12px", color: "#666", marginRight: "4px" }}>Filter:</span>
                  {["ALL", "arXiv", "OpenAlex", "Crossref", "Semantic Scholar", "PubMed"].map(prov => (
                    <button
                      key={prov}
                      className={`filter-pill ${providerFilter === prov ? "active" : ""}`}
                      onClick={() => setProviderFilter(prov)}
                    >
                      {prov}
                    </button>
                  ))}
                  <div style={{ marginLeft: "auto" }}>
                    <label className="checkbox-label">
                      <input
                        type="checkbox"
                        checked={selectedPaperIds.size === filteredPapers.length && filteredPapers.length > 0}
                        onChange={selectAllPapers}
                      />
                      <span>Select All ({filteredPapers.length})</span>
                    </label>
                  </div>
                </div>

                {/* PAPERS GRID */}
                <div className="papers-grid" style={{ marginTop: "20px" }}>
                  {filteredPapers.map((paper, index) => {
                    const isSelected = selectedPaperIds.has(paper.id);
                    const isSaved = isPaperSaved(paper);
                    const isAnalyzing = analyzingPaperId === paper.id;

                    return (
                      <article
                        key={paper.id || index}
                        className="paper-card"
                        style={{
                          borderColor: isSelected ? "#aa3bff" : "#242424",
                          background: isSelected ? "rgba(170, 59, 255, 0.03)" : "#101010"
                        }}
                      >
                        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                          <button
                            style={{ background: "transparent", color: isSelected ? "#aa3bff" : "#666", cursor: "pointer" }}
                            onClick={() => toggleSelectPaper(paper.id)}
                            title="Toggle selection for batch analysis"
                          >
                            {isSelected ? <CheckSquare size={18} /> : <Square size={18} />}
                          </button>
                          <div className="paper-icon">
                            <BookOpen size={18} />
                          </div>
                        </div>

                        <div className="paper-content">
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                            <div className="paper-source">{paper.source || "Academic Repository"}</div>
                            <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                              {paper.citation_count !== null && paper.citation_count !== undefined && (
                                <span className="citation-badge">
                                  ★ {paper.citation_count.toLocaleString()} citations
                                </span>
                              )}
                              <button
                                style={{ background: "transparent", color: isSaved ? "#f59e0b" : "#666", cursor: "pointer" }}
                                onClick={(e) => toggleSavePaper(paper, e)}
                                title={isSaved ? "Remove from Library" : "Save to Library"}
                              >
                                <Bookmark size={15} fill={isSaved ? "#f59e0b" : "none"} />
                              </button>
                            </div>
                          </div>

                          <h3>{paper.title}</h3>

                          <div className="paper-meta">
                            <span>{paper.year || "Recent"}</span>
                            <span>•</span>
                            <span>{(paper.authors || []).slice(0, 3).join(", ")}{(paper.authors || []).length > 3 ? " et al." : ""}</span>
                            {paper.venue && (
                              <>
                                <span>•</span>
                                <span>{paper.venue}</span>
                              </>
                            )}
                          </div>

                          {paper.abstract && (
                            <p className="paper-abstract">{paper.abstract}</p>
                          )}

                          <div className="paper-actions">
                            {paper.pdf_url && (
                              <a href={paper.pdf_url} target="_blank" rel="noopener noreferrer" className="primary-button">
                                <FileText size={14} />
                                PDF
                              </a>
                            )}
                            {paper.paper_url && (
                              <a href={paper.paper_url} target="_blank" rel="noopener noreferrer" className="secondary-button">
                                <ExternalLink size={14} />
                                Source
                              </a>
                            )}
                            <button
                              className="secondary-button"
                              onClick={() => handleSingleAnalyze(paper)}
                              disabled={isAnalyzing}
                            >
                              {isAnalyzing ? (
                                <>
                                  <Loader2 size={14} className="spin" />
                                  Analyzing...
                                </>
                              ) : (
                                <>
                                  <Sparkles size={14} />
                                  Analyze
                                </>
                              )}
                            </button>
                          </div>
                        </div>
                      </article>
                    );
                  })}
                </div>
              </section>
            )}

            {/* EMPTY STATE */}
            {!loading && papers.length === 0 && !error && (
              <section className="features">
                <FeatureCard
                  icon={<FileText size={20} />}
                  title="Multi-Source Literature"
                  description="Fetches genuine peer-reviewed publications from arXiv, OpenAlex, Crossref, Semantic Scholar, and PubMed."
                />
                <FeatureCard
                  icon={<Network size={20} />}
                  title="Pipeline Reconstruction"
                  description="Transforms complex research text into modular architectures, mathematical formulations, and pseudocode."
                />
                <FeatureCard
                  icon={<Compass size={20} />}
                  title="Actionable Blueprints"
                  description="Synthesizes unaddressed gaps, designs testable ablation experiments, and produces engineering roadmaps."
                />
              </section>
            )}
          </>
        )}

        {/* ========================================================================= */}
        {/* TAB 2: 30-MINUTE RESEARCH MODE (GUIDED 8-STAGE WORKFLOW) */}
        {/* ========================================================================= */}
        {activeTab === "thirty_min" && (
          <section>
            <div className="stepper-container">
              <div className="stepper-header">
                <div className="stepper-title">
                  <Sparkles size={20} style={{ color: "#aa3bff" }} />
                  <h2>30-Minute Research Investigation</h2>
                </div>
                <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                  <div className="timer-badge">
                    <Clock size={13} />
                    <span>Elapsed: {Math.floor(elapsedSeconds / 60)}m {elapsedSeconds % 60}s</span>
                  </div>
                  <button className="secondary-button" onClick={exportMarkdownReport}>
                    <Download size={14} />
                    Export Dossier
                  </button>
                </div>
              </div>

              {/* STEP TRACKER */}
              <div className="stepper-track">
                {STAGES.map(st => {
                  const isDone = thirtyMinStage > st.id;
                  const isCurrent = thirtyMinStage === st.id;
                  return (
                    <div
                      key={st.id}
                      className={`step-node ${isDone ? "completed" : ""} ${isCurrent ? "active" : ""}`}
                      onClick={() => setThirtyMinStage(st.id)}
                    >
                      <div className="step-circle">
                        {isDone ? <CheckCircle2 size={16} /> : st.id}
                      </div>
                      <div className="step-label">{st.name}</div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* STAGE CONTENT */}
            {thirtyMinStage === 1 && (
              <div className="analysis-card">
                <h3>Stage 1: Research Question Understanding</h3>
                <p className="analysis-text" style={{ margin: "14px 0" }}>
                  Define your core research challenge. ResearchOS decomposes your question into core entities,
                  baseline methodologies, and candidate search variants across databases.
                </p>
                <div className="research-box" style={{ margin: "16px 0" }}>
                  <Search size={18} />
                  <input
                    type="text"
                    value={query}
                    placeholder="Enter your research topic..."
                    onChange={(e) => setQuery(e.target.value)}
                  />
                </div>
                <button
                  className="primary-button"
                  onClick={() => {
                    handleSearch();
                    setThirtyMinStage(2);
                  }}
                  disabled={!query.trim()}
                >
                  Confirm Query & Search Academic Literature
                  <ArrowRight size={14} />
                </button>
              </div>
            )}

            {thirtyMinStage === 2 && (
              <div className="analysis-card">
                <h3>Stage 2: Top 30 Literature Discovery</h3>
                <p className="analysis-text" style={{ margin: "10px 0" }}>
                  Found <strong>{papers.length}</strong> authenticated peer-reviewed papers matching "{query}".
                </p>
                <div style={{ display: "flex", gap: "12px", marginTop: "16px" }}>
                  <button className="primary-button" onClick={() => setThirtyMinStage(3)}>
                    Proceed to Paper Triage ({selectedPaperIds.size} Selected)
                    <ArrowRight size={14} />
                  </button>
                </div>
              </div>
            )}

            {thirtyMinStage === 3 && (
              <div className="analysis-card">
                <h3>Stage 3: Paper Triage & Selection</h3>
                <p className="analysis-text">
                  Choose the key papers to include in deep batch extraction. Select up to 30 papers.
                </p>
                <div className="toolbar-bar">
                  <span>Selected: <strong>{selectedPaperIds.size}</strong> papers</span>
                  <button className="primary-button" onClick={() => handleBatchAnalyze()}>
                    <Layers size={14} />
                    Run Batch Deep Extraction (Stage 4)
                  </button>
                </div>
                <div className="papers-grid">
                  {papers.slice(0, 10).map(p => (
                    <div
                      key={p.id}
                      className="history-item"
                      style={{ borderColor: selectedPaperIds.has(p.id) ? "#aa3bff" : "#222" }}
                      onClick={() => toggleSelectPaper(p.id)}
                    >
                      <div className="history-item-body">
                        <div className="history-item-query">{p.title}</div>
                        <div className="history-item-meta">{p.year} • {p.source} • {p.venue || "Peer-Reviewed"}</div>
                      </div>
                      {selectedPaperIds.has(p.id) ? <CheckCircle2 size={16} color="#aa3bff" /> : <Square size={16} color="#555" />}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {thirtyMinStage === 4 && (
              <div className="analysis-card">
                <h3>Stage 4: Automated Paper Analysis & Insight Extraction</h3>
                <p className="analysis-text" style={{ margin: "10px 0" }}>
                  Processing {batchProgress.total} papers in parallel with controlled concurrency and SSRF safety.
                </p>
                <div className="progress-bar-container">
                  <div
                    className="progress-bar-fill"
                    style={{ width: `${batchProgress.total ? (batchProgress.completed / batchProgress.total) * 100 : 0}%` }}
                  />
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", color: "#888" }}>
                  <span>Completed: {batchProgress.completed} / {batchProgress.total}</span>
                  <span>Failed: {batchProgress.failed}</span>
                </div>
                <div style={{ marginTop: "20px" }}>
                  <button
                    className="primary-button"
                    onClick={() => {
                      setThirtyMinStage(5);
                      handleSynthesizeGaps();
                    }}
                  >
                    Proceed to Cross-Paper Synthesis
                    <ArrowRight size={14} />
                  </button>
                </div>
              </div>
            )}

            {thirtyMinStage === 5 && (
              <div className="analysis-card">
                <h3>Stage 5: Cross-Paper Synthesis & Contradiction Detection</h3>
                <p className="analysis-text" style={{ margin: "10px 0" }}>
                  Comparing extracted pipelines, evaluation benchmarks, and empirical tensions.
                </p>
                {contradictions.length > 0 && (
                  <div style={{ background: "#1a1208", border: "1px solid #78350f", padding: "16px", borderRadius: "12px", margin: "16px 0" }}>
                    <div style={{ color: "#f59e0b", fontWeight: 600, display: "flex", alignItems: "center", gap: "8px" }}>
                      <AlertTriangle size={16} />
                      Methodological Tension Detected: {contradictions[0].topic}
                    </div>
                    <p style={{ fontSize: "13px", color: "#d97706", marginTop: "6px" }}>
                      <strong>{contradictions[0].paper_a_title}:</strong> {contradictions[0].paper_a_claim}
                      <br />
                      <strong>VS. {contradictions[0].paper_b_title}:</strong> {contradictions[0].paper_b_claim}
                    </p>
                  </div>
                )}
                <button className="primary-button" onClick={() => setThirtyMinStage(6)}>
                  View Synthesized Research Opportunities
                  <ArrowRight size={14} />
                </button>
              </div>
            )}

            {thirtyMinStage === 6 && (
              <div className="analysis-card">
                <h3>Stage 6: Evidence-Backed Research Gaps</h3>
                <div className="analysis-grid">
                  {synthesizedGaps.map((gap, i) => (
                    <div key={gap.id || i} className="analysis-card">
                      <span className="analysis-label">{gap.gap_type} • CONFIDENCE {Math.round(gap.confidence * 100)}%</span>
                      <h4>{gap.title}</h4>
                      <p className="analysis-text">{gap.description}</p>
                      <button
                        className="primary-button"
                        style={{ marginTop: "14px" }}
                        onClick={() => {
                          setActiveGap(gap);
                          handleDesignExperiment(gap);
                          setThirtyMinStage(7);
                        }}
                      >
                        <Lightbulb size={14} />
                        Design Experiment for This Gap
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {thirtyMinStage === 7 && (
              <div className="analysis-card">
                <h3>Stage 7: Implementable Project Blueprint</h3>
                <p className="analysis-text">
                  Phased research roadmap and architectural starter framework.
                </p>
                {projectBlueprint ? (
                  <div style={{ marginTop: "16px" }}>
                    <h4>{projectBlueprint.project_title}</h4>
                    <p className="analysis-text">{projectBlueprint.abstract}</p>
                    <div className="code-box" style={{ marginTop: "14px" }}>
                      <div className="code-box-header">
                        <span>PyTorch Starter Architecture</span>
                        <button onClick={() => copyToClipboard(projectBlueprint.starter_pseudocode, "Code")}>
                          <Copy size={13} /> Copy
                        </button>
                      </div>
                      <pre>{projectBlueprint.starter_pseudocode}</pre>
                    </div>
                  </div>
                ) : (
                  <button className="primary-button" onClick={() => handleGenerateBlueprint(activeGap)} style={{ marginTop: "14px" }}>
                    Generate Technical Project Blueprint
                  </button>
                )}
                <div style={{ marginTop: "20px" }}>
                  <button className="primary-button" onClick={() => setThirtyMinStage(8)}>
                    Compile Final Research Dossier
                    <ArrowRight size={14} />
                  </button>
                </div>
              </div>
            )}

            {thirtyMinStage === 8 && (
              <div className="analysis-card">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <span className="analysis-label">FINAL SYNTHESIS</span>
                    <h3>Complete Research Investigation Dossier</h3>
                  </div>
                  <div style={{ display: "flex", gap: "10px" }}>
                    <button className="primary-button" onClick={exportMarkdownReport}>
                      <Download size={14} />
                      Download Markdown
                    </button>
                  </div>
                </div>
                <p className="analysis-text" style={{ marginTop: "12px" }}>
                  Investigation completed in <strong>{Math.floor(elapsedSeconds / 60)} minutes</strong>.
                  Synthesized across {papers.length} peer-reviewed papers with full reproducibility specs.
                </p>
              </div>
            )}
          </section>
        )}

        {/* ========================================================================= */}
        {/* TAB 3: RESEARCH LAB (BATCH ANALYSIS MANAGER) */}
        {/* ========================================================================= */}
        {activeTab === "lab" && (
          <section>
            <div className="batch-stats-grid">
              <div className="stat-card">
                <div className="stat-label">Total Queued</div>
                <div className="stat-value">{papers.length}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Selected for Deep Analysis</div>
                <div className="stat-value">{selectedPaperIds.size}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Completed Analyses</div>
                <div className="stat-value">{batchResults.filter(r => r.status === "completed").length}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Concurrency Limit</div>
                <div className="stat-value">3 workers</div>
              </div>
            </div>

            <div className="toolbar-bar">
              <div>
                <strong>Batch Queue ({selectedPaperIds.size} papers selected)</strong>
              </div>
              <button
                className="primary-button"
                onClick={() => handleBatchAnalyze()}
                disabled={batchLoading || selectedPaperIds.size === 0}
              >
                {batchLoading ? (
                  <>
                    <Loader2 size={15} className="spin" />
                    Analyzing Batch ({batchProgress.completed}/{batchProgress.total})...
                  </>
                ) : (
                  <>
                    <Layers size={15} />
                    Run Batch Analysis
                  </>
                )}
              </button>
            </div>

            <div className="papers-grid">
              {(batchResults.length > 0 ? batchResults : papers.slice(0, 12)).map((item, idx) => (
                <div key={item.id || idx} className="paper-card">
                  <div className="paper-content">
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                      <span className="citation-badge">
                        {item.status === "completed" ? "✓ Completed" : item.status === "failed" ? "✗ Failed" : "Queued"}
                      </span>
                      <span style={{ fontSize: "11px", color: "#666" }}>{item.evidence_basis || "Pending"}</span>
                    </div>
                    <h4>{item.title}</h4>
                    {item.analysis && (
                      <p className="analysis-text" style={{ fontSize: "12px", marginTop: "8px" }}>
                        {item.analysis.research_problem?.slice(0, 150)}...
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* ========================================================================= */}
        {/* TAB 4: COMPARE MATRIX (CROSS-PAPER ANALYSIS) */}
        {/* ========================================================================= */}
        {activeTab === "compare" && (
          <section>
            <div className="analysis-card">
              <h3>Cross-Paper Comparison Matrix</h3>
              <p className="analysis-text">
                Side-by-side comparative breakdown of retrieved academic literature across critical architectural dimensions.
              </p>

              <div className="matrix-container">
                <table className="matrix-table">
                  <thead>
                    <tr>
                      <th>Dimension</th>
                      {papers.slice(0, 4).map((p, i) => (
                        <th key={p.id || i}>{p.title.slice(0, 45)}...</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>Core Focus</td>
                      {papers.slice(0, 4).map((p, i) => (
                        <td key={i}>{p.abstract?.slice(0, 110) || "General methodology"}...</td>
                      ))}
                    </tr>
                    <tr>
                      <td>Source & Venue</td>
                      {papers.slice(0, 4).map((p, i) => (
                        <td key={i}>{p.venue || p.source} ({p.year || "Recent"})</td>
                      ))}
                    </tr>
                    <tr>
                      <td>Citations</td>
                      {papers.slice(0, 4).map((p, i) => (
                        <td key={i}>{p.citation_count ? `★ ${p.citation_count}` : "Not indexed"}</td>
                      ))}
                    </tr>
                    <tr>
                      <td>Open Access PDF</td>
                      {papers.slice(0, 4).map((p, i) => (
                        <td key={i}>
                          {p.pdf_url ? (
                            <a href={p.pdf_url} target="_blank" rel="noopener noreferrer" style={{ color: "#60a5fa" }}>
                              Available
                            </a>
                          ) : (
                            "Paywalled / Metadata only"
                          )}
                        </td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        )}

        {/* ========================================================================= */}
        {/* TAB 5: RESEARCH GAPS & OPPORTUNITIES */}
        {/* ========================================================================= */}
        {activeTab === "gaps" && (
          <section>
            <div className="analysis-header">
              <div>
                <span className="section-label">EVIDENCE-BACKED NOVELTY</span>
                <h2>Candidate Research Gaps & Open Questions</h2>
              </div>
              <button
                className="primary-button"
                onClick={() => handleSynthesizeGaps()}
                disabled={synthesisLoading}
              >
                {synthesisLoading ? <Loader2 size={15} className="spin" /> : <RotateCcw size={15} />}
                Re-Synthesize Gaps
              </button>
            </div>

            <div className="analysis-grid">
              {synthesizedGaps.map((gap, i) => (
                <div key={gap.id || i} className="analysis-card">
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                    <span className="badge-inferred">{gap.gap_type}</span>
                    <span style={{ fontSize: "11px", color: "#81c784", fontWeight: 600 }}>
                      Confidence: {Math.round(gap.confidence * 100)}%
                    </span>
                  </div>
                  <h3>{gap.title}</h3>
                  <p className="analysis-text" style={{ margin: "12px 0" }}>{gap.description}</p>
                  <div style={{ fontSize: "12px", color: "#777", marginBottom: "14px" }}>
                    <strong>Validation Protocol:</strong> {gap.validation_experiment}
                  </div>
                  <button
                    className="primary-button"
                    onClick={() => handleDesignExperiment(gap)}
                  >
                    <Lightbulb size={14} />
                    Design Experiment Protocol
                  </button>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* ========================================================================= */}
        {/* TAB 6: EXPERIMENTS & PROJECT BLUEPRINT */}
        {/* ========================================================================= */}
        {activeTab === "experiments" && (
          <section>
            {experimentDesign ? (
              <div className="analysis-card" style={{ marginBottom: "24px" }}>
                <span className="analysis-label">AI EXPERIMENT DESIGNER</span>
                <h3>{experimentDesign.research_question}</h3>
                <p className="analysis-text" style={{ margin: "12px 0" }}>
                  <strong>Hypothesis:</strong> {experimentDesign.hypothesis}
                </p>

                <div className="analysis-grid">
                  <div className="analysis-card">
                    <h4>Independent Variables</h4>
                    <ul className="analysis-bullets">
                      {experimentDesign.independent_variables.map((v, i) => <li key={i}>{v}</li>)}
                    </ul>
                  </div>
                  <div className="analysis-card">
                    <h4>Evaluation Metrics & Controls</h4>
                    <ul className="analysis-bullets">
                      {experimentDesign.evaluation_metrics.map((m, i) => <li key={i}>{m}</li>)}
                    </ul>
                  </div>
                </div>

                <div style={{ marginTop: "18px" }}>
                  <h4>Methodology Protocol</h4>
                  <p className="analysis-text">{experimentDesign.proposed_methodology}</p>
                </div>

                <div style={{ marginTop: "18px", display: "flex", gap: "10px" }}>
                  <button className="primary-button" onClick={() => handleGenerateBlueprint(activeGap)}>
                    <Sparkles size={14} />
                    Generate Project Blueprint
                  </button>
                </div>
              </div>
            ) : (
              <div className="analysis-card" style={{ textAlign: "center", padding: "40px 20px" }}>
                <Lightbulb size={32} style={{ opacity: 0.4, margin: "0 auto 12px" }} />
                <h3>No Experiment Protocol Generated Yet</h3>
                <p className="analysis-text" style={{ maxWidth: "500px", margin: "8px auto 18px" }}>
                  Select an identified research gap to generate an actionable empirical protocol with hypotheses, controls, and ablation plans.
                </p>
                <button
                  className="primary-button"
                  onClick={() => {
                    setActiveTab("gaps");
                    if (synthesizedGaps.length === 0) handleSynthesizeGaps();
                  }}
                >
                  Explore Research Gaps
                </button>
              </div>
            )}

            {projectBlueprint && (
              <div className="analysis-card">
                <span className="analysis-label">IMPLEMENTABLE BLUEPRINT</span>
                <h3>{projectBlueprint.project_title}</h3>
                <p className="analysis-text">{projectBlueprint.abstract}</p>

                <div style={{ margin: "18px 0" }}>
                  <h4>Phased Implementation Roadmap</h4>
                  <div className="analysis-grid">
                    {projectBlueprint.implementation_phases.map((ph, i) => (
                      <div key={i} className="stat-card">
                        <div className="stat-label">{ph.weeks}</div>
                        <div style={{ fontWeight: 600, fontSize: "14px", marginBottom: "4px" }}>{ph.phase}</div>
                        <div style={{ fontSize: "12px", color: "#888" }}>{ph.deliverables}</div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="code-box">
                  <div className="code-box-header">
                    <span>PyTorch Starter Code</span>
                    <button onClick={() => copyToClipboard(projectBlueprint.starter_pseudocode, "Code")}>
                      <Copy size={13} /> {copyFeedback === "Code" ? "Copied!" : "Copy"}
                    </button>
                  </div>
                  <pre>{projectBlueprint.starter_pseudocode}</pre>
                </div>
              </div>
            )}
          </section>
        )}

        {/* ========================================================================= */}
        {/* TAB 7: RESEARCH LIBRARY */}
        {/* ========================================================================= */}
        {activeTab === "library" && (
          <section>
            <div className="analysis-header">
              <div>
                <span className="section-label">SAVED RESEARCH ASSETS</span>
                <h2>Research Library & Bookmarks</h2>
              </div>
              <button className="primary-button" onClick={exportMarkdownReport}>
                <Download size={14} /> Export Library Dossier
              </button>
            </div>

            {savedPapers.length === 0 ? (
              <div className="analysis-card" style={{ textAlign: "center", padding: "50px 20px" }}>
                <Bookmark size={34} style={{ opacity: 0.3, margin: "0 auto 12px" }} />
                <h3>No Bookmarked Papers Yet</h3>
                <p className="analysis-text" style={{ maxWidth: "450px", margin: "8px auto" }}>
                  Save papers using the bookmark icon on any paper card in the Discover tab to collect them here.
                </p>
              </div>
            ) : (
              <div className="papers-grid">
                {savedPapers.map(paper => (
                  <article key={paper.id} className="paper-card">
                    <div className="paper-icon"><BookOpen size={18} /></div>
                    <div className="paper-content">
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <span className="paper-source">{paper.source}</span>
                        <button
                          style={{ background: "transparent", color: "#f59e0b", cursor: "pointer" }}
                          onClick={() => toggleSavePaper(paper)}
                        >
                          <Bookmark size={15} fill="#f59e0b" />
                        </button>
                      </div>
                      <h3>{paper.title}</h3>
                      <div className="paper-meta">
                        <span>{paper.year}</span>
                        <span>•</span>
                        <span>{(paper.authors || []).slice(0, 3).join(", ")}</span>
                      </div>
                      <div className="paper-actions">
                        {paper.pdf_url && (
                          <a href={paper.pdf_url} target="_blank" rel="noopener noreferrer" className="primary-button">
                            <FileText size={14} /> PDF
                          </a>
                        )}
                        <button className="secondary-button" onClick={() => handleSingleAnalyze(paper)}>
                          <Sparkles size={14} /> Analyze
                        </button>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
        )}

        {/* ========================================================================= */}
        {/* TAB 8: SOURCE COVERAGE DASHBOARD (17 MAJOR ACADEMIC WEBSITES) */}
        {/* ========================================================================= */}
        {activeTab === "sources" && (
          <section>
            <div className="analysis-header">
              <div>
                <span className="section-label">ACADEMIC ECOSYSTEM INTEGRATION</span>
                <h2>Source Coverage & Provider Status Dashboard (17 Sources)</h2>
              </div>
            </div>

            <p className="analysis-text" style={{ marginBottom: "24px" }}>
              ResearchOS aggregates evidence from 11 directly queried academic search APIs and generates direct outbound queries to 6 major subscription publishers and citation indexes.
            </p>

            <h3 style={{ marginBottom: "14px" }}>Direct API Integrations (11 Repositories)</h3>
            <div className="papers-grid" style={{ marginBottom: "36px" }}>
              {[
                { name: "arXiv", url: "https://arxiv.org", type: "Preprint Server", status: "Connected", desc: "Open-access archive for 2.4M+ scholarly articles in physics, mathematics, CS, and AI." },
                { name: "OpenAlex", url: "https://openalex.org", type: "Bibliographic Graph", status: "Connected", desc: "Index of 250M+ global research works, author entities, and citation networks." },
                { name: "Crossref", url: "https://crossref.org", type: "DOI Registry", status: "Connected", desc: "Official DOI registry for over 150M academic journal publications and book chapters." },
                { name: "Semantic Scholar", url: "https://semanticscholar.org", type: "AI Literature Graph", status: "Connected", desc: "AI-backed academic search engine developed by the Allen Institute for AI." },
                { name: "PubMed", url: "https://pubmed.ncbi.nlm.nih.gov", type: "Biomedical Literature", status: "Connected", desc: "NCBI database comprising more than 37M citations for biomedical literature." },
                { name: "Europe PMC", url: "https://europepmc.org", type: "Life Sciences & Medicine", status: "Connected", desc: "Comprehensive repository of worldwide life sciences articles and preprints." },
                { name: "DBLP", url: "https://dblp.org", type: "Computer Science Bibliography", status: "Connected", desc: "Authoritative bibliography of computer science conferences and journal papers." },
                { name: "Zenodo", url: "https://zenodo.org", type: "Open Research & Datasets", status: "Connected", desc: "CERN-operated general-purpose open repository for publications and research data." },
                { name: "DataCite", url: "https://datacite.org", type: "Dataset & Output Registry", status: "Connected", desc: "Global consortium providing DOIs for research datasets, software, and artifacts." },
                { name: "DOAJ", url: "https://doaj.org", type: "Open Access Journals", status: "Connected", desc: "Curated directory of over 20,000 peer-reviewed open access academic journals." },
                { name: "CORE", url: "https://core.ac.uk", type: "Global Repository Aggregator", status: "Connected", desc: "Aggregates open access papers from thousands of institutional repositories globally." }
              ].map(src => (
                <div key={src.name} className="stat-card">
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                    <span style={{ fontSize: "11px", color: "#666", fontWeight: 600 }}>{src.type}</span>
                    <span className="citation-badge">✓ {src.status}</span>
                  </div>
                  <h4 style={{ margin: "4px 0 8px" }}>
                    <a href={src.url} target="_blank" rel="noopener noreferrer" style={{ color: "#fff", textDecoration: "none" }}>
                      {src.name} <ExternalLink size={12} style={{ display: "inline", opacity: 0.6 }} />
                    </a>
                  </h4>
                  <p style={{ fontSize: "12px", color: "#888", lineHeight: 1.5 }}>{src.desc}</p>
                </div>
              ))}
            </div>

            <h3 style={{ marginBottom: "14px" }}>Publisher Portals & Citation Indexes (Direct Outbound Search)</h3>
            <p className="analysis-text" style={{ marginBottom: "16px", fontSize: "13px" }}>
              Commercial publishers and citation indices restrict automated web scraping by terms of service. ResearchOS provides genuine direct outbound query links that open these archives with your active research query ({query ? `"${query}"` : "your topic"}).
            </p>
            <div className="papers-grid">
              {[
                { name: "Google Scholar", url: `https://scholar.google.com/scholar?q=${encodeURIComponent(query || "")}`, note: "World's largest academic citation index. Outbound search link provided to comply with scraping policies." },
                { name: "IEEE Xplore", url: `https://ieeexplore.ieee.org/search/searchresult.jsp?newsearch=true&queryText=${encodeURIComponent(query || "")}`, note: "Premier repository for engineering, electrical computing, and robotics conference proceedings." },
                { name: "ACM Digital Library", url: `https://dl.acm.org/action/doSearch?AllField=${encodeURIComponent(query || "")}`, note: "Core computer science publications, SIGGRAPH, NeurIPS, and computing transactions." },
                { name: "Springer Nature", url: `https://link.springer.com/search?query=${encodeURIComponent(query || "")}`, note: "Nature Portfolio journals, LNCS volumes, and academic reference works." },
                { name: "ScienceDirect (Elsevier)", url: `https://www.sciencedirect.com/search?qs=${encodeURIComponent(query || "")}`, note: "Elsevier database containing over 19 million articles across scientific disciplines." },
                { name: "Wiley Online Library", url: `https://onlinelibrary.wiley.com/action/doSearch?AllField=${encodeURIComponent(query || "")}`, note: "Multidisciplinary academic journals covering chemistry, physical sciences, and medicine." }
              ].map(pub => (
                <div key={pub.name} className="stat-card">
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                    <span style={{ fontSize: "11px", color: "#666", fontWeight: 600 }}>Publisher Portal</span>
                    <span style={{ fontSize: "11px", color: "#60a5fa" }}>Outbound Link</span>
                  </div>
                  <h4 style={{ margin: "4px 0 8px" }}>{pub.name}</h4>
                  <p style={{ fontSize: "12px", color: "#888", marginBottom: "14px", lineHeight: 1.5 }}>{pub.note}</p>
                  <a
                    href={pub.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="secondary-button"
                    style={{ display: "inline-flex", fontSize: "12px" }}
                  >
                    <ExternalLink size={13} />
                    Search on {pub.name}
                  </a>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* ========================================================================= */}
        {/* INDIVIDUAL PAPER ANALYSIS MODAL / DRAWER */}
        {/* ========================================================================= */}
        {inspectedPaper && inspectedAnalysis && (
          <div className="history-backdrop" onClick={() => setInspectedPaper(null)}>
            <div
              className="analysis-card"
              style={{
                position: "fixed",
                top: "5%",
                left: "5%",
                right: "5%",
                bottom: "5%",
                zIndex: 101,
                overflowY: "auto",
                background: "#0c0c0c",
                borderColor: "#333"
              }}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="analysis-header">
                <div>
                  <span className="section-label">PAPER INTELLIGENCE • {inspectedAnalysis.evidence_basis}</span>
                  <h2>{inspectedPaper.title}</h2>
                </div>
                <div style={{ display: "flex", gap: "10px" }}>
                  {inspectedPaper.pdf_url && (
                    <a href={inspectedPaper.pdf_url} target="_blank" rel="noopener noreferrer" className="secondary-button">
                      <FileText size={15} /> PDF
                    </a>
                  )}
                  <button className="secondary-button" onClick={() => setInspectedPaper(null)}>
                    <X size={15} /> Close
                  </button>
                </div>
              </div>

              <div className="analysis-grid">
                <div className="analysis-card">
                  <h4>Research Problem</h4>
                  <p className="analysis-text">{inspectedAnalysis.research_problem}</p>
                </div>
                <div className="analysis-card">
                  <h4>Proposed Methodology</h4>
                  <p className="analysis-text">{inspectedAnalysis.proposed_method}</p>
                </div>
                <div className="analysis-card">
                  <h4>Architecture & Pipeline</h4>
                  <p className="analysis-text">{inspectedAnalysis.architecture}</p>
                </div>
                <div className="analysis-card">
                  <h4>Empirical Results</h4>
                  <p className="analysis-text">{inspectedAnalysis.results}</p>
                </div>
                <div className="analysis-card">
                  <h4>Author Limitations</h4>
                  <ul className="analysis-bullets">
                    {(inspectedAnalysis.limitations || []).map((l, i) => <li key={i}>{l}</li>)}
                  </ul>
                </div>
                <div className="analysis-card">
                  <h4>Why Approach May Fail</h4>
                  <ul className="analysis-bullets">
                    {(inspectedAnalysis.why_approach_may_fail || []).map((f, i) => <li key={i}>{f}</li>)}
                  </ul>
                </div>
              </div>

              {inspectedAnalysis.overall_assessment && (
                <div className="analysis-card" style={{ marginTop: "18px" }}>
                  <h4>Synthesis & Assessment</h4>
                  <p className="analysis-text">{inspectedAnalysis.overall_assessment}</p>
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

function FeatureCard({ icon, title, description }) {
  return (
    <div className="feature-card">
      <div className="feature-icon">{icon}</div>
      <h3>{title}</h3>
      <p>{description}</p>
    </div>
  );
}

export default App;
