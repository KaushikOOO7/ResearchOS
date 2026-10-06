<div align="center">

# ResearchOS

**AI Research Intelligence Platform**

Turn a research idea into ranked literature, structured paper analyses, limitations,
research gaps and new research directions.

`React 19` · `Vite` · `FastAPI` · `Python` · `Google Gemini` · `arXiv / OpenAlex / Crossref / Semantic Scholar / PubMed`

</div>

---

## Overview

ResearchOS is a research intelligence workspace, not a paper search box. You give it an
idea — *"Graph neural networks for drug discovery"* — and it:

1. **understands** the query (keyphrases, acronym expansion, domain and recency intent),
2. **searches several academic sources in parallel** and collects a candidate pool,
3. **deduplicates** the same paper arriving from multiple providers,
4. **ranks** candidates with an explainable, multi-component score,
5. returns the **Top 30 papers** with real metadata, PDF/source links and score breakdowns,
6. **analyses a paper on demand** — PDF download, text extraction, section detection, then a
   structured AI analysis that separates *what the paper states* from *what the model infers*,
7. surfaces **limitations, failure modes, author-stated gaps, AI-inferred gaps, improvements
   and new research directions**.

The product journey the interface is built around:

```
Idea → Research landscape → Top 30 papers → Select a paper → AI analysis
     → Limitations → Research gaps → New research direction → Project
```

## Problem statement

Going from an idea to a defensible research direction is slow and fragmented:

- literature is spread across arXiv, Crossref, OpenAlex, Semantic Scholar and PubMed,
- the same paper appears many times with conflicting/incomplete metadata,
- reading enough papers to understand the state of the art takes weeks,
- limitations and research gaps are buried in discussion sections,
- generic AI summaries hallucinate datasets, metrics and results — unacceptable in research.

## Solution

A single, honest pipeline: real multi-source retrieval, transparent ranking, and a
provenance-labelled AI analyst. ResearchOS never fabricates papers, citations, datasets,
metrics or analysis. Missing data is shown as **"Not available"**, unstated content is
reported as **"Not stated in the provided paper."**, and every AI claim is labelled
**"From paper"** (author-stated) or **"AI-inferred"**.

## Features

### Implemented (Phases 1–3)

| Area | What works |
| --- | --- |
| Multi-source retrieval | arXiv, OpenAlex, Crossref, Semantic Scholar (with API key), PubMed (biomedical queries), queried in parallel with per-provider timeouts and failure isolation |
| Query understanding | tokenisation, keyphrases, acronym expansion (`GNN → graph neural network`), biomedical detection, recency/year intent |
| Candidate pool | configurable target (~90 candidates by default), per-provider budget allocation |
| Deduplication | DOI → arXiv id → normalised title → fuzzy title matching (character + token containment) with metadata merging |
| Ranking | BM25 relevance (field-weighted), metadata quality, log-scaled citation impact, exponential recency decay, source reliability, configurable weights, per-paper weight renormalisation |
| Explainability | every paper exposes a score breakdown *and* a "why this rank?" panel |
| Paper cards | rank, title, authors, year, venue, source(s), relevance %, citations (or "Not available"), quality label, PDF/source links, save, analyse |
| PDF pipeline | SSRF-guarded download, size/page limits, per-page extraction isolation, cleaning, section detection, scanned-PDF detection |
| AI analysis | structured 14-key output, strict JSON validation, JSON repair retry, bounded exponential backoff, fallback model, friendly error mapping |
| Analysis dashboard | 13 numbered sections, provenance badges, gap panel (author-stated vs AI-inferred), metadata panel (pages, characters, sections, model) |
| Workspace (local) | saved papers, saved analyses, recent searches (browser-persisted until the DB phase) |
| Observability | `[ResearchOS] …` structured logs for every pipeline stage; no secrets ever logged |
| Testing | 77 backend tests: utils, providers (realistic fixtures), dedup, ranking, PDF/SSRF, schemas, analysis flow, API contract, full pipeline integration |

### Roadmap

- **Phase 4** — research-gap engine across papers, multi-paper comparison, novelty analysis, project idea generator.
- **Phase 5** — section-aware chunking + embeddings, RAG over long papers, page-level evidence citations for every AI claim.
- **Phase 6** — server-side workspace (projects, notes, history), literature review generator, exports (Markdown/PDF/DOCX).
- **Phase 7** — PostgreSQL persistence, authentication, production hardening, deployment.

## Architecture

