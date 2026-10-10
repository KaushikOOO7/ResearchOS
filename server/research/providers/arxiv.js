/**
 * arXiv Provider (Node.js)
 */

import { normalizePaper } from '../normalizer.js';

const USER_AGENT = 'ResearchOS/1.0 (academic-platform; contact@researchos.dev)';

export async function searchArxiv(query, maxResults = 30) {
  if (!query || !query.trim()) return [];

  const encoded = encodeURIComponent(query.trim());
  const url = `https://export.arxiv.org/api/query?search_query=all:${encoded}&start=0&max_results=${maxResults}&sortBy=relevance&sortOrder=descending`;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 12000);

  try {
    const res = await fetch(url, {
      headers: { 'User-Agent': USER_AGENT, Accept: 'application/atom+xml' },
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (!res.ok) {
      if (res.status === 429) throw new Error('rate_limited');
      return [];
    }

    const xml = await res.text();
    const papers = [];
    const entryRegex = /<entry>([\s\S]*?)<\/entry>/g;
    let match;

    while ((match = entryRegex.exec(xml)) !== null) {
      const entry = match[1];
      const titleMatch = /<title[^>]*>([\s\S]*?)<\/title>/.exec(entry);
      const summaryMatch = /<summary[^>]*>([\s\S]*?)<\/summary>/.exec(entry);
      const publishedMatch = /<published[^>]*>([\s\S]*?)<\/published>/.exec(entry);
      const idMatch = /<id[^>]*>([\s\S]*?)<\/id>/.exec(entry);

      const title = titleMatch ? titleMatch[1].replace(/\s+/g, ' ').trim() : '';
      const abstract = summaryMatch ? summaryMatch[1].replace(/\s+/g, ' ').trim() : '';
      const published = publishedMatch ? publishedMatch[1].trim() : '';
      const paperUrl = idMatch ? idMatch[1].trim() : '';

      if (!title) continue;

      const authors = [];
      const authorRegex = /<author>[\s\S]*?<name>([\s\S]*?)<\/name>[\s\S]*?<\/author>/g;
      let aMatch;
      while ((aMatch = authorRegex.exec(entry)) !== null) {
        authors.push(aMatch[1].trim());
      }

      const arxivId = paperUrl.includes('/abs/') ? paperUrl.split('/abs/').pop() : '';
      const pdfUrl = arxivId ? `https://arxiv.org/pdf/${arxivId}` : null;

      papers.push(
        normalizePaper({
          id: `arxiv:${arxivId || title}`,
          title,
          authors,
          abstract,
          publishedDate: published,
          arxivId,
          paperUrl,
          pdfUrl,
          source: 'arXiv',
          venue: 'arXiv preprint',
        })
      );
    }

    return papers;
  } catch (err) {
    clearTimeout(timeoutId);
    throw err;
  }
}
