"""
ResearchOS AI paper analysis.

Turns extracted paper text into the structured analysis the platform promises
(project brief, sections 14-16):

    research_problem, existing_approach, proposed_method, architecture,
    dataset, model_algorithm, results, limitations,
    additional_technical_limitations, why_approach_may_fail, research_gap
    {author_stated_gaps, ai_inferred_gaps}, possible_improvements,
    new_research_direction, overall_assessment

The model is instructed to distinguish *what the paper states* from *what the
analyst infers*, to write "Not stated in the provided paper." instead of
guessing, and to return strict JSON. Responses are then validated and
normalised through :class:`~app.schemas.analysis.PaperAnalysis`, so a slightly
malformed model reply degrades gracefully instead of breaking the UI.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from pydantic import ValidationError

from app.schemas.analysis import PaperAnalysis
from app.services.gemini_client import AIProviderError, GeminiClient
from app.utils.logging_setup import get_logger
from app.utils.text import extract_first_json_object

logger = get_logger("analyzer")

SYSTEM_INSTRUCTION = """You are ResearchOS, a rigorous AI research analyst.

You read one research paper at a time and produce a structured, technically
precise analysis for students, engineers and researchers.

NON-NEGOTIABLE RULES
1. Never invent datasets, dataset sizes, metrics, architectures, results,
   baselines, or citations. If the paper does not state something, write
   exactly: "Not stated in the provided paper."
2. Separate facts from inference:
   - limitations -> only limitations the AUTHORS state.
   - additional_technical_limitations -> your own analysis; each item MUST
     start with "AI-inferred limitation:".
   - research_gap.author_stated_gaps -> gaps/future work the authors mention;
     each item MUST start with "Author-stated gap:".
   - research_gap.ai_inferred_gaps -> gaps you infer; each item MUST start
     with "AI-inferred gap:".
   - why_approach_may_fail -> realistic failure scenarios, phrased as
     possibilities. Never claim a failure occurred unless the paper reports it.
3. Quote numbers only when they appear in the text.
4. Be concrete and technical: name the models, losses, datasets and metrics
   that the paper actually uses.
5. Prefer short, information-dense sentences over long paragraphs.
6. Never output Markdown, prose outside JSON, code fences, or comments.
7. Output must be a single valid JSON object matching the requested schema."""

_PROMPT_TEMPLATE = """Analyse the research paper below for ResearchOS.

TITLE:
{title}

ABSTRACT (as published):
{abstract}

{mode_note}
MEDIA / FULL TEXT:
{paper_text}

Return ONE JSON object with exactly these keys:

{{
  "research_problem": "",
  "existing_approach": "",
  "proposed_method": "",
  "architecture": "",
  "dataset": "",
  "model_algorithm": "",
  "results": "",
  "limitations": [],
  "additional_technical_limitations": [],
  "why_approach_may_fail": [],
  "research_gap": {{
    "author_stated_gaps": [],
    "ai_inferred_gaps": []
  }},
  "possible_improvements": [],
  "new_research_direction": [],
  "overall_assessment": ""
}}

FIELD REQUIREMENTS

research_problem: the exact problem the paper addresses, in 2-4 sentences.
existing_approach: what was done before this work and why it was insufficient.
proposed_method: what the authors propose; state precisely what is new.
architecture: the pipeline/modules step by step. Name layers, encoders,
  fusion strategies, losses. If the paper is vague, say so explicitly.
dataset: dataset names, sizes, splits, preprocessing, and domain — ONLY if
  stated. Otherwise "Not stated in the provided paper."
model_algorithm: the core algorithm/model and the training objective.
results: headline numbers with the metrics used, and baseline comparisons.
  Do not extrapolate beyond reported results.
limitations: 2-6 items, each starting with "Author-stated limitation:".
additional_technical_limitations: 2-6 items, each starting with
  "AI-inferred limitation:".
why_approach_may_fail: 2-6 concrete scenarios (distribution shift, label
  noise, compute cost, scalability, deployment constraints, evaluation bias…).
