import { Compass, Sparkles } from "lucide-react";

import BulletList from "./BulletList";

/**
 * Research gap panel — the core ResearchOS output.
 *
 * Author-stated gaps and AI-inferred gaps are always visually separated so a
 * reader can tell what the paper claims from what the model proposes.
 */
export default function ResearchGapPanel({ gap }) {
  const authorGaps = gap?.author_stated_gaps || [];
  const inferredGaps = gap?.ai_inferred_gaps || [];

  return (
    <div className="gap-panel">
      <div className="gap-panel__column gap-panel__column--fact">
        <header className="gap-panel__head">
          <Compass size={15} aria-hidden="true" />
          <h4>Stated by the authors</h4>
          <span className="provenance-badge provenance-badge--fact">From paper</span>
        </header>
        <BulletList
          items={authorGaps}
          tone="fact"
          emptyText="The paper does not explicitly state remaining gaps or future work."
        />
      </div>

      <div className="gap-panel__column gap-panel__column--inferred">
        <header className="gap-panel__head">
          <Sparkles size={15} aria-hidden="true" />
          <h4>Inferred by ResearchOS AI</h4>
          <span className="provenance-badge provenance-badge--inferred">AI-inferred</span>
        </header>
        <BulletList
          items={inferredGaps}
          tone="inferred"
          emptyText="No additional gaps were inferred from this paper."
        />
      </div>
    </div>
  );
}
