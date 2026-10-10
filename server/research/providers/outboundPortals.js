/**
 * Academic Publisher Outbound Search Portals (Node.js)
 */

export function getOutboundPortals(query = '') {
  const q = encodeURIComponent(query.trim());
  return [
    {
      id: 'google_scholar',
      name: 'Google Scholar',
      category: 'Citation Index',
      searchUrl: `https://scholar.google.com/scholar?q=${q}`,
      note: 'Global academic citation index. Outbound query provided to comply with scraping policies.',
      accessType: 'Public Web Search',
    },
    {
      id: 'ieee_xplore',
      name: 'IEEE Xplore',
      category: 'Engineering & CS',
      searchUrl: `https://ieeexplore.ieee.org/search/searchresult.jsp?newsearch=true&queryText=${q}`,
      note: 'Electrical engineering, computer science, and robotics publications.',
      accessType: 'Institutional / Subscription',
    },
    {
      id: 'acm_dl',
      name: 'ACM Digital Library',
      category: 'Computer Science',
      searchUrl: `https://dl.acm.org/action/doSearch?AllField=${q}`,
      note: 'ACM computing conferences, SIGGRAPH, and transactions.',
      accessType: 'Institutional / Open-TOC',
    },
    {
      id: 'springer_nature',
      name: 'Springer Nature',
      category: 'Multidisciplinary',
      searchUrl: `https://link.springer.com/search?query=${q}`,
      note: 'Nature Portfolio journals, LNCS series, and books.',
      accessType: 'Publisher Portal',
    },
    {
      id: 'sciencedirect',
      name: 'ScienceDirect (Elsevier)',
      category: 'Multidisciplinary',
      searchUrl: `https://www.sciencedirect.com/search?qs=${q}`,
      note: 'Peer-reviewed literature across life, physical, and medical sciences.',
      accessType: 'Publisher Portal',
    },
    {
      id: 'wiley',
      name: 'Wiley Online Library',
      category: 'Multidisciplinary',
      searchUrl: `https://onlinelibrary.wiley.com/action/doSearch?AllField=${q}`,
      note: 'Scientific, technical, medical, and scholarly journals.',
      accessType: 'Publisher Portal',
    },
  ];
}
