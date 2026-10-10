/**
 * DataCite Provider (Node.js)
 */

import { normalizePaper } from '../normalizer.js';

const USER_AGENT = 'ResearchOS/1.0 (academic-platform; contact@researchos.dev)';

export async function searchDataCite(query, maxResults = 15) {
  if (!query || !query.trim()) return [];

  const encoded = encodeURIComponent(query.trim());
  const url = `https://api.datacite.org/dois?query=${encoded}&page[size]=${maxResults}`;

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
    const items = data.data || [];
    const papers = [];

    for (const item of items) {
      const attr = item.attributes || {};
      const titles = attr.titles || [];
      const title = titles[0]?.title ? titles[0].title.replace(/\s+/g, ' ').trim() : '';
      if (!title) continue;

      const creators = attr.creators || [];
      const authors = creators.map(c => c.name).filter(Boolean);

      const year = attr.publicationYear ? String(attr.publicationYear) : null;
      const doi = attr.doi ? String(attr.doi).toLowerCase() : null;
      const abstract = attr.descriptions?.[0]?.description || '';
      const paperUrl = attr.url || (doi ? `https://doi.org/${doi}` : '');
      const resourceType = attr.types?.resourceTypeGeneral || 'DataCite Record';

      papers.push(
        normalizePaper({
          id: `datacite:${doi || title}`,
          title,
          authors,
          abstract,
          year,
          doi,
          paperUrl,
          source: 'DataCite',
          citationCount: attr.citationCount || null,
          venue: resourceType,
        })
      );
    }

    return papers;
  } catch (err) {
    clearTimeout(timeoutId);
    throw err;
  }
}
