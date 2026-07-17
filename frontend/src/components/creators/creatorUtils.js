import { getPlatformColor, getPlatformLabel } from '../../utils/platform';

export const CREATOR_TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'performance', label: 'Performance' },
  { id: 'trends', label: 'Trends' },
  { id: 'content', label: 'Content' },
  { id: 'growth', label: 'Growth' },
  { id: 'audience', label: 'Audience' },
  { id: 'opportunities', label: 'Opportunities' },
];

export const PLATFORM_ORDER = ['youtube', 'tiktok', 'instagram', 'reddit'];

export function number(value) {
  const result = Number(value);
  return Number.isFinite(result) ? result : 0;
}

export function formatCompactNumber(value) {
  const amount = number(value);
  if (amount >= 1_000_000) return `${(amount / 1_000_000).toFixed(amount >= 10_000_000 ? 0 : 1)}M`;
  if (amount >= 1_000) return `${(amount / 1_000).toFixed(amount >= 100_000 ? 0 : 1)}K`;
  return amount.toLocaleString();
}

export function formatPercent(value, precision = 1) {
  return `${(number(value) * 100).toFixed(precision)}%`;
}

export function formatScore(value) {
  return number(value).toFixed(2);
}

export function getInitials(channel) {
  const words = String(channel || 'Creator').replace(/[@_.-]+/g, ' ').trim().split(/\s+/).filter(Boolean);
  return words.slice(0, 2).map((word) => word[0]?.toUpperCase()).join('') || 'C';
}

export function getAvatarTone(channel) {
  const colors = ['#7657d7', '#1f82d6', '#d05a95', '#1b9d86', '#c77d32', '#3d62b6'];
  const seed = [...String(channel || '')].reduce((sum, character) => sum + character.charCodeAt(0), 0);
  return colors[seed % colors.length];
}

export function normalizeCreator(creator = {}, platformMap = {}) {
  const channel = String(creator.channel || 'Unknown creator');
  const platform = platformMap[channel]?.platform || '';
  const velocity = creator.recent_velocity;
  const hasVelocityHistory = Number.isFinite(Number(velocity)) && Math.abs(number(velocity)) > 0.00001;

  return {
    ...creator,
    channel,
    video_count: number(creator.video_count),
    total_views: number(creator.total_views),
    avg_engagement: number(creator.avg_engagement ?? creator.avg_engagement_rate),
    avg_score: number(creator.avg_score),
    total_score: number(creator.total_score),
    trend_dominance_score: number(creator.trend_dominance_score),
    opportunity_alignment: number(creator.opportunity_alignment),
    recent_velocity: number(velocity),
    hasVelocityHistory,
    top_topics: Array.isArray(creator.top_topics) ? creator.top_topics.filter(Boolean) : [],
    platform,
    platformLabel: platform ? getPlatformLabel(platform) : 'Unavailable',
    platformColor: platform ? getPlatformColor(platform) : '#71809d',
  };
}

export function buildCreatorPlatformMap(videos = []) {
  const byCreator = new Map();

  videos.forEach((video) => {
    const channel = String(video?.channel || '').trim();
    const platform = String(video?.platform || '').toLowerCase();
    if (!channel || !platform) return;

    const current = byCreator.get(channel) || {};
    current[platform] = (current[platform] || 0) + 1;
    byCreator.set(channel, current);
  });

  return [...byCreator.entries()].reduce((result, [channel, counts]) => {
    const [platform, count] = Object.entries(counts).sort(([, left], [, right]) => right - left)[0] || [];
    if (platform) result[channel] = { platform, count };
    return result;
  }, {});
}

export function getVelocityDisplay(creator) {
  if (!creator?.hasVelocityHistory) {
    return { label: 'Insufficient history', tone: 'muted', detail: 'A 7-day versus 30-day score comparison needs more published history.' };
  }

  const velocity = number(creator.recent_velocity);
  if (velocity > 0) return { label: 'Rising', tone: 'positive', detail: 'Recent score is higher than the 30-day baseline.' };
  return { label: 'Cooling', tone: 'negative', detail: 'Recent score is below the 30-day baseline.' };
}

export function getCreatorSortValue(creator, sortMode) {
  const modes = {
    score: creator.avg_score,
    engagement: creator.avg_engagement,
    dominance: creator.trend_dominance_score,
    opportunity: creator.opportunity_alignment,
    views: creator.total_views,
    content: creator.video_count,
    growth: creator.hasVelocityHistory ? creator.recent_velocity : -Infinity,
  };
  return number(modes[sortMode] ?? creator.avg_score);
}

export function tabSortMode(tab) {
  return {
    overview: 'score',
    performance: 'score',
    trends: 'dominance',
    content: 'views',
    growth: 'growth',
    audience: 'engagement',
    opportunities: 'opportunity',
  }[tab] || 'score';
}

export function buildEngagementDistribution(creators = []) {
  const tiers = [
    { key: 'high', label: 'High (10%+)', color: '#3b82f6', test: (value) => value >= 0.1 },
    { key: 'medium', label: 'Medium (5–10%)', color: '#34d399', test: (value) => value >= 0.05 },
    { key: 'low', label: 'Low (<5%)', color: '#ec4899', test: () => true },
  ].map((tier) => ({ ...tier, count: 0 }));

  creators.forEach((creator) => {
    const tier = tiers.find((item) => item.test(number(creator.avg_engagement)));
    if (tier) tier.count += 1;
  });

  return tiers;
}

export function buildPlatformLeaders(videos = []) {
  const platforms = videos.reduce((result, video) => {
    const platform = String(video?.platform || '').toLowerCase();
    const channel = String(video?.channel || '').trim();
    if (!platform) return result;
    if (!result[platform]) result[platform] = { platform, videos: 0, creators: new Set(), engagementTotal: 0 };
    result[platform].videos += 1;
    result[platform].engagementTotal += number(video.engagement_rate);
    if (channel) result[platform].creators.add(channel);
    return result;
  }, {});

  return Object.values(platforms)
    .map((item) => ({
      platform: item.platform,
      label: getPlatformLabel(item.platform),
      color: getPlatformColor(item.platform),
      videos: item.videos,
      creators: item.creators.size,
      avgEngagement: item.videos ? item.engagementTotal / item.videos : 0,
    }))
    .sort((left, right) => right.creators - left.creators || right.avgEngagement - left.avgEngagement);
}

export function buildOpportunityNiches(creators = []) {
  const topics = new Map();

  creators.forEach((creator) => {
    creator.top_topics.slice(0, 4).forEach((topic) => {
      const key = String(topic || '').trim().toLowerCase();
      if (!key) return;
      const current = topics.get(key) || { label: key, creatorCount: 0, fitTotal: 0 };
      current.creatorCount += 1;
      current.fitTotal += number(creator.opportunity_alignment);
      topics.set(key, current);
    });
  });

  return [...topics.values()]
    .map((item) => ({ ...item, averageFit: item.creatorCount ? item.fitTotal / item.creatorCount : 0 }))
    .sort((left, right) => right.averageFit - left.averageFit || right.creatorCount - left.creatorCount)
    .slice(0, 5);
}

export function relativeUpdatedAt(date) {
  if (!date) return 'Not updated yet';
  const seconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));
  if (seconds < 60) return 'Updated just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `Updated ${minutes} minute${minutes === 1 ? '' : 's'} ago`;
  return `Updated ${Math.floor(minutes / 60)}h ago`;
}
