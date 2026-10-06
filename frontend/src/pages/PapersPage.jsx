import { Bookmark, Trash } from "lucide-react";

import PaperGrid from "../components/papers/PaperGrid";
import { EmptyState } from "../components/state/StateBlocks";

/**
 * Saved papers.
 *
 * Stored in the browser for now (see useWorkspace); the layout mirrors the
 * server-side workspace planned for the database phase.
 */
export default function PapersPage({ workspace, onAnalyze, onOpenAnalysis, onNavigate }) {
  const papers = workspace.savedPapers;

  if (papers.length === 0) {
    return (
      <EmptyState
        icon={<Bookmark size={20} />}
        title="No saved papers yet"
        description="Save papers from a search to build your own reading list. Saved papers stay in this browser until the server-side workspace ships."
        action={{ label: "Start a search", onClick: () => onNavigate("research") }}
      />
    );
  }

  return (
    <section className="results">
      <div className="results__head">
        <div>
          <span className="eyebrow">Saved papers</span>
          <h2>{papers.length} paper{papers.length === 1 ? "" : "s"} in your library</h2>
        </div>
        <button type="button" className="button button--ghost button--sm" onClick={workspace.clearSavedPapers}>
          <Trash size={15} aria-hidden="true" />
          Clear all
        </button>
      </div>

      <PaperGrid
        papers={papers}
        onAnalyze={onAnalyze}
        onOpen={onOpenAnalysis}
        analyzingId={null}
        savedPaperIds={workspace.savedPaperIds}
        onToggleSave={workspace.toggleSavePaper}
      />
    </section>
  );
}
