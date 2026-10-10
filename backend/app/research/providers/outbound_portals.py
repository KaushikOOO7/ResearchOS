"""
Academic publisher outbound search portals generator.
Provides genuine, authorized outbound search links for Google Scholar, IEEE Xplore,
ACM Digital Library, Springer Nature, ScienceDirect, and Wiley Online Library.
"""

from typing import Dict, List
from urllib.parse import quote


def get_outbound_academic_portals(query: str) -> List[Dict[str, str]]:
    """
    Generate authentic direct search query links to major publisher archives
    and citation indexes where direct scraping is restricted or requires publisher institutional subscriptions.
    """
    clean_q = quote(query.strip()) if query else ""

    return [
        {
            "id": "google_scholar",
            "name": "Google Scholar",
            "category": "Citation Index",
            "search_url": f"https://scholar.google.com/scholar?q={clean_q}",
            "note": "Comprehensive citation index and profile graph. Outbound link to avoid automated scraping bans.",
            "access_type": "Public Web Search",
        },
        {
            "id": "ieee_xplore",
            "name": "IEEE Xplore",
            "category": "Engineering & CS",
            "search_url": f"https://ieeexplore.ieee.org/search/searchresult.jsp?newsearch=true&queryText={clean_q}",
            "note": "Primary repository for electrical engineering, robotics, and computing standards.",
            "access_type": "Institutional / Subscription",
        },
        {
            "id": "acm_dl",
            "name": "ACM Digital Library",
            "category": "Computer Science",
            "search_url": f"https://dl.acm.org/action/doSearch?AllField={clean_q}",
            "note": "Premier computer science society proceedings, SIGGRAPH, NeurIPS, and transactions.",
            "access_type": "Institutional / Open-TOC",
        },
        {
            "id": "springer_nature",
            "name": "Springer Nature",
            "category": "Multidisciplinary",
            "search_url": f"https://link.springer.com/search?query={clean_q}",
            "note": "Nature Portfolio, Lecture Notes in Computer Science (LNCS), and scientific books.",
            "access_type": "Publisher Portal",
        },
        {
            "id": "sciencedirect",
            "name": "ScienceDirect (Elsevier)",
            "category": "Multidisciplinary",
            "search_url": f"https://www.sciencedirect.com/search?qs={clean_q}",
            "note": "Extensive peer-reviewed research in life sciences, physical sciences, and engineering.",
            "access_type": "Publisher Portal",
        },
        {
            "id": "wiley",
            "name": "Wiley Online Library",
            "category": "Multidisciplinary",
            "search_url": f"https://onlinelibrary.wiley.com/action/doSearch?AllField={clean_q}",
            "note": "Authoritative journals spanning chemistry, medicine, physics, and social sciences.",
            "access_type": "Publisher Portal",
        },
    ]
