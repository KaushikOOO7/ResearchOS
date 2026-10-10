/**
 * DBLP Computer Science Provider (Node.js)
 */

import { normalizePaper } from '../normalizer.js';

const USER_AGENT = 'ResearchOS/1.0 (academic-platform; contact@researchos.dev)';

export async function searchDblp(query, maxResults = 15) {
  if (!query || !query.trim()) return [];

  const encoded = encodeURIComponent(query.trim());
  const url = `https://dblp.org/search/publ/api?q=${encoded}&format=json&h=${maxResults}`;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 10000);

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
    const hits = data.result?.hits?.hit || [];
    const papers = [];

    for (const hit of hits) {
      const info = hit.info || {};
      const title = (info.title || '').replace(/\s+/g, ' ').trim();
      if (!title) continue;

      let authors = [];
      const authorsData = info.authors?.author;
      if (Array.isArray(authorsData)) {
        authors = authorsData.map(a => typeof a === 'string' ? a : a.text).filter(Boolean);
      } else if (authorsData) {
        authors = [typeof authorsData === 'string' ? authorsData : authorsData.text].filter(Boolean);
      }

      const year = info.year ? String(info.year) : null;
      const venue = info.venue || null;
      const doi = info.doi ? String(info.doi).toLowerCase() : null;
      const paperUrl = info.ee || (doi ? `https://doi.org/${doi}` : info.url || '');

      papers.push(
        normalizePaper({
          id: `dblp:${doi || info.key || title}`,
          title,
          authors,
          abstract: '',
          year,
          doi,
          paperUrl,
          source: 'DBLP',
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
