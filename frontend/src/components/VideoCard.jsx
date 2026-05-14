import { Link } from 'react-router-dom';

const DEFAULT_THUMBNAIL = 'https://via.placeholder.com/320x180.png?text=No+Thumbnail';

const REGION_FLAGS = {
  US: '🇺🇸', GB: '🇬🇧', CA: '🇨🇦', DE: '🇩🇪', FR: '🇫🇷', AU: '🇦🇺',
  AE: '🇦🇪', IN: '🇮🇳', JP: '🇯🇵', KR: '🇰🇷', BR: '🇧🇷', MX: '🇲🇽',
  SA: '🇸🇦', EG: '🇪🇬', TR: '🇹🇷', IT: '🇮🇹', ES: '🇪🇸', NL: '🇳🇱',
};

function fmt(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return String(n);
}

function getTrendBadge(video) {
  const eng = video.engagement_rate * 100;
  if (eng > 6 && video.score > 0.4) return { emoji: '🔥', label: 'Trending', cls: 'trend-badge-fire' };
  if (video.score > 0.6) return { emoji: '🧠', label: 'High Value', cls: 'trend-badge-brain' };
  if (eng > 4) return { emoji: '🚀', label: 'Rising', cls: 'trend-badge-rising' };
  return null;
}

function extractTags(video) {
  const tags = [];
  if (video.niche) tags.push(video.niche);
  if (video.platform) tags.push(video.platform === 'reddit' ? 'Reddit' : 'YouTube');
  // Extract keywords from title
  const keywords = (video.title || '')
    .replace(/[^\w\s]/g, '')
    .split(/\s+/)
    .filter(w => w.length > 4)
    .slice(0, 2)
    .map(w => w.toLowerCase());
  keywords.forEach(k => {
    if (!tags.some(t => t.toLowerCase() === k)) tags.push(k);
  });
  return tags.slice(0, 4);
}

export default function VideoCard({ video, onTranscript, onGenerate }) {
  const trendBadge = getTrendBadge(video);
  const tags = extractTags(video);
  const isPending = (val) => !val || val === 'Analysis pending';
  const hasInsight = !isPending(video.target_audience) || !isPending(video.content_gap) || !isPending(video.strategic_advice);

  return (
    <div className="vcard">
      {/* Thumbnail */}
      <div className="vcard-thumb-wrap">
        <Link to={`/video/${video.video_id}`}>
          <img
            src={video.thumbnail_url || DEFAULT_THUMBNAIL}
            alt={video.title}
            className="vcard-thumb"
            loading="lazy"
            onError={(e) => { e.target.src = DEFAULT_THUMBNAIL; }}
          />
        </Link>
        {trendBadge && (
          <span className={`vcard-trend ${trendBadge.cls}`}>
            {trendBadge.emoji} {trendBadge.label}
          </span>
        )}
        <span className="vcard-score-float">
          {video.score?.toFixed(2)}
        </span>
      </div>

      {/* Body */}
      <div className="vcard-body">
        <Link to={`/video/${video.video_id}`} className="vcard-title-link">
          <h3 className="vcard-title">{video.title}</h3>
        </Link>

        <p className="vcard-channel">
          {video.platform === 'reddit' ? '💬' : '🎬'} {video.channel || 'Unknown'}
          {video.source_region && (
            <span className="vcard-region-badge" title={`Source: ${video.source_region}`}>
              {REGION_FLAGS[video.source_region] || '🌐'} {video.source_region}
            </span>
          )}
        </p>

        <div className="vcard-stats">
          <span className="vcard-stat">
            <span className="vcard-stat-icon">👁</span>
            {fmt(video.views)}
          </span>
          <span className="vcard-stat">
            <span className="vcard-stat-icon">👍</span>
            {fmt(video.likes)}
          </span>
          <span className={`vcard-engagement ${video.engagement_rate > 0.05 ? 'high' : video.engagement_rate > 0.02 ? 'mid' : 'low'}`}>
            {(video.engagement_rate * 100).toFixed(1)}%
          </span>
        </div>

        {/* Tags */}
        <div className="vcard-tags">
          {tags.map((tag, i) => (
            <span key={i} className="vcard-tag">#{tag}</span>
          ))}
        </div>

        {/* Actions */}
        <div className="vcard-actions">
          <Link to={`/video/${video.video_id}`} className="vcard-btn vcard-btn-detail">
            View Details
          </Link>
          {video.platform !== 'reddit' && (
            <button
              className="vcard-btn vcard-btn-transcript"
              onClick={() => onTranscript(video)}
            >
              📝 Transcript
            </button>
          )}
          <button
            className="vcard-btn vcard-btn-detail"
            onClick={() => onGenerate && onGenerate(video)}
            style={{ background: 'var(--color-accent-purple-bg)', color: 'var(--color-accent-purple)', borderColor: 'var(--color-accent-purple)' }}
          >
            ✨ Generate
          </button>
        </div>
      </div>

      {/* Insight Hover Panel */}
      {hasInsight && (
        <div className="vcard-insight-panel">
          {!isPending(video.target_audience) && (
            <div className="vcard-insight-row">
              <span className="vcard-insight-label">🎯 Audience</span>
              <p>{video.target_audience}</p>
            </div>
          )}
          {!isPending(video.content_gap) && (
            <div className="vcard-insight-row">
              <span className="vcard-insight-label">💡 Content Gap</span>
              <p>{video.content_gap}</p>
            </div>
          )}
          {!isPending(video.strategic_advice) && (
            <div className="vcard-insight-row">
              <span className="vcard-insight-label">🧭 Strategy</span>
              <p>{video.strategic_advice}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
