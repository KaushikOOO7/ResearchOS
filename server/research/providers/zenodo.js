/**
 * Zenodo Provider (Node.js)
 */

import { normalizePaper } from '../normalizer.js';

const USER_AGENT = 'ResearchOS/1.0 (academic-platform; contact@researchos.dev)';

export async function searchZenodo(query, maxResults = 15) {
  if (!query || !query.trim()) return [];

  const encoded = encodeURIComponent(query.trim());
  const url = `https://zenodo.org/api/records?q=${encoded}&size=${maxResults}&sort=bestmatch`;

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
    const hits = data.hits?.hits || [];
    const papers = [];

    for (const hit of hits) {
      const meta = hit.metadata || {};
      const title = (meta.title || '').replace(/\s+/g, ' ').trim();
      if (!title) continue;

      const creators = meta.creators || [];
      const authors = creators.map(c => c.name).filter(Boolean);

      let year = null;
      if (meta.publication_date) {
        year = String(meta.publication_date).slice(0, 4);
      }

      const doi = (hit.doi || meta.doi ? String(hit.doi || meta.doi).toLowerCase() : null);
      const abstract = (meta.description || '').replace(/<[^>]+>/g, ' ').trim();
      const paperUrl = hit.links?.html || (doi ? `https://doi.org/${doi}` : '');

      let pdfUrl = null;
      for (const f of (hit.files || [])) {
        if (f.key?.endsWith('.pdf')) {
          pdfUrl = f.links?.self;
          break;
        }
      }

      const resourceType = meta.resource_type?.title || 'Zenodo Publication';

      papers.push(
        normalizePaper({
          id: `zenodo:${hit.id || doi || title}`,
          title,
          authors,
          abstract,
          year,
          doi,
          paperUrl,
          pdfUrl,
          source: 'Zenodo',
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