research_gap.author_stated_gaps: from the paper's future-work/limitations.
research_gap.ai_inferred_gaps: gaps you infer across the problem space.
possible_improvements: 2-6 technically actionable improvements.
new_research_direction: 2-5 directions; each states what changes, why it
  matters and the research question it answers.
overall_assessment: 3-5 sentences on contribution, significance, practical
  usefulness and remaining challenges.

Calibrate confidence: if the full text is unavailable, base claims on the
abstract and say so inside the relevant field."""

_ABSTRACT_ONLY_NOTE = """NOTE: the full text could not be retrieved, so you only have the title and
abstract. Keep every field strictly within what the abstract supports, and
mark anything beyond it as "Not stated in the provided paper."
"""


@dataclass
class AnalysisResult:
    """Validated analysis plus provenance."""

    analysis: PaperAnalysis
    model: str
    used_fallback: bool
    attempts: int
    prompt_chars: int


def build_prompt(
    title: str,
    abstract: str,
    paper_text: str,
    abstract_only: bool = False,
) -> str:
    """Compose the analysis prompt (pure function -- easy to unit test)."""
    return _PROMPT_TEMPLATE.format(
        title=title.strip(),
        abstract=(abstract or "").strip() or "Not available.",
        paper_text=(paper_text or "").strip() or "Not available.",
        mode_note=_ABSTRACT_ONLY_NOTE if abstract_only else "",
    )


def _parse_analysis(raw_text: str) -> Optional[PaperAnalysis]:
    """Parse + validate a model reply; ``None`` when it is not usable JSON."""
    if not raw_text:
        return None

    payload = None
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        candidate = extract_first_json_object(raw_text)
        if candidate:
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                payload = None

    if payload is None:
        return None

    # Some models wrap the object: {"analysis": {...}} / [ {...} ].
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        payload = payload[0]
    if isinstance(payload, dict):
        for wrapper in ("analysis", "result", "output", "data"):
            inner = payload.get(wrapper)
            if isinstance(inner, dict) and "research_problem" in inner:
                payload = inner
                break

    if not isinstance(payload, dict):
        return None

    try:
        return PaperAnalysis.model_validate(payload)
    except ValidationError as exc:
        logger.info("Analysis validation failed: %d error(s)", exc.error_count())
        return None


def analyze_paper(
    title: str,
    abstract: str,
    paper_text: str,
    abstract_only: bool = False,
    client: Optional[GeminiClient] = None,
) -> AnalysisResult:
    """
    Analyse a paper and return the validated ResearchOS analysis.

    Raises
    ------
    AIProviderError
        On provider failures (with a user-safe message) or when the model
        repeatedly returns unusable JSON.
    """
    client = client or GeminiClient()
    prompt = build_prompt(title, abstract, paper_text, abstract_only=abstract_only)

    logger.info("AI analysis started (%d prompt characters)", len(prompt))

    result = client.generate_json(prompt, system_instruction=SYSTEM_INSTRUCTION)
    analysis = _parse_analysis(result.text)

    # One bounded repair attempt with a stricter instruction.
    if analysis is None:
        logger.info("AI response was not valid analysis JSON — requesting a repair")
        repair_prompt = (
            f"{prompt}\n\nIMPORTANT: your previous reply could not be parsed. "
            "Return ONLY the JSON object, with no prose, no code fences and no trailing text."
        )
        result = client.generate_json(repair_prompt, system_instruction=SYSTEM_INSTRUCTION)
        analysis = _parse_analysis(result.text)

    if analysis is None:
        raise AIProviderError(
            "The AI returned a response that ResearchOS could not read as a structured analysis. "
            "Please try again.",
            code="invalid_json",
            retryable=True,
            model=result.model,
        )

    return AnalysisResult(
        analysis=analysis,
        model=result.model,
        used_fallback=result.used_fallback,
        attempts=result.attempts,
        prompt_chars=len(prompt),
    )


def analyzer_status() -> dict:
    """Non-sensitive status used by ``/health``."""
    client = GeminiClient()
    return {
        "configured": client.configured,
        "model": client.model or None,
        "fallback_model": client.fallback_model or None,
    }
