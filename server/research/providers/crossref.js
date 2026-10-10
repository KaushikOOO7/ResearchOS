/**
 * Crossref Provider (Node.js)
 */

import { normalizePaper } from '../normalizer.js';

const USER_AGENT = 'ResearchOS/1.0 (academic-platform; contact@researchos.dev)';

export async function searchCrossref(query, maxResults = 25) {
  if (!query || !query.trim()) return [];

  const encoded = encodeURIComponent(query.trim());
  const url = `https://api.crossref.org/works?query=${encoded}&rows=${maxResults}&sort=relevance`;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 12000);

  try {
    const res = await fetch(url, {
      headers: { 'User-Agent': USER_AGENT, Accept: 'application/json' },
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (!res.ok) {
      if (res.status === 429) throw new Error('rate_limited');
      return [];
    }

    const data = await res.json();
    const items = data.message?.items || [];
    const papers = [];

    for (const item of items) {
      const titles = item.title || [];
      if (!titles.length || !titles[0]) continue;
      const title = titles[0].replace(/\s+/g, ' ').trim();

      const authors = (item.author || []).map(a => `${a.given || ''} ${a.family || ''}`.trim()).filter(Boolean);
      const doi = item.DOI ? String(item.DOI).toLowerCase() : null;

      let year = null;
      const parts = item['published-print']?.['date-parts'] || item.created?.['date-parts'];
      if (parts && parts[0] && parts[0][0]) {
        year = String(parts[0][0]);
      }

      let abstract = (item.abstract || '').replace(/<[^>]+>/g, ' ').trim();
      const venue = item['container-title']?.[0] || null;
      const paperUrl = item.URL || (doi ? `https://doi.org/${doi}` : '');
      const citations = item['is-referenced-by-count'] || null;

      let pdfUrl = null;
      for (const link of (item.link || [])) {
        if (link['content-type']?.includes('pdf')) {
          pdfUrl = link.URL;
          break;
        }
      }

      papers.push(
        normalizePaper({
          id: `crossref:${doi || title}`,
          title,
          authors,
          abstract,
          year,
          doi,
          paperUrl,
          pdfUrl,
          source: 'Crossref',
          citationCount: citations,
          venue,
        })
      );
    }

    return papers;
  } catch (err) {
    clearTimeout(timeoutId);
    throw err;
  }
}
