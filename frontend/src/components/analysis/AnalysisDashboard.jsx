import {
  Activity,
  Blocks,
  ChartBar,
  CircleAlert,
  Compass,
  Cpu,
  Database,
  ExternalLink,
  FileText,
  FlaskConical,
  Layers,
  Lightbulb,
  Route,
  Scale,
  Target,
  TriangleAlert,
  Bookmark,
  BookmarkCheck,
} from "lucide-react";

import BulletList from "./BulletList";
import ResearchGapPanel from "./ResearchGapPanel";
import { safeExternalUrl } from "../../utils/format";

const NOT_STATED = "Not stated in the provided paper.";

/** Section definition: number, title, icon, provenance and renderer. */
function buildSections(analysis) {
  return [
    {
      id: "problem",
      number: "01",
      title: "Research Problem",
      icon: Target,
      provenance: "fact",
      body: <p className="section-text">{analysis.research_problem || NOT_STATED}</p>,
    },
    {
      id: "existing",
      number: "02",
      title: "Existing Approach",
      icon: Layers,
      provenance: "fact",
      body: <p className="section-text">{analysis.existing_approach || NOT_STATED}</p>,
    },
    {
      id: "method",
      number: "03",
      title: "Proposed Method",
      icon: FlaskConical,
      provenance: "fact",
      body: <p className="section-text">{analysis.proposed_method || NOT_STATED}</p>,
    },
    {
      id: "architecture",
      number: "04",
      title: "Architecture",
      icon: Blocks,
      provenance: "fact",
      body: <p className="section-text">{analysis.architecture || NOT_STATED}</p>,
    },
    {
      id: "dataset",
      number: "05",
      title: "Dataset",
      icon: Database,
      provenance: "fact",
      body: <p className="section-text">{analysis.dataset || NOT_STATED}</p>,
    },
    {
      id: "model",
      number: "06",
      title: "Model / Algorithm",
      icon: Cpu,
      provenance: "fact",
      body: <p className="section-text">{analysis.model_algorithm || NOT_STATED}</p>,
    },
    {
      id: "results",
      number: "07",
      title: "Results",
      icon: ChartBar,
      provenance: "fact",
      body: <p className="section-text">{analysis.results || NOT_STATED}</p>,
    },
    {
      id: "limitations",
      number: "08",
      title: "Limitations",
      icon: TriangleAlert,
      provenance: "mixed",
      wide: true,
      body: (
        <div className="split">
          <div>
            <h4 className="split__title">
              Stated by the authors
              <span className="provenance-badge provenance-badge--fact">From paper</span>
            </h4>
            <BulletList items={analysis.limitations} tone="fact" />
          </div>
          <div>
            <h4 className="split__title">
              Additional technical limitations
              <span className="provenance-badge provenance-badge--inferred">AI-inferred</span>
            </h4>
            <BulletList
              items={analysis.additional_technical_limitations}
              tone="inferred"
              emptyText="No additional technical limitations were identified."
            />
          </div>
        </div>
      ),
    },
    {
      id: "failure",
      number: "09",
      title: "Why This Approach May Fail",
      icon: CircleAlert,
      provenance: "inferred",
      wide: true,
      body: <BulletList items={analysis.why_approach_may_fail} tone="inferred" />,
    },
    {
      id: "gap",
      number: "10",
      title: "Research Gap",
      icon: Compass,
      provenance: "mixed",
      wide: true,
      body: <ResearchGapPanel gap={analysis.research_gap} />,
    },
    {
      id: "improvements",
      number: "11",
      title: "Possible Improvements",
      icon: Lightbulb,
      provenance: "inferred",
      body: <BulletList items={analysis.possible_improvements} tone="inferred" />,
    },
    {
      id: "directions",
      number: "12",
      title: "New Research Directions",
      icon: Route,
      provenance: "inferred",
      wide: true,
      body: <BulletList items={analysis.new_research_direction} tone="inferred" />,
    },
    {
      id: "assessment",
      number: "13",
      title: "Overall Assessment",
      icon: Scale,
      provenance: "inferred",
      body: <p className="section-text">{analysis.overall_assessment || NOT_STATED}</p>,
    },
  ];
}

