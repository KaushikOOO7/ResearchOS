/**
 * ResearchOS Paper Deduplicator (Node.js)
 */

function titleFingerprint(title) {
  return String(title || '').toLowerCase().replace(/[^a-z0-9]/g, '');
}

function titleTokens(title) {
  const words = String(title || '').toLowerCase().match(/[a-z0-9]{3,}/g) || [];
  const stop = new Set(['the', 'and', 'for', 'with', 'from', 'that', 'this', 'via', 'using', 'into']);
  return new Set(words.filter(w => !stop.has(w)));
}

function areFuzzyMatch(t1, t2, threshold = 0.85) {
  const s1 = titleTokens(t1);
  const s2 = titleTokens(t2);
  if (s1.size === 0 || s2.size === 0) return false;
  let intersection = 0;
  for (const w of s1) {
    if (s2.has(w)) intersection++;
  }
  const union = new Set([...s1, ...s2]).size;
  return union > 0 && (intersection / union) >= threshold;
}

function mergeRecords(primary, secondary) {
  if ((secondary.abstract || '').length > (primary.abstract || '').length) {
    primary.abstract = secondary.abstract;
  }
  if (primary.citationCount === null && secondary.citationCount !== null) {
    primary.citationCount = secondary.citationCount;
  }
  if (!primary.pdfUrl && secondary.pdfUrl) {
    primary.pdfUrl = secondary.pdfUrl;
  }
  if (!primary.doi && secondary.doi) {
    primary.doi = secondary.doi;
  }
  if (!primary.arxivId && secondary.arxivId) {
    primary.arxivId = secondary.arxivId;
  }
  if (!primary.venue && secondary.venue) {
    primary.venue = secondary.venue;
  }
  if (secondary.authors.length > primary.authors.length) {
    primary.authors = secondary.authors;
  }
  if (secondary.source && !primary.source.includes(secondary.source)) {
    primary.source = `${primary.source}, ${secondary.source}`;
  }
  return primary;
}

export function deduplicatePapers(papers) {
  const seenDois = new Map();
  const seenArxiv = new Map();
  const seenFp = new Map();
  const unique = [];

  for (const paper of papers) {
    if (!paper || !paper.title) continue;

    let matched = null;

    if (paper.doi && seenDois.has(paper.doi)) {
      matched = seenDois.get(paper.doi);
    }

    if (!matched && paper.arxivId && seenArxiv.has(paper.arxivId)) {
      matched = seenArxiv.get(paper.arxivId);
    }

    const fp = titleFingerprint(paper.title);
    if (!matched && fp && seenFp.has(fp)) {
      matched = seenFp.get(fp);
    }

    if (!matched && paper.title.length > 15) {
      for (const existing of unique) {
        if (areFuzzyMatch(paper.title, existing.title)) {
          matched = existing;
          break;
        }
      }
    }

    if (matched) {
      mergeRecords(matched, paper);
    } else {
      unique.push(paper);
      if (paper.doi) seenDois.set(paper.doi, paper);
      if (paper.arxivId) seenArxiv.set(paper.arxivId, paper);
      if (fp) seenFp.set(fp, paper);
    }
  }

  return unique;
}
