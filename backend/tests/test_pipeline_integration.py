"""
Full-pipeline integration test.

All five providers are exercised through the real ``run_search`` pipeline with
mocked HTTP transports, so normalisation → deduplication → ranking → API
serialisation is verified end-to-end without touching the network.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.research import arxiv as arxiv_module
from app.research import crossref as crossref_module
from app.research import openalex as openalex_module
from app.research import pubmed as pubmed_module
from app.research.search_engine import run_search
from app.services.cache import search_cache

QUERY = "Graph neural networks for molecular property prediction"

ARXIV_XML = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2401.11111v1</id>
    <published>2024-01-10T00:00:00Z</published>
    <title>Message Passing Graph Neural Networks for Molecular Property Prediction</title>
    <summary>We propose a message passing graph neural network for molecular property
      prediction, evaluated on MoleculeNet datasets.</summary>
    <author><name>Riya Sharma</name></author>
    <arxiv:primary_category term="cs.LG"/>
    <link title="pdf" href="https://arxiv.org/pdf/2401.11111v1" type="application/pdf"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2402.22222v1</id>
    <published>2024-02-10T00:00:00Z</published>
    <title>Graph Neural Networks for Molecular Property Prediction: A Benchmark</title>
    <summary>A benchmark study of graph neural networks for molecular property prediction.</summary>
    <author><name>Wei Chen</name></author>
    <arxiv:primary_category term="cs.LG"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2001.33333v1</id>
    <published>2020-01-10T00:00:00Z</published>
    <title>Deep Learning for Power Grid State Estimation</title>
    <summary>Deep learning for power grid state estimation.</summary>
    <arxiv:primary_category term="eess.SP"/>
  </entry>
</feed>
"""

OPENALEX_PAYLOAD = {
    "results": [
        {
            "id": "https://openalex.org/W1",
            "doi": "https://doi.org/10.1000/gnn.1",
            "title": "Message Passing Graph Neural Networks for Molecular Property Prediction",
            "publication_year": 2024,
            "cited_by_count": 64,
            "type": "article",
            "authorships": [{"author": {"display_name": "Riya Sharma"}}],
            "abstract_inverted_index": {
                "We": [0], "propose": [1], "a": [2], "message": [3], "passing": [4],
                "graph": [5], "neural": [6], "network": [7], "for": [8],
                "molecular": [9], "property": [10], "prediction": [11],
            },
            "primary_location": {"source": {"display_name": "Journal of Chemical Information", "type": "journal"}},
            "best_oa_location": {"pdf_url": "https://example.org/oa.pdf"},
            "open_access": {"is_oa": True, "oa_url": "https://example.org/oa.pdf"},
            "keywords": [{"display_name": "Graph neural networks"}],
        },
        {
            "id": "https://openalex.org/W2",
            "doi": None,
            "title": "Molecular Property Prediction with Graph Convolutions",
            "publication_year": 2023,
            "cited_by_count": 15,
            "type": "article",
            "authorships": [{"author": {"display_name": "Ana Ribeiro"}}],
            "abstract_inverted_index": {
                "Graph": [0], "convolutions": [1], "improve": [2], "molecular": [3],
                "property": [4], "prediction": [5],
            },
            "primary_location": {"source": {"display_name": "Chemometrics Today", "type": "journal"}},
            "best_oa_location": None,
            "open_access": {"is_oa": False, "oa_url": None},
            "keywords": [],
        },
    ]
}

CROSSREF_PAYLOAD = {
    "message": {
        "items": [
            {
                "DOI": "10.1000/gnn.2",
                "title": ["Attention-Based Graph Models for Molecular Property Prediction"],
                "type": "journal-article",
                "issued": {"date-parts": [[2022, 6, 1]]},
                "container-title": ["Journal of Cheminformatics"],
                "is-referenced-by-count": 210,
                "abstract": "<jats:p>An attention based graph model for molecules.</jats:p>",
                "author": [{"given": "Lena", "family": "Fischer"}],
                "URL": "https://doi.org/10.1000/gnn.2",
            }
        ]
    }
}

PUBMED_XML = """<?xml version="1.0"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>99999999</PMID>
      <Article>
        <ArticleTitle>Graph neural networks for molecular property prediction in drug discovery.</ArticleTitle>
        <Abstract><AbstractText>Graph neural networks are applied to molecular property
          prediction tasks in early drug discovery.</AbstractText></Abstract>
        <AuthorList><Author><LastName>Ivanov</LastName><Initials>D</Initials></Author></AuthorList>
        <Journal>
          <Title>Journal of Medicinal Chemistry</Title>
          <JournalIssue><PubDate><Year>2024</Year></PubDate></JournalIssue>
        </Journal>
        <ELocationID EIdType="doi">10.1000/pubmed.gnn</ELocationID>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
"""