function Section({ section }) {
  const Icon = section.icon;
  return (
    <section
      className={`analysis-section ${section.wide ? "analysis-section--wide" : ""}`}
      aria-labelledby={`section-${section.id}`}
    >
      <header className="analysis-section__head">
        <span className="analysis-section__number">{section.number}</span>
        <span className="analysis-section__icon" aria-hidden="true">
          <Icon size={16} />
        </span>
        <h3 id={`section-${section.id}`}>{section.title}</h3>
        {section.provenance === "fact" && (
          <span className="provenance-badge provenance-badge--fact">From paper</span>
        )}
        {section.provenance === "inferred" && (
          <span className="provenance-badge provenance-badge--inferred">AI-inferred</span>
        )}
      </header>
      <div className="analysis-section__body">{section.body}</div>
    </section>
  );
}

/**
 * AI research analysis dashboard: 13 structured sections with explicit
 * provenance, plus the metadata that documents what the model actually read.
 */
export default function AnalysisDashboard({
  paper,
  analysis,
  metadata,
  onClose,
  onSave,
  isSaved,
}) {
  const pdfUrl = safeExternalUrl(paper?.pdf_url);
  const sourceUrl = safeExternalUrl(paper?.paper_url);
  const warnings = metadata?.warnings || [];
  const sections = buildSections(analysis);

  return (
    <section className="analysis" aria-label="AI paper analysis">
      <header className="analysis__header">
        <div className="analysis__heading">
          <span className="eyebrow">AI research analysis</span>
          <h2>{paper?.title}</h2>
          <p className="analysis__meta">
            {paper?.authors_display}
            {paper?.year ? ` · ${paper.year}` : ""}
            {paper?.source ? ` · ${paper.source}` : ""}
            {paper?.doi ? ` · DOI ${paper.doi}` : ""}
            {paper?.arxiv_id ? ` · arXiv ${paper.arxiv_id}` : ""}
          </p>
        </div>

        <div className="analysis__actions">
          {pdfUrl && (
            <a className="button button--secondary button--sm" href={pdfUrl} target="_blank" rel="noopener noreferrer">
              <FileText size={15} aria-hidden="true" /> PDF
            </a>
          )}
          {sourceUrl && (
            <a className="button button--secondary button--sm" href={sourceUrl} target="_blank" rel="noopener noreferrer">
              <ExternalLink size={15} aria-hidden="true" /> Source
            </a>
          )}
          <button
            type="button"
            className={`button button--sm ${isSaved ? "button--primary" : "button--secondary"}`}
            onClick={onSave}
            aria-pressed={isSaved}
          >
            {isSaved ? <BookmarkCheck size={15} /> : <Bookmark size={15} />}
            {isSaved ? "Saved" : "Save analysis"}
          </button>
          <button type="button" className="button button--ghost button--sm" onClick={onClose}>
            Close
          </button>
        </div>
      </header>

      <div className="analysis__provenance">
        <span className="provenance-item">
          <Activity size={13} aria-hidden="true" />
          {metadata?.referenced_abstract_only
            ? "Analysed from title + abstract only"
            : `Full text analysed${metadata?.pages ? ` · ${metadata.pages} pages` : ""}`}
        </span>
        {metadata?.analysed_chars ? (
          <span className="provenance-item">
            {metadata.analysed_chars.toLocaleString()} characters processed
          </span>
        ) : null}
        {metadata?.model && <span className="provenance-item">Model: {metadata.model}</span>}
        {metadata?.sections_detected?.length > 0 && (
          <span className="provenance-item">
            Sections: {metadata.sections_detected.join(", ")}
          </span>
        )}
        {metadata?.elapsed_ms ? (
          <span className="provenance-item">
            Generated in {(metadata.elapsed_ms / 1000).toFixed(1)}s
          </span>
        ) : null}
      </div>

      {warnings.length > 0 && (
        <ul className="analysis__warnings" role="note">
          {warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}

      <div className="analysis__grid">
        {sections.map((section) => (
          <Section key={section.id} section={section} />
        ))}
      </div>

      <footer className="analysis__footer">
        <p>
          Facts marked <span className="provenance-badge provenance-badge--fact">From paper</span> come
          from the provided text. Items marked{" "}
          <span className="provenance-badge provenance-badge--inferred">AI-inferred</span> are the
          model&apos;s analysis and have not been verified experimentally.
        </p>
      </footer>
    </section>
  );
}
