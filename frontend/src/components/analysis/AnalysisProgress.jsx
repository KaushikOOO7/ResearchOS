import { LoaderCircle } from "lucide-react";

/**
 * Progress indicator for the analysis pipeline.
 *
 * ResearchOS does not stream partial analysis, so the stages shown describe
 * what the backend is doing (in order) together with real elapsed time —
 * no fake percentage bar.
 */
export default function AnalysisProgress({ paper, elapsed }) {
  const hasPdf = Boolean(paper?.pdf_url);
  const stages = hasPdf
    ? ["Downloading PDF", "Extracting text", "Detecting sections", "AI analysis"]
    : ["Using abstract", "AI analysis"];

  return (
    <section className="analysis-progress" role="status" aria-live="polite">
      <div className="analysis-progress__head">
        <LoaderCircle size={18} className="spin" aria-hidden="true" />
        <div>
          <h3>{hasPdf ? "Analysing the paper" : "Analysing the abstract"}</h3>
          <p className="muted">{paper?.title}</p>
        </div>
        <span className="analysis-progress__time">{elapsed}s</span>
      </div>

      <ol className="analysis-progress__stages">
        {stages.map((stage, index) => (
          <li key={stage} className={index === 0 ? "is-active" : ""}>
            <span className="dot" aria-hidden="true" />
            {stage}
          </li>
        ))}
      </ol>

      <p className="muted analysis-progress__note">
        AI analysis typically takes 20–60 seconds depending on paper length. Don&apos;t
        close this tab — the result appears here as soon as it is ready.
      </p>
    </section>
  );
}
