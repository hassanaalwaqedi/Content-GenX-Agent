import { getPlatformColor, getPlatformLabel } from '../../utils/platform';

export const REGIONS = [
  { code: 'US', label: 'United States', flag: 'US' },
  { code: 'CA', label: 'Canada', flag: 'CA' },
  { code: 'BR', label: 'Brazil', flag: 'BR' },
  { code: 'MX', label: 'Mexico', flag: 'MX' },
  { code: 'GB', label: 'United Kingdom', flag: 'GB' },
  { code: 'DE', label: 'Germany', flag: 'DE' },
  { code: 'FR', label: 'France', flag: 'FR' },
  { code: 'AE', label: 'UAE', flag: 'AE' },
  { code: 'SA', label: 'Saudi Arabia', flag: 'SA' },
  { code: 'EG', label: 'Egypt', flag: 'EG' },
  { code: 'TR', label: 'Turkey', flag: 'TR' },
  { code: 'AU', label: 'Australia', flag: 'AU' },
  { code: 'JP', label: 'Japan', flag: 'JP' },
  { code: 'KR', label: 'South Korea', flag: 'KR' },
  { code: 'IN', label: 'India', flag: 'IN' },
];

export const DOMAINS = [
  'music', 'gaming', 'sports', 'entertainment', 'education', 'science & technology',
  'news & politics', 'comedy', 'howto & style', 'people & blogs', 'film & animation', 'travel & events',
];

export const SIGNAL_SUGGESTIONS = ['AI', 'ChatGPT', 'Claude', 'Finance', 'Gaming', 'Startups', 'Marketing', 'SaaS', 'Crypto', 'Fitness'];
export const PLATFORM_IDS = ['youtube', 'reddit', 'tiktok', 'instagram'];

export const DEFAULT_PIPELINE_CONFIG = {
  name: 'Custom',
  regions: ['US'],
  platforms: ['youtube'],
  categories: [],
  keywords: [],
  content_type: 'all',
  is_preset: false,
};

const VALID_REGION_CODES = new Set(REGIONS.map((region) => region.code));
const VALID_CONTENT_TYPES = new Set(['all', 'shorts', 'long']);

export function normalizePipelineConfig(config = {}) {
  const hasRegions = Array.isArray(config.regions);
  const hasPlatforms = Array.isArray(config.platforms);
  const hasCategories = Array.isArray(config.categories);
  const hasKeywords = Array.isArray(config.keywords);
  const regions = (config.regions || []).filter((region) => VALID_REGION_CODES.has(region)).slice(0, 5);
  const platforms = (config.platforms || []).filter((platform) => PLATFORM_IDS.includes(platform));
  const categories = [...new Set((config.categories || []).map((category) => String(category).toLowerCase().trim()).filter(Boolean))].slice(0, 15);
  const keywords = [...new Set((config.keywords || []).map((keyword) => String(keyword).trim().replace(/[^\w\s-]/g, '')).filter(Boolean))].slice(0, 10);
  return {
    ...DEFAULT_PIPELINE_CONFIG,
    ...config,
    regions: hasRegions ? regions : DEFAULT_PIPELINE_CONFIG.regions,
    platforms: hasPlatforms ? platforms : DEFAULT_PIPELINE_CONFIG.platforms,
    categories: hasCategories ? categories : DEFAULT_PIPELINE_CONFIG.categories,
    keywords: hasKeywords ? keywords : DEFAULT_PIPELINE_CONFIG.keywords,
    content_type: VALID_CONTENT_TYPES.has(config.content_type) ? config.content_type : 'all',
    is_preset: Boolean(config.is_preset),
  };
}

export function validatePipelineConfig(config, connectors = {}) {
  const issues = [];
  if (!config.regions?.length) issues.push('Select at least one target market.');
  if (config.regions?.length > 5) issues.push('A scan can include up to five target markets.');
  if (!config.platforms?.length) issues.push('Select at least one platform.');
  const unavailable = (config.platforms || []).filter((platform) => ['disabled', 'unavailable'].includes(connectors?.[platform]?.status));
  if (unavailable.length) issues.push(`${unavailable.map(getPlatformLabel).join(', ')} is unavailable.`);
  return { valid: issues.length === 0, issues };
}

export function estimateRuntime(config) {
  const seconds = 12 + (config.regions?.length || 0) * 4 + (config.platforms?.length || 0) * 5 + (config.keywords?.length || 0) * 2;
  if (seconds < 30) return '~20 sec';
  if (seconds < 60) return '~40 sec';
  if (seconds < 120) return '~1–2 min';
  return '~2–3 min';
}

export function estimateDepth(config) {
  const factors = (config.regions?.length || 0) + (config.keywords?.length || 0) + (config.categories?.length || 0);
  if (factors <= 3) return 'Focused';
  if (factors <= 8) return 'Standard';
  return 'Deep scan';
}

export function formatRelativeTime(value) {
  if (!value) return 'No completed scan';
  const timestamp = new Date(value).getTime();
  if (Number.isNaN(timestamp)) return 'Unknown';
  const minutes = Math.max(0, Math.floor((Date.now() - timestamp) / 60000));
  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function getFreshnessScore(value) {
  if (!value) return 0;
  const timestamp = new Date(value).getTime();
  if (Number.isNaN(timestamp)) return 0;
  const hours = (Date.now() - timestamp) / 3600000;
  if (hours < 1) return 100;
  if (hours < 6) return 80;
  if (hours < 24) return 60;
  if (hours < 72) return 35;
  return 10;
}

export function formatDuration(seconds) {
  const value = Number(seconds);
  if (!Number.isFinite(value) || value < 0) return '—';
  if (value < 60) return `${value.toFixed(value < 10 ? 1 : 0)}s`;
  const minutes = Math.floor(value / 60);
  return `${minutes}m ${Math.round(value % 60)}s`;
}

export function formatElapsed(startTime) {
  if (!startTime) return '—';
  return formatDuration(Math.max(0, (Date.now() - startTime) / 1000));
}

export function normalizeRunStatus(status) {
  const normalized = String(status || 'unknown').toLowerCase();
  const states = {
    completed: { label: 'Completed', tone: 'success' },
    completed_empty: { label: 'No results', tone: 'warning' },
    completed_filtered: { label: 'Filtered', tone: 'warning' },
    running: { label: 'Running', tone: 'running' },
    failed: { label: 'Failed', tone: 'danger' },
    crashed: { label: 'Crashed', tone: 'danger' },
  };
  return states[normalized] || { label: normalized || 'Unknown', tone: 'muted' };
}

export function connectorSummary(connectors = {}) {
  const values = PLATFORM_IDS.map((platform) => connectors?.[platform]).filter(Boolean);
  const healthy = values.filter((connector) => connector.status === 'healthy').length;
  const active = values.filter((connector) => !['disabled', 'unavailable'].includes(connector.status)).length;
  return { total: PLATFORM_IDS.length, healthy, active };
}

export function getPlatformMeta(platform) {
  return { label: getPlatformLabel(platform), color: getPlatformColor(platform) };
}

export function getRegionLabel(code) {
  return REGIONS.find((region) => region.code === code)?.label || code;
}

export function getRunDepth(run) {
  const ingested = Number(run?.videos_ingested || 0);
  if (ingested > 100) return 'Deep';
  if (ingested > 30) return 'Standard';
  if (ingested > 0) return 'Focused';
  return '—';
}
