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
"""

import json
import logging
import os
import random
import time

from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors
from google.genai import types


# Load variables from backend/.env
load_dotenv()


# Safe diagnostic logger. NEVER logs the API key.
logger = logging.getLogger("researchos.gemini")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[ResearchOS] %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------

# Primary Gemini model. Can be overridden from .env using GEMINI_MODEL.
_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.8-flash"
)

# Optional fallback model. Only used if the primary model keeps failing with
# a transient error after all retries. Left empty to disable the fallback.
# Can be overridden from .env using GEMINI_FALLBACK_MODEL.
_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "").strip()


# ---------------------------------------------------------------------------
# Retry configuration
# ---------------------------------------------------------------------------

# Maximum number of additional retry attempts (3 retries on top of the
# initial attempt, as requested).
_MAX_RETRIES = 3

# Base delays (seconds) between retries. The delay for attempt N is taken
# from this list (clamped to the last entry if more retries are configured).
_RETRY_DELAYS = [2, 5, 10]

# Maximum random jitter (seconds) added to each delay to smooth out
# thundering-herd effects across concurrent requests.
_JITTER_MAX = 0.5


def _is_retryable_error(exc: Exception) -> bool:
    """
    Decide whether a Gemini error is a *transient* failure worth retrying.

    Retries on:
      - HTTP 5xx (ServerError, e.g. 503 UNAVAILABLE)
      - HTTP 429 (ClientError, rate limit / quota)
      - Any error whose message contains "UNAVAILABLE"
    """
    # google.genai raises ServerError for 5xx and ClientError for 4xx.
    if isinstance(exc, genai_errors.ServerError):
        return True

    if isinstance(exc, genai_errors.ClientError):
        # 429 -> too many requests / quota exceeded.
        if getattr(exc, "code", None) == 429:
            return True
        # Some 429-like conditions surface as a plain message instead of a
        # numeric code; cover that case too.
        message = (str(exc) or "").upper()
        if "429" in message or "QUOTA" in message or "RATE LIMIT" in message:
            return True

    # Catch-all for any APIError carrying an "UNAVAILABLE" status/message.
    if isinstance(exc, genai_errors.APIError):
        status = (getattr(exc, "status", "") or "").upper()
        message = (getattr(exc, "message", "") or "").upper()
        if "UNAVAILABLE" in status or "UNAVAILABLE" in message:
            return True
        if "503" in str(getattr(exc, "code", "")):
            return True

    # Be defensive: even non-APIError exceptions (e.g. network resets) that
    # mention UNAVAILABLE should be retried.
    if "UNAVAILABLE" in str(exc).upper():
        return True

    return False


def _delay_for_attempt(attempt: int) -> float:
    """
    Return the backoff delay (with jitter) before the given retry attempt.

    ``attempt`` is 0-based (0 = first retry). The base delays are
    [2, 5, 10] seconds; the last value is reused if more retries are
    configured than there are entries.
    """
    base = _RETRY_DELAYS[min(attempt, len(_RETRY_DELAYS) - 1)]
    jitter = random.uniform(0, _JITTER_MAX)
    return base + jitter


def _generate_with_retries(client, model: str, prompt: str, config):
    """
    Call ``client.models.generate_content`` with bounded retry logic.

    Returns the response on success. Raises ``RuntimeError`` if all
    attempts fail, with a clear message about the AI provider being
    temporarily unavailable.
    """
    last_error = None

    logger.info("Primary model: %s", model)

    for attempt in range(_MAX_RETRIES + 1):  # 1 initial + 3 retries
        try:
            logger.info(
                "Generating content with model=%s (attempt %d/%d)",
                model,
                attempt + 1,
                _MAX_RETRIES + 1,
            )
            return client.models.generate_content(
                model=model,
                contents=prompt,
                config=config,
            )
        except Exception as exc:
            last_error = exc

            logger.warning(
                "Primary attempt failed: %s | %s",
                type(exc).__name__,
                str(exc)[:200],
            )

            if not _is_retryable_error(exc):
                # Non-transient error -> do not retry.
                raise RuntimeError(
                    f"Gemini analysis failed with a non-retryable error: {exc}"
                ) from exc

            if attempt >= _MAX_RETRIES:
                # Out of retries.
                break

            delay = _delay_for_attempt(attempt)
            time.sleep(delay)

    raise RuntimeError(
        "The AI provider (Gemini) is temporarily unavailable. "
        f"The model '{model}' could not be reached after {_MAX_RETRIES} "
        "retry attempts. Please try again later."
    ) from last_error


def _model_is_available(client, model: str) -> bool:
    """
    Return True if ``model`` is usable through the installed Gemini API.

    Uses ``client.models.get`` which raises if the model does not exist or
    is not accessible with the current API key. Returns False on any
    failure rather than raising.
    """
    try:
        client.models.get(model=model)
        return True
    except Exception as exc:
        logger.warning(
            "models.get check failed for model=%s: %s | %s",
            model,
            type(exc).__name__,
            str(exc)[:200],
        )
        return False


def analyze_paper(
    title: str,
    abstract: str,
    paper_text: str,
) -> dict:
    """
    Analyze an academic research paper using Google Gemini.

    Parameters
    ----------
    title:
        Title of the research paper.

    abstract:
        Abstract of the research paper.

    paper_text:
        Text extracted from the research paper PDF.

    Returns
    -------
    dict
        Structured ResearchOS paper analysis.

    Raises
    ------
    RuntimeError
        If the Gemini API key is missing or the Gemini request fails.
    """

    # ---------------------------------------------------------
    # 1. Check API key
    # ---------------------------------------------------------

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. "
            "Please configure it in backend/.env"
        )

    # ---------------------------------------------------------
    # 2. Create Gemini client
    # ---------------------------------------------------------

    client = genai.Client(
        api_key=api_key
    )

    # ---------------------------------------------------------
    # 3. Prevent extremely large requests
    # ---------------------------------------------------------

    max_chars = 60000

    if not paper_text:
        paper_text = "No paper text was extracted."

    if len(paper_text) > max_chars:
        paper_text = paper_text[:max_chars]

    # ---------------------------------------------------------
    # 4. ResearchOS analysis prompt
    # ---------------------------------------------------------

    prompt = f"""
