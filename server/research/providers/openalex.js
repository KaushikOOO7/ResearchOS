/**
 * OpenAlex Provider (Node.js)
 */

import { normalizePaper } from '../normalizer.js';

const USER_AGENT = 'ResearchOS/1.0 (academic-platform; contact@researchos.dev)';

export async function searchOpenAlex(query, maxResults = 30) {
  if (!query || !query.trim()) return [];

  const encoded = encodeURIComponent(query.trim());
  const url = `https://api.openalex.org/works?search=${encoded}&per-page=${maxResults}&select=id,title,publication_year,publication_date,doi,primary_location,authorships,cited_by_count,abstract_inverted_index`;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 12000);

  const headers = { 'User-Agent': USER_AGENT, Accept: 'application/json' };
  const apiKey = process.env.OPENALEX_API_KEY;
  if (apiKey) headers['api_key'] = apiKey;

  try {
    const res = await fetch(url, { headers, signal: controller.signal });
    clearTimeout(timeoutId);

    if (!res.ok) {
      if (res.status === 429) throw new Error('rate_limited');
      return [];
    }

    const data = await res.json();
    const results = data.results || [];
    const papers = [];

    for (const item of results) {
      const title = (item.title || '').replace(/\s+/g, ' ').trim();
      if (!title) continue;

      let abstract = '';
      if (item.abstract_inverted_index) {
        const words = [];
        for (const [w, positions] of Object.entries(item.abstract_inverted_index)) {
          for (const pos of positions) words.push([pos, w]);
        }
        words.sort((a, b) => a[0] - b[0]);
        abstract = words.map(x => x[1]).join(' ');
      }

      const authors = (item.authorships || []).map(a => a.author?.display_name).filter(Boolean);
      const doi = item.doi ? item.doi.replace(/^https?:\/\/doi\.org\//, '') : null;
      const pdfUrl = item.primary_location?.pdf_url || null;
      const paperUrl = item.primary_location?.landing_page_url || item.id || (doi ? `https://doi.org/${doi}` : '');
      const venue = item.primary_location?.source?.display_name || null;

      papers.push(
        normalizePaper({
          id: `openalex:${item.id ? item.id.split('/').pop() : title}`,
          title,
          authors,
          abstract,
          year: item.publication_year ? String(item.publication_year) : null,
          publishedDate: item.publication_date || null,
          doi,
          paperUrl,
          pdfUrl,
          source: 'OpenAlex',
          citationCount: item.cited_by_count || null,
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
