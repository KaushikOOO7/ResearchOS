# ResearchOS 🔬

**AI Research Intelligence Platform**

ResearchOS accelerates scientific inquiry by aggregating scholarly papers across major open academic repositories, extracting document architectures, identifying critical limitations and failure modes, and detecting unaddressed research gaps.

---

## Table of Contents
1. [Overview](#overview)
2. [Key Features](#key-features)
3. [Architecture](#architecture)
4. [Technology Stack](#technology-stack)
5. [Project Structure](#project-structure)
6. [Search Pipeline](#search-pipeline)
7. [Top 30 Ranking Engine](#top-30-ranking-engine)
8. [Paper Analysis](#paper-analysis)
9. [Research Gap Detection](#research-gap-detection)
10. [Local Storage Search History](#local-storage-search-history)
11. [Local Development Setup](#local-development-setup)
12. [Environment Variables](#environment-variables)
13. [Starting the Backend](#starting-the-backend)
14. [Starting the Frontend](#starting-the-frontend)
15. [API Endpoints](#api-endpoints)
16. [Running Tests](#running-tests)
17. [Troubleshooting](#troubleshooting)
18. [Deployment (Render & Vercel)](#deployment-render--vercel)
19. [Security & SSRF Safeguards](#security--ssrf-safeguards)
20. [Known Limitations](#known-limitations)
21. [Roadmap](#roadmap)
22. [Contributing](#contributing)
23. [License](#license)

---

## 1. Overview
ResearchOS bridges literature search and deep technical comprehension. Traditional search engines return links; ResearchOS reads papers, analyzes methodology, and provides researchers and students with actionable architectural breakdowns, failure conditions, and novel project ideas.

---

## 2. Key Features
- **Multi-Source Academic Search**: Aggregates arXiv, OpenAlex, Crossref, Semantic Scholar, and PubMed.
- **Top 30 Deterministic Ranking**: Deduplicates and scores papers by keyword relevance, citation volume, recency, and direct open-access PDF availability.
- **Local Search History**: Automatically persists previous research queries in local storage; accessible via an interactive sidebar for one-click re-querying.
- **13-Dimensional AI Paper Analysis**:
  - Research problem formulation
  - Prior baselines and shortcomings
  - Proposed methodological innovation
  - Technical pipeline & architecture
  - Datasets & algorithms
  - Empirical evaluation results
  - Stated author limitations & AI-inferred technical boundaries
  - Realistic failure conditions (distribution shift, hardware bounds)
  - Research gaps (explicit author future work vs. inferred open questions)
  - Actionable engineering improvements
  - Novel follow-up research directions
  - Comprehensive synthesis and assessment
- **SSRF-Protected PDF Extraction**: Ingests academic PDFs with IP validation (blocking private/loopback/cloud metadata ranges) and size bounding.

---

## 3. Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                      ResearchOS Client                      │
│            React SPA (Vite, Axios, Lucide Icons)            │
└──────────────┬──────────────────────────────▲───────────────┘
               │                              │
               │ POST /research               │ JSON Results
               │ POST /analyze-paper          │
               ▼                              │
┌─────────────────────────────────────────────┴───────────────┐
│                      FastAPI Backend                        │
│                 (Python 3.10+, Uvicorn)                     │
│                                                             │
│  ┌───────────────────────┐       ┌───────────────────────┐  │
│  │   Search Orchestrator │       │   Analysis Pipeline   │  │
│  │                       │       │                       │  │
│  │ • arXiv API           │       │ • SSRF-Safe Extractor │  │
│  │ • OpenAlex API        │       │ • pypdf Parser        │  │
│  │ • Crossref API        │       │ • Google GenAI SDK    │  │
│  │ • Semantic Scholar    │       │ • Structured Schema   │  │
│  │ • PubMed API          │       │                       │  │
│  │ • Multi-Signal Ranker │       │                       │  │
│  └───────────────────────┘       └───────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Technology Stack

### Frontend
- **Framework**: React 19, Vite
- **Styling**: Native dark-mode responsive CSS
- **Icons**: Lucide React
- **HTTP Client**: Axios with centralized service layer
- **Persistence**: LocalStorage API for search history

### Backend
- **Framework**: FastAPI, Uvicorn
- **Validation**: Pydantic v2
- **PDF Extraction**: pypdf with custom socket-level SSRF safeguards
- **AI Engine**: Google GenAI SDK (`@google/genai` / `google-genai`)
- **Testing**: pytest, FastAPI TestClient (`httpx`)

---

## 5. Project Structure

```text
ResearchOS/
├── backend/
│   ├── app/
│   │   ├── analysis/
│   │   │   ├── paper_analyzer.py      # Gemini paper analysis engine
│   │   │   ├── pdf_extractor.py       # SSRF-protected PDF downloader & parser
│   │   │   └── __init__.py
│   │   ├── research/
│   │   │   ├── arxiv.py               # arXiv Atom query client
│   │   │   ├── openalex.py            # OpenAlex scholarly client
│   │   │   ├── crossref.py            # Crossref API client
│   │   │   ├── semantic_scholar.py    # Semantic Scholar client
│   │   │   ├── pubmed.py              # PubMed E-utilities client
│   │   │   ├── deduplicator.py        # DOI/arXiv/title deduplication
│   │   │   ├── normalizer.py          # Metadata standardization
│   │   │   ├── ranker.py              # Deterministic scoring algorithm
│   │   │   ├── engine.py              # Parallel search orchestrator
│   │   │   └── __init__.py
│   │   ├── schemas/
│   │   │   ├── paper.py               # Pydantic data schemas
│   │   │   └── __init__.py
│   │   ├── main.py                    # FastAPI entry point & CORS
│   │   └── __init__.py
│   ├── tests/
│   │   ├── test_analysis.py           # SSRF & PDF tests
│   │   ├── test_api.py                # Endpoint integration tests
│   │   ├── test_research.py           # Ranking & deduplication tests
│   │   └── __init__.py
│   ├── requirements.txt               # Pinned Python dependencies
│   └── .env.example                   # Backend configuration template
├── frontend/
│   ├── src/
│   │   ├── services/
│   │   │   └── api.js                 # Centralized API service
│   │   ├── App.jsx                    # Primary UI component
│   │   ├── App.css                    # Design system & dark theme
│   │   ├── index.css                  # Global reset
│   │   └── main.jsx                   # React mounting
│   ├── public/                        # Static icons
│   ├── package.json                   # Frontend npm configuration
│   ├── vite.config.js                 # Vite server & proxy configuration
│   └── .env.example                   # Frontend configuration template
├── render.yaml                        # Render backend deployment spec
├── metadata.json                      # AI Studio platform configuration
├── LICENSE                            # MIT License
├── .gitignore
└── README.md
```

---

## 6. Search Pipeline
1. **Parallel Querying**: The user's query is dispatched concurrently to arXiv, OpenAlex, Crossref, Semantic Scholar, and PubMed with individual timeouts.
2. **Provider Failover**: If any individual provider times out or throttles, the search continues and returns papers from surviving providers.
3. **Metadata Normalization**: Titles, publication dates, DOIs, and arXiv identifiers are normalized.
4. **Multi-Signal Deduplication**: Matches items across databases using DOI matching, arXiv ID matching, title fingerprints, and fuzzy token Jaccard similarity (>0.85). Metadata is merged so citations and full-text links are preserved.

---

## 7. Top 30 Ranking Engine
Papers are scored deterministically based on:
- **Textual Precision (50%)**: Exact query phrase in title (+30), title token occurrences (+10 each), abstract token occurrences (+2 each).
- **Citation Impact (25%)**: Real citations log-scaled: $6 \times \log_{10}(\text{citations} + 1)$ (capped at +25).
- **Recency Signal (15%)**: Current/recent publication years receive tiered bonus points (+15 to +3).
- **Open Access (10%)**: Direct PDF link accessibility bonus (+10).

The top 30 candidates are returned deterministically.

---

## 8. Paper Analysis
When a user clicks "Analyze Paper", the backend downloads the PDF (or falls back to the abstract if unavailable), extracts text, and queries Gemini (`gemini-2.5-flash` or `gemini-3.8-flash`) with strict structured JSON constraints.

---

## 9. Research Gap Detection
The analyzer specifically separates:
- **Author-Stated Gaps**: Explicit open problems highlighted in the paper's discussion/conclusion.
- **AI-Inferred Gaps**: Methodological blind spots, untested edge conditions, and theoretical boundaries identified during technical analysis.

---

## 10. Local Storage Search History
Users can browse previous queries in an interactive slide-out sidebar:
- Saved in `localStorage` under `researchos_search_history`.
- Shows query text, relative time elapsed, and paper count.
- One-click query replay.
- Options to delete individual queries or clear all history.

---

## 11. Local Development Setup

### Prerequisites
- Python 3.10+
- Node.js 18+ and npm

---

## 12. Environment Variables

### Backend (`backend/.env`)
```ini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
GEMINI_FALLBACK_MODEL=
CORS_ORIGINS=http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173
PORT=8000
```

### Frontend (`frontend/.env`)
```ini
VITE_API_BASE_URL=http://127.0.0.1:8000
```

---

## 13. Starting the Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate       # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Interactive Swagger documentation is available at `http://127.0.0.1:8000/docs`.

---

## 14. Starting the Frontend

```bash
cd frontend
npm install
npm run dev -- --port 5173
```

Open `http://localhost:5173` in your browser.

---

## 15. API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Service identification |
| `GET` | `/health` | Service health & Gemini configuration status |
| `POST` | `/research` | Multi-provider academic search (Top 30 papers) |
| `POST` | `/analyze-paper` | Structured AI paper analysis |

---

## 16. Running Tests

```bash
PYTHONPATH=backend pytest backend/tests -v
```

All 20 backend integration and unit tests run against mock fixtures without consuming Gemini quota or requiring internet access.

---

## 17. Troubleshooting

- **"Unable to fetch research papers"**: Ensure the backend is running on `127.0.0.1:8000` or that `VITE_API_BASE_URL` matches your running backend.
- **"Gemini API key is not configured"**: Add `GEMINI_API_KEY` to `backend/.env`. Academic search works without Gemini; analysis requires the key.
- **Port 8000 Already in Use**: Change `PORT` in `.env` and launch with `uvicorn app.main:app --port 8001`, updating `VITE_API_BASE_URL` accordingly.

---

## 18. Deployment (Render & Vercel)

### Backend on Render
1. Connect your repository to Render.
2. Select **Web Service** using `render.yaml` or manual setup:
   - **Root Directory**: `backend`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Configure environment variables in Render: `GEMINI_API_KEY`, `CORS_ORIGINS` (set to your Vercel URL).

### Frontend on Vercel
1. Import repository on Vercel.
2. Set **Root Directory** to `frontend`.
3. Set environment variable: `VITE_API_BASE_URL=https://your-backend.onrender.com`.
4. Deploy.

---

## 19. Security & SSRF Safeguards
- **DNS Resolution Check**: The PDF downloader resolves hostnames before making HTTP requests.
- **Address Blocking**: Rejects loopback (`127.0.0.0/8`), private networks (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), link-local IPs (`169.254.0.0/16`), and internal cloud metadata endpoints (`metadata.google.internal`).
- **Redirect Re-Validation**: Manually checks target destinations up to 3 hops, re-validating the resolved IP on each hop.
- **Resource Limits**: Download size is strictly capped at 15 MB; extracted text is capped at 60,000 characters.
- **Zero Secret Leakage**: API keys are excluded from git, error responses, and client bundles.

---

## 20. Known Limitations
- Semantic Scholar and OpenAlex rate-limits may apply under heavy concurrent usage without API keys.
- Scanned PDF papers without an embedded text layer cannot be parsed without external OCR.

---

## 21. Roadmap
- [ ] Export analysis summaries to Markdown, BibTeX, and Notion.
- [ ] Citation graph visualization between retrieved papers.
- [ ] Multi-paper comparative synthesis mode.

---

## 22. Contributing
Contributions are welcome! Please open an issue or submit a pull request with unit tests for any new providers or analysis features.

---

## 23. License
This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