You are an expert AI research scientist and academic paper analyst.

Your job is to analyze the provided research paper for a platform
called ResearchOS.

ResearchOS helps students and researchers understand research papers,
identify limitations, discover research gaps, and generate meaningful
future research directions.

IMPORTANT RULES:

1. Do NOT invent information.
2. Clearly distinguish facts from your own technical analysis.
3. Base claims on the provided paper whenever possible.
4. If something is not available in the paper, write:
   "Not stated in the provided paper."
5. Do not assume datasets, metrics, architectures, or results that
   are not supported by the paper.
6. For inferred limitations, clearly mark them as:
   "AI-inferred limitation".
7. For research gaps, distinguish between:
   - gaps explicitly mentioned by the authors
   - gaps inferred from the paper
8. Be technically precise but easy for a student to understand.
9. Do not return Markdown.
10. Return ONLY valid JSON.

==================================================
PAPER INFORMATION
==================================================

TITLE:
{title}

ABSTRACT:
{abstract}

FULL PAPER TEXT:
{paper_text}

==================================================
RESEARCHOS ANALYSIS
==================================================

Return a JSON object with EXACTLY these keys:

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

==================================================
FIELD INSTRUCTIONS
==================================================

research_problem:
Explain the exact research problem the paper attempts to solve.

existing_approach:
Explain what approaches existed before this paper and their
important shortcomings.

proposed_method:
Explain what the authors propose and what is different about it.

architecture:
Explain the complete architecture or processing pipeline step-by-step.
If the paper does not provide enough architectural information,
say so.

dataset:
Mention:
- dataset name
- number of samples
- features
- preprocessing
- train/validation/test split
- important characteristics

Only include information actually supported by the paper.

model_algorithm:
Explain the main machine-learning model, algorithm, mathematical
method, or AI technique used.

