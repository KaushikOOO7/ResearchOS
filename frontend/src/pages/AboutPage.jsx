import { Blocks, CircleCheck, Compass, Gauge, ShieldCheck, Sparkle } from "lucide-react";

const PIPELINE = [
  ["1. Query understanding", "Tokenisation, keyphrase extraction, acronym expansion, intent + domain detection."],
  ["2. Multi-source retrieval", "arXiv, OpenAlex, Crossref, Semantic Scholar (with key) and PubMed for biomedical ideas — queried in parallel with per-provider isolation."],
  ["3. Normalisation", "One schema for every paper: title, authors, year, DOI/arXiv id, abstract, venue, links, citations, keywords."],
  ["4. Deduplication", "DOI → arXiv id → normalised title → fuzzy title matching, merging the richest metadata from each source."],
  ["5. Scoring", "BM25 relevance (title/keywords/abstract/subjects, phrase + coverage bonuses), metadata quality, log-scaled citation impact, exponential recency decay, source reliability."],
  ["6. Ranking", "Weighted overall score with per-paper weight renormalisation when a component is unavailable."],
  ["7. AI analysis", "SSRF-guarded PDF download → text extraction → section detection → Gemini structured analysis with strict JSON validation."],
];

const SCORE_FORMULA = [
  ["Relevance", "0.50", "BM25 over field-weighted metadata + topic coverage + exact-phrase bonuses."],
  ["Quality", "0.20", "Metadata completeness heuristic: abstract, DOI, venue, type, cross-source corroboration."],
  ["Citation impact", "0.15", "log(1 + citations), saturating at 1,000. Left unavailable when no source reports citations."],
  ["Recency", "0.10", "100 for ≤1 year, exponential decay afterwards (7-year half-life, floor 15)."],
  ["Source reliability", "0.05", "Metadata openness/completeness of the provider, not a judgement about the paper."],
];

const HONESTY = [
  "No fabricated papers, authors, citations, datasets, metrics or analysis — ever.",
  "Missing metadata is labelled “Not available” instead of guessed.",
  "AI output separates what the paper states from what the model infers.",
  "Quality scores describe metadata completeness, not scientific merit.",
  "Unavailable ranking components are excluded from the weighted average rather than scored as zero.",
];

const ROADMAP = [
  ["Phase 1-3 (done)", "Stable frontend ↔ backend, multi-source Top 30 ranking engine, PDF extraction, structured AI analysis dashboard."],
  ["Phase 4 (next)", "Research gap engine across papers, multi-paper comparison, novelty analysis, project idea generator."],
  ["Phase 5", "Section-aware RAG chunking, page-level evidence citations for every AI claim."],
  ["Phase 6", "Server-side workspace: saved papers, history, projects, literature review generator, exports (Markdown/PDF/DOCX)."],
  ["Phase 7", "PostgreSQL persistence, authentication, production hardening and deployment."],
];

/** About: what ResearchOS is, how it works, and what is honest about it. */
export default function AboutPage({ health }) {
  const healthData = health.data;

  return (
    <div className="about">
      <section className="about__intro">
        <span className="badge">
          <Sparkle size={14} aria-hidden="true" />
          About ResearchOS
        </span>
        <h1>An AI research command center for the whole idea → literature → gap journey.</h1>
        <p>
          ResearchOS takes a research idea, retrieves and ranks the most relevant literature
          it can find across multiple academic sources, then analyses selected papers to
          surface methods, datasets, limitations, failure modes and research gaps — ending in
          concrete directions you can pursue.
        </p>
      </section>

      <section className="about__grid">
        <article className="about-card">
          <header>
            <Blocks size={16} aria-hidden="true" />
            <h2>Retrieval &amp; ranking pipeline</h2>
          </header>
          <ol className="about-list">
            {PIPELINE.map(([title, text]) => (
              <li key={title}>
                <strong>{title}</strong>
                <span>{text}</span>
              </li>
            ))}
          </ol>
        </article>

        <article className="about-card">
          <header>
            <Gauge size={16} aria-hidden="true" />
            <h2>Ranking weights &amp; methodology</h2>
          </header>
          <table className="weights-table">
            <thead>
              <tr>
                <th scope="col">Component</th>
                <th scope="col">Weight</th>
                <th scope="col">How it is computed</th>
              </tr>
            </thead>
            <tbody>
              {SCORE_FORMULA.map(([name, weight, how]) => (
                <tr key={name}>
                  <th scope="row">{name}</th>
                  <td>{weight}</td>
                  <td>{how}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted">
            Weights are configurable on the backend (RANK_WEIGHT_* environment variables).
            Relevance is scaled so the best candidate of a result set scores 100.
          </p>
        </article>

        <article className="about-card">
          <header>
            <ShieldCheck size={16} aria-hidden="true" />
            <h2>Research integrity rules</h2>
          </header>
          <ul className="integrity-list">
            {HONESTY.map((item) => (
              <li key={item}>
                <CircleCheck size={14} aria-hidden="true" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </article>

        <article className="about-card">
          <header>
            <Compass size={16} aria-hidden="true" />
            <h2>Roadmap</h2>
          </header>
          <ol className="about-list">
            {ROADMAP.map(([phase, text]) => (
              <li key={phase}>
                <strong>{phase}</strong>
                <span>{text}</span>
              </li>
            ))}
          </ol>
        </article>
      </section>

      {healthData && (
        <section className="about__status">
          <h2>Server capabilities</h2>
          <ul className="capability-list">
            <li>
              <span className={healthData.gemini_configured ? "dot dot--ok" : "dot dot--off"} />
              AI analysis ({healthData.gemini_model}) —{" "}
              {healthData.gemini_configured ? "configured" : "no API key configured"}
            </li>
            {healthData.network && (
              <li>
                <span className={healthData.network.internet ? "dot dot--ok" : "dot dot--off"} />
                outbound internet access —{" "}
                {healthData.network.internet
                  ? `reachable (${healthData.network.detail})`
                  : `blocked (${healthData.network.detail})`}
              </li>
            )}
            {Object.entries(healthData.providers || {}).map(([name, enabled]) => (
              <li key={name}>
                <span className={enabled ? "dot dot--ok" : "dot dot--off"} />
                {name} — {enabled ? "enabled" : "needs credentials"}
              </li>
            ))}
          </ul>
          {healthData.warnings?.length > 0 && (
            <ul className="about__warnings">
              {healthData.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
