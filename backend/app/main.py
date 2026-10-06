from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.research.arxiv import search_arxiv
from app.analysis.pdf_extractor import extract_pdf_text
from app.analysis.paper_analyzer import analyze_paper

app = FastAPI(
    title="ResearchOS",
    description="AI Research Intelligence Platform",
    version="0.1.0"
)


# --------------------------------------------------
# CORS CONFIGURATION
# --------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# REQUEST MODEL
# --------------------------------------------------

class ResearchRequest(BaseModel):
    query: str


# --------------------------------------------------
# ROOT ENDPOINT
# --------------------------------------------------

@app.get("/")
def root():
    return {
        "project": "ResearchOS",
        "status": "running",
        "message": "AI Research Intelligence Platform"
    }


# --------------------------------------------------
# HEALTH ENDPOINT
# --------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


# --------------------------------------------------
# RESEARCH ENDPOINT
# --------------------------------------------------

@app.post("/research")
def research(request: ResearchRequest):

    papers = search_arxiv(
        request.query,
        max_results=8
    )

    return {
        "status": "success",
        "query": request.query,
        "count": len(papers),
        "papers": papers
    }
@app.post("/analyze-paper")
def analyze_paper_endpoint(paper: dict):

    title = paper.get("title", "")
    abstract = paper.get("abstract", "")
    pdf_url = paper.get("pdf_url", "")

    if not pdf_url:
        return {
            "status": "error",
            "message": "PDF URL is missing."
        }

    try:
        print(f"Downloading paper: {title}")

        paper_text = extract_pdf_text(pdf_url)

        # Limit text for the first prototype
        paper_text = paper_text[:60000]

        print("Sending paper to Gemini...")

        analysis = analyze_paper(
            title=title,
            abstract=abstract,
            paper_text=paper_text
        )

        return {
            "status": "success",
            "title": title,
            "analysis": analysis
        }

    except Exception as error:
        print(f"Analysis error: {error}")

        return {
            "status": "error",
            "message": str(error)
        }