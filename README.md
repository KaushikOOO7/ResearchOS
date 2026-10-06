<div align="center">

# ResearchOS

**AI Research Intelligence Platform**

Turn a research idea into ranked literature, structured paper analyses, limitations,
research gaps and new research directions.

`React 19 · Vite` · `FastAPI · Python 3.11` · `Google Gemini` · `arXiv · OpenAlex · Crossref · Semantic Scholar · PubMed`

[![Backend](https://img.shields.io/badge/backend-FastAPI-009688)](#tech-stack)
[![Frontend](https://img.shields.io/badge/frontend-React%2019-61DAFB)](#tech-stack)
[![Tests](https://img.shields.io/badge/tests-103%20passing-brightgreen)](#testing)
[![License](https://img.shields.io/badge/license-MIT-blue)](#license)

</div>

---

## 1. Overview

ResearchOS is a research intelligence workspace — not a paper search box. You give it an
idea such as *"Graph neural networks for drug discovery"* and it:

1. **understands** the query (keyphrases, acronym expansion `GNN → graph neural network`, biomedical + recency intent),
2. **searches up to five academic sources in parallel** and collects a ~90-candidate pool,
3. **deduplicates** the same paper arriving from multiple providers,
4. **ranks** candidates with a transparent, multi-component score,
5. returns the **Top 30 papers** with real metadata, score breakdowns and PDF/source links,
6. **analyses any paper on demand** — PDF download, text extraction, section detection, then a structured Gemini analysis that separates what the paper *states* from what the model *infers*.

The interface is built around one journey:

```
Idea → Research landscape → Top 30 papers → Select a paper → AI analysis
     → Limitations → Research gaps → New research directions → Project
```

**Research integrity is a product requirement, not a slogan.** ResearchOS never fabricates
papers, authors, citations, datasets, metrics or analysis. Missing metadata is shown as
*"Not available"*, unstated content as *"Not stated in the provided paper."*, and every AI
claim is labelled **From paper** or **AI-inferred**.

## 2. Features

| Area | Implementation |
| --- | --- |
| Multi-source search | arXiv, OpenAlex, Crossref, Semantic Scholar (API key), PubMed (biomedical queries) — parallel, per-provider timeouts, failure isolation |
| Query understanding | tokenisation, keyphrases, acronym expansion, biomedical/recency detection, year filters |
| Candidate pool | ~90 candidates by default with proportional per-provider budgets (configurable) |
| Deduplication | DOI → arXiv id → exact normalised title → fuzzy title match (character + token containment) with metadata merging |
| Ranking | BM25 relevance (field-weighted) + metadata quality + log-scaled citation impact + exponential recency + source reliability, configurable weights, per-paper renormalisation |
| Explainability | per-paper score breakdown, *"Why this rank?"* panel, provider status chips, pipeline stats |
| Paper cards | rank, title, authors, year, venue/journal, source(s), relevance %, citations (or *Not available*), quality label, PDF/source links, save, analyze |
| PDF pipeline | SSRF-guarded download, size/page caps, per-page isolation, cleaning, section detection, scanned-PDF detection |
| AI analysis | 14-key structured output, strict JSON validation + repair, bounded retries, fallback model, provenance metadata |
| Workspace | saved papers, saved analyses, recent searches (browser-persisted; server-side in the roadmap) |
| Observability | `[ResearchOS] …` stage logging for every pipeline step; secrets never logged |
| Testing | 103 backend tests incl. a mocked full-pipeline run; frontend lint + build gates |

## 3. Architecture

```
                    ┌──────────────────────── React (Vite) ──────────────────────────┐
                    │ Research · Papers · Workspace · About                          │
                    │ services/api.js  (VITE_API_BASE_URL or proxied /api)           │
                    │ hooks/ (useResearch · usePaperAnalysis · useWorkspace · useHealth)
                    └──────────────────────────────┬─────────────────────────────────┘
                        dev proxy /api → :8000     │     production: VITE_API_BASE_URL
                    ┌──────────────────────────────▼─────────────────────────────────┐
                    │                    FastAPI  (backend/app)                      │
                    │ api/research.py · api/analysis.py · api/health.py              │
                    │ CORS (env-driven) · error envelope · Pydantic contracts        │
                    └───────┬──────────────────────────────────────────┬─────────────┘
                            │                                          │
        ┌───────────────────▼──────────────────┐   ┌───────────────────▼────────────────┐
        │        research/ pipeline            │   │        analysis/ pipeline          │
        │ query_understanding → providers →    │   │ pdf_extractor (SSRF-safe) →        │
        │ normalizer → deduplicator →          │   │ text_cleaner → section detection → │
        │ ranking → search_engine              │   │ paper_analyzer → gemini_client      │
        │ arxiv openalex crossref              │   │ (retries · fallback model · JSON)  │
        │ semantic_scholar pubmed              │   │                                    │
        └───────────────────┬──────────────────┘   └───────────────────┬────────────────┘
                            │                                          │
                  Academic provider APIs                     Google Gemini API
```

## 4. Tech Stack

| Layer | Technology |
| --- | --- |
| Frontend | React 19, Vite 8, JavaScript/JSX, Axios, lucide-react, hand-written CSS (no UI kit) |
| Backend | Python 3.11+, FastAPI, Uvicorn, Pydantic v2, requests, python-dotenv |
| AI | Google Gemini via `google-genai` (JSON mode, retries, optional fallback model) |
| PDF | pypdf |
| Testing | pytest (+ FastAPI TestClient), oxlint, Vite build |
| Sources | arXiv Atom API, OpenAlex, Crossref REST, Semantic Scholar Graph, NCBI PubMed E-utilities |

## 5. Project Structure

```
ResearchOS/
├── backend/
│   ├── app/
│   │   ├── main.py                 # app factory, CORS, /api aliases, error handlers
│   │   ├── config.py               # env-driven settings + ranking weights
│   │   ├── version.py
│   │   ├── api/                    # research.py, analysis.py, health.py, helpers.py
│   │   ├── research/               # providers + pipeline
│   │   │   ├── arxiv.py  openalex.py  crossref.py
│   │   │   ├── semantic_scholar.py  pubmed.py
│   │   │   ├── query_understanding.py
│   │   │   ├── normalizer.py       # canonical paper schema
│   │   │   ├── deduplicator.py     # DOI → arXiv → title → fuzzy merge
│   │   │   ├── ranking.py          # transparent weighted scoring
│   │   │   ├── search_engine.py    # orchestration (parallel, timeouts, isolation)
│   │   │   └── base.py             # ResearchSource abstraction
│   │   ├── analysis/               # pdf_extractor.py, text_cleaner.py, paper_analyzer.py
│   │   ├── models/paper.py         # canonical Paper entity + stable ids
│   │   ├── schemas/                # request/response + analysis contracts
│   │   ├── services/               # gemini_client, analysis_service, cache, paper_store
│   │   └── utils/                  # text, http (retries + SSRF guard), logging, connectivity
│   ├── tests/                      # 103 tests (unit + contract + full-pipeline)
│   ├── requirements.txt            # runtime deps
│   ├── requirements-dev.txt        # + pytest/httpx
│   ├── pytest.ini
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/             # layout · search · papers · analysis · state
│   │   ├── pages/                  # Research · Papers · Workspace · About
│   │   ├── hooks/                  # state machines for every async operation
│   │   ├── services/api.js         # every backend call, single source of truth
│   │   ├── utils/format.js
│   │   └── App.jsx · App.css · index.css · main.jsx
│   ├── public/favicon.svg
│   ├── index.html
│   ├── vercel.json
│   ├── vite.config.js              # /api proxy + preview-safe host binding
│   └── .env.example
├── render.yaml
├── run.sh / run.bat                # one-command local launcher
├── .gitignore
├── LICENSE
└── README.md
```

## 6. How It Works

1. You type an idea; the frontend `POST`s `{query}` to `/research`.
2. The backend analyses the query (keyphrases, acronyms, domain, intent).
3. Every applicable provider is queried **in parallel** with individual timeouts.
4. Results are normalised into one schema; a failing provider is recorded and skipped.
5. Duplicates are merged (richest metadata wins; citation counts take the max).
6. Each paper is scored and the list is sorted by `final_score`.
7. The Top 30 are returned with pipeline telemetry and a per-provider status map.
8. Clicking **Analyze** sends the paper reference to `/analyze-paper`, which downloads and
   parses the PDF, then asks Gemini for a strict structured analysis.
9. The dashboard renders 13 sections with **From paper** / **AI-inferred** provenance.

## 7. Academic Search Pipeline

```
USER QUERY
  → QUERY UNDERSTANDING        (tokens, phrases, acronyms, domain, recency, year)
  → MULTI-SOURCE SEARCH        (parallel · per-provider timeout · isolation)
  → COLLECT CANDIDATES         (~50–100 target, proportional budgets)
  → NORMALISE METADATA         (normalizer.py → canonical schema)
  → DEDUPLICATE                (DOI → arXiv ID → title → fuzzy)
  → SCORE: relevance · quality · recency · citation · source
  → WEIGHTED FINAL RANKING
  → TOP 30
```

Provider behaviour:

| Provider | Key required | Notes |
| --- | --- | --- |
| arXiv | no | Atom API; two-pass query (precise → broader); no citation counts exposed |
| OpenAlex | no (email = polite pool) | primary metadata source; citation counts; open-access PDF locations |
| Crossref | no (email = polite pool) | DOI registry; published (non-preprint) records |
| Semantic Scholar | **yes** (`SEMANTIC_SCHOLAR_API_KEY`) | skipped without a key because the public pool returns HTTP 429 |
| PubMed | no (key optional) | **only** for biomedical queries; no direct PDF (source page instead) |

A failing provider never fails the request: the response includes
`providers: {"arxiv": "success", "crossref": "failed", …}` and the UI shows which sources
were used, empty, skipped or unreachable.

## 8. Top 30 Ranking

```
final_score = 0.50·relevance + 0.20·quality + 0.15·citation + 0.10·recency + 0.05·source
```

| Component | How it is computed |
| --- | --- |
| **Relevance** | Okapi BM25 over field-weighted metadata (title ×3, keywords ×2, subjects ×1.5, abstract ×1, venue ×0.5) + topic-coverage factor + exact-phrase bonuses; scaled so the best candidate of the result set scores 100 |
| **Quality** | Metadata completeness heuristic: abstract depth, DOI, published venue, document type, cross-source corroboration, author list. *Not* a judgement of scientific merit |
| **Citation impact** | `log(1 + citations)`, saturating at 1,000. `null` when no provider reports citations |
| **Recency** | 100 for ≤1 year old, exponential decay afterwards (7-year half-life, floor 15) |
| **Source reliability** | Metadata openness/completeness of the provider (OpenAlex 92, PubMed 90, Crossref 88, Semantic Scholar 85, arXiv 82) |

Weights are `RANK_WEIGHT_*` environment variables. When a component cannot be computed
(e.g. an arXiv-only record with no citation count), its weight is **redistributed** rather
than scored as zero, so no paper is punished for missing metadata. Every response includes
`relevance_score`, `quality_score`, `citation_score`, `recency_score`, `source_score`,
`overall_score` and `final_score` (alias of `overall_score`), plus human-readable
`score_explanations`.

## 9. AI Paper Analysis

`POST /analyze-paper` →

1. validate the paper reference (Pydantic),
2. reject unsafe PDF URLs (SSRF guard) and non-http(s) schemes,
3. download with a size cap + timeout, verify the `%PDF` magic header,
4. extract text with pypdf (per-page isolation), clean it, detect sections,
5. flag scanned/image-only PDFs and fall back to title + abstract (clearly reported),
6. build a section-labelled document and truncate at a safe character budget,
7. call Gemini in JSON mode,
8. validate + normalise against the exact schema (one repair retry on malformed JSON),
9. return the analysis plus provenance (pages, characters, sections, model, warnings).

Extracted PDF text is cached per URL, so re-analysing or retrying never re-downloads.

## 10. Research Gap Detection

The analysis schema separates:

- `limitations` — **author-stated**, each prefixed `Author-stated limitation:`
- `additional_technical_limitations` — **AI-inferred**, each prefixed `AI-inferred limitation:`
- `research_gap.author_stated_gaps` — **from the paper**, prefixed `Author-stated gap:`
- `research_gap.ai_inferred_gaps` — **inferred**, prefixed `AI-inferred gap:`

The dashboard renders these in visually distinct panels with provenance badges, so a reader
can always tell which claims come from the paper and which are the model's analysis.
Cross-paper gap synthesis (`POST /research-gap`), comparison and novelty analysis are
Phase 4 (see the roadmap) — they are **not** implemented yet and are not faked.

## 11. Local Development

```bash
git clone https://github.com/<you>/ResearchOS.git
cd ResearchOS

# Backend
python3 -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env     # add GEMINI_API_KEY for AI analysis

# Frontend (new terminal)
cd frontend
npm install
cp .env.example .env                 # leave VITE_API_BASE_URL empty locally
```

Or use the launcher, which does all of the above and starts both services:

```bash
./run.sh          # macOS / Linux
run.bat           # Windows
```

## 12. Environment Variables

**Backend** (`backend/.env`)

| Variable | Purpose |
| --- | --- |
| `GEMINI_API_KEY` | Enables AI analysis. Search works without it |
| `GEMINI_MODEL` | Primary model (default `gemini-3.8-flash`) |
| `GEMINI_FALLBACK_MODEL` | Used when the primary keeps failing with transient errors (default `gemini-3.7-flash`) |
| `GEMINI_MAX_OUTPUT_TOKENS`, `GEMINI_TEMPERATURE` | Generation controls |
| `OPENALEX_EMAIL`, `CROSSREF_EMAIL`, `CONTACT_EMAIL` | Polite-pool identification (recommended) |
| `SEMANTIC_SCHOLAR_API_KEY` | Enables the Semantic Scholar provider |
| `PUBMED_ENABLED`, `NCBI_API_KEY`, `PUBMED_EMAIL` | PubMed controls |
| `RESEARCH_TARGET_CANDIDATES`, `RESEARCH_MAX_RESULTS` | Candidate pool target (90) and returned Top-N (30) |
| `PROVIDER_TIMEOUT_SECONDS`, `SEARCH_DEADLINE_SECONDS` | Retrieval budgets |
| `RANK_WEIGHT_{RELEVANCE,QUALITY,CITATION,RECENCY,SOURCE}` | Ranking weights |
| `PDF_MAX_BYTES`, `PDF_MAX_PAGES`, `PDF_DOWNLOAD_TIMEOUT`, `ANALYSIS_MAX_CHARS` | PDF/analysis limits |
| `PDF_ALLOWED_HOSTS` | Optional **strict** host allowlist for PDF downloads (empty = any public host) |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins |
| `CORS_ORIGIN_REGEX` | Regex for extra trusted origins (e.g. Vercel previews); empty disables |
| `PORT`, `LOG_LEVEL`, `ENVIRONMENT` | Server settings |

**Frontend** (`frontend/.env`)

| Variable | Purpose |
| --- | --- |
| `VITE_API_BASE_URL` | Deployed backend origin (e.g. `https://researchos-api.onrender.com`). **Empty locally** — the dev proxy handles `/api` |
| `VITE_BACKEND_URL` | Dev-proxy target (default `http://127.0.0.1:8000`) |

> `frontend/.env` must never contain backend secrets: every `VITE_*` value is embedded in
> the browser bundle.

## 13. Backend Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# optional: pip install -r requirements-dev.txt   (adds pytest + httpx)
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Startup never requires Gemini: without `GEMINI_API_KEY` the API still serves search, and
`/health` reports `"gemini_configured": false` so the UI explains it in advance.

## 14. Frontend Setup

```bash
cd frontend
npm install
npm run dev -- --port 5173
```

The dev server proxies `/api/*` to `VITE_BACKEND_URL` (default `http://127.0.0.1:8000`),
which is why no localhost URL is hardcoded in any component.

## 15. Running the Application

| Service | URL | Notes |
| --- | --- | --- |
| Frontend | <http://localhost:5173> | Vite dev server (proxy to the API) |
| Backend | <http://127.0.0.1:8000> | Uvicorn |
| Swagger UI | <http://127.0.0.1:8000/docs> | Interactive API docs |
| ReDoc / schema | <http://127.0.0.1:8000/redoc> · `/openapi.json` | |

Production-style backend start (respects `$PORT`):

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Frontend production build:

```bash
npm run build     # → frontend/dist
npm run preview   # → http://localhost:4173
```

## 16. API Endpoints

| Method | Path | Aliases | Description |
| --- | --- | --- | --- |
| GET | `/` | `/api` | Service info + endpoint index |
| GET | `/health` | `/api/health` | Health, configured capabilities, outbound-connectivity preflight |
| POST | `/research` | `/api/research` | Ranked Top-N papers, pipeline stats, provider status |
| POST | `/analyze-paper` | `/api/analyze-paper` | Structured AI analysis with provenance |
| GET | `/papers/{paper_id}` | `/api/papers/{paper_id}` | Paper detail from a recent search |

**POST /research**

```bash
curl -X POST http://127.0.0.1:8000/research \
  -H 'Content-Type: application/json' \
  -d '{"query": "graph neural networks for drug discovery"}'
```

```json
{
  "status": "success",
  "query": "graph neural networks for drug discovery",
  "count": 30,
  "providers": { "arxiv": "success", "openalex": "success", "crossref": "failed",
                 "pubmed": "success", "semantic_scholar": "skipped" },
  "stats": { "candidates_collected": 121, "duplicates_removed": 31, "returned": 30,
             "providers_succeeded": 4, "elapsed_ms": 8340 },
  "papers": [
    {
      "id": "p_1a2b3c4d5e6f7a8b", "rank": 1,
      "title": "…", "authors": ["…"], "year": 2024, "published_date": "2024-03-01",
      "abstract": "…", "doi": "10.1000/xyz", "arxiv_id": null,
      "paper_url": "https://doi.org/10.1000/xyz", "pdf_url": "https://…/paper.pdf",
      "source": "OpenAlex", "sources": ["OpenAlex", "Crossref"],
      "citation_count": 120, "journal": "Journal of Cheminformatics",
      "venue": "Journal of Cheminformatics", "keywords": ["…"],
      "relevance_score": 100, "quality_score": 82, "citation_score": 61,
      "recency_score": 87, "source_score": 92,
      "overall_score": 89.4, "final_score": 89.4,
      "quality_label": "High", "score_explanations": { "overall": "…" }
    }
  ]
}
```

Optional request fields: `limit` (1–50), `sources` (`["arxiv","openalex"]`), `year_from`,
`open_access_only`.

**POST /analyze-paper**

```bash
curl -X POST http://127.0.0.1:8000/analyze-paper \
  -H 'Content-Type: application/json' \
  -d '{"title": "…", "abstract": "…", "pdf_url": "https://arxiv.org/pdf/2401.01234"}'
```

Errors use one envelope and never leak stack traces:

```json
{ "detail": { "status": "error", "code": "missing_api_key",
              "message": "AI analysis is unavailable because GEMINI_API_KEY is not configured…",
              "retryable": false } }
```

## 17. Deployment

```
GitHub ──► Render (backend, uvicorn $PORT) ──► URL like https://researchos-api.onrender.com
   └────► Vercel (frontend, VITE_API_BASE_URL=http://…onrender.com)
```

### 18. Vercel Deployment (frontend)

1. Push the repository to GitHub.
2. Vercel → **Add New Project** → import the repo.
3. **Root Directory:** `frontend` (framework auto-detects Vite; `vercel.json` is included).
4. **Environment Variables:**
   `VITE_API_BASE_URL = https://your-service.onrender.com` (no trailing slash)
5. Deploy. `npm run build` must succeed (verified locally).

### 19. Render Deployment (backend)

**Option A — Blueprint (recommended, uses `render.yaml`)**

1. Render → **New → Blueprint** → select the repository.
2. Render reads `render.yaml`, creates `researchos-api` with:
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, health check `/health`.
3. Set the secret environment variables when prompted:
   - `GEMINI_API_KEY` = your key
   - `CORS_ORIGINS` = `https://your-frontend.vercel.app`
   - optionally `GEMINI_MODEL`, `GEMINI_FALLBACK_MODEL`
4. Deploy and confirm `https://your-service.onrender.com/health` returns `"status": "healthy"`.

**Option B — Manual web service**

| Setting | Value |
| --- | --- |
| Root Directory | `backend` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health Check Path | `/health` |
| Env vars | `GEMINI_API_KEY`, `CORS_ORIGINS`, `GEMINI_MODEL`, `GEMINI_FALLBACK_MODEL` |

> Outbound HTTPS is required for academic APIs and Gemini. Verify with `/health` — its
> `network` block probes a provider endpoint and reports `internet: false` when the host
> blocks egress (many sandboxed/preview environments do).

### Deployment checklist

1. Push to GitHub. 2. Create the Render service. 3. Set backend env vars. 4. Deploy the
backend. 5. Copy its URL. 6. Create the Vercel project. 7. Set `VITE_API_BASE_URL`.
8. Set `CORS_ORIGINS` on Render to the Vercel URL (and redeploy if it changed).
9. `GET /health` → `healthy`. 10. Search from the frontend. 11. Analyse a paper. 12. Confirm
no secrets were committed (`git log -p | grep -i gemini_api_key`).

## 20. Security

- **Secrets** live only in environment variables. `backend/.env` is gitignored; `.env.example`
  files contain placeholders only. No key is ever logged, returned in a response, or shipped
  to the browser (the frontend talks exclusively to its own API).
- **CORS** is origin-listed from `CORS_ORIGINS` plus an optional regex for preview domains.
  Credentials are enabled, so `allow_origins=["*"]` is never used.
- **SSRF protection** on PDF downloads: only `http`/`https`, a small port set, and hosts that
  resolve exclusively to public addresses. Loopback, private, link-local, multicast, reserved
  and metadata hosts (`localhost`, `127.0.0.1`, `0.0.0.0`, `10.x`, `169.254.169.254`,
  `metadata.google.internal`, `*.internal`, `*.local`, `::1`, …) are always refused.
  Documented compromise: an open allowlist is the default because open-access PDFs live on
  thousands of publisher domains — the SSRF class is blocked by the address checks above.
  Set `PDF_ALLOWED_HOSTS` for strict allowlisting (e.g. `arxiv.org,doi.org,mdpi.com`).
- **Resource limits**: PDF size/page caps, download and provider timeouts, bounded retries,
  response payload trimming (abstracts ≤6000 chars, ≤40 authors).
- **Input validation**: every request body is a Pydantic model, including the analysis input.
- **Error hygiene**: users see friendly messages with stable codes; stack traces stay in the
  server log.

## 21. Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| Frontend shows *"ResearchOS API is unavailable"* | Backend not running, or `VITE_API_BASE_URL` points elsewhere. Start uvicorn on :8000, or set the variable to your deployed API |
| Header warns *"VITE_API_BASE_URL not set"* | You built a production bundle without the variable. Set it and redeploy |
| Search returns 0 papers, chips show every provider `failed` | The host has no outbound internet. Check `/health` → `network.internet`. Deploy where outbound HTTPS is allowed |
| *"AI analysis requires GEMINI_API_KEY"* (503, code `missing_api_key`) | Add `GEMINI_API_KEY` to `backend/.env` (or the host's env vars) and restart |
| *"quota has been reached"* (429) | Gemini rate/quota limit: wait, or use a different model/quota. ResearchOS retries with backoff before reporting this |
| *"AI service is temporarily unavailable"* (503 after retries) | Transient Gemini outage; the primary model was retried and the fallback model attempted |
| Analysis says abstract-only | The PDF was unavailable, blocked, scanned, or too short — the response metadata (`referenced_abstract_only`) states which |
| *"Refused to download an unsafe URL"* | The PDF URL resolves to a private/local address. Use the paper's source page |
| CORS error in the browser console | Add the frontend origin to `CORS_ORIGINS` on the backend and restart/redeploy |
| Local port already in use | Backend: `uvicorn … --port 8001` (+ `VITE_BACKEND_URL`); frontend: `npm run dev -- --port 5174` (already in `CORS_ORIGINS`) |
| Windows: `./run.sh` won't run | Use `run.bat`, or `bash run.sh` from Git Bash/WSL |

## 22. Testing

```bash
cd backend
pip install -r requirements-dev.txt
pytest                      # 103 tests
```

Coverage highlights — all offline (providers are mocked with realistic payloads; no paid API
is ever called by the suite):

- health, root and `/api/*` aliases; Swagger/OpenAPI availability
- search validation (empty/whitespace/short queries), empty-result handling without a traceback
- provider parsing for arXiv, OpenAlex, Crossref, Semantic Scholar, PubMed
- normalisation (dates from ISO / date-parts / textual forms, year derivation, markup stripping, bounds)
- deduplication (DOI, arXiv id, exact title, fuzzy + containment, metadata merging)
- ranking (relevance ordering, missing-citation handling, weight renormalisation, determinism)
- PDF pipeline (valid, multi-page, scanned, non-PDF, SSRF URL rejection)
- analysis schema (placeholder cleaning, malformed-JSON repair, author vs AI prefixes)
- Gemini behaviour (missing key → 503 `missing_api_key`, invalid URL → 400, stubbed success path)
- full-pipeline integration: 7 mocked candidates → dedup → ranking → API serialisation

Frontend gates:

```bash
cd frontend
npm run lint      # oxlint — 0 warnings
npm run build     # production build
npm run preview   # serve the built bundle
```

## 23. Future Roadmap

- **Phase 4** — cross-paper research-gap engine, multi-paper comparison, novelty analysis, project idea generator.
- **Phase 5** — section-aware chunking + embeddings, RAG over long papers, page-level evidence citations for AI claims.
- **Phase 6** — server-side workspace with PostgreSQL (projects, notes, history), literature review generator, exports (Markdown/PDF/DOCX).
- **Phase 7** — authentication, rate limiting, caching layer (Redis), CI/CD, observability dashboards.

## 24. Contributing

1. Fork and branch: `git checkout -b feature/my-change`.
2. Keep providers modular — add one file under `backend/app/research/` plus a registration line.
3. Never fabricate data in code, tests or docs; missing values stay `null`/"Not available".
4. Run the gates before opening a PR:
   ```bash
   cd backend && pytest
   cd ../frontend && npm run lint && npm run build
   ```
5. Conventional commit messages (`feat:`, `fix:`, `docs:`, `chore:`), one logical change each.

## 25. License

MIT — see [LICENSE](LICENSE). Retrieved metadata remains subject to each provider's terms
(arXiv, OpenAlex, Crossref, Semantic Scholar, NCBI).
