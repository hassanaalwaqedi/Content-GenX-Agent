import { useEffect } from 'react';
import PlatformIcon from '../PlatformIcon';
import { getContentThumbnail } from '../top-content/contentUtils';
import { formatCompactNumber, formatPercent, formatScore, getAvatarTone, getInitials, getVelocityDisplay } from './creatorUtils';

function DrawerThumbnail({ video }) {
  const thumbnail = getContentThumbnail(video);
  return <div className="cr-drawer-thumbnail">{thumbnail ? <img src={thumbnail} alt="" onError={(event) => { event.currentTarget.style.display = 'none'; }} /> : null}<span aria-hidden="true">{video.platform || 'content'}</span></div>;
}

export default function CreatorDetailDrawer({ creator, videos, loading, onClose }) {
  useEffect(() => {
    if (!creator) return undefined;
    const onKeyDown = (event) => { if (event.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [creator, onClose]);

  if (!creator) return null;
  const velocity = getVelocityDisplay(creator);
  const metrics = [
    ['Content', creator.video_count], ['Views', formatCompactNumber(creator.total_views)], ['Engagement', formatPercent(creator.avg_engagement)], ['AI score', formatScore(creator.avg_score)],
  ];

  return (
    <div className="cr-drawer-backdrop" onMouseDown={onClose} role="presentation">
      <aside className="cr-detail-drawer" aria-label={`${creator.channel} details`} onMouseDown={(event) => event.stopPropagation()}>
        <button type="button" className="cr-drawer-close" onClick={onClose} aria-label="Close creator details">×</button>
        <div className="cr-drawer-identity">
          <span className="cr-creator-avatar large" style={{ '--avatar-color': getAvatarTone(creator.channel) }}>{getInitials(creator.channel)}</span>
          <div><p>Creator profile</p><h2>{creator.channel}</h2><span>{creator.platform ? <><PlatformIcon platform={creator.platform} size={14} /> {creator.platformLabel}</> : 'Platform unavailable from aggregate data'}</span></div>
        </div>
        <div className="cr-drawer-metrics">{metrics.map(([label, value]) => <div key={label}><small>{label}</small><strong>{value}</strong></div>)}</div>
        <section className="cr-drawer-section">
          <h3>Performance signals</h3>
          <div className="cr-drawer-signal"><span>Trend dominance</span><strong>{formatPercent(creator.trend_dominance_score)}</strong><i><b style={{ width: `${creator.trend_dominance_score * 100}%` }} /></i></div>
          <div className="cr-drawer-signal"><span>Opportunity fit</span><strong>{formatPercent(creator.opportunity_alignment, 0)}</strong><i><b style={{ width: `${creator.opportunity_alignment * 100}%` }} /></i></div>
          <div className={`cr-drawer-velocity ${velocity.tone}`}><strong>{velocity.label}</strong><span>{velocity.detail}</span></div>
        </section>
        <section className="cr-drawer-section">
          <h3>Top topics</h3>
          <div className="cr-drawer-topics">{creator.top_topics?.length ? creator.top_topics.map((topic) => <span key={topic}>#{topic}</span>) : <span className="cr-no-data">Topics unavailable</span>}</div>
        </section>
        <section className="cr-drawer-section cr-drawer-content">
          <h3>Top content</h3>
          {loading ? <div className="cr-drawer-loading">Loading creator content…</div> : videos.length ? <div>{videos.slice(0, 6).map((video) => <article key={video.video_id}><DrawerThumbnail video={video} /><div><strong>{video.title || 'Untitled content'}</strong><span>{formatCompactNumber(video.views)} views · {formatPercent(video.engagement_rate)} engagement</span></div></article>)}</div> : <p className="cr-no-data">No creator content is available yet.</p>}
        </section>
      </aside>
    </div>
  );
}
