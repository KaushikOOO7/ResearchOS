import { SCORE_LABELS, formatScore, scoreTone } from "../../utils/format";

/**
 * One ranking component rendered as a labelled bar.
 * `unavailable` communicates honestly that the metric could not be computed.
 */
function ScoreBar({ name, score, explanation, available = true }) {
  const tone = available ? scoreTone(score) : "muted";

  return (
    <div className="score-row" title={explanation || ""}>
      <span className="score-row__label">{SCORE_LABELS[name] || name}</span>
      <span className={`score-row__track score-row__track--${tone}`}>
        <span
          className="score-row__fill"
          style={{ width: available ? `${Math.max(2, Math.min(100, score))}%` : "0%" }}
        />
      </span>
      <span className="score-row__value">
        {available ? formatScore(score) : "n/a"}
      </span>
    </div>
  );
}

/** Full explainable score breakdown for one paper. */
export default function ScoreBreakdown({ paper }) {
  const explanations = paper.score_explanations || {};

  return (
    <div className="score-breakdown">
      <ScoreBar
        name="overall"
        score={paper.overall_score}
        explanation={explanations.overall}
      />
      <ScoreBar
        name="relevance"
        score={paper.relevance_score}
        explanation={explanations.relevance}
      />
      <ScoreBar
        name="quality"
        score={paper.quality_score}
        explanation={explanations.quality}
      />
      <ScoreBar
        name="citation"
        score={paper.citation_score}
        explanation={explanations.citation}
        available={paper.citation_score !== null && paper.citation_score !== undefined}
      />
      <ScoreBar
        name="recency"
        score={paper.recency_score}
        explanation={explanations.recency}
        available={paper.recency_score !== null && paper.recency_score !== undefined}
      />
      <ScoreBar
        name="source"
        score={paper.source_score}
        explanation={explanations.source}
      />
    </div>
  );
}
