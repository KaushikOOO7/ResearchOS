import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 45000,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const searchPapers = async (query, maxResults = 30) => {
  try {
    const response = await api.post('/research', {
      query: query.trim(),
      max_results: maxResults,
    });
    return response.data;
  } catch (err) {
    if (err.response?.data?.message) throw new Error(err.response.data.message);
    if (err.response?.data?.detail) {
      throw new Error(typeof err.response.data.detail === 'string' ? err.response.data.detail : 'Validation error');
    }
    if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) {
      throw new Error('Search request timed out. Academic servers might be experiencing high load.');
    }
    if (!err.response) {
      throw new Error('Unable to connect to ResearchOS server. Please check your network connection.');
    }
    throw new Error(`Server returned HTTP ${err.response.status}. Please try again.`);
  }
};

export const analyzePaper = async (paper) => {
  try {
    const response = await api.post('/analyze-paper', {
      title: paper.title,
      abstract: paper.abstract || '',
      pdf_url: paper.pdf_url || null,
    });
    return response.data;
  } catch (err) {
    if (err.response?.data?.message) throw new Error(err.response.data.message);
    if (err.response?.data?.detail) {
      throw new Error(typeof err.response.data.detail === 'string' ? err.response.data.detail : 'Analysis error');
    }
    throw new Error(err.message || 'Paper analysis failed.');
  }
};

export const batchAnalyzePapers = async (papers, maxConcurrent = 3) => {
  try {
    const response = await api.post('/batch-analyze', {
      papers,
      max_concurrent: maxConcurrent,
    });
    return response.data;
  } catch (err) {
    if (err.response?.data?.message) throw new Error(err.response.data.message);
    throw new Error(err.message || 'Batch paper analysis failed.');
  }
};

export const synthesizeGaps = async (query, papers) => {
  try {
    const response = await api.post('/synthesize-gaps', {
      query,
      papers,
    });
    return response.data;
  } catch (err) {
    if (err.response?.data?.message) throw new Error(err.response.data.message);
    throw new Error(err.message || 'Research gap synthesis failed.');
  }
};

export const designExperiment = async (gap, query = '', supportingPapers = []) => {
  try {
    const response = await api.post('/design-experiment', {
      gap,
      query,
      supporting_papers: supportingPapers,
    });
    return response.data;
  } catch (err) {
    if (err.response?.data?.message) throw new Error(err.response.data.message);
    throw new Error(err.message || 'Experiment design failed.');
  }
};

export const generateBlueprint = async (gapOrIdea, title = '', supportingPapers = [], compute = '1x RTX 4090', timeline = 8) => {
  try {
    const response = await api.post('/generate-blueprint', {
      gap_or_idea: gapOrIdea,
      title,
      supporting_papers: supportingPapers,
      available_compute: compute,
      timeline_weeks: timeline,
    });
    return response.data;
  } catch (err) {
    if (err.response?.data?.message) throw new Error(err.response.data.message);
    throw new Error(err.message || 'Project blueprint generation failed.');
  }
};

export const fetchSessions = async () => {
  try {
    const response = await api.get('/sessions');
    return response.data?.sessions || [];
  } catch {
    return [];
  }
};

export const fetchSourceCoverage = async (query = '') => {
  try {
    const response = await api.get(`/sources?query=${encodeURIComponent(query)}`);
    return response.data?.coverage;
  } catch {
    return null;
  }
};

export const saveSession = async (session) => {
  try {
    const response = await api.post('/sessions', session);
    return response.data?.session;
  } catch {
    return null;
  }
};

export const checkHealth = async () => {
  try {
    const response = await api.get('/health', { timeout: 4000 });
    return response.data;
  } catch {
    return { status: 'offline', gemini_configured: false };
  }
};
