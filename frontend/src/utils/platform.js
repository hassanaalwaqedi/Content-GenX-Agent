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

/** Get the emoji icon for a platform (text fallback) */
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
