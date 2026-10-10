/**
 * CORE Open Access Provider (Node.js)
 */

import { normalizePaper } from '../normalizer.js';

const USER_AGENT = 'ResearchOS/1.0 (academic-platform; contact@researchos.dev)';

export async function searchCore(query, maxResults = 15) {
  if (!query || !query.trim()) return [];

  const encoded = encodeURIComponent(query.trim());
  const url = `https://api.core.ac.uk/v3/search/works?q=${encoded}&limit=${maxResults}`;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 10000);

  const headers = { 'User-Agent': USER_AGENT, Accept: 'application/json' };
  const apiKey = process.env.CORE_API_KEY;
  if (apiKey) headers['Authorization'] = `Bearer ${apiKey}`;

  try {
    const res = await fetch(url, { headers, signal: controller.signal });
    clearTimeout(timeoutId);

    if (!res.ok) {
      if (res.status === 401 || res.status === 403) throw new Error('authentication_required');
      if (res.status === 429) throw new Error('rate_limited');
      return [];
    }

    const data = await res.json();
    const results = data.results || [];
    const papers = [];

    for (const item of results) {
      const title = (item.title || '').replace(/\s+/g, ' ').trim();
      if (!title) continue;

      const authors = (item.authors || []).map(a => a.name).filter(Boolean);
      const year = item.yearPublished ? String(item.yearPublished) : null;
      const doi = item.doi ? String(item.doi).toLowerCase() : null;
      const abstract = item.abstract || '';
      const pdfUrl = item.downloadUrl || null;
      const paperUrl = item.sourceFulltextUrls?.[0] || (doi ? `https://doi.org/${doi}` : '');

      papers.push(
        normalizePaper({
          id: `core:${item.id || doi || title}`,
          title,
          authors,
          abstract,
          year,
          doi,
          paperUrl,
          pdfUrl,
          source: 'CORE',
          citationCount: item.citationCount || null,
          venue: item.publisher || 'CORE Repository',
        })
      );
    }

    return papers;
  } catch (err) {
    clearTimeout(timeoutId);
    throw err;
  }
}
