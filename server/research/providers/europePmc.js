/**
 * Europe PMC Provider (Node.js)
 */

import { normalizePaper } from '../normalizer.js';

const USER_AGENT = 'ResearchOS/1.0 (academic-platform; contact@researchos.dev)';

export async function searchEuropePmc(query, maxResults = 20) {
  if (!query || !query.trim()) return [];

  const encoded = encodeURIComponent(query.trim());
  const url = `https://europepmc.org/RestfulWebService/rest/search?query=${encoded}&format=json&pageSize=${maxResults}&resultType=core`;

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
    const results = data.resultList?.result || [];
    const papers = [];

    for (const item of results) {
      const title = (item.title || '').replace(/\s+/g, ' ').trim();
      if (!title) continue;

      const authorsStr = item.authorString || '';
      const authors = authorsStr.split(',').map(a => a.trim()).filter(Boolean);

      const year = item.pubYear ? String(item.pubYear) : null;
      const doi = item.doi ? String(item.doi).toLowerCase() : null;
      const pmid = item.pmid;
      const pmcid = item.pmcid;
      const abstract = item.abstractText || '';
      const venue = item.journalTitle || null;
      const citations = item.citedByCount || null;

      const pdfUrl = pmcid ? `https://europepmc.org/articles/${pmcid}?pdf=render` : null;
      const paperUrl = pmid ? `https://europepmc.org/article/MED/${pmid}` : (doi ? `https://doi.org/${doi}` : '');

      papers.push(
        normalizePaper({
          id: `europepmc:${pmcid || pmid || doi || title}`,
          title,
          authors: authors.slice(0, 6),
          abstract,
          year,
          doi,
          paperUrl,
          pdfUrl,
          source: 'Europe PMC',
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
