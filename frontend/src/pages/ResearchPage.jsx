import { useMemo, useState } from "react";
import {
  BookOpen,
  CircleAlert,
  Compass,
  Layers,
  Route,
  SearchX,
  Sparkle,
  Target,
} from "lucide-react";

import SearchPanel from "../components/search/SearchPanel";
import AnalysisDashboard from "../components/analysis/AnalysisDashboard";
import AnalysisProgress from "../components/analysis/AnalysisProgress";
import PaperGrid from "../components/papers/PaperGrid";
import PapersToolbar, { PipelineSummary } from "../components/papers/PapersToolbar";
import { EmptyState, ErrorState, SkeletonCards } from "../components/state/StateBlocks";

const SORT_ACCESSORS = {
  best: (paper) => -(paper.overall_score ?? 0),
  relevance: (paper) => -(paper.relevance_score ?? 0),
  citations: (paper) => -(paper.citation_count ?? -1),
  recent: (paper) => -(paper.year ?? 0),
};

const JOURNEY = [
  {
    icon: Sparkle,
    title: "Query understanding",
    text: "Your idea is tokenised, keyphrases extracted and acronyms expanded (GNN → graph neural network).",
  },
  {
    icon: Layers,
    title: "Multi-source retrieval",
    text: "arXiv, OpenAlex, Crossref, Semantic Scholar and PubMed (for biomedical ideas) are queried in parallel.",
  },
  {
    icon: BookOpen,
    title: "Top 30 papers",
    text: "Duplicates are merged across sources, then ranked on relevance, metadata quality, impact and recency.",
  },
  {
    icon: Target,
    title: "AI paper analysis",
    text: "Pick a paper and ResearchOS extracts the PDF and produces a structured, provenance-aware analysis.",
  },
  {
    icon: Compass,
    title: "Limitations & gaps",
    text: "Author-stated limitations are separated from AI-inferred ones and from explicit research gaps.",
  },
  {
    icon: Route,
    title: "New directions",
    text: "Improvements and research directions you can actually pursue — grounded in the paper you selected.",
  },
];

/** Research view: idea → ranked literature → AI analysis. */
export default function ResearchPage({
  research,
  analysis,
  workspace,
  health,
  onAnalyze,
  onOpenAnalysis,
}) {
  const [sort, setSort] = useState("best");
  const [pdfOnly, setPdfOnly] = useState(false);

  const visiblePapers = useMemo(() => {
    const papers = research.data?.papers ?? [];
    const list = pdfOnly ? papers.filter((paper) => Boolean(paper.pdf_url)) : [...papers];
    const accessor = SORT_ACCESSORS[sort] || SORT_ACCESSORS.best;
    return list.sort((a, b) => accessor(a) - accessor(b) || (a.rank ?? 0) - (b.rank ?? 0));
  }, [research.data, pdfOnly, sort]);

  const papers = research.data?.papers ?? [];

  // Distinguish "nothing matched" from "every provider failed": the UI should
  // tell the user which one happened instead of blaming their query.
  const sourcesUnreachable =
    Boolean(research.data) &&
    papers.length === 0 &&
    (research.data.stats?.providers_succeeded ?? 0) === 0 &&
    (research.data.stats?.providers_queried ?? 0) > 0;

  const analyzingId = analysis.status === "loading" ? analysis.paper?.id : null;
  const showLanding = research.status === "idle";

  return (
    <>
      <section className="hero">
        <span className="badge">
          <Sparkle size={14} aria-hidden="true" />
          AI research intelligence
        </span>
        <h1>
          Turn your idea into <span className="hero__accent">research intelligence.</span>
        </h1>
        <p className="hero__subtitle">
          Discover research papers, understand the architectures behind them, identify
          limitations, uncover research gaps, and find new research directions — grounded in
          real academic metadata, never invented.
        </p>

        <SearchPanel
          onSearch={research.search}
          status={research.status}
          elapsed={research.elapsed}
        />

        {health.status === "ready" && !health.data?.gemini_configured && (
          <p className="hero__notice" role="note">
            <CircleAlert size={14} aria-hidden="true" />
            Search is fully operational. AI analysis is disabled until{" "}
            <code>GEMINI_API_KEY</code> is configured on the backend.
          </p>
        )}
      </section>

      {showLanding && (
        <section className="journey" aria-label="What ResearchOS does">
          {JOURNEY.map((step, index) => {
            const Icon = step.icon;
            return (
              <article className="journey__step" key={step.title}>
                <span className="journey__index">{String(index + 1).padStart(2, "0")}</span>
                <span className="journey__icon" aria-hidden="true">
                  <Icon size={16} />
                </span>
                <h3>{step.title}</h3>
                <p>{step.text}</p>
              </article>
            );
          })}
        </section>
      )}

      {research.status === "loading" && (
        <section className="results" aria-busy="true">
          <div className="results__head">
            <h2>Searching for “{research.query}”</h2>
            <p className="muted">
              Collecting a candidate pool across academic sources, removing duplicates and
              ranking the results.
            </p>
          </div>
          <SkeletonCards count={6} />
        </section>
      )}

      {research.status === "error" && (
        <ErrorState
          error={research.error}
          title="We couldn't complete this search"
          onRetry={() => research.retry()}
        />
      )}

      {research.status === "empty" && (
        <section className="results">
          <PipelineSummary data={research.data} />
          <EmptyState
            icon={<SearchX size={20} />}
            title={
              sourcesUnreachable
                ? "Academic sources could not be reached"
                : "No papers matched your query"
            }
            description={
              research.data?.message ||
              "Try a broader phrasing, remove the year filter, or disable the open-access-only option."
            }
            action={{ label: "Clear filters and search again", onClick: () => research.search(research.query, {}) }}
          />
        </section>
      )}

      {research.status === "success" && (
        <section className="results" aria-label="Search results">
          <div className="results__head">
            <div>
              <span className="eyebrow">Research landscape</span>
              <h2>
                Top {papers.length} papers for “{research.query}”
              </h2>
            </div>
            <PapersToolbar
              papers={papers}
              sort={sort}
              onSortChange={setSort}
              pdfOnly={pdfOnly}
              onPdfOnlyChange={setPdfOnly}
            />
          </div>

          <PipelineSummary data={research.data} />

          <PaperGrid
            papers={visiblePapers}
            onAnalyze={onAnalyze}
            onOpen={onOpenAnalysis}
            analyzingId={analyzingId}
            savedPaperIds={workspace.savedPaperIds}
            onToggleSave={workspace.toggleSavePaper}
          />

          <p className="results__disclaimer">
            Ranking is computed from real metadata (relevance, metadata quality, citation
            impact, recency, source reliability). Fields a source does not provide are shown
            as “Not available” — ResearchOS never fabricates values.
          </p>
        </section>
      )}

      {analysis.status === "loading" && (
        <AnalysisProgress paper={analysis.paper} elapsed={analysis.elapsed} />
      )}

      {analysis.status === "error" && (
        <ErrorState
          error={analysis.error}
          title="AI analysis unavailable"
          onRetry={analysis.retry}
        />
      )}

      {analysis.status === "success" && (
        <AnalysisDashboard
          paper={analysis.paper}
          analysis={analysis.analysis}
          metadata={analysis.metadata}
          onClose={analysis.clear}
          isSaved={workspace.savedAnalysisIds.has(analysis.paper?.id)}
          onSave={() =>
            workspace.saveAnalysis(analysis.paper, analysis.analysis, analysis.metadata)
          }
        />
      )}
    </>
  );
}
