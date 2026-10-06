/** Presentation helpers — pure functions, no side effects. */

export const NOT_AVAILABLE = "Not available";

/** Format a citation count, or return null when the metadata lacks it. */
export function formatCitations(count) {
  if (count === null || count === undefined) return null;
  if (count >= 1000) return `${(count / 1000).toFixed(1).replace(/\.0$/, "")}k`;
  return String(count);
}

/** Round a 0-100 score for display. */
export function formatScore(score) {
  if (score === null || score === undefined) return "—";
  return `${Math.round(score)}`;
}

/** Human labels for the ranking components. */
export const SCORE_LABELS = {
  relevance: "Relevance",
  quality_quality: "Quality",
  quality: "Quality",
  citation: "Impact",
  recency: "Recency",
  source: "Source",
  overall: "Overall",
};

/** Colour class for a 0-100 score bar. */
export function scoreTone(score) {
  if (score === null || score === undefined) return "muted";
  if (score >= 75) return "high";
  if (score >= 50) return "medium";
  return "low";
}

/**
 * Only allow http(s) links to reach the DOM. Titles/URLs come from external
 * APIs, so this is a defence-in-depth measure alongside React's escaping.
 */
export function safeExternalUrl(url) {
  if (typeof url !== "string" || !url.trim()) return null;
  try {
    const parsed = new URL(url, window.location.origin);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return null;
    return parsed.toString();
  } catch {
    return null;
  }
}

/** Truncate long text for cards (full text is shown in the detail view). */
export function truncate(text, max = 320) {
  if (!text) return "";
  const clean = String(text).trim();
  if (clean.length <= max) return clean;
  const cut = clean.slice(0, max);
  const boundary = cut.lastIndexOf(". ");
  return `${boundary > max * 0.5 ? cut.slice(0, boundary + 1) : cut}…`;
}

/** Elapsed seconds label for progress states. */
export function formatElapsed(seconds) {
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `${minutes}m ${String(rest).padStart(2, "0")}s`;
}

/** "2024-03-01T..." -> "2024-03-01 12:04" (local time). */
export function formatTimestamp(isoString) {
  if (!isoString) return NOT_AVAILABLE;
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return NOT_AVAILABLE;
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Paper identifier line for cards ("arXiv 2401.01234 · DOI 10.1000/x"). */
export function identifierLabel(paper) {
  const parts = [];
  if (paper.arxiv_id) parts.push(`arXiv ${paper.arxiv_id}`);
  if (paper.doi) parts.push(`DOI ${paper.doi}`);
  return parts;
}
