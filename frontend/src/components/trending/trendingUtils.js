import { getPlatformLabel, fmt } from '../../utils/platform';
import { formatPublishedAt, getContentTags, getContentThumbnail } from '../top-content/contentUtils';

export { formatPublishedAt, getContentTags, getContentThumbnail };

export function formatPercentage(value, digits = 1) {
  return `${(Number(value || 0) * 100).toFixed(digits)}%`;
}

export function formatCompactNumber(value) {
  return fmt(Number(value || 0));
}

export function getMomentum(video) {
  const engagement = Math.max(0, Number(video?.engagement_rate || 0));
  const score = Math.max(0, Number(video?.score || 0));
  return Math.round((engagement * 0.65 + score * 0.35) * 100);
}

export function getTrendStatus(video) {
  const engagement = Number(video?.engagement_rate || 0);
  const score = Number(video?.score || 0);
  if (engagement >= 0.08 && score >= 0.55) return { label: 'Breaking out', tone: 'hot' };
  if (engagement >= 0.05) return { label: 'Rising', tone: 'green' };
  if (score >= 0.55) return { label: 'High signal', tone: 'purple' };
  return { label: 'Emerging', tone: 'blue' };
}

export function getRisingTopic(videos) {
  const first = videos[0];
  if (!first) return { name: 'Awaiting signals', momentum: 0 };
  const tags = getContentTags(first, 1);
  const name = first.niche && first.niche.toLowerCase() !== 'general'
    ? first.niche
    : tags[0] || getPlatformLabel(first.platform);
  return { name, momentum: getMomentum(first) };
}

export function buildKeywordRanks(videos, limit = 8) {
  const counts = {};
  videos.forEach((video) => {
    const words = `${video?.title || ''} ${video?.niche || ''}`
      .toLowerCase()
      .replace(/[^a-z0-9\s]/g, '')
      .split(/\s+/)
      .filter((word) => word.length > 3 && !['this', 'that', 'with', 'from', 'your', 'about', 'video'].includes(word));
    new Set(words).forEach((word) => { counts[word] = (counts[word] || 0) + 1; });
  });
  return Object.entries(counts)
    .sort(([, a], [, b]) => b - a)
    .slice(0, limit)
    .map(([word, count]) => ({ word, count, momentum: Math.min(99, 30 + count * 12) }));
}

export function getAvatarLabel(video) {
  const creator = String(video?.channel || 'Unknown creator').trim();
  return creator.charAt(0).toUpperCase() || 'C';
}

export function getDurationLabel(video) {
  const duration = Number(video?.duration || video?.duration_seconds || 0);
  if (!duration) return '';
  const minutes = Math.floor(duration / 60);
  const seconds = Math.floor(duration % 60).toString().padStart(2, '0');
  return `${minutes}:${seconds}`;
}
