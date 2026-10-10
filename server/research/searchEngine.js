/**
 * ResearchOS Unified Multi-Provider Academic Search Engine (Node.js)
 */

import { searchArxiv } from './providers/arxiv.js';
import { searchOpenAlex } from './providers/openalex.js';
import { searchCrossref } from './providers/crossref.js';
import { searchSemanticScholar } from './providers/semanticScholar.js';
import { searchEuropePmc } from './providers/europePmc.js';
import { searchPubmed } from './providers/pubmed.js';
import { searchCore } from './providers/core.js';
import { searchDataCite } from './providers/dataCite.js';
import { searchZenodo } from './providers/zenodo.js';
import { searchDblp } from './providers/dblp.js';
import { deduplicatePapers } from './deduplicator.js';
import { rankPapers } from './ranking.js';
import { getOutboundPortals } from './providers/outboundPortals.js';

export async function executeUnifiedAcademicSearch(query, maxResults = 30) {
  const cleanQ = String(query || '').trim();
  if (!cleanQ) {
    return {
      status: 'error',
      message: 'Query cannot be empty',
      count: 0,
      papers: [],
      providerStatus: {},
      providerBreakdown: {},
    };
  }

  const providers = [
    { key: 'arxiv', name: 'arXiv', fn: () => searchArxiv(cleanQ, 35) },
    { key: 'openalex', name: 'OpenAlex', fn: () => searchOpenAlex(cleanQ, 35) },
    { key: 'crossref', name: 'Crossref', fn: () => searchCrossref(cleanQ, 25) },
    { key: 'semanticScholar', name: 'Semantic Scholar', fn: () => searchSemanticScholar(cleanQ, 20) },
    { key: 'europePmc', name: 'Europe PMC', fn: () => searchEuropePmc(cleanQ, 20) },
    { key: 'pubmed', name: 'PubMed', fn: () => searchPubmed(cleanQ, 15) },
    { key: 'core', name: 'CORE', fn: () => searchCore(cleanQ, 15) },
    { key: 'dataCite', name: 'DataCite', fn: () => searchDataCite(cleanQ, 15) },
    { key: 'zenodo', name: 'Zenodo', fn: () => searchZenodo(cleanQ, 15) },
    { key: 'dblp', name: 'DBLP', fn: () => searchDblp(cleanQ, 15) },
  ];

  const providerStatus = {};
  const providerBreakdown = {};
  const allCandidates = [];

  // Execute all providers concurrently with Promise.allSettled
  const results = await Promise.allSettled(providers.map(p => p.fn()));

  results.forEach((res, idx) => {
    const prov = providers[idx];
    if (res.status === 'fulfilled') {
      const papers = res.value || [];
      if (papers.length > 0) {
        providerStatus[prov.key] = 'success';
        providerBreakdown[prov.name] = papers.length;
        allCandidates.push(...papers);
      } else {
        providerStatus[prov.key] = 'no_records';
        providerBreakdown[prov.name] = 0;
      }
    } else {
      const err = res.reason;
      const msg = String(err?.message || err);
      if (msg.includes('rate_limited') || msg.includes('429')) {
        providerStatus[prov.key] = 'rate_limited';
      } else if (msg.includes('authentication_required') || msg.includes('401') || msg.includes('403')) {
        providerStatus[prov.key] = 'authentication_required';
      } else if (msg.includes('timeout') || err?.name === 'AbortError') {
        providerStatus[prov.key] = 'timeout';
      } else {
        providerStatus[prov.key] = 'unavailable';
      }
      providerBreakdown[prov.name] = 0;
    }
  });

  // 1. Deduplicate across providers
  const uniquePapers = deduplicatePapers(allCandidates);

  // 2. Rank deterministically and select Top 30
  const topPapers = rankPapers(uniquePapers, cleanQ, maxResults);

  return {
    status: 'success',
    query: cleanQ,
    totalDiscovered: allCandidates.length,
    uniqueAfterDedup: uniquePapers.length,
    count: topPapers.length,
    providerStatus,
    providerBreakdown,
    providersQueried: providers.map(p => p.name),
    providersSucceeded: Object.keys(providerBreakdown).filter(k => providerBreakdown[k] > 0),
    outboundPortals: getOutboundPortals(cleanQ),
    papers: topPapers,
  };
}
