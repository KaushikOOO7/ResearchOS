/**
 * ResearchOS API service.
 *
 * Every backend call lives here — components never talk to axios directly.
 * Requests go to `/api/...` (relative) and are proxied to the FastAPI server
 * by the Vite dev server, so the same build works locally, behind a proxy,
 * and inside hosted preview environments.
 */

import axios from "axios";

const baseURL = import.meta.env.VITE_API_BASE_URL || "/api";

export const http = axios.create({
  baseURL,
  timeout: 180_000, // PDF download + AI analysis can legitimately take a while
  headers: { "Content-Type": "application/json" },
});

/** Error shape ResearchOS components can rely on. */
export class ApiError extends Error {
  constructor({ message, code = "error", status = 0, retryable = false }) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.retryable = retryable;
  }
}

const STATUS_FALLBACKS = {
  400: "The request was rejected. Please check your input.",
  403: "The publisher blocked automated access to this resource.",
  404: "This resource is no longer available. Run the search again.",
  413: "That paper is too large for the analysis pipeline.",
  422: "The request could not be processed. Try a different paper or query.",
  429: "The AI service is rate limiting requests. Please try again in a moment.",
  500: "Something went wrong on the ResearchOS server.",
  502: "A service ResearchOS depends on returned an unexpected response.",
  503: "A required service is temporarily unavailable. Please try again shortly.",
  504: "The request timed out. Please try again.",
};

/** Convert any axios/network failure into a friendly, structured ApiError. */
export function toApiError(error) {
  if (error instanceof ApiError) return error;

  if (error?.code === "ECONNABORTED" || error?.code === "ETIMEDOUT") {
    return new ApiError({
      message: "The request took too long. Please try again.",
      code: "timeout",
      retryable: true,
    });
  }

  const response = error?.response;
  if (!response) {
    return new ApiError({
      message:
        "Could not reach the ResearchOS backend. Make sure the API server is running.",
      code: "network_error",
      retryable: true,
    });
  }

  // FastAPI puts our ErrorResponse inside `detail`.
  const detail = response.data?.detail ?? response.data ?? {};
  const message =
    (typeof detail === "string" ? detail : detail.message) ||
    STATUS_FALLBACKS[response.status] ||
    "Something went wrong. Please try again.";

  return new ApiError({
    message,
    code: (typeof detail === "object" && detail.code) || `http_${response.status}`,
    status: response.status,
    retryable: Boolean(typeof detail === "object" && detail.retryable),
  });
}

/** GET /health — service + capability status. */
export async function getHealth() {
  try {
    const { data } = await http.get("/health");
    return data;
  } catch (error) {
    throw toApiError(error);
  }
}

/**
 * POST /research — multi-source search + ranking.
 * @param {string} query research idea
 * @param {{limit?: number, sources?: string[], yearFrom?: number|null, openAccessOnly?: boolean}} options
 */
export async function searchResearch(query, options = {}) {
  const payload = { query };
  if (options.limit) payload.limit = options.limit;
  if (options.sources?.length) payload.sources = options.sources;
  if (options.yearFrom) payload.year_from = options.yearFrom;
  if (options.openAccessOnly) payload.open_access_only = true;

  try {
    const { data } = await http.post("/research", payload);
    return data;
  } catch (error) {
    throw toApiError(error);
  }
}

/** POST /analyze-paper — download, extract and analyse one paper. */
export async function analyzePaper(paper) {
  const payload = {
    title: paper.title,
    abstract: paper.abstract || "",
    pdf_url: paper.pdf_url || "",
    paper_url: paper.paper_url || "",
    doi: paper.doi || "",
    arxiv_id: paper.arxiv_id || "",
    source: paper.source || "",
    year: paper.year ?? null,
    authors: paper.authors || [],
    paper_id: paper.id || "",
  };

  try {
    const { data } = await http.post("/analyze-paper", payload);
    return data;
  } catch (error) {
    throw toApiError(error);
  }
}

/** GET /papers/{id} — paper detail for papers from a recent search. */
export async function getPaper(paperId) {
  try {
    const { data } = await http.get(`/papers/${encodeURIComponent(paperId)}`);
    return data.paper;
  } catch (error) {
    throw toApiError(error);
  }
}

/* --------------------------------------------------------------------------
 * Roadmap endpoints (implemented in later phases) — declared here so the
 * frontend contract is explicit and components never inline URLs.
 * ------------------------------------------------------------------------ */

export const ROADMAP_ENDPOINTS = {
  comparePapers: "POST /compare-papers",
  researchGap: "POST /research-gap",
  generateProject: "POST /generate-project",
};
