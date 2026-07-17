import { getPlatformIcon, getPlatformLabel, fmt } from '../../utils/platform';

export const EMPTY_THUMBNAIL = '';

export function getContentThumbnail(content = {}) {
  const candidates = [
    content.thumbnail_url,
    content.thumbnailUrl,
    content.thumbnail,
    content.cover_url,
    content.coverUrl,
    content.image_url,
    content.imageUrl,
    content.display_url,
    content.media_url,
  ];

  return candidates.find((value) => {
    const url = String(value || '').trim();
    return url && !['self', 'default', 'nsfw', 'spoiler', 'undefined', 'null'].includes(url.toLowerCase());
  }) || EMPTY_THUMBNAIL;
}

export function getContentStatus(video) {
  const score = Number(video?.score || 0);
  const engagement = Number(video?.engagement_rate || 0);
  if (engagement >= 0.06 && score >= 0.4) return { label: 'Trending', tone: 'hot' };
  if (score >= 0.65) return { label: 'High value', tone: 'high' };
  if (engagement >= 0.035) return { label: 'Rising', tone: 'rising' };
  return { label: 'Discovered', tone: 'neutral' };
}

export function getContentTags(video, limit = 4) {
  const source = Array.isArray(video?.topics)
    ? video.topics.join(' ')
    : `${video?.topics || ''} ${video?.niche || ''} ${video?.title || ''}`;
  const ignored = new Set(['about', 'their', 'there', 'which', 'these', 'video', 'with', 'from', 'this', 'that', 'your']);
  const tags = source
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, '')
    .split(/\s+/)
    .filter((word) => word.length > 3 && !ignored.has(word));

  return [...new Set(tags)].slice(0, limit);
}

export function getContentInsight(video) {
  const gap = String(video?.content_gap || '').trim();
  if (gap && gap !== 'Analysis pending') return gap;

  const engagement = Number(video?.engagement_rate || 0);
  if (engagement >= 0.06) return 'Audience response is well above the current content baseline.';
  if (Number(video?.score || 0) >= 0.6) return 'Strong score suggests this format is worth adapting for your audience.';
  return 'Use the performance pattern and topic angle as a creative benchmark.';
}

export function getContentMetrics(video) {
  return [
    { icon: '▶', label: 'Views', value: fmt(video?.views || 0) },
    { icon: '♥', label: 'Likes', value: fmt(video?.likes || 0) },
    { icon: '▣', label: 'Comments', value: fmt(video?.comments || 0) },
    { icon: '↗', label: 'Engagement', value: `${(Number(video?.engagement_rate || 0) * 100).toFixed(1)}%` },
  ];
}

export function formatPublishedAt(value) {
  if (!value) return 'Recent';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Recent';
  const days = Math.max(0, Math.floor((Date.now() - date.getTime()) / 86400000));
  if (days === 0) return 'Today';
  if (days === 1) return '1 day ago';
  if (days < 30) return `${days} days ago`;
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

export function platformMeta(platform) {
  return {
    icon: getPlatformIcon(platform),
    label: getPlatformLabel(platform),
  };
}
