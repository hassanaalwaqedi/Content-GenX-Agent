/**
 * Shared platform utilities for multi-platform intelligence.
 * Single source of truth for platform icons, labels, colors, and scoring.
 */

export const PLATFORM_CONFIG = {
  youtube:   { icon: '▶️',  label: 'YouTube',   color: '#ff4444', bg: 'rgba(255,68,68,0.1)',   contentLabel: 'video' },
  reddit:    { icon: '💬',  label: 'Reddit',    color: '#ff6633', bg: 'rgba(255,102,51,0.1)',  contentLabel: 'post' },
  tiktok:    { icon: '🎵',  label: 'TikTok',    color: '#ff2d75', bg: 'rgba(255,45,117,0.1)',  contentLabel: 'video' },
  instagram: { icon: '📸',  label: 'Instagram', color: '#c837ab', bg: 'rgba(200,55,171,0.1)',  contentLabel: 'reel' },
};

/** Get the emoji icon for a platform */
export function getPlatformIcon(platform) {
  return PLATFORM_CONFIG[platform]?.icon || '⚡';
}

/** Get the full label for a platform */
export function getPlatformLabel(platform) {
  return PLATFORM_CONFIG[platform]?.label || platform || 'Unknown';
}

/** Get platform color */
export function getPlatformColor(platform) {
  return PLATFORM_CONFIG[platform]?.color || '#4f8cff';
}

/** Get platform background color */
export function getPlatformBg(platform) {
  return PLATFORM_CONFIG[platform]?.bg || 'rgba(79,140,255,0.1)';
}

/**
 * Get the content type label for a piece of content.
 * Uses content_type field if available, falls back to platform default.
 */
export function getContentLabel(item) {
  if (item?.content_type && item.content_type !== 'video') {
    return item.content_type; // reel, short, post
  }
  return PLATFORM_CONFIG[item?.platform]?.contentLabel || 'content';
}

/**
 * Get pluralized content label for counts.
 * e.g. "3 videos", "1 post", "12 content items"
 */
export function getContentCountLabel(count, platform) {
  if (platform && PLATFORM_CONFIG[platform]) {
    const base = PLATFORM_CONFIG[platform].contentLabel;
    return `${count} ${base}${count !== 1 ? 's' : ''}`;
  }
  return `${count} content item${count !== 1 ? 's' : ''}`;
}

/** Generic "content" plural for mixed-platform datasets */
export function contentPlural(count) {
  return `${count} content item${count !== 1 ? 's' : ''}`;
}

/**
 * Get the source URL for a content item.
 * Falls back to constructing from platform + id.
 */
export function getSourceUrl(item) {
  if (item?.source_url) return item.source_url;
  switch (item?.platform) {
    case 'youtube':
      return `https://www.youtube.com/watch?v=${item.video_id}`;
    case 'reddit':
      return `https://www.reddit.com/search/?q=${encodeURIComponent(item.title || '')}`;
    case 'tiktok':
      return `https://www.tiktok.com/search?q=${encodeURIComponent(item.title || '')}`;
    case 'instagram':
      return `https://www.instagram.com/explore/tags/${encodeURIComponent((item.title || '').split(' ')[0])}`;
    default:
      return '#';
  }
}

/**
 * Normalize engagement metrics across platforms into a comparable score.
 * Different platforms weight metrics differently:
 * - YouTube: views-heavy
 * - TikTok: shares/saves-heavy (virality)
 * - Instagram: engagement-rate-heavy
 * - Reddit: comments/upvotes-heavy
 */
export function normalizedIntelligenceScore(item) {
  if (!item) return 0;

  const engagement = item.engagement_rate || 0;
  const virality = item.virality_score || 0;
  const velocity = item.trend_velocity || 0;
  const score = item.score || 0;

  // Base weighted score
  let normalized = score * 0.4 + engagement * 3 + virality * 10 + velocity * 5;

  // Platform multiplier (normalize across different scale ranges)
  const multipliers = { youtube: 1.0, tiktok: 1.1, instagram: 1.05, reddit: 0.95 };
  normalized *= (multipliers[item.platform] || 1.0);

  return Math.min(Math.max(normalized, 0), 1);
}

/**
 * Format number with K/M suffixes
 */
export function fmt(n) {
  if (n == null) return '0';
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return String(n);
}

/**
 * Get all available platform keys
 */
export const ALL_PLATFORMS = ['youtube', 'tiktok', 'instagram', 'reddit'];
