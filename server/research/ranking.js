/**
 * ResearchOS Paper Ranker (Node.js)
 */

function extractQueryTokens(query) {
  const words = String(query || '').toLowerCase().match(/[a-z0-9]{2,}/g) || [];
  const stop = new Set(['the', 'and', 'for', 'with', 'from', 'that', 'this', 'via', 'using', 'into', 'what', 'how']);
  return words.filter(w => !stop.has(w));
}

export function computePaperScore(paper, query, currentYear = 2026) {
  let score = 0;
  const qLower = String(query || '').trim().toLowerCase();
  const tokens = extractQueryTokens(query);

  const titleLower = (paper.title || '').toLowerCase();
  const abstractLower = (paper.abstract || '').toLowerCase();

  // 1. Title precision
  if (qLower && titleLower.includes(qLower)) {
    score += 30;
  }
  for (const t of tokens) {
    if (titleLower.includes(t)) score += 10;
  }

  // 2. Abstract keywords
  let absMatches = 0;
  for (const t of tokens) {
    if (abstractLower.includes(t)) absMatches++;
  }
  score += Math.min(absMatches * 2, 10);

  // 3. Citation impact (log-scaled)
  if (typeof paper.citationCount === 'number' && paper.citationCount > 0) {
    score += Math.min(Math.log10(paper.citationCount + 1) * 6, 25);
  }

  // 4. Recency signal
  if (paper.year) {
    const y = parseInt(paper.year, 10);
    if (!isNaN(y)) {
      const diff = Math.max(0, currentYear - y);
      if (diff <= 1) score += 15;
      else if (diff <= 3) score += 10;
      else if (diff <= 5) score += 6;
      else if (diff <= 10) score += 3;
    }
  }

  // 5. Open-access direct PDF accessibility
  if (paper.pdfUrl) {
    score += 10;
  }

  return Math.round(score * 100) / 100;
}

export function rankPapers(papers, query, limit = 30) {
  for (const p of papers) {
    p.score = computePaperScore(p, query);
  }

  return papers
    .sort((a, b) => {
      if ((b.score || 0) !== (a.score || 0)) {
        return (b.score || 0) - (a.score || 0);
      }
      const yA = parseInt(a.year || '0', 10);
      const yB = parseInt(b.year || '0', 10);
      if (yB !== yA) return yB - yA;
      return (a.title || '').localeCompare(b.title || '');
    })
    .slice(0, limit);
}
