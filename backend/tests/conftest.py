"""
Shared pytest fixtures.

The provider payloads below mirror the *real* response shapes of each API
(arXiv Atom, OpenAlex JSON, Crossref JSON, PubMed XML) so parsers are tested
against realistic input without making network calls.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

# Make ``app`` importable when pytest is run from backend/.
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


# ---------------------------------------------------------------------------
# Minimal valid PDF factory (used by the PDF pipeline tests)
# ---------------------------------------------------------------------------

def build_pdf(text: str = "ResearchOS test document.", pages: int = 1) -> bytes:
    """Create a small, valid PDF containing extractable text."""
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")

    page_ids = list(range(3, 3 + pages))
    content_ids = list(range(3 + pages, 3 + 2 * pages))
    font_id = 3 + 2 * pages
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)

    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {pages} >>".encode(),
    ]
    for index, pid in enumerate(page_ids):
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Contents {content_ids[index]} 0 R "
                f"/Resources << /Font << /F1 {font_id} 0 R >> >> >>"
            ).encode()
        )
    for index in range(pages):
        stream = f"BT /F1 12 Tf 72 720 Td ({text} page {index + 1}) Tj ET".encode()
        objects.append(
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
        )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")

    xref_position = out.tell()
    size = len(objects) + 1
    out.write(f"xref\n0 {size}\n".encode())
    out.write(b"0000000000 65535 f \n")
    for offset in offsets:
        out.write(f"{offset:010d} 00000 n \n".encode())
    out.write(
        f"trailer\n<< /Size {size} /Root 1 0 R >>\nstartxref\n{xref_position}\n%%EOF\n".encode()
    )
    return out.getvalue()


@pytest.fixture
def pdf_factory():
    """Return a callable that builds a small valid PDF."""
    return build_pdf


# ---------------------------------------------------------------------------
# Provider payload fixtures
# ---------------------------------------------------------------------------

ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2401.01234v2</id>
    <published>2024-01-03T10:00:00Z</published>
    <title>Graph Neural Networks for Molecular Property
      Prediction: A Survey</title>
    <summary>We survey graph neural network architectures for molecular
      property prediction, covering message passing, readout functions and
      benchmark datasets such as MoleculeNet.</summary>
    <author><name>Ada Lovelace</name></author>
    <author><name>Alan Turing</name></author>
    <arxiv:doi>10.1000/example.doi</arxiv:doi>
    <arxiv:comment>20 pages, 5 figures</arxiv:comment>
    <arxiv:primary_category term="cs.LG"/>
    <category term="cs.LG"/>
    <category term="q-bio.BM"/>
    <link href="http://arxiv.org/abs/2401.01234v2" rel="alternate" type="text/html"/>
    <link title="pdf" href="http://arxiv.org/pdf/2401.01234v2" rel="related" type="application/pdf"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2402.09999v1</id>
    <published>2024-02-15T10:00:00Z</published>
    <title>Federated Learning for Internet of Things Intrusion Detection</title>
    <summary>We study federated learning for IoT intrusion detection.</summary>
    <author><name>Grace Hopper</name></author>
    <arxiv:primary_category term="cs.CR"/>
    <link title="pdf" href="http://arxiv.org/pdf/2402.09999v1" rel="related" type="application/pdf"/>
  </entry>
</feed>
"""

OPENALEX_PAYLOAD = {
    "results": [
        {
            "id": "https://openalex.org/W1234567890",
            "doi": "https://doi.org/10.1000/example.doi",
            "title": "Graph Neural Networks for Molecular Property Prediction: A Survey",
            "publication_year": 2024,
            "cited_by_count": 87,
            "type": "review",
            "authorships": [
                {"author": {"display_name": "Ada Lovelace"}},
                {"author": {"display_name": "Alan Turing"}},
            ],
            "abstract_inverted_index": {
                "Graph": [0],
                "neural": [1],
                "networks": [2],
                "for": [3],
                "molecular": [4],
                "property": [5],
                "prediction": [6],
            },
            "primary_location": {"source": {"display_name": "Journal of Cheminformatics", "type": "journal"}},
            "best_oa_location": {"pdf_url": "https://example.org/paper.pdf"},
            "open_access": {"is_oa": True, "oa_url": "https://example.org/paper.pdf"},
            "keywords": [{"display_name": "Molecular property prediction"}],
        },
        {
            "id": "https://openalex.org/W0987654321",
            "doi": None,
            "title": "Power Grid Load Forecasting with Recurrent Networks",
            "publication_year": 2019,
            "cited_by_count": 12,
            "type": "article",
            "authorships": [{"author": {"display_name": "Nikola Tesla"}}],
            "abstract_inverted_index": {"Power": [0], "grid": [1], "forecasting": [2]},
            "primary_location": {"source": {"display_name": "Energy Systems", "type": "journal"}},
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
                "DOI": "10.1000/example.doi",
                "title": ["Graph Neural Networks for Molecular Property Prediction: A Survey"],
                "type": "journal-article",
                "issued": {"date-parts": [[2024, 3, 1]]},
                "container-title": ["Journal of Cheminformatics"],
                "is-referenced-by-count": 91,
                "abstract": "<jats:p>We survey graph neural network architectures.</jats:p>",
                "author": [
                    {"given": "Ada", "family": "Lovelace"},
                    {"given": "Alan", "family": "Turing"},
                ],
                "URL": "https://doi.org/10.1000/example.doi",
                "link": [{"content-type": "application/pdf", "URL": "https://example.org/crossref.pdf"}],
                "subject": ["Chemistry", "Computer Science"],
            },
            {
                "DOI": "10.1000/other.doi",
                "title": ["Unrelated Editorial Note"],
                "type": "component",
                "issued": {"date-parts": [[2021]]},
            },
        ]
    }
}

PUBMED_XML = """<?xml version="1.0"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>12345678</PMID>
      <Article>
        <ArticleTitle>Graph neural networks for drug discovery.</ArticleTitle>
        <Abstract>
          <AbstractText Label="BACKGROUND">Graph neural networks are widely used.</AbstractText>
          <AbstractText Label="RESULTS">They improve property prediction.</AbstractText>
        </Abstract>
        <AuthorList>
          <Author><LastName>Lovelace</LastName><Initials>A</Initials></Author>
        </AuthorList>
        <Journal>
          <Title>Journal of Biomedical Informatics</Title>
          <JournalIssue><PubDate><Year>2023</Year></PubDate></JournalIssue>
        </Journal>
        <ELocationID EIdType="doi">10.1000/pubmed.doi</ELocationID>
      </Article>
      <MeshHeadingList>
        <MeshHeading><DescriptorName>Drug Discovery</DescriptorName></MeshHeading>
      </MeshHeadingList>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="pubmed">12345678</ArticleId>
        <ArticleId IdType="doi">10.1000/pubmed.doi</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
"""


@pytest.fixture
def arxiv_xml() -> str:
    return ARXIV_XML


@pytest.fixture
def openalex_payload() -> dict:
    return OPENALEX_PAYLOAD


@pytest.fixture
def crossref_payload() -> dict:
    return CROSSREF_PAYLOAD


@pytest.fixture
def pubmed_xml() -> str:
    return PUBMED_XML
