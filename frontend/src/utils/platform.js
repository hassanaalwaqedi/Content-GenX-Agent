/**
 * Shared platform utilities for multi-platform intelligence.
 * Single source of truth for platform icons, labels, colors, and scoring.
 */

/* ── Brand SVG paths (viewBox 0 0 24 24) ────────────────────────────── */
const _BRAND_SVGS = {
  youtube: (
    '<path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.546 12 3.546 12 3.546s-7.505 0-9.377.504A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.504 9.376.504 9.376.504s7.505 0 9.377-.504a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" fill="currentColor"/>'
  ),
  reddit: (
    '<path d="M12 0A12 12 0 1 0 12 24A12 12 0 1 0 12 0zM19.8 13.2a1.4 1.4 0 0 1-.3.9 5.5 5.5 0 0 1-3 2.6 10.2 10.2 0 0 1-4.5.8 10.2 10.2 0 0 1-4.5-.8 5.5 5.5 0 0 1-3-2.6 1.4 1.4 0 0 1-.3-.9c0-.5.2-.9.6-1.2a1.5 1.5 0 0 1 1.3-.3 5.8 5.8 0 0 1 2.7-1.5c.1 0 .2 0 .2.1l.9 2.2a.8.8 0 0 0 .5-.2.8.8 0 0 0 .2-.6.8.8 0 0 1 .8-.8.8.8 0 0 1 .8.8.8.8 0 0 0 .7.8l.9-2.2c0-.1.1-.1.2-.1a5.8 5.8 0 0 1 2.7 1.5 1.5 1.5 0 0 1 1.3.3c.4.3.6.7.6 1.2z" fill="currentColor"/>'
  ),
  tiktok: (
    '<path d="M16.6 5.82s.51.49 1.7.49V8.5c-.62 0-1.24-.13-1.7-.49v4.53c0 2.26-1.84 4.1-4.1 4.1a4.1 4.1 0 0 1-4.1-4.1 4.1 4.1 0 0 1 4.1-4.1c.22 0 .44.02.65.06v2.2a1.9 1.9 0 0 0-.65-.11 1.9 1.9 0 0 0-1.9 1.9 1.9 1.9 0 0 0 1.9 1.9 1.9 1.9 0 0 0 1.9-1.83V2h2.2c.18 1.66 1.49 2.96 3.1 3.17v2.2a5.3 5.3 0 0 1-3.1-.97v.37" fill="currentColor"/>'
  ),
  instagram: (
    '<path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 1 0 0 12.324 6.162 6.162 0 0 0 0-12.324zM12 16a4 4 0 1 1 0-8 4 4 0 0 1 0 8zm6.406-11.845a1.44 1.44 0 1 0 0 2.881 1.44 1.44 0 0 0 0-2.881z" fill="currentColor"/>'
  ),
};

export const PLATFORM_CONFIG = {
  youtube:   { icon: '▶️',  label: 'YouTube',   color: '#ff4444', bg: 'rgba(255,68,68,0.1)',   contentLabel: 'video' },
  reddit:    { icon: '💬',  label: 'Reddit',    color: '#ff6633', bg: 'rgba(255,102,51,0.1)',  contentLabel: 'post' },
  tiktok:    { icon: '🎵',  label: 'TikTok',    color: '#ff2d75', bg: 'rgba(255,45,117,0.1)',  contentLabel: 'video' },
  instagram: { icon: '📸',  label: 'Instagram', color: '#c837ab', bg: 'rgba(200,55,171,0.1)',  contentLabel: 'reel' },
};

/** Get the emoji icon for a platform (text fallback) */
export function getPlatformIcon(platform) {
  return PLATFORM_CONFIG[platform]?.icon || '⚡';
}

/**
 * Get a brand SVG icon as a raw HTML string for dangerouslySetInnerHTML.
 * @param {string} platform - e.g. 'youtube', 'tiktok'
 * @param {number} size - icon size in px (default 18)
 * @returns {string} SVG markup string
 */
export function getPlatformSvg(platform, size = 18) {
  const inner = _BRAND_SVGS[platform];
  if (!inner) return '';
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="${size}" height="${size}" style="display:inline-block;vertical-align:middle">${inner}</svg>`;
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
