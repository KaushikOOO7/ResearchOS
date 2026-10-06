import requests
import xml.etree.ElementTree as ET
from urllib.parse import quote


ARXIV_API_URL = "https://export.arxiv.org/api/query"


def search_arxiv(query: str, max_results: int = 8):

    encoded_query = quote(query)

    url = (
        f"{ARXIV_API_URL}"
        f"?search_query=all:{encoded_query}"
        f"&start=0"
        f"&max_results={max_results}"
        f"&sortBy=relevance"
        f"&sortOrder=descending"
    )

    response = requests.get(
        url,
        timeout=20
    )

    response.raise_for_status()

    root = ET.fromstring(response.text)

    namespace = {
        "atom": "http://www.w3.org/2005/Atom"
    }

    papers = []

    for entry in root.findall("atom:entry", namespace):

        title_element = entry.find(
            "atom:title",
            namespace
        )

        summary_element = entry.find(
            "atom:summary",
            namespace
        )

        published_element = entry.find(
            "atom:published",
            namespace
        )

        id_element = entry.find(
            "atom:id",
            namespace
        )

        title = (
            title_element.text.strip()
            if title_element is not None
            else ""
        )

        abstract = (
            summary_element.text.strip()
            if summary_element is not None
            else ""
        )

        published = (
            published_element.text[:4]
            if published_element is not None
            else ""
        )

        paper_url = (
            id_element.text.strip()
            if id_element is not None
            else ""
        )

        authors = []

        for author in entry.findall(
            "atom:author",
            namespace
        ):

            name = author.find(
                "atom:name",
                namespace
            )

            if name is not None:
                authors.append(
                    name.text.strip()
                )

        arxiv_id = paper_url.split("/abs/")[-1]

        pdf_url = (
            f"https://arxiv.org/pdf/{arxiv_id}"
        )

        papers.append(
            {
                "title": title,
                "authors": authors,
                "year": published,
                "abstract": abstract,
                "paper_url": paper_url,
                "pdf_url": pdf_url,
                "source": "arXiv"
            }
        )

    return papers