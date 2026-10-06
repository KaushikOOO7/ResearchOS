import { useMemo, useState } from "react";
import { CircleCheck, CircleX, Info } from "lucide-react";

const SORTS = {
  best: "Best match (overall score)",
  relevance: "Most relevant",
  citations: "Most cited",
  recent: "Newest first",
};

/** Sort + filter controls for a result set. */
export default function PapersToolbar({ papers, sort, onSortChange, pdfOnly, onPdfOnlyChange }) {
  const withPdf = useMemo(() => papers.filter((paper) => Boolean(paper.pdf_url)).length, [papers]);

  return (
    <div className="toolbar">
      <div className="toolbar__group">
        <label className="field field--inline">
          <span className="field__label">Sort by</span>
          <select
            className="field__control"
            value={sort}
            onChange={(event) => onSortChange(event.target.value)}
          >
            {Object.entries(SORTS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>

        <label className="checkbox checkbox--inline">
          <input
            type="checkbox"
            checked={pdfOnly}
            onChange={(event) => onPdfOnlyChange(event.target.checked)}
          />
          <span>
            Only papers with PDF ({withPdf}/{papers.length})
          </span>
        </label>
      </div>
    </div>
  );
}

/** Provenance panel: where the papers came from and what the pipeline did. */
export function PipelineSummary({ data }) {
  const [showNotes, setShowNotes] = useState(false);
  const stats = data?.stats || {};
  const sources = data?.sources || [];
  const analysis = data?.query_analysis;

  return (
    <section className="pipeline" aria-label="Search pipeline summary">
      <div className="pipeline__stats">
        <Stat label="Candidates collected" value={stats.candidates_collected} />
        <Stat label="Duplicates removed" value={stats.duplicates_removed} />
        <Stat label="Papers returned" value={stats.returned} />
        <Stat
          label="Providers used"
          value={`${stats.providers_succeeded}/${stats.providers_queried}`}
        />
        <Stat
          label="Pipeline time"
          value={stats.elapsed_ms ? `${(stats.elapsed_ms / 1000).toFixed(1)}s` : "—"}
        />
      </div>

      <div className="pipeline__sources">
        <span className="pipeline__heading">Sources</span>
        {sources.map((source) => (
          <span
            key={source.name}
            className={`source-chip ${source.ok && source.result_count > 0 ? "is-ok" : source.ok ? "is-empty" : "is-down"}`}
            title={source.error || `${source.result_count} results in ${source.elapsed_ms} ms`}
          >
            {source.ok && source.result_count > 0 ? (
              <CircleCheck size={13} aria-hidden="true" />
            ) : source.ok ? (
              <Info size={13} aria-hidden="true" />
            ) : (
              <CircleX size={13} aria-hidden="true" />
            )}
            {source.name}
            <span className="source-chip__count">
              {source.ok ? source.result_count : "failed"}
            </span>
          </span>
        ))}
      </div>

      {analysis && (
        <div className="pipeline__understanding">
          <span className="pipeline__heading">Query understanding</span>
          <div className="pipeline__terms">
            {analysis.topical_terms?.slice(0, 12).map((term) => (
              <span className="term-chip" key={term}>
                {term}
              </span>
            ))}
          </div>
          {analysis.notes?.length > 0 && (
            <ul className="pipeline__notes">
              {analysis.notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      <button
        type="button"
        className="link-button"
        aria-expanded={showNotes}
        onClick={() => setShowNotes((value) => !value)}
      >
        {showNotes ? "Hide ranking methodology" : "How are these papers ranked?"}
      </button>

      {showNotes && (
        <ul className="pipeline__method">
          {(data?.ranking_notes || []).map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Stat({ label, value }) {
  return (
    <div className="stat">
      <span className="stat__value">{value ?? "—"}</span>
      <span className="stat__label">{label}</span>
    </div>
  );
}
