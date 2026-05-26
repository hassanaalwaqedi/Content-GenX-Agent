/**
 * API client for Content Intelligence Platform.
 * Wraps all backend endpoints with error handling.
 * All data endpoints support dataset_id for workspace scoping.
 *
 * Auth: JWT Bearer token stored in localStorage (cross-origin safe).
 */

// In development, use empty string so requests go through Vite proxy (same-origin).
// In production, set VITE_API_URL to the actual backend URL.
const BASE_URL = import.meta.env.VITE_API_URL || '';

const TOKEN_KEY = 'genx_auth_token';

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
}

function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

async function request(endpoint, options = {}) {
  const url = `${BASE_URL}${endpoint}`;
  const token = getToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const { headers: _h, ...restOptions } = options;

  const res = await fetch(url, {
    headers,
    credentials: 'include',
    ...restOptions,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/**
 * Helper: append dataset_id to URLSearchParams.
 */
function _appendDatasetId(params, datasetId) {
  if (datasetId === null) {
    params.set('dataset_id', '0');
  } else if (datasetId !== undefined) {
    params.set('dataset_id', datasetId);
  }
}

// ---- Auth API ----
export const authApi = {
  login: (username, password) => {
    const token = getToken();
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    return fetch(`${BASE_URL}/auth/login`, {
      method: 'POST',
      headers,
      credentials: 'include',
      body: JSON.stringify({ username, password }),
    }).then(async (res) => {
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Login failed');
      // Store the JWT token from the response body
      if (data.token) setToken(data.token);
      return data;
    });
  },

  logout: () => {
    clearToken();
    localStorage.removeItem('genx_auth_user');
    const headers = {};

    return fetch(`${BASE_URL}/auth/logout`, {
      method: 'POST',
      headers,
      credentials: 'include',
    }).then((res) => res.json());
  },

  me: () => {
    const token = getToken();
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    return fetch(`${BASE_URL}/auth/me`, {
      headers,
      credentials: 'include',
    }).then((res) => res.json());
  },
};

export const api = {
  // ---- System ----
  getHealth: () => request('/health'),
  getConnectorHealth: () => request('/connectors/health'),
  getStats: (datasetId) => {
    const params = new URLSearchParams();
    _appendDatasetId(params, datasetId);
    const qs = params.toString();
    return request(`/stats${qs ? '?' + qs : ''}`);
  },

  // ---- Videos ----
  getTopVideos: (niche, days = 365, limit = 20, filters = {}, datasetId) => {
    const params = new URLSearchParams({ days, limit });
    if (niche) params.set('niche', niche);
    if (filters.region) params.set('region', filters.region);
    if (filters.category) params.set('category', filters.category);
    if (filters.content_type) params.set('content_type', filters.content_type);
    _appendDatasetId(params, datasetId);
    return request(`/videos/top?${params.toString()}`);
  },
  getTrending: (days = 30, limit = 20, filters = {}, datasetId) => {
    const params = new URLSearchParams({ days, limit });
    if (filters.region) params.set('region', filters.region);
    if (filters.category) params.set('category', filters.category);
    if (filters.content_type) params.set('content_type', filters.content_type);
    _appendDatasetId(params, datasetId);
    return request(`/videos/trending?${params.toString()}`);
  },
  getVideo: (id) => request(`/videos/${encodeURIComponent(id)}`),

  // ---- Creators ----
  getTopCreators: (limit = 20, minVideos = 2, datasetId) => {
    const params = new URLSearchParams({ limit, min_videos: minVideos });
    _appendDatasetId(params, datasetId);
    return request(`/creators/top?${params.toString()}`);
  },
  getCreatorIntelligence: (days = 365, limit = 30, minVideos = 1, datasetId) => {
    const params = new URLSearchParams({ days, limit, min_videos: minVideos });
    _appendDatasetId(params, datasetId);
    return request(`/creators/intelligence?${params.toString()}`);
  },
  getRisingCreators: (days = 90, limit = 10, datasetId) => {
    const params = new URLSearchParams({ days, limit });
    _appendDatasetId(params, datasetId);
    return request(`/creators/rising?${params.toString()}`);
  },
  getCreatorsByTrend: (trend, days = 365, limit = 20, datasetId) => {
    const params = new URLSearchParams({ trend, days, limit });
    _appendDatasetId(params, datasetId);
    return request(`/creators/by-trend?${params.toString()}`);
  },
  getCreatorVideos: (channel, limit = 20) =>
    request(`/creators/${encodeURIComponent(channel)}/videos?limit=${limit}`),

  // ---- Datasets ----
  getDatasets: (limit = 20) => request(`/datasets?limit=${limit}`),
  getActiveDataset: () => request('/datasets/active'),
  activateDataset: (runId) => request(`/datasets/${runId}/activate`, { method: 'POST' }),

  // ---- Pipeline ----
  triggerPipeline: (apiKey, configId) =>
    request(`/pipeline/run${configId ? `?config_id=${configId}` : ''}`, {
      method: 'POST',
      headers: apiKey ? { 'X-API-Key': apiKey } : {},
    }),
  getPipelineHistory: (limit = 10) =>
    request(`/pipeline/history?limit=${limit}`),

  // Pipeline Config CRUD
  savePipelineConfig: (config) =>
    request('/pipeline/config', {
      method: 'POST',
      body: JSON.stringify(config),
    }),
  listPipelineConfigs: (presetsOnly = false) =>
    request(`/pipeline/configs?presets_only=${presetsOnly}`),
  getPipelineConfig: (id) =>
    request(`/pipeline/config/${id}`),
  getLastUsedConfig: () =>
    request('/pipeline/config/last'),
  deletePipelineConfig: (id) =>
    request(`/pipeline/config/${id}`, { method: 'DELETE' }),

  // ---- Transcripts ----
  getTranscriptStats: () => request('/stats/transcripts'),
  fetchTranscript: (videoId) =>
    request(`/videos/${encodeURIComponent(videoId)}/transcript`, { method: 'POST' }),

  // ---- Trends & Opportunities ----
  discoverTrends: (days = 30, limit = 20, datasetId) => {
    const params = new URLSearchParams({ days, limit });
    _appendDatasetId(params, datasetId);
    return request(`/trends/discover?${params.toString()}`);
  },
  getOpportunities: (days = 30, limit = 15, datasetId) => {
    const params = new URLSearchParams({ days, limit });
    _appendDatasetId(params, datasetId);
    return request(`/opportunities?${params.toString()}`);
  },

  // ---- AI Content ----
  generateContent: (videoId, platform = 'youtube', tone = 'professional') =>
    request('/ai/generate-content', {
      method: 'POST',
      body: JSON.stringify({ video_id: videoId, platform, tone }),
    }),
};