```
                    ┌──────────────────────────── React (Vite) ───────────────────────────┐
                    │  Research view · Analysis dashboard · Papers · Workspace · About     │
                    │  services/api.js  (relative /api calls)   hooks/ (state machines)    │
                    └───────────────────────────────┬──────────────────────────────────────┘
                                        Vite dev proxy │  /api → 127.0.0.1:8000
                    ┌───────────────────────────────▼──────────────────────────────────────┐
                    │                        FastAPI (backend/app)                         │
                    │  api/research.py · api/analysis.py · api/health.py · CORS + errors   │
                    └───────┬─────────────────────────────────────────────┬────────────────┘
                            │                                             │
        ┌───────────────────▼───────────────────┐        ┌────────────────▼─────────────────┐
        │           research/ pipeline          │        │        analysis/ pipeline        │
        │ query_understanding → sources →       │        │ pdf_extractor (SSRF-safe) →      │
        │ deduplicator → ranker → search_engine │        │ text_cleaner → section detection │
        │ (arxiv, openalex, crossref,           │        │ → paper_analyzer (prompt+JSON)   │
        │  semantic_scholar, pubmed)            │        │ → services/gemini_client (retry) │
        └───────────────────┬───────────────────┘        └────────────────┬─────────────────┘
                            │                                             │
                  Academic provider APIs                        Google Gemini API
```

### Ranking methodology

```
overall = w_rel · relevance + w_qual · quality + w_cit · citation + w_rec · recency + w_src · source
defaults:   0.50            0.20           0.15            0.10          0.05
```

| Component | How it is computed |
| --- | --- |
| **Relevance** | Okapi BM25 over field-weighted metadata (title ×3, keywords ×2, subjects ×1.5, abstract ×1, venue ×0.5) + query-topic coverage factor + exact-phrase bonuses; scaled so the best candidate of the result set scores 100 |
| **Quality** | Metadata-completeness heuristic: abstract depth, DOI, published venue, document type, cross-source corroboration, author list. *Not* a judgement of scientific merit |
| **Citation impact** | `log(1 + citations)`, saturating at 1,000 citations. `null` when no provider reports citations |
| **Recency** | 100 for papers ≤1 year old, exponential decay afterwards (7-year half-life, floor 15) |
| **Source reliability** | Metadata openness/completeness of the provider (OpenAlex 92, PubMed 90, Crossref 88, Semantic Scholar 85, arXiv 82) |

Weights are configurable (`RANK_WEIGHT_*`). When a component is unavailable for a paper
(for example an arXiv-only record with no citation count), its weight is **redistributed**
instead of being scored as zero — a paper is never punished for missing metadata.

### AI analysis pipeline

```
POST /analyze-paper
  1. validate the paper reference
  2. download the PDF       → SSRF validation, size cap, timeout, %PDF magic check
  3. extract text           → pypdf, per-page isolation, cleaning, section detection
  4. flag scanned PDFs      → clearly reported, then falls back to title + abstract
  5. build a section-labelled document, truncate at a safe character budget
  6. Gemini structured call → JSON mode, retries (2s/5s/10s + jitter), optional fallback model
  7. validate + normalise   → Pydantic schema, JSON repair retry, placeholder clean-up
  8. return analysis + provenance (pages, characters, sections, model, warnings)
```

The analysis contract is exactly:

```json
{
  "research_problem": "", "existing_approach": "", "proposed_method": "",
  "architecture": "", "dataset": "", "model_algorithm": "", "results": "",
  "limitations": [], "additional_technical_limitations": [],
  "why_approach_may_fail": [],
  "research_gap": { "author_stated_gaps": [], "ai_inferred_gaps": [] },
  "possible_improvements": [], "new_research_direction": [],
  "overall_assessment": ""
}
```

## Tech stack

| Layer | Technology |
| --- | --- |
| Frontend | React 19, Vite 8, JavaScript/JSX, Axios, lucide-react, hand-written CSS (no UI framework) |
| Backend | Python 3.11+, FastAPI, Uvicorn, Pydantic v2, requests, python-dotenv |
| AI | Google Gemini via the `google-genai` SDK (JSON mode, retries, fallback model) |
| PDF | pypdf |
| Testing | pytest (+ FastAPI TestClient) |
| Sources | arXiv Atom API, OpenAlex, Crossref, Semantic Scholar Graph API, NCBI PubMed E-utilities |

## Folder structure

