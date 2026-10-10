/**
 * Semantic Scholar Provider (Node.js)
 */

import { normalizePaper } from '../normalizer.js';

const USER_AGENT = 'ResearchOS/1.0 (academic-platform; contact@researchos.dev)';

export async function searchSemanticScholar(query, maxResults = 20) {
  if (!query || !query.trim()) return [];

  const encoded = encodeURIComponent(query.trim());
  const fields = 'title,authors,year,abstract,citationCount,url,openAccessPdf,externalIds,venue';
  const url = `https://api.semanticscholar.org/graph/v1/paper/search?query=${encoded}&limit=${maxResults}&fields=${fields}`;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 12000);

  const headers = { 'User-Agent': USER_AGENT, Accept: 'application/json' };
  const apiKey = process.env.SEMANTIC_SCHOLAR_API_KEY;
  if (apiKey) headers['x-api-key'] = apiKey;

  try {
    const res = await fetch(url, { headers, signal: controller.signal });
    clearTimeout(timeoutId);

    if (!res.ok) {
      if (res.status === 429) throw new Error('rate_limited');
      return [];
    }

    const data = await res.json();
    const items = data.data || [];
    const papers = [];

    for (const item of items) {
      const title = (item.title || '').replace(/\s+/g, ' ').trim();
      if (!title) continue;

      const authors = (item.authors || []).map(a => a.name).filter(Boolean);
      const doi = item.externalIds?.DOI ? String(item.externalIds.DOI).toLowerCase() : null;
      const arxivId = item.externalIds?.ArXiv ? String(item.externalIds.ArXiv) : null;
      const pdfUrl = item.openAccessPdf?.url || null;
      const paperUrl = item.url || (doi ? `https://doi.org/${doi}` : '');

      papers.push(
        normalizePaper({
          id: `s2:${item.paperId || doi || title}`,
          title,
          authors,
          abstract: item.abstract || '',
          year: item.year ? String(item.year) : null,
          doi,
          arxivId,
          paperUrl,
          pdfUrl,
          source: 'Semantic Scholar',
          citationCount: item.citationCount || null,
          venue: item.venue || null,
        })
      );
    }

    return papers;
  } catch (err) {
    clearTimeout(timeoutId);
    throw err;
  }
}