results:
Explain the main experiments and important evaluation metrics.
Mention comparisons with baseline/state-of-the-art methods when
available.

limitations:
List limitations explicitly stated by the authors.

additional_technical_limitations:
Identify reasonable technical limitations that are NOT explicitly
stated by the authors.

Every item must start with:
"AI-inferred limitation:"

why_approach_may_fail:
Explain realistic situations where the proposed approach could
perform poorly.

Consider things such as:
- distribution shift
- insufficient data
- noisy data
- computational cost
- scalability
- generalization
- overfitting
- domain differences
- deployment constraints

Do not claim that these failures actually occurred unless the paper
provides evidence.

research_gap:
Separate the research gap into:

author_stated_gaps:
Gaps or future work explicitly mentioned by the authors.

ai_inferred_gaps:
Potential research gaps inferred from the paper.

possible_improvements:
Suggest technically meaningful improvements to the approach.

new_research_direction:
Suggest realistic research projects that could build upon this work.

Each suggestion should explain:
- what could be changed
- why it matters
- what research question could be investigated

overall_assessment:
Give a concise assessment of:
- research contribution
- technical significance
- practical usefulness
- remaining challenges

==================================================

Return ONLY valid JSON.
"""

    # ---------------------------------------------------------
    # 5. Send request to Gemini (with retries + fallback)
    # ---------------------------------------------------------

    config = types.GenerateContentConfig(
        temperature=0.2,
        response_mime_type="application/json",
    )

    # Try the primary model first. If it keeps failing with a transient
    # error after all retries, fall back to GEMINI_FALLBACK_MODEL only if
    # that model is actually available through the installed API.
    models_to_try = [_MODEL]
    if _FALLBACK_MODEL and _FALLBACK_MODEL != _MODEL:
        if _model_is_available(client, _FALLBACK_MODEL):
            models_to_try.append(_FALLBACK_MODEL)

    logger.info(
        "Models to try: %s",
        ", ".join(models_to_try),
    )

    last_error = None
    response = None

    for model in models_to_try:
        try:
            response = _generate_with_retries(
                client=client,
                model=model,
                prompt=prompt,
                config=config,
            )
            logger.info("Model %s succeeded.", model)
            break  # success -> no need to try further models
        except RuntimeError as exc:
            last_error = exc
            if model == _MODEL:
                logger.warning(
                    "Primary model exhausted after retries. "
                    "Attempting fallback model..."
                )
            # Continue to the next model (if any) before giving up.
            continue

    if response is None:
        # All models exhausted. Surface a clear, friendly error that
        # includes the ACTUAL underlying exception so it is diagnosable.
        underlying = ""
        if last_error is not None and last_error.__cause__ is not None:
            underlying = f" Underlying error: {last_error.__cause__}"
        elif last_error is not None:
            underlying = f" Last error: {last_error}"

        if len(models_to_try) > 1:
            message = (
                "The AI provider (Gemini) is temporarily unavailable. "
                "Both the primary model and the configured fallback model "
                "could not be reached. Please try again later."
                f"{underlying}"
            )
        else:
            message = str(last_error) + underlying
        raise RuntimeError(message) from last_error

    # ---------------------------------------------------------
    # 6. Extract Gemini response
    # ---------------------------------------------------------

    raw_text = getattr(
        response,
        "text",
        ""
    ) or ""

    raw_text = raw_text.strip()

    if not raw_text:
        raise RuntimeError(
            "Gemini returned an empty response."
        )

    # ---------------------------------------------------------
    # 7. Parse JSON
    # ---------------------------------------------------------

    try:

        analysis = json.loads(
            raw_text
        )

    except json.JSONDecodeError:

        # Sometimes a model can still return unexpected text.
        # Preserve it instead of crashing the API.

        analysis = {
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
            "research_gap": {
                "author_stated_gaps": [],
                "ai_inferred_gaps": []
            },
            "possible_improvements": [],
            "new_research_direction": [],
            "overall_assessment": "",
            "raw_response": raw_text
        }

    # ---------------------------------------------------------
    # 8. Return structured analysis
    # ---------------------------------------------------------

    return analysis