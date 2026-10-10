"""Pydantic schemas for ResearchOS."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class Paper(BaseModel):
    """Normalized research paper schema."""
    id: str
    title: str
    authors: List[str] = Field(default_factory=list)
    abstract: str = ""
    year: Optional[str] = None
    published_date: Optional[str] = None
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    paper_url: str = ""
    pdf_url: Optional[str] = None
    source: str = "Unknown"
    citation_count: Optional[int] = None
    journal: Optional[str] = None
    venue: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    score: Optional[float] = None


class ResearchRequest(BaseModel):
    """Request model for academic search."""
    query: str = Field(..., min_length=1, max_length=500, description="Search query")
    max_results: int = Field(default=30, ge=1, le=100, description="Target number of papers")

    @field_validator("query")
    @classmethod
    def strip_and_validate_query(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Query cannot be empty or only whitespace")
        return clean


class ResearchResponse(BaseModel):
    """Response model for academic search."""
    status: str
    query: str
    count: int
    papers: List[Paper]
    providers_queried: List[str] = Field(default_factory=list)
    providers_succeeded: List[str] = Field(default_factory=list)


class AnalyzePaperRequest(BaseModel):
    """Request model for AI paper analysis."""
    title: str = Field(..., min_length=1, max_length=1000)
    abstract: Optional[str] = Field(default="", max_length=100000)
    pdf_url: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Paper title cannot be empty")
        return clean


class ResearchGap(BaseModel):
    """Identified research gaps."""
    author_stated_gaps: List[str] = Field(default_factory=list)
    ai_inferred_gaps: List[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    """Structured paper analysis schema."""
    research_problem: str = ""
    existing_approach: str = ""
    proposed_method: str = ""
    architecture: str = ""
    dataset: str = ""
    model_algorithm: str = ""
    results: str = ""
    limitations: List[str] = Field(default_factory=list)
    additional_technical_limitations: List[str] = Field(default_factory=list)
    why_approach_may_fail: List[str] = Field(default_factory=list)
    research_gap: ResearchGap = Field(default_factory=ResearchGap)
    possible_improvements: List[str] = Field(default_factory=list)
    new_research_direction: List[str] = Field(default_factory=list)
    overall_assessment: str = ""
    evidence_basis: str = "Full-text analysis"
    reproducibility_score: Optional[int] = None


class AnalyzePaperResponse(BaseModel):
    """Response model for paper analysis."""
    status: str
    title: str
    analysis: AnalysisResult
    message: Optional[str] = None


class BatchPaperStatus(BaseModel):
    """Status and result of a paper within a batch analysis job."""
    id: str
    title: str
    status: str = "queued"  # queued | processing | completed | failed
    evidence_basis: str = "Pending"
    analysis: Optional[AnalysisResult] = None
    error: Optional[str] = None


class BatchAnalyzeRequest(BaseModel):
    """Request to batch analyze up to 30 papers."""
    papers: List[Dict[str, Any]] = Field(..., max_length=30)
    max_concurrent: int = Field(default=3, ge=1, le=5)


class BatchAnalyzeResponse(BaseModel):
    """Batch analysis results and statistics."""
    status: str
    total: int
    completed: int
    failed: int
    results: List[BatchPaperStatus]


class ResearchGapItem(BaseModel):
    """Synthesized research gap across multiple papers."""
    id: str
    title: str
    description: str
    gap_type: str = "Methodological"  # Methodological | Dataset | Evaluation | Scalability | Theoretical
    supporting_papers: List[str] = Field(default_factory=list)
    contradictory_evidence: List[str] = Field(default_factory=list)
    evidence_strength: str = "High"  # High | Medium | Emerging
    confidence: float = 0.85
    validation_experiment: str = ""
    known_uncertainties: List[str] = Field(default_factory=list)


class ContradictionItem(BaseModel):
    """Detected tension or contradictory findings between papers."""
    topic: str
    paper_a_title: str
    paper_a_claim: str
    paper_b_title: str
    paper_b_claim: str
    possible_explanation: str
    suggested_verification: str


class GapSynthesisRequest(BaseModel):
    """Request to synthesize gaps across analyzed papers."""
    query: str
    papers: List[Dict[str, Any]] = Field(default_factory=list)


class GapSynthesisResponse(BaseModel):
    """Synthesized gaps and contradictions."""
    status: str
    query: str
    gaps: List[ResearchGapItem]
    contradictions: List[ContradictionItem] = Field(default_factory=list)


class ExperimentDesignRequest(BaseModel):
    """Request to design an empirical experiment for a gap."""
    gap: Dict[str, Any]
    query: Optional[str] = ""
    supporting_papers: List[Dict[str, Any]] = Field(default_factory=list)


class ExperimentDesign(BaseModel):
    """Complete experimental protocol."""
    research_question: str
    hypothesis: str
    motivation: str
    dataset_recommendations: List[str] = Field(default_factory=list)
    baselines: List[str] = Field(default_factory=list)
    proposed_methodology: str
    independent_variables: List[str] = Field(default_factory=list)
    dependent_variables: List[str] = Field(default_factory=list)
    experimental_controls: List[str] = Field(default_factory=list)
    evaluation_metrics: List[str] = Field(default_factory=list)
    ablation_plan: List[str] = Field(default_factory=list)
    statistical_tests: List[str] = Field(default_factory=list)
    compute_requirements: str
    potential_risks_and_failure_modes: List[str] = Field(default_factory=list)
    validation_checklist: List[str] = Field(default_factory=list)


class ExperimentDesignResponse(BaseModel):
    """Response containing experiment design."""
    status: str
    experiment: ExperimentDesign


class ProjectBlueprintRequest(BaseModel):
    """Request to generate an implementable project blueprint."""
    title: Optional[str] = ""
    gap_or_idea: Dict[str, Any]
    supporting_papers: List[Dict[str, Any]] = Field(default_factory=list)
    available_compute: Optional[str] = "Standard GPU (1x RTX 4090 / Colab Pro)"
    timeline_weeks: Optional[int] = 8


class ProjectBlueprint(BaseModel):
    """Complete implementation blueprint."""
    project_title: str
    abstract: str
    problem_statement: str
    objectives: List[str] = Field(default_factory=list)
    literature_context: str
    proposed_architecture: str
    mermaid_diagram: Optional[str] = None
    recommended_tech_stack: List[str] = Field(default_factory=list)
    datasets: List[str] = Field(default_factory=list)
    implementation_phases: List[Dict[str, Any]] = Field(default_factory=list)
    starter_pseudocode: str
    evaluation_metrics: List[str] = Field(default_factory=list)
    feasibility_score: int = 85  # 0 - 100
    risks_and_mitigations: List[Dict[str, str]] = Field(default_factory=list)


class ProjectBlueprintResponse(BaseModel):
    """Response containing project blueprint."""
    status: str
    blueprint: ProjectBlueprint


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    service: str
    version: str
    gemini_configured: bool = False