@pytest.fixture
def mocked_providers(monkeypatch):
    """Mock the four applicable providers with realistic payloads."""
    monkeypatch.setattr(arxiv_module, "get_text", lambda *a, **k: ARXIV_XML)
    monkeypatch.setattr(openalex_module, "get_json", lambda *a, **k: OPENALEX_PAYLOAD)
    monkeypatch.setattr(crossref_module, "get_json", lambda *a, **k: CROSSREF_PAYLOAD)

    def fake_pubmed_json(provider, url, params=None, **kwargs):
        if "esearch" in url:
            return {"esearchresult": {"idlist": ["99999999"]}}
        return {}

    monkeypatch.setattr(pubmed_module, "get_json", fake_pubmed_json)
    monkeypatch.setattr(pubmed_module, "get_text", lambda *a, **k: PUBMED_XML)


def test_pipeline_end_to_end(mocked_providers):
    outcome = run_search(QUERY, limit=30)

    # 3 arXiv + 2 OpenAlex + 1 Crossref + 1 PubMed
    assert outcome.stats.candidates_collected == 7
    # The arXiv and OpenAlex copies of the "Message Passing..." paper merge.
    assert outcome.stats.duplicates_removed == 1
    assert outcome.stats.returned == 6
    assert len(outcome.papers) == 6

    # Sources are reported per provider for UI transparency.
    statuses = {status.name: status for status in outcome.source_outcomes}
    assert statuses["arXiv"].result_count == 3
    assert statuses["OpenAlex"].result_count == 2
    assert statuses["Semantic Scholar"].configured is False

    # Ranking: on-topic GNN + molecular papers occupy the top of the list...
    top_three = outcome.papers[:3]
    assert all("olecular" in paper.title for paper in top_three)
    assert all(paper.relevance_score >= 90 for paper in top_three)
    assert max(paper.relevance_score for paper in outcome.papers) == 100.0
    assert outcome.papers[0].rank == 1

    # ...and the single off-topic paper (keyword overlap only) sinks to last.
    off_topic = next(p for p in outcome.papers if "Power Grid" in p.title)
    assert off_topic.relevance_score < 20
    assert off_topic.rank == len(outcome.papers)

    # A well-cited on-topic paper keeps a high citation contribution.
    cited = next(p for p in outcome.papers if p.citation_count == 64)
    assert cited.citation_score is not None and cited.citation_score > 50

    # Merged metadata keeps the best of both sources.
    merged = next(p for p in outcome.papers if p.doi == "10.1000/gnn.1")
    assert merged.citation_count == 64
    assert set(merged.sources) == {"arXiv", "OpenAlex"}
    # A usable PDF survives the merge (OpenAlex is the primary metadata record
    # here, so its open-access PDF is kept; the unit tests cover the case where
    # only the arXiv copy has one).
    assert merged.pdf_url in {
        "https://arxiv.org/pdf/2401.11111v1",
        "https://example.org/oa.pdf",
    }

    # Every paper is fully scored and explainable.
    for paper in outcome.papers:
        assert 0 <= paper.overall_score <= 100
        assert paper.score_explanations["overall"].startswith("Overall")
        # On-topic papers list the query terms they matched; a paper that
        # matches nothing is honestly reported as matching nothing.
        if paper.relevance_score > 5:
            assert paper.matched_terms
        else:
            assert paper.matched_terms == []


def test_api_returns_ranked_top_papers(mocked_providers):
    search_cache.clear()
    with TestClient(create_app()) as client:
        response = client.post("/research", json={"query": QUERY, "limit": 30})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["stats"]["candidates_collected"] == 7
    assert body["stats"]["duplicates_removed"] == 1
    assert body["query_analysis"]["acronyms"].get("gnn") == "graph neural network"
    assert body["weights"]["relevance"] == pytest.approx(0.5)

    papers = body["papers"]
    assert len(papers) == 6
    assert [paper["rank"] for paper in papers] == list(range(1, 7))

    first = papers[0]
    assert first["id"].startswith("p_")
    assert first["quality_label"] in {"High", "Medium", "Basic"}
    assert first["authors_display"]

    # The merged OpenAlex/arXiv record carries the citation count OpenAlex
    # reported, while the PubMed record stays null (PubMed exposes none).
    merged_paper = next(p for p in papers if p["doi"] == "10.1000/gnn.1")
    assert merged_paper["citation_count"] == 64
    assert merged_paper["citation_score"] is not None
    # Citation counts that no source reported stay null (never invented).
    pubmed_paper = next(p for p in papers if p["source"] == "PubMed")
    assert pubmed_paper["citation_count"] is None
    assert pubmed_paper["citation_score"] is None
    assert "not available" in pubmed_paper["score_explanations"]["citation"]

    # Papers are retrievable by id for the detail view.
    detail = client.get(f"/papers/{first['id']}")
    assert detail.status_code == 200
    assert detail.json()["paper"]["title"] == first["title"]

    search_cache.clear()
