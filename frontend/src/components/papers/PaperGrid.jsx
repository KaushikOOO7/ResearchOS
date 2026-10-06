import PaperCard from "./PaperCard";

/** Responsive paper grid (2 columns on desktop, 1 on mobile). */
export default function PaperGrid({
  papers,
  onAnalyze,
  onOpen,
  analyzingId,
  savedPaperIds,
  onToggleSave,
}) {
  return (
    <div className="papers-grid">
      {papers.map((paper) => (
        <PaperCard
          key={paper.id}
          paper={paper}
          onAnalyze={onAnalyze}
          onOpen={onOpen}
          isAnalyzing={analyzingId === paper.id}
          isSaved={savedPaperIds.has(paper.id)}
          onToggleSave={onToggleSave}
          highlightTerm
        />
      ))}
    </div>
  );
}
