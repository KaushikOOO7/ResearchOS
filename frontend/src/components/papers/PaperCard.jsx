import { useState } from "react";
import {
  ChevronDown,
  ExternalLink,
  FileText,
  LoaderCircle,
  Bookmark,
  BookmarkCheck,
  Sparkles,
} from "lucide-react";

import ScoreBreakdown from "./ScoreBar";
import {
  formatCitations,
  formatScore,
  identifierLabel,
  safeExternalUrl,
  scoreTone,
  truncate,
} from "../../utils/format";

/**
 * Paper card: rank, metadata, abstract preview, explainable scores and actions.
 * Unavailable metadata is labelled instead of being invented.
 */
export default function PaperCard({
  paper,
  onAnalyze,
  onOpen,
  isAnalyzing,
  isSaved,
  onToggleSave,
  highlightTerm,
}) {
  const [showScores, setShowScores] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const pdfUrl = safeExternalUrl(paper.pdf_url);
  const sourceUrl = safeExternalUrl(paper.paper_url);
  const citations = formatCitations(paper.citation_count);
  const identifiers = identifierLabel(paper);

  return (
    <article className={`paper-card ${isAnalyzing ? "paper-card--busy" : ""}`}>
      <header className="paper-card__head">
        <span className="rank" aria-label={`Rank ${paper.rank}`}>
          #{paper.rank}
        </span>

        <div className="paper-card__tags">
          <span
            className={`score-pill score-pill--${scoreTone(paper.relevance_score)}`}
            title={paper.score_explanations?.relevance || "Relevance score"}
          >
            {formatScore(paper.relevance_score)}% match
          </span>
          <span className="tag tag--source">{paper.source}</span>
          {paper.sources?.length > 1 && (
            <span className="tag" title={`Also indexed by ${paper.sources.slice(1).join(", ")}`}>
              +{paper.sources.length - 1} source{paper.sources.length > 2 ? "s" : ""}
            </span>
          )}
          {paper.quality_label && (
            <span className={`tag tag--quality tag--quality-${paper.quality_label.toLowerCase()}`}>
              {paper.quality_label} metadata
            </span>
          )}
          {paper.is_open_access && <span className="tag tag--oa">Open access</span>}
        </div>

        <button
          type="button"
          className={`save-button ${isSaved ? "is-saved" : ""}`}
          onClick={() => onToggleSave(paper)}
          aria-pressed={isSaved}
          aria-label={isSaved ? "Remove from saved papers" : "Save paper"}
        >
          {isSaved ? <BookmarkCheck size={16} /> : <Bookmark size={16} />}
        </button>
      </header>

      <h3 className="paper-card__title">
        <button type="button" className="paper-card__title-button" onClick={() => onOpen(paper)}>
          {paper.title}
        </button>
      </h3>

      <p className="paper-card__meta">
        <span>{paper.year || "Year not available"}</span>
        <span aria-hidden="true">·</span>
        <span>{paper.authors_display || "Authors not available"}</span>
        {paper.venue && (
          <>
            <span aria-hidden="true">·</span>
            <span className="paper-card__venue">{paper.venue}</span>
          </>
        )}
      </p>

      <p className={`paper-card__abstract ${expanded ? "" : "is-clamped"}`}>
        {paper.abstract
          ? expanded
            ? paper.abstract
            : truncate(paper.abstract, 300)
          : "Abstract not available from the queried sources."}
      </p>

      {paper.abstract && paper.abstract.length > 300 && (
        <button type="button" className="link-button" onClick={() => setExpanded((value) => !value)}>
          {expanded ? "Show less" : "Show full abstract"}
        </button>
      )}

      <dl className="paper-card__stats">
        <div>
          <dt>Citations</dt>
          <dd>{citations ? citations : <span className="muted">Not available</span>}</dd>
        </div>
        <div>
          <dt>Quality</dt>
          <dd>{paper.quality_label || "Unknown"}</dd>
        </div>
        {identifiers.length > 0 && (
          <div className="paper-card__stats-wide">
            <dt>Identifiers</dt>
            <dd>{identifiers.join(" · ")}</dd>
          </div>
        )}
      </dl>

      {highlightTerm && paper.matched_terms?.length > 0 && (
        <p className="paper-card__matches">
          Matched on: {paper.matched_terms.slice(0, 8).join(", ")}
        </p>
      )}

      <button
        type="button"
        className="score-toggle"
        aria-expanded={showScores}
        onClick={() => setShowScores((value) => !value)}
      >
        <ChevronDown size={14} className={showScores ? "rotate-180" : ""} aria-hidden="true" />
        {showScores ? "Hide ranking breakdown" : "Why this rank?"}
      </button>

      {showScores && (
        <div className="paper-card__scores">
          <ScoreBreakdown paper={paper} />
          <p className="paper-card__explain">
            {paper.score_explanations?.overall ||
              "Overall score combines relevance, metadata quality, citation impact, recency and source reliability."}
          </p>
        </div>
      )}

      <footer className="paper-card__actions">
        {pdfUrl ? (
          <a
            className="button button--primary button--sm"
            href={pdfUrl}
            target="_blank"
            rel="noopener noreferrer"
          >
            <FileText size={15} aria-hidden="true" />
            View PDF
          </a>
        ) : (
          <span className="button button--disabled button--sm" title="No direct PDF link available">
            <FileText size={15} aria-hidden="true" />
            No PDF
          </span>
        )}

        {sourceUrl && (
          <a
            className="button button--secondary button--sm"
            href={sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
          >
            <ExternalLink size={15} aria-hidden="true" />
            Source
          </a>
        )}

        <button
          type="button"
          className="button button--accent button--sm"
          onClick={() => onAnalyze(paper)}
          disabled={isAnalyzing}
        >
          {isAnalyzing ? (
            <>
              <LoaderCircle size={15} className="spin" aria-hidden="true" />
              Analysing…
            </>
          ) : (
            <>
              <Sparkles size={15} aria-hidden="true" />
              Analyze
            </>
          )}
        </button>
      </footer>
    </article>
  );
}