```
ResearchOS/
├── backend/
│   ├── app/
│   │   ├── main.py                 # app factory, CORS, routers, error handlers
│   │   ├── config.py               # env-driven Settings + ranking weights
│   │   ├── api/                    # research.py, analysis.py, health.py, helpers.py
│   │   ├── research/               # arxiv, openalex, crossref, semantic_scholar, pubmed,
│   │   │                           # query_understanding, deduplicator, ranker, search_engine
│   │   ├── analysis/               # pdf_extractor, text_cleaner, paper_analyzer
│   │   ├── models/paper.py         # canonical Paper schema + stable ids
│   │   ├── schemas/                # request/response + analysis contracts
│   │   ├── services/               # gemini_client, analysis_service, cache, paper_store
│   │   └── utils/                  # text, http (retries + SSRF guard), logging
│   ├── tests/                      # 77 tests incl. full-pipeline integration
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/             # layout, search, papers, analysis, state
│   │   ├── pages/                  # ResearchPage, PapersPage, WorkspacePage, AboutPage
│   │   ├── hooks/                  # useResearch, usePaperAnalysis, useWorkspace, useHealth
│   │   ├── services/api.js         # every backend call in one place
│   │   ├── utils/format.js
│   │   ├── App.jsx · App.css · index.css · main.jsx
│   ├── vite.config.js              # /api proxy → backend, preview-safe dev server
│   └── package.json
└── README.md
```

## Installation

