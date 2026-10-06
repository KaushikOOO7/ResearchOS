"""Tests for the deterministic text utilities."""

from __future__ import annotations

from app.utils.text import (
    extract_acronyms,
    extract_first_json_object,
    is_biomedical,
    keyphrases,
    normalize_arxiv_id,
    normalize_doi,
    normalize_title,
    sanitize_external_text,
    significance_tokens,
    token_set_ratio,
    truncate_smart,
)


class TestNormalisation:
    def test_normalize_doi_strips_url_prefixes_and_lowercases(self):
        assert normalize_doi("https://doi.org/10.1000/ABC.Def") == "10.1000/abc.def"
        assert normalize_doi("doi:10.1000/xyz") == "10.1000/xyz"
        assert normalize_doi(None) == ""

    def test_normalize_arxiv_id_strips_url_and_version(self):
        assert normalize_arxiv_id("http://arxiv.org/abs/2401.01234v2") == "2401.01234"
        assert normalize_arxiv_id("arXiv:2401.01234") == "2401.01234"
        assert normalize_arxiv_id("2401.01234v10") == "2401.01234"

    def test_normalize_title_is_punctuation_free(self):
        assert normalize_title("Graph Neural Networks: A Survey!") == "graph neural networks a survey"
        assert normalize_title("Don't Panic — Really") == "don t panic really"

    def test_sanitize_external_text_removes_markup_and_controls(self):
        cleaned = sanitize_external_text("<jats:p>Hello</jats:p>\x00 world")
        assert cleaned == "Hello world"


class TestTokenisation:
    def test_significance_tokens_drop_stopwords_and_stem(self):
        tokens = significance_tokens("Graph neural networks for drug discovery")
        assert "graph" in tokens
        assert "neural" in tokens
        assert "for" not in tokens

    def test_keyphrases_prefers_meaningful_bigrams(self):
        phrases, terms = keyphrases("Graph neural networks for molecular property prediction")
        assert "graph neural" in phrases
        assert "molecular property" in phrases
        assert "molecular" in terms

    def test_acronym_expansion(self):
        expansions = extract_acronyms("GNN models for ADMET prediction")
        assert expansions.get("gnn") == "graph neural network"
        assert expansions.get("admet")

    def test_biomedical_detection(self):
        assert is_biomedical("graph neural networks for drug discovery")
        assert not is_biomedical("federated learning for power grid optimisation")


class TestSimilarity:
    def test_token_set_ratio_handles_subtitles(self):
        a = normalize_title("Graph Neural Networks for Molecular Property Prediction")
        b = normalize_title(
            "Graph Neural Networks for Molecular Property Prediction: A Survey"
        )
        assert token_set_ratio(a, b) > 0.85

    def test_token_set_ratio_rejects_unrelated_titles(self):
        a = normalize_title("Graph Neural Networks for Drug Discovery")
        b = normalize_title("Power Grid Load Forecasting with Recurrent Networks")
        assert token_set_ratio(a, b) < 0.5


class TestTextHandling:
    def test_truncate_smart_prefers_boundaries(self):
        text = "First sentence. " * 50
        truncated = truncate_smart(text, 120)
        assert len(truncated) <= 160
        assert truncated.startswith("First sentence.")

    def test_extract_first_json_object_ignores_surrounding_prose(self):
        raw = 'Here you go:\n```json\n{"a": {"b": 1}}\n```\nThanks!'
        assert extract_first_json_object(raw) == '{"a": {"b": 1}}'

    def test_extract_first_json_object_handles_braces_in_strings(self):
        raw = 'prefix {"note": "use { braces } carefully"} suffix'
        assert extract_first_json_object(raw) == '{"note": "use { braces } carefully"}'
