/**
 * ResearchOS Paper Normalizer (Node.js)
 */

export function cleanString(str) {
  if (!str) return '';
  return String(str).replace(/\s+/g, ' ').trim();
}

export function cleanDoi(doi) {
  if (!doi) return null;
  let d = String(doi).trim();
  d = d.replace(/^https?:\/\/(dx\.)?doi\.org\//i, '');
  d = d.replace(/^doi:\s*/i, '');
  return d.trim().toLowerCase() || null;
}

export function cleanArxivId(id) {
  if (!id) return null;
  let clean = String(id).trim();
  clean = clean.replace(/^https?:\/\/arxiv\.org\/(abs|pdf)\//i, '');
  clean = clean.replace(/(\.pdf|v\d+)$/i, '');
  return clean.trim() || null;
}

export function normalizePaper({
  id = '',
  title = '',
  authors = [],
  abstract = '',
  year = null,
  publishedDate = null,
  doi = null,
  arxivId = null,
  paperUrl = '',
  pdfUrl = null,
  source = 'Unknown',
  citationCount = null,
  venue = null,
  keywords = [],
  score = null,
}) {
  const normTitle = cleanString(title);
  const normDoi = cleanDoi(doi);
  const normArxiv = cleanArxivId(arxivId);
  const normYear = year ? String(year).slice(0, 4) : (publishedDate ? String(publishedDate).slice(0, 4) : null);

  const cleanAuthors = (Array.isArray(authors) ? authors : [])
    .map(a => typeof a === 'string' ? a.trim() : (a.name || a.text || ''))
    .filter(Boolean);

  let cleanId = id;
  if (!cleanId) {
    cleanId = normDoi ? `doi:${normDoi}` : (normArxiv ? `arxiv:${normArxiv}` : `${source.toLowerCase()}:${normTitle}`);
  }

  return {
    id: cleanId,
    title: normTitle,
    authors: cleanAuthors,
    abstract: cleanString(abstract),
    year: normYear,
    publishedDate: publishedDate ? String(publishedDate).slice(0, 10) : null,
    doi: normDoi,
    arxivId: normArxiv,
    paperUrl: cleanString(paperUrl) || (normDoi ? `https://doi.org/${normDoi}` : ''),
    pdfUrl: cleanString(pdfUrl) || (normArxiv ? `https://arxiv.org/pdf/${normArxiv}` : null),
    source: cleanString(source),
    citationCount: typeof citationCount === 'number' && !isNaN(citationCount) ? citationCount : null,
    venue: cleanString(venue) || null,
    keywords: Array.isArray(keywords) ? keywords.filter(Boolean) : [],
    score: typeof score === 'number' ? score : null,
  };
}
