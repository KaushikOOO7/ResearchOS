"""
Academic paper analysis using Google Gemini.

ResearchOS AI Paper Analyzer:
- Research problem
- Existing approach
- Proposed method
- Architecture
- Dataset
- Model / algorithm
- Results
- Limitations
- Failure conditions
- Research gaps
- Possible improvements
- New research directions
- Overall assessment
"""

import json
import logging
import os
import random
import time
from typing import Any, Dict, Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("researchos.gemini")

# Model configuration
DEFAULT_MODEL = "gemini-2.5-flash"
_MODEL = os.getenv("GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "").strip()

_MAX_RETRIES = 2
_RETRY_DELAYS = [2.0, 5.0]


def is_gemini_configured() -> bool:
    """Check if a Gemini API key is configured without exposing it."""
    key = os.getenv("GEMINI_API_KEY", "").strip()
    return bool(key)


def _is_transient_error(exc: Exception) -> bool:
    """Identify if an error is temporary and safe to retry."""
    msg = str(exc).upper()
    return any(term in msg for term in ("429", "RESOURCE_EXHAUSTED", "RATE_LIMIT", "QUOTA", "503", "UNAVAILABLE", "TIMEOUT", "500"))


def analyze_paper(
    title: str,
    abstract: str,
    paper_text: str = "",
) -> Dict[str, Any]:
    """
    Analyze an academic research paper using Google Gemini.
    Returns validated structured ResearchOS analysis dict.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "Gemini API key is not configured. Please set GEMINI_API_KEY in backend/.env"
        )

    try:
        from google import genai
        from google.genai import types
    except ImportError as e:
        raise RuntimeError(
            "The google-genai package is not installed. Please install requirements: pip install google-genai"
        ) from e

    client = genai.Client(api_key=api_key)

    # Cap text length to avoid token limits
    max_chars = 50000
    cleaned_text = (paper_text or "").strip()
    if cleaned_text and len(cleaned_text) > max_chars:
        cleaned_text = cleaned_text[:max_chars]

    prompt = f"""
You are an expert AI research scientist and academic paper analyst.

Your job is to analyze the provided research paper for a platform called ResearchOS.
ResearchOS helps students and researchers understand papers, identify limitations, discover research gaps, and formulate future research directions.

RULES:
1. Base all facts on the provided paper text and abstract.
2. If specific details are not stated, output "Not stated in the provided paper."
3. For inferred limitations, prefix each with "AI-inferred limitation:".
4. For research gaps, distinguish author-stated gaps from AI-inferred gaps.
5. Return ONLY a valid JSON object matching the exact schema below without markdown backticks.

==================================================
PAPER INFORMATION
==================================================
TITLE:
{title}

ABSTRACT:
{abstract or 'No abstract provided.'}

PAPER TEXT:
{cleaned_text or 'Full paper text unavailable; abstract provided above.'}

==================================================
TARGET JSON STRUCTURE
==================================================
{{
    "research_problem": "Precise research problem the paper addresses",
    "existing_approach": "Prior approaches and their limitations",
    "proposed_method": "Novel methodology proposed in the paper",
    "architecture": "Architecture and pipeline description",
    "dataset": "Datasets used, samples, evaluation splits",
    "model_algorithm": "Core algorithms, architectures, models",
    "results": "Key empirical metrics and benchmark comparisons",
    "limitations": [
        "Limitation explicitly stated by authors"
    ],
    "additional_technical_limitations": [
        "AI-inferred limitation: Technical trade-off not explicitly stated"
    ],
    "why_approach_may_fail": [
        "Failure condition (distribution shift, edge cases, scalability)"
    ],
    "research_gap": {{
        "author_stated_gaps": [
            "Future work or open questions highlighted by authors"
        ],
        "ai_inferred_gaps": [
            "Unexplored angles or under-tested settings inferred from work"
        ]
    }},
    "possible_improvements": [
        "Actionable technical enhancement"
    ],
    "new_research_direction": [
        "Novel future research project building upon this work"
    ],
    "overall_assessment": "Concise summary of research significance, contribution, and challenges"
}}
"""

    config = types.GenerateContentConfig(
        temperature=0.2,
        response_mime_type="application/json",
    )

    models_to_try = [_MODEL]
    if _FALLBACK_MODEL and _FALLBACK_MODEL != _MODEL:
        models_to_try.append(_FALLBACK_MODEL)

    last_error: Optional[Exception] = None
    response = None

    for model_name in models_to_try:
        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=config,
                )
                break
            except Exception as exc:
                last_error = exc
                if not _is_transient_error(exc) or attempt >= _MAX_RETRIES:
                    break
                delay = _RETRY_DELAYS[min(attempt, len(_RETRY_DELAYS) - 1)] + random.uniform(0.1, 0.4)
                time.sleep(delay)

        if response is not None:
            break

    if response is None:
        safe_msg = str(last_error or "Unknown error")
        # Ensure API key is never in the error message
        if api_key in safe_msg:
            safe_msg = safe_msg.replace(api_key, "[REDACTED]")
        raise RuntimeError(f"Gemini analysis unavailable: {safe_msg}")

    raw_text = getattr(response, "text", "") or ""
    raw_text = raw_text.strip()
    if not raw_text:
        raise RuntimeError("Gemini returned an empty response.")

    # Strip markdown code fence if model returned it despite instructions
    if raw_text.startswith("```"):
        lines = raw_text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        raw_text = "\n".join(lines).strip()

    try:
        analysis_data = json.loads(raw_text)
    except json.JSONDecodeError:
        # Fallback dictionary if JSON parser fails
        analysis_data = {
            "research_problem": "Raw analysis output obtained",
            "existing_approach": "",
            "proposed_method": "",
            "architecture": "",
            "dataset": "",
            "model_algorithm": "",
            "results": "",
            "limitations": [],
            "additional_technical_limitations": [],
            "why_approach_may_fail": [],
            "research_gap": {
                "author_stated_gaps": [],
                "ai_inferred_gaps": []
            },
            "possible_improvements": [],
            "new_research_direction": [],
            "overall_assessment": raw_text[:1000]
        }

    return analysis_data
