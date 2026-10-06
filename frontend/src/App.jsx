import { useState } from "react";
import axios from "axios";

import {
  Search,
  Sparkles,
  FileText,
  Network,
  AlertTriangle,
  ExternalLink,
  BookOpen,
  Loader2
} from "lucide-react";


function App() {

  // =============================================
  // STATE
  // =============================================

  // Search query entered by user
  const [query, setQuery] = useState("");

  // Papers returned by FastAPI
  const [papers, setPapers] = useState([]);

  // Research loading state
  const [loading, setLoading] = useState(false);

  // Research error
  const [error, setError] = useState("");

  // Paper currently being analyzed
  const [selectedPaper, setSelectedPaper] = useState(null);

  // AI analysis returned from backend
  const [analysis, setAnalysis] = useState(null);

  // Paper currently being analyzed
  const [analyzingPaper, setAnalyzingPaper] = useState(null);

  // AI analysis error
  const [analysisError, setAnalysisError] = useState("");


  // =============================================
  // RESEARCH FUNCTION
  // =============================================

  const handleResearch = async () => {

    // Don't search empty input
    if (!query.trim()) {
      return;
    }

    try {

      // Start loading
      setLoading(true);

      // Clear previous errors
      setError("");

      // Clear previous papers
      setPapers([]);

      // Clear previous analysis
      setAnalysis(null);
      setSelectedPaper(null);
      setAnalysisError("");


      // Send request to FastAPI
      const response = await axios.post(
        "http://127.0.0.1:8000/research",
        {
          query: query
        }
      );


      // Store papers
      setPapers(response.data.papers);

    } catch (err) {

      console.error(err);

      setError(
        "Unable to fetch research papers. Please try again."
      );

    } finally {

      // Stop loading
      setLoading(false);

    }
  };


  // =============================================
  // AI PAPER ANALYSIS FUNCTION
  // =============================================

  const handleAnalyze = async (paper) => {

    try {

      // Mark selected paper as analyzing
      setAnalyzingPaper(paper.paper_url);

      // Clear previous analysis error
      setAnalysisError("");

      // Clear previous analysis
      setAnalysis(null);

      // Store selected paper
      setSelectedPaper(paper);


      // Send paper to FastAPI
      const response = await axios.post(
        "http://127.0.0.1:8000/analyze-paper",
        {
          title: paper.title,
          abstract: paper.abstract,
          pdf_url: paper.pdf_url
        }
      );


      // Check backend response
      if (response.data.status !== "success") {

        throw new Error(
          response.data.message ||
          "Paper analysis failed."
        );

      }


      // Store AI analysis
      setAnalysis(response.data.analysis);


    } catch (err) {

      console.error("Analysis error:", err);

      setAnalysisError(
        err.response?.data?.message ||
        err.message ||
        "Unable to analyze this paper."
      );

    } finally {

      // Stop analyzing
      setAnalyzingPaper(null);

    }
  };


  // =============================================
  // CLOSE ANALYSIS
  // =============================================

  const handleCloseAnalysis = () => {

    setAnalysis(null);
    setSelectedPaper(null);
    setAnalysisError("");

  };


  // =============================================
  // MAIN UI
  // =============================================

  return (

    <div className="app">

      {/* =========================================
          HEADER
      ========================================== */}

      <header className="header">

        <div className="logo">

          <Sparkles size={22} />

          <span>
            ResearchOS
          </span>

        </div>


        <div className="status">

          <span className="status-dot"></span>

          AI Research Engine

        </div>

      </header>


      {/* =========================================
          MAIN
      ========================================== */}

      <main className="main">

        {/* =========================================
            HERO
        ========================================== */}

        <section className="hero">

          <div className="badge">

            <Sparkles size={16} />

            AI Research Intelligence

          </div>


          <h1>

            Turn your idea into

            <span>
              {" "}research intelligence.
            </span>

          </h1>


          <p>

            Discover research papers, understand architectures,
            identify limitations, analyze failures and find research gaps.

          </p>


          {/* =========================================
              SEARCH BOX
          ========================================== */}

          <div className="research-box">

            <Search size={22} />


            <input
              type="text"
              placeholder="What do you want to research?"
              value={query}

              onChange={(event) =>
                setQuery(event.target.value)
              }

              onKeyDown={(event) => {

                if (event.key === "Enter") {
                  handleResearch();
                }

              }}

            />


            <button
              onClick={handleResearch}
              disabled={loading}
            >

              {loading ? (

                <>

                  <Loader2
                    size={17}
                    className="spin"
                  />

                  Searching...

                </>

              ) : (

                "Research"

              )}

            </button>

          </div>


          {/* =========================================
              RESEARCH ERROR
          ========================================== */}

          {error && (

            <div className="error-message">

              {error}

            </div>

          )}

        </section>


        {/* =========================================
            RESEARCH RESULTS
        ========================================== */}

        {papers.length > 0 && (

          <section className="results-section">

            <div className="results-header">

              <div>

                <span className="section-label">

                  RESEARCH RESULTS

                </span>


                <h2>

                  Papers related to your idea

                </h2>

              </div>


              <div className="paper-count">

                {papers.length} papers

              </div>

            </div>


            <div className="papers-grid">

              {papers.map((paper, index) => (

                <PaperCard

                  key={
                    paper.paper_url || index
                  }

                  paper={paper}

                  handleAnalyze={handleAnalyze}

                  analyzingPaper={analyzingPaper}

                />

              ))}

            </div>

          </section>

        )}


        {/* =========================================
            AI ANALYSIS ERROR
        ========================================== */}

        {analysisError && (

          <section className="analysis-error">

            <div>

              <AlertTriangle size={20} />

            </div>


            <div>

              <h3>
                AI Analysis Unavailable
              </h3>


              <p>
                {analysisError}
              </p>


              {selectedPaper && (

                <button
                  className="secondary-button"
                  onClick={() =>
                    handleAnalyze(selectedPaper)
                  }
                >

                  Try Again

                </button>

              )}

            </div>

          </section>

        )}


        {/* =========================================
            AI RESEARCH ANALYSIS
        ========================================== */}

        {analysis && selectedPaper && (

          <section className="analysis-section">

            {/* ANALYSIS HEADER */}

            <div className="analysis-header">

              <div>

                <span className="section-label">

                  AI RESEARCH ANALYSIS

                </span>


                <h2>

                  {selectedPaper.title}

                </h2>

              </div>


              <div className="analysis-header-actions">

                <a
                  href={selectedPaper.pdf_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="secondary-button"
                >

                  <FileText size={16} />

                  View PDF

                </a>


                <button
                  className="secondary-button"
                  onClick={handleCloseAnalysis}
                >

                  Close Analysis

                </button>

              </div>

            </div>


            {/* =====================================
                RESEARCH PROBLEM
            ====================================== */}

            <div className="analysis-card">

              <div className="analysis-card-header">

                <div className="analysis-card-icon">

                  <Search size={18} />

                </div>


                <div>

                  <span className="analysis-label">

                    RESEARCH PROBLEM

                  </span>


                  <h3>

                    What problem does this paper solve?

                  </h3>

                </div>

              </div>


              <p className="analysis-text">

                {analysis.research_problem ||
                  "No research problem was identified."}

              </p>

            </div>

          </section>

        )}


        {/* =========================================
            EMPTY STATE
        ========================================== */}

        {!loading &&
          papers.length === 0 &&
          !error &&
          !analysis && (

          <section className="features">

            <FeatureCard

              icon={<FileText />}

              title="Research Papers"

              description="Find relevant papers with direct source and PDF access."

            />


            <FeatureCard

              icon={<Network />}

              title="AI Architecture"

              description="Reconstruct and explain architectures from research papers."

            />


            <FeatureCard

              icon={<AlertTriangle />}

              title="Limitations"

              description="Understand why existing approaches fail and where they break."

            />

          </section>

        )}

      </main>

    </div>

  );
}


/* =============================================
   PAPER CARD
============================================= */

function PaperCard({
  paper,
  handleAnalyze,
  analyzingPaper
}) {

  const isAnalyzing =
    analyzingPaper === paper.paper_url;


  return (

    <article className="paper-card">

      {/* PAPER ICON */}

      <div className="paper-icon">

        <BookOpen size={22} />

      </div>


      <div className="paper-content">

        {/* SOURCE */}

        <div className="paper-source">

          {paper.source}

        </div>


        {/* TITLE */}

        <h3>

          {paper.title}

        </h3>


        {/* META */}

        <div className="paper-meta">

          <span>
            {paper.year}
          </span>


          <span>
            •
          </span>


          <span>

            {paper.authors
              .slice(0, 3)
              .join(", ")}

            {paper.authors.length > 3 &&
              " et al."}

          </span>

        </div>


        {/* ABSTRACT */}

        <p className="paper-abstract">

          {paper.abstract}

        </p>


        {/* ACTIONS */}

        <div className="paper-actions">

          {/* VIEW PDF */}

          <a
            href={paper.pdf_url}
            target="_blank"
            rel="noopener noreferrer"
            className="primary-button"
          >

            <FileText size={16} />

            View PDF

          </a>


          {/* SOURCE */}

          <a
            href={paper.paper_url}
            target="_blank"
            rel="noopener noreferrer"
            className="secondary-button"
          >

            <ExternalLink size={16} />

            Source

          </a>


          {/* ANALYZE */}

          <button
            className="secondary-button"
            onClick={() =>
              handleAnalyze(paper)
            }
            disabled={isAnalyzing}
          >

            {isAnalyzing ? (

              <>

                <Loader2
                  size={16}
                  className="spin"
                />

                Analyzing...

              </>

            ) : (

              <>

                <Sparkles size={16} />

                Analyze

              </>

            )}

          </button>

        </div>

      </div>

    </article>

  );
}


/* =============================================
   FEATURE CARD
============================================= */

function FeatureCard({
  icon,
  title,
  description
}) {

  return (

    <div className="feature-card">

      <div className="feature-icon">

        {icon}

      </div>


      <h3>

        {title}

      </h3>


      <p>

        {description}

      </p>

    </div>

  );
}


export default App;