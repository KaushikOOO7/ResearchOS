"""
PubMed provider (biomedical only).

Uses NCBI E-utilities (``esearch`` + ``efetch``). PubMed is only queried when
the user's idea contains clear biomedical signal -- running every query
through a biomedical index would add noise, not recall.

Docs: https://www.ncbi.nlm.nih.gov/books/NBK25501/
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Dict, List, Optional

from app.config import settings
from app.models.paper import Paper, QueryAnalysis
from app.research.base import ResearchSource, build_paper
from app.utils.http import ProviderError, get_json, get_text
from app.utils.logging_setup import get_logger
from app.utils.text import sanitize_external_text

logger = get_logger("pubmed")

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


class PubMedSource(ResearchSource):
    """NCBI PubMed (biomedical and life sciences literature)."""

    name = "PubMed"
    tier = 1
    source_score = 90.0

    def is_configured(self) -> bool:
        return bool(settings.pubmed_enabled)

    def is_applicable(self, query_analysis: QueryAnalysis) -> bool:
        return bool(query_analysis.is_biomedical)

    def fetch(self, query: str, limit: int, query_analysis: QueryAnalysis) -> List[Paper]:
        common: Dict[str, str] = {"tool": "ResearchOS", "db": "pubmed"}
        if settings.pubmed_email:
            common["email"] = settings.pubmed_email
        if settings.ncbi_api_key:
            common["api_key"] = settings.ncbi_api_key

        # 1. Find candidate PMIDs.
        search_payload = get_json(
            self.name,
            ESEARCH_URL,
            params={
                **common,
                "term": query,
                "retmode": "json",
                "retmax": max(1, min(limit, 50)),
                "sort": "relevance",
            },
        )
        result = (search_payload or {}).get("esearchresult") or {}
        pmids = [str(pid) for pid in (result.get("idlist") or []) if str(pid).isdigit()]
        if not pmids:
            return []

        # 2. Fetch full records for those PMIDs.
        xml_text = get_text(
            self.name,
            EFETCH_URL,
            params={**common, "id": ",".join(pmids), "retmode": "xml"},
        )

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise ProviderError(self.name, "could not parse PubMed XML response") from exc

        papers: List[Paper] = []
        for article in root.findall(".//PubmedArticle"):
            paper = self._parse_article(article)
            if paper and paper.title:
                papers.append(paper)
        return papers

    def _parse_article(self, article: ET.Element) -> Optional[Paper]:
        citation = article.find("MedlineCitation")
        if citation is None:
            return None

        article_node = citation.find("Article")
        if article_node is None:
            return None

        title = sanitize_external_text(
            "".join(article_node.findtext("ArticleTitle", default="") or ""), max_chars=600
        )

        # PubMed splits abstracts into labelled sections.
        abstract_parts: List[str] = []
        abstract_node = article_node.find("Abstract")
        if abstract_node is not None:
            for chunk in abstract_node.findall("AbstractText"):
                text = sanitize_external_text("".join(chunk.itertext()), max_chars=4000)
                label = chunk.attrib.get("Label")
                if not text:
                    continue
                abstract_parts.append(f"{label}: {text}" if label else text)
        abstract = " ".join(abstract_parts)

        authors: List[str] = []
        author_list = article_node.find("AuthorList")
        if author_list is not None:
            for author in author_list.findall("Author"):
                last = author.findtext("LastName", default="")
                initials = author.findtext("Initials", default="")
                collective = author.findtext("CollectiveName", default="")
                if collective:
                    authors.append(collective)
                elif last:
                    authors.append(f"{last} {initials}".strip())

        journal = article_node.find("Journal")
        venue = journal.findtext("Title", default="") if journal is not None else ""

        year: Optional[int] = None
        pub_date = journal.find("JournalIssue/PubMedPubDate") if journal is not None else None
        candidates = []
        if pub_date is not None:
            candidates.append(pub_date.findtext("Year", default=""))
        if journal is not None:
            candidates.append(journal.findtext("JournalIssue/PubDate/Year", default=""))
        for value in candidates:
            if value and value.isdigit():
                year = int(value)
                break

        doi = None
        pmc_id = None
        article_ids = article.find("PubmedData/ArticleIdList")
        if article_ids is not None:
            for article_id in article_ids.findall("ArticleId"):
                id_type = (article_id.attrib.get("IdType") or "").lower()
                if id_type == "doi" and article_id.text:
                    doi = article_id.text
                elif id_type == "pmc" and article_id.text:
                    pmc_id = article_id.text
        if not doi:
            for elocation in article_node.findall("ELocationID"):
                if (elocation.attrib.get("EIdType") or "").lower() == "doi" and elocation.text:
                    doi = elocation.text
                    break

        pmid = citation.findtext("PMID", default="")
        paper_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None

        subjects = [
            sanitize_external_text("".join(node.itertext()), max_chars=80)
            for node in citation.findall("MeshHeadingList/MeshHeading/DescriptorName")
        ]

        return build_paper(
            title=title,
            abstract=abstract,
            authors=authors,
            year=year,
            doi=doi,
            arxiv_id=None,
            venue=venue or None,
            paper_url=paper_url,
            # PubMed does not expose a reliably downloadable open PDF; PMC
            # links are provided as the paper page instead of pretending a
            # direct PDF exists.
            pdf_url=None,
            citation_count=None,
            is_open_access=None,
            keywords=[pmc_id] if pmc_id else [],
            subjects=subjects,
            doc_type="journal-article",
            source_score=self.source_score,
            source=self.name,
        )
