"""
Text utilities used across ResearchOS.

Everything here is deterministic and dependency-free (stdlib only) so it can
be unit-tested in isolation and reused by the search engine, the deduplicator,
the ranker and the PDF pipeline.
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Dict, Iterable, List, Sequence, Set, Tuple

# ---------------------------------------------------------------------------
# Stopwords (conservative list: only words that never carry research meaning)
# ---------------------------------------------------------------------------

STOPWORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "also", "am",
    "an", "and", "any", "are", "as", "at", "be", "because", "been", "before",
    "being", "below", "between", "both", "but", "by", "can", "cannot", "could",
    "did", "do", "does", "doing", "done", "down", "during", "each", "few",
    "for", "from", "further", "had", "has", "have", "having", "he", "her",
    "here", "hers", "herself", "him", "himself", "his", "how", "however", "i",
    "if", "in", "into", "is", "it", "its", "itself", "just", "me", "more",
    "most", "my", "myself", "no", "nor", "not", "now", "of", "off", "on",
    "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out",
    "over", "own", "same", "she", "should", "so", "some", "such", "than",
    "that", "the", "their", "theirs", "them", "themselves", "then", "there",
    "these", "they", "this", "those", "through", "to", "too", "under", "until",
    "up", "use", "used", "using", "very", "was", "we", "were", "what", "when",
    "where", "which", "while", "who", "whom", "why", "will", "with", "would",
    "you", "your", "yours", "yourself", "yourselves", "based", "novel",
    "approach", "study", "paper", "research", "method", "methods", "results",
    "review", "analysis", "state", "art",
}

# Words that describe *intent* rather than *topic*; stripped from the topic
# signal but kept for query understanding.
INTENT_WORDS: Set[str] = {
    "recent", "latest", "new", "newest", "current", "modern", "survey",
    "review", "overview", "sota", "benchmark", "comparison", "compare",
    "introduction", "tutorial", "explain", "explainable", "future",
}

# ---------------------------------------------------------------------------
# Acronym handling
#
# A small, curated, *extensible* map. Different providers tokenise acronyms
# differently ("GNN" vs "graph neural network"), so expanding them measurably
# improves cross-source matching. Unknown acronyms are left untouched --
# nothing is guessed.
# ---------------------------------------------------------------------------

ACRONYMS: Dict[str, str] = {
    "gnn": "graph neural network",
    "gnns": "graph neural network",
    "cnn": "convolutional neural network",
    "cnns": "convolutional neural network",
    "rnn": "recurrent neural network",
    "lstm": "long short term memory",
    "gru": "gated recurrent unit",
    "gan": "generative adversarial network",
    "gans": "generative adversarial network",
    "vae": "variational autoencoder",
    "ae": "autoencoder",
    "mlp": "multilayer perceptron",
    "llm": "large language model",
    "llms": "large language model",
    "lm": "language model",
    "rag": "retrieval augmented generation",
    "nlp": "natural language processing",
    "cv": "computer vision",
    "ml": "machine learning",
    "dl": "deep learning",
    "rl": "reinforcement learning",
    "ner": "named entity recognition",
    "qa": "question answering",
    "ir": "information retrieval",
    "kg": "knowledge graph",
    "kge": "knowledge graph embedding",
    "bert": "bidirectional encoder representations transformers",
    "vit": "vision transformer",
    "sota": "state of the art",
    "gcn": "graph convolutional network",
    "gat": "graph attention network",
    "mpnn": "message passing neural network",
    "dgl": "deep graph library",
    "smiles": "simplified molecular input line entry system",
    "qsar": "quantitative structure activity relationship",
    "admet": "absorption distribution metabolism excretion toxicity",
    "iot": "internet of things",
    "uav": "unmanned aerial vehicle",
    "eeg": "electroencephalography",
    "ecg": "electrocardiography",
    "fmri": "functional magnetic resonance imaging",
    "mri": "magnetic resonance imaging",
    "ct": "computed tomography",
    "wsi": "whole slide image",
    "sar": "synthetic aperture radar",
    "lidar": "light detection and ranging",
    "fl": "federated learning",
    "xai": "explainable artificial intelligence",
    "nlg": "natural language generation",
    "mt": "machine translation",
    "asr": "automatic speech recognition",
    "tts": "text to speech",
    "ocr": "optical character recognition",
    "vqa": "visual question answering",
    "ssl": "self supervised learning",
    "gnnbased": "graph neural network",
    "moe": "mixture of experts",
    "peft": "parameter efficient fine tuning",
    "lora": "low rank adaptation",
    "ragbased": "retrieval augmented generation",
}

# Reverse map: "graph neural network" -> "gnn" for query expansion.
_ACRONYM_REVERSE: Dict[str, str] = {}
for _short, _long in ACRONYMS.items():
    _ACRONYM_REVERSE.setdefault(_long, _short)

# ---------------------------------------------------------------------------
# Biomedical lexicon (used to decide whether PubMed is applicable)
# ---------------------------------------------------------------------------

BIOMEDICAL_TERMS: Set[str] = {
    "drug", "drugs", "disease", "diseases", "clinical", "patient", "patients",
    "cancer", "tumor", "tumour", "protein", "proteins", "gene", "genes",
    "genomic", "genomics", "biomedical", "biology", "biological", "molecular",
    "molecule", "molecules", "therapy", "therapeutic", "medical", "medicine",
    "health", "healthcare", "diagnosis", "diagnostic", "biomarker", "cells",
    "cell", "tissue", "enzyme", "receptor", "antibody", "vaccine", "virus",
    "bacteria", "infection", "epidemiology", "pharmacology", "toxicology",
    "admet", "qsar", "crispr", "rna", "dna", "sequencing", "ehr", "radiology",
    "histopathology", "eeg", "ecg", "fmri", "mri", "electroencephalography",
}

# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

_LIGATURES = {
    "\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl", "\ufb03": "ffi",
    "\ufb04": "ffl", "\u2019": "'", "\u2018": "'", "\u201c": '"',
    "\u201d": '"', "\u2013": "-", "\u2014": "-", "\u2212": "-",
    "\u00a0": " ", "\u2009": " ", "\u2028": " ", "\u2029": " ",
}

_WHITESPACE_RE = re.compile(r"[ \t\x0b\x0c\r\f]+")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9 ]+")
_MULTI_SPACE_RE = re.compile(r" {2,}")
_HYPHEN_BREAK_RE = re.compile(r"(\w)-\n(\w)")
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[-'][a-z0-9]+)*")
_SUFFIX_RE = re.compile(r"(?P<stem>.{4,}?)(?:ings?|ed|es|s|ly|ity|ities)$")


def fix_ligatures(text: str) -> str:
    """Replace typographic ligatures/quotes that break tokenisation."""
    for bad, good in _LIGATURES.items():
        text = text.replace(bad, good)
    return text


def strip_accents(text: str) -> str:
    """Remove combining accents (``Beyoncé`` -> ``Beyonce``)."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize_space(text: str) -> str:
    """Collapse runs of whitespace into single spaces."""
    if not text:
        return ""
    text = fix_ligatures(text)
    text = _WHITESPACE_RE.sub(" ", text)
    text = _MULTI_NEWLINE_RE.sub("\n\n", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    return text.strip()


def normalize_title(title: str) -> str:
    """
    Produce a canonical title key used for exact/near duplicate detection.

    Lowercase, accent-free, punctuation-free, single-spaced.
    """
    if not title:
        return ""
    text = strip_accents(fix_ligatures(title)).lower()
    text = text.replace("&", " and ")
    text = _NON_ALNUM_RE.sub(" ", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    return text.strip()


def normalize_doi(doi: str | None) -> str:
    """Normalise a DOI to its bare lowercase form (no URL prefix)."""
    if not doi:
        return ""
    value = str(doi).strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/",
                   "http://dx.doi.org/", "doi:", "doi "):
        if value.startswith(prefix):
            value = value[len(prefix):]
    return value.strip().strip(".")


def normalize_arxiv_id(arxiv_id: str | None) -> str:
    """
    Normalise an arXiv identifier (strip URL prefix and version suffix).

    ``https://arxiv.org/abs/2401.01234v3`` -> ``2401.01234``
    """
    if not arxiv_id:
        return ""
    value = str(arxiv_id).strip()
    for prefix in ("https://arxiv.org/abs/", "http://arxiv.org/abs/",
                   "https://arxiv.org/pdf/", "http://arxiv.org/pdf/",
                   "arxiv:"):
        if value.lower().startswith(prefix):
            value = value[len(prefix):]
    value = value.split("?")[0]
    if value.lower().endswith(".pdf"):
        value = value[:-4]
    value = re.sub(r"v\d+$", "", value, flags=re.IGNORECASE)
    return value.strip().strip("/").lower()


def tokenize(text: str) -> List[str]:
    """Lowercase word/number tokens (keeps hyphens/apostrophes inside words)."""
    if not text:
        return []
    return _TOKEN_RE.findall(strip_accents(fix_ligatures(text)).lower())


def stem(token: str) -> str:
    """
    Very light, conservative stemmer.

    Only strips common English inflections on words of 5+ characters so that
    meaningful short tokens (``gan``, ``lstm``) are never mangled. This is a
    heuristic, not a linguistically complete stemmer -- documented as such.
    """
    if len(token) < 5:
        return token
    match = _SUFFIX_RE.match(token)
    if not match:
        return token
    candidate = match.group("stem")
    return candidate if len(candidate) >= 4 else token


def content_tokens(text: str) -> List[str]:
    """Tokens with stopwords removed (stopwords are never stemmed away)."""
    return [tok for tok in tokenize(text) if tok not in STOPWORDS and len(tok) > 1]


def significance_tokens(text: str) -> List[str]:
    """Stemmed, stopword-free tokens used by the relevance scorer."""
    return [stem(tok) for tok in content_tokens(text)]


def ngrams(tokens: Sequence[str], n: int) -> List[str]:
    """Return space-joined n-grams from a token sequence."""
    if n <= 0 or len(tokens) < n:
        return []
    return [" ".join(tokens[i: i + n]) for i in range(len(tokens) - n + 1)]


# ---------------------------------------------------------------------------
# Similarity
# ---------------------------------------------------------------------------

def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    """Jaccard similarity between two token collections."""
    set_a, set_b = set(a), set(b)
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def sequence_ratio(a: str, b: str) -> float:
    """Ratios of matching characters between two strings (0-1)."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def token_containment(a: str, b: str) -> float:
    """
    How completely the smaller token set is contained in the larger one.

    ``1.0`` means every token of the shorter title appears in the longer one
    (the classic subtitle case: ``X`` vs ``X: A Survey``).
    """
    tokens_a, tokens_b = set(tokenize(a)), set(tokenize(b))
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / min(len(tokens_a), len(tokens_b))


def token_set_ratio(a: str, b: str) -> float:
    """
    Order-insensitive fuzzy similarity that is robust to added subtitles.

    Combines the plain character ratio with a token-overlap term, which is far
    more reliable than character matching alone for academic titles
    (``... : A Survey`` suffixes, subtitle reordering, etc.).
    """
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    char_ratio = sequence_ratio(a, b)
    tokens_a, tokens_b = set(tokenize(a)), set(tokenize(b))
    overlap = jaccard(tokens_a, tokens_b)
    containment = 0.0
    if tokens_a and tokens_b:
        containment = len(tokens_a & tokens_b) / min(len(tokens_a), len(tokens_b))
    return max(char_ratio, 0.55 * overlap + 0.45 * containment)


# ---------------------------------------------------------------------------
# Query understanding helpers
# ---------------------------------------------------------------------------

def extract_acronyms(text: str) -> Dict[str, str]:
    """Return ``{acronym: expansion}`` for known acronyms found in ``text``."""
    found: Dict[str, str] = {}
    lowered = strip_accents(text or "").lower()
    for token in set(tokenize(lowered)):
        expansion = ACRONYMS.get(token)
        if expansion:
            found[token] = expansion
    # Also expand spelled-out phrases into their acronym ("graph neural
    # network" -> "gnn") so metadata written with either form still matches.
    for long_form, short_form in _ACRONYM_REVERSE.items():
        if long_form in lowered:
            found.setdefault(short_form, long_form)
    return found


def keyphrases(text: str, max_phrases: int = 8, max_terms: int = 14) -> Tuple[List[str], List[str]]:
    """
    Extract simple keyword phrases from a query.

    Returns ``(phrases, terms)`` where phrases are 2-3 word n-grams and terms
    are individual content words. Deterministic and cheap -- no model needed.
    """
    tokens = content_tokens(text)
    if not tokens:
        return [], []

    # Frequency of each unigram inside the (short) query is a decent salience
    # proxy; order of appearance breaks ties.
    order: Dict[str, int] = {}
    for index, token in enumerate(tokens):
        order.setdefault(stem(token), index)

    bigrams = ngrams(tokens, 2)
    trigrams = ngrams(tokens, 3)

    def rank(phrase: str) -> Tuple[int, int, int]:
        words = phrase.split()
        length_bonus = -len(words)  # prefer longer phrases
        generic = sum(1 for w in words if w in INTENT_WORDS)
        return (generic, length_bonus, order.get(stem(words[0]), 99))

    candidates = [p for p in trigrams if not any(w in INTENT_WORDS for w in p.split())]
    candidates += [p for p in bigrams if not any(w in INTENT_WORDS for w in p.split())]
    phrases = sorted(dict.fromkeys(candidates), key=rank)[:max_phrases]

    terms: List[str] = []
    for token in tokens:
        if token in INTENT_WORDS:
            continue
        if token not in terms:
            terms.append(token)
    return phrases, terms[:max_terms]


def is_biomedical(text: str) -> bool:
    """True when the query shows clear biomedical signal (enables PubMed)."""
    tokens = set(tokenize(text or ""))
    if not tokens:
        return False
    hits = tokens & BIOMEDICAL_TERMS
    return len(hits) >= 1


def detect_year_intent(text: str) -> Tuple[bool, int | None]:
    """
    Detect recency intent and an explicit year lower bound.

    Returns ``(wants_recent, year_from)``.
    """
    lowered = (text or "").lower()
    wants_recent = bool(re.search(r"\b(recent|latest|newest|sota|state of the art|cutting[- ]edge)\b", lowered))
    year_from: int | None = None
    explicit = re.findall(r"\b(19|20)\d{2}\b", lowered)
    if explicit:
        years = [int(y) for y in re.findall(r"\b((?:19|20)\d{2})\b", lowered)]
        if years:
            year_from = min(years)
    match = re.search(r"\b(?:last|past)\s+(\d{1,2})\s+years?\b", lowered)
    if match:
        from datetime import datetime

        try:
            years_back = int(match.group(1))
        except ValueError:
            years_back = 5
        year_from = datetime.utcnow().year - min(max(years_back, 1), 50)
        wants_recent = True
    if re.search(r"\bsince\s+((?:19|20)\d{2})\b", lowered):
        year_from = int(re.search(r"\bsince\s+((?:19|20)\d{2})\b", lowered).group(1))
    return wants_recent, year_from


# ---------------------------------------------------------------------------
# Truncation / sanitisation
# ---------------------------------------------------------------------------

def truncate_smart(text: str, max_chars: int, suffix: str = "\n\n[...truncated...]") -> str:
    """
    Truncate ``text`` at a paragraph/sentence boundary near ``max_chars``.

    Never cuts in the middle of a word when a reasonable boundary exists.
    """
    if not text or len(text) <= max_chars:
        return text or ""
    window = text[:max_chars]
    for boundary in ("\n\n", ". ", "\n"):
        index = window.rfind(boundary)
        if index > max_chars * 0.6:
            return window[:index].rstrip() + suffix
    return window.rstrip() + suffix


def sanitize_external_text(text: str, max_chars: int | None = None) -> str:
    """
    Clean third-party text (titles/abstracts) before it reaches the UI.

    Strips control characters and JATS/HTML markup, collapses whitespace and
    optionally truncates. Rendering is additionally escaped by React.
    """
    if not text:
        return ""
    cleaned = re.sub(r"<[^>]+>", " ", str(text))
    cleaned = re.sub(r"&(?:lt|gt|amp|quot|apos|#\d+);", " ", cleaned)
    cleaned = "".join(ch for ch in cleaned if ch.isprintable() or ch in "\n\t ")
    cleaned = normalize_space(cleaned)
    # Metadata fields (titles, abstracts, venues) are single-block strings:
    # flatten any remaining line breaks so cards never render ragged text.
    cleaned = re.sub(r"\s+", " ", cleaned)
    if max_chars is not None and len(cleaned) > max_chars:
        cleaned = truncate_smart(cleaned, max_chars, suffix="…")
    return cleaned


def extract_first_json_object(text: str) -> str | None:
    """
    Return the first balanced ``{...}`` block found in ``text``.

    Used as a repair path when a language model wraps JSON in prose or code
    fences. Returns ``None`` when no balanced object exists.
    """
    if not text:
        return None
    start = text.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start: index + 1]
        start = text.find("{", start + 1)
    return None
