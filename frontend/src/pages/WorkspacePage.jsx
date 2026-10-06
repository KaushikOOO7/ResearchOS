import {
  Activity,
  Compass,
  ExternalLink,
  History,
  Sparkle,
  Trash,
} from "lucide-react";

import { EmptyState } from "../components/state/StateBlocks";
import { formatTimestamp, safeExternalUrl } from "../utils/format";

/**
 * Research workspace: saved analyses + recent searches.
 *
 * Everything here is real data produced by this browser session (nothing is
 * mocked). Persistence is local until the PostgreSQL workspace phase.
 */
export default function WorkspacePage({ workspace, onOpenAnalysis, onNavigate, onReanalyze }) {
  const analyses = workspace.savedAnalyses;
  const searches = workspace.recentSearches;

  return (
    <div className="workspace">
      <section className="workspace__column">
        <header className="workspace__head">
          <div>
            <span className="eyebrow">Saved analyses</span>
            <h2>
              {analyses.length} analys{analyses.length === 1 ? "is" : "es"}
            </h2>
          </div>
          {analyses.length > 0 && (
            <button
              type="button"
              className="button button--ghost button--sm"
              onClick={workspace.clearSavedAnalyses}
            >
              <Trash size={15} aria-hidden="true" />
              Clear
            </button>
          )}
        </header>

        {analyses.length === 0 ? (
          <EmptyState
            icon={<Sparkle size={20} />}
            title="No saved analyses"
            description="Analyse a paper and press “Save analysis” to keep it here."
            action={{ label: "Go to research", onClick: () => onNavigate("research") }}
          />
        ) : (
          <ul className="workspace__list">
            {analyses.map((entry) => {
              const paper = entry.paper || {};
              const pdfUrl = safeExternalUrl(paper.pdf_url);
              const sourceUrl = safeExternalUrl(paper.paper_url);
              const gapCount =
                (entry.analysis?.research_gap?.author_stated_gaps?.length || 0) +
                (entry.analysis?.research_gap?.ai_inferred_gaps?.length || 0);

              return (
                <li className="workspace__item" key={paper.id || paper.title}>
                  <div className="workspace__item-main">
                    <h3>{paper.title}</h3>
                    <p className="muted">
                      {paper.year || "Year not available"} · {paper.source || "source not available"}
                      {" · saved "}
                      {formatTimestamp(entry.saved_at)}
                    </p>
                    <div className="workspace__metrics">
                      <span className="metric">
                        <Compass size={13} aria-hidden="true" /> {gapCount} gap
                        {gapCount === 1 ? "" : "s"} identified
                      </span>
                      <span className="metric">
                        <Activity size={13} aria-hidden="true" />
                        {entry.metadata?.referenced_abstract_only
                          ? "abstract-based"
                          : "full text"}
                      </span>
                      {entry.metadata?.model && (
                        <span className="metric">model: {entry.metadata.model}</span>
                      )}
                    </div>
                  </div>

                  <div className="workspace__item-actions">
                    <button
                      type="button"
                      className="button button--secondary button--sm"
                      onClick={() => onOpenAnalysis(entry.paper, entry.analysis, entry.metadata)}
                    >
                      Open analysis
                    </button>
                    <button
                      type="button"
                      className="button button--ghost button--sm"
                      onClick={() => onReanalyze(entry.paper)}
                    >
                      Re-run AI
                    </button>
                    {pdfUrl && (
                      <a
                        className="button button--ghost button--sm"
                        href={pdfUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        PDF
                      </a>
                    )}
                    {sourceUrl && (
                      <a
                        className="button button--ghost button--sm"
                        href={sourceUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        <ExternalLink size={14} aria-hidden="true" />
                        Source
                      </a>
                    )}
                    <button
                      type="button"
                      className="icon-button icon-button--danger"
                      aria-label={`Delete analysis for ${paper.title}`}
                      onClick={() => workspace.removeSavedAnalysis(paper.id)}
                    >
                      <Trash size={15} />
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className="workspace__column">
        <header className="workspace__head">
          <div>
            <span className="eyebrow">Recent searches</span>
            <h2>{searches.length} quer{searches.length === 1 ? "y" : "ies"}</h2>
          </div>
          {searches.length > 0 && (
            <button
              type="button"
              className="button button--ghost button--sm"
              onClick={workspace.clearRecentSearches}
            >
              <Trash size={15} aria-hidden="true" />
              Clear
            </button>
          )}
        </header>

        {searches.length === 0 ? (
          <EmptyState
            icon={<History size={20} />}
            title="No searches yet"
            description="Your research queries will appear here so you can jump back into a topic."
            action={{ label: "Start a search", onClick: () => onNavigate("research") }}
          />
        ) : (
          <ul className="history">
            {searches.map((entry) => (
              <li key={`${entry.query}-${entry.searched_at}`}>
                <button
                  type="button"
                  className="history__item"
                  onClick={() => onNavigate("research", entry.query)}
                >
                  <span className="history__query">{entry.query}</span>
                  <span className="history__meta">
                    {entry.paper_count} paper{entry.paper_count === 1 ? "" : "s"} ·{" "}
                    {formatTimestamp(entry.searched_at)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