Requirements: **Python 3.11+**, **Node.js 18+**, internet access (academic APIs).

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then add your GEMINI_API_KEY (optional for search)
uvicorn app.main:app --reload --port 8000
```

- API root: <http://127.0.0.1:8000/>
- Interactive docs: <http://127.0.0.1:8000/docs>

### Frontend

```bash
cd frontend
npm install
npm run dev                        # http://localhost:5173
```

The dev server proxies `/api/*` to `http://127.0.0.1:8000`, so no CORS setup is needed in
development and no localhost URL is hardcoded in the frontend.

### Tests

```bash
cd backend
.venv/bin/python -m pytest         # 77 tests, includes a mocked full-pipeline run
```

## Environment variables

All variables live in `backend/.env` (gitignored). Only the Gemini key is required for AI
analysis; search works without any key.

| Variable | Purpose |
| --- | --- |
| `GEMINI_API_KEY` | Enables AI analysis (never exposed to the frontend) |
| `GEMINI_MODEL` / `GEMINI_FALLBACK_MODEL` | Primary + fallback model |
| `GEMINI_MAX_OUTPUT_TOKENS`, `GEMINI_TEMPERATURE` | Generation controls |
| `OPENALEX_EMAIL`, `CROSSREF_EMAIL`, `CONTACT_EMAIL` | Polite-pool identification (recommended) |
| `SEMANTIC_SCHOLAR_API_KEY` | Enables the Semantic Scholar provider |
| `PUBMED_ENABLED`, `NCBI_API_KEY`, `PUBMED_EMAIL` | PubMed provider controls |
| `RESEARCH_TARGET_CANDIDATES`, `RESEARCH_MAX_RESULTS` | Candidate pool size and returned Top-N |
| `PROVIDER_TIMEOUT_SECONDS`, `SEARCH_DEADLINE_SECONDS` | Retrieval time budgets |
| `RANK_WEIGHT_{RELEVANCE,QUALITY,CITATION,RECENCY,SOURCE}` | Ranking weights |
| `PDF_MAX_BYTES`, `PDF_MAX_PAGES`, `PDF_DOWNLOAD_TIMEOUT`, `ANALYSIS_MAX_CHARS` | PDF/analysis limits |
| `CORS_ORIGINS`, `CORS_ORIGIN_REGEX` | Allowed frontend origins |
| `LOG_LEVEL`, `ENVIRONMENT` | Observability |

## API documentation

| Endpoint | Description |
| --- | --- |
| `GET /` | Service metadata and endpoint index |
| `GET /health` | Health + capability report (which providers and AI are configured, plus an outbound-connectivity preflight so a blocked-egress deployment explains itself) |
| `POST /research` | `{query, limit?, sources?, year_from?, open_access_only?}` → ranked papers, query analysis, pipeline stats, per-source status, ranking notes |
| `POST /analyze-paper` | `{title, abstract, pdf_url, ...}` → structured analysis + provenance metadata |
| `GET /papers/{paper_id}` | Paper detail for papers from a recent search |

Errors use a consistent envelope and never leak stack traces:

```json
{ "detail": { "status": "error", "code": "rate_limited",
              "message": "The AI service is rate limiting requests right now…",
              "retryable": true } }
```

`POST /research` response (abridged):

```json
{
  "status": "success",
  "message": null,
  "query": "Graph neural networks for drug discovery",
  "query_analysis": { "terms": ["graph", "neural", "networks", "drug", "discovery"],
                      "acronyms": { "gnn": "graph neural network" },
                      "is_biomedical": true, "notes": ["Biomedical signal detected — PubMed included as a source"] },
  "stats": { "candidates_collected": 121, "duplicates_removed": 31, "returned": 30,
             "providers_succeeded": 4, "elapsed_ms": 8340 },
  "sources": [ { "name": "OpenAlex", "ok": true, "result_count": 45, "elapsed_ms": 1204 } ],
  "weights": { "relevance": 0.5, "quality": 0.2, "citation": 0.15, "recency": 0.1, "source": 0.05 },
  "papers": [ { "rank": 1, "title": "…", "relevance_score": 100, "quality_score": 82,
                "citation_score": 61, "overall_score": 89.4, "quality_label": "High",
                "score_explanations": { "overall": "Overall 89/100 — weighted over …" } } ]
}
```

## Error handling

| Failure | Behaviour |
| --- | --- |
| Provider down / network error | That source is skipped, the search continues, and the UI shows which providers failed |
| Empty result set | Explained with an actionable message plus per-source diagnostics |
| Missing `GEMINI_API_KEY` | `/health` reports it and the UI warns before you click Analyse; the endpoint returns a clear 503 |
| Gemini 429 / 5xx / timeout | Bounded retries (2s → 5s → 10s + jitter), then the fallback model |
| Invalid API key / unknown model | Not retried; clear message, no key material in logs or responses |
| Malformed AI JSON | One repair attempt, then a friendly "could not read the analysis" error |
| Scanned/encrypted/oversized PDF | Specific, user-facing message; scanned PDFs fall back to the abstract and say so |
| No outbound internet (hosted sandbox, corporate proxy) | `/health` probes a provider endpoint (cached 60s) and the UI says plainly that academic sources cannot be reached here instead of showing a misleading "no results" |
| Unhandled server error | Logged in full server-side, returned as a generic retryable message |

## Observability

```
[ResearchOS] Search started
[ResearchOS] Query: Graph neural networks for drug discovery
[ResearchOS] Query understanding: Expanded acronyms: GNN → graph neural network
[ResearchOS] OpenAlex results: 45 (1204 ms)
[ResearchOS] arXiv results: 38 (2210 ms)
[ResearchOS] Crossref failed: ProviderError: [Crossref] network error: SSLError
[ResearchOS] Candidates collected: 121
[ResearchOS] Duplicates removed: 31 (from 121 candidates -> 90 unique)
[ResearchOS] Ranking complete — top score 89.4
[ResearchOS] Final Top 30 generated
[ResearchOS] PDF extraction started
[ResearchOS] PDF extraction completed — 14 pages, 41203 characters, 7 sections
[ResearchOS] AI analysis started
[ResearchOS] AI analysis completed
```

## Research integrity

- No fabricated papers, authors, citations, metrics, datasets or analysis — ever.
- Provided metadata is passed through unchanged; unknown fields stay `null` / "Not available".
- Ranking components that cannot be computed are excluded from the weighted average.
- The AI analyst is instructed (and the schema enforces) to write
  *"Not stated in the provided paper."* rather than guess, and to prefix inferences with
  `AI-inferred limitation:`, `AI-inferred gap:` and `Author-stated gap:`.
- The dashboard labels every section as **From paper** or **AI-inferred**.
- Quality/relevance scores are described as what they are: metadata heuristics.

## Screenshots

> Add your own captures here after running the app locally.

| View | What to capture |
| --- | --- |
| Landing + search | hero, suggestions, pipeline explainer |
| Results | Top 30 grid with rank badges, relevance %, per-source status panel |
| Why this rank | expanded score breakdown on a paper card |
| Analysis dashboard | 13 sections with provenance badges and the gap panel |
| Workspace | saved analyses and recent searches |

```
docs/screenshots/landing.png
docs/screenshots/results.png
docs/screenshots/analysis.png
docs/screenshots/workspace.png
```

## License

Released for academic and portfolio use. Third-party metadata remains subject to each
provider's terms (arXiv, OpenAlex, Crossref, Semantic Scholar, NCBI).
