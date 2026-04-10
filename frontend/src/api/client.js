/**
 * API client for Content Intelligence Platform.
 * Wraps all backend endpoints with error handling.
 */

const BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

async function request(endpoint, options = {}) {
  const url = `${BASE_URL}${endpoint}`;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  getHealth: () => request('/health'),
  getStats: () => request('/stats'),
  getTopVideos: (niche, days = 365, limit = 20) =>
    request(`/videos/top?niche=${encodeURIComponent(niche)}&days=${days}&limit=${limit}`),
  getTrending: (days = 30, limit = 20) =>
    request(`/videos/trending?days=${days}&limit=${limit}`),
  getVideo: (id) => request(`/videos/${encodeURIComponent(id)}`),
  getTopCreators: (limit = 20, minVideos = 2) =>
    request(`/creators/top?limit=${limit}&min_videos=${minVideos}`),
  triggerPipeline: (apiKey) =>
    request('/pipeline/run', {
      method: 'POST',
      headers: apiKey ? { 'X-API-Key': apiKey } : {},
    }),
  getPipelineHistory: (limit = 10) =>
    request(`/pipeline/history?limit=${limit}`),
  getTranscriptStats: () => request('/stats/transcripts'),
};
