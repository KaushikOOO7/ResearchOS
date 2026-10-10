/**
 * PubMed Provider (Node.js)
 */

import { normalizePaper } from '../normalizer.js';

const USER_AGENT = 'ResearchOS/1.0 (academic-platform; contact@researchos.dev)';

export async function searchPubmed(query, maxResults = 15) {
  if (!query || !query.trim()) return [];

  const encoded = encodeURIComponent(query.trim());
  const apiKey = process.env.NCBI_API_KEY ? `&api_key=${process.env.NCBI_API_KEY}` : '';
  const searchUrl = `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=${encoded}&retmax=${maxResults}&retmode=json&sort=relevance${apiKey}`;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 12000);

  try {
    const sRes = await fetch(searchUrl, {
      headers: { 'User-Agent': USER_AGENT },
      signal: controller.signal,
    });
    if (!sRes.ok) {
      clearTimeout(timeoutId);
      if (sRes.status === 429) throw new Error('rate_limited');
      return [];
    }

    const sData = await sRes.json();
    const idList = sData.esearchresult?.idlist || [];
    if (!idList.length) {
      clearTimeout(timeoutId);
      return [];
    }

    const summaryUrl = `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id=${idList.join(',')}&retmode=json${apiKey}`;
    const sumRes = await fetch(summaryUrl, {
      headers: { 'User-Agent': USER_AGENT },
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (!sumRes.ok) return [];
    const sumData = await sumRes.json();
    const resultDict = sumData.result || {};
    const papers = [];

    for (const pmid of idList) {
      const doc = resultDict[pmid];
      if (!doc) continue;

      const title = (doc.title || '').replace(/\s+/g, ' ').trim();
      if (!title) continue;

      const authors = (doc.authors || []).map(a => a.name).filter(Boolean);
      const pubDate = doc.pubdate || '';
      const year = pubDate.slice(0, 4);

      let doi = null;
      for (const aid of (doc.articleids || [])) {
        if (aid.idtype === 'doi') {
          doi = aid.value?.toLowerCase();
          break;
        }
      }

      papers.push(
        normalizePaper({
          id: `pubmed:${pmid}`,
          title,
          authors,
          abstract: '',
          year: year && !isNaN(year) ? year : null,
          publishedDate: pubDate,
          doi,
          paperUrl: `https://pubmed.ncbi.nlm.nih.gov/${pmid}/`,
          source: 'PubMed',
          venue: doc.source || 'PubMed',
        })
      );
    }

    return papers;
  } catch (err) {
    clearTimeout(timeoutId);
    throw err;
  }
}
