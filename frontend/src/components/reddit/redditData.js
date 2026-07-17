export const SENTIMENT_META = {
  positive: { label: 'Positive', color: '#35d69b' },
  neutral: { label: 'Neutral', color: '#f5b942' },
  negative: { label: 'Negative', color: '#ff6474' },
  mixed: { label: 'Mixed', color: '#a982ff' },
};

export function compactNumber(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return '—';
  return new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 }).format(number);
}

export function formatPercent(value, digits = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? `${(number * 100).toFixed(digits)}%` : '—';
}

export function formatScore(value) {
  const number = Number(value);
  return Number.isFinite(number) ? Math.round(number).toString() : '—';
}

export function relativeTime(value) {
  if (!value) return 'Date unavailable';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Date unavailable';
  const diff = Math.max(0, Date.now() - date.getTime());
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function subredditLabel(value) {
  return value ? `r/${String(value).replace(/^r\//, '')}` : 'Subreddit unavailable';
}

export function initials(value) {
  const clean = String(value || 'reddit').replace(/^u\//, '').trim();
  return clean.slice(0, 2).toUpperCase() || 'R';
}

export function sentimentMeta(value) {
  return SENTIMENT_META[value] || { label: 'Not analyzed', color: '#7f91b4' };
}

export function chartSegments(items = []) {
  return items.filter((item) => Number(item?.count) > 0).map((item) => ({ ...item, color: SENTIMENT_META[item.label]?.color || '#5576b8' }));
}
