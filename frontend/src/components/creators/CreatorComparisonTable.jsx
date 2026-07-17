import { formatCompactNumber, formatPercent, formatScore, getAvatarTone, getInitials, getVelocityDisplay } from './creatorUtils';
import PlatformIcon from '../PlatformIcon';

function ScoreBadge({ value }) {
  const score = Number(value || 0);
  const tone = score >= 0.7 ? 'high' : score >= 0.45 ? 'medium' : 'base';
  return <span className={`cr-score-badge ${tone}`}>{formatScore(score)}</span>;
}

function CreatorRow({ creator, rank, onOpen }) {
  const velocity = getVelocityDisplay(creator);
  return (
    <button type="button" className="cr-table-row" onClick={() => onOpen(creator)}>
      <span className={`cr-table-rank ${rank <= 3 ? `top-${rank}` : ''}`}>{rank}</span>
      <span className="cr-table-creator">
        <span className="cr-creator-avatar small" style={{ '--avatar-color': getAvatarTone(creator.channel) }}>{getInitials(creator.channel)}</span>
        <span><strong>{creator.channel}</strong><small>{creator.top_topics?.slice(0, 2).map((topic) => `#${topic}`).join(' · ') || 'Topics unavailable'}</small></span>
      </span>
      <span className="cr-table-number"><strong>{creator.video_count}</strong><small>{formatCompactNumber(creator.total_views)} views</small></span>
      <span className="cr-table-metric green"><strong>{formatPercent(creator.avg_engagement)}</strong><small>Engagement</small></span>
      <span className="cr-table-metric"><strong>{formatPercent(creator.trend_dominance_score)}</strong><small>Top-ranked content</small></span>
      <span className="cr-fit-cell"><strong>{formatPercent(creator.opportunity_alignment, 0)}</strong><i><b style={{ width: `${Math.min(100, creator.opportunity_alignment * 100)}%` }} /></i></span>
      <span><ScoreBadge value={creator.avg_score} /></span>
      <span className={`cr-growth-cell ${velocity.tone}`}><strong>{velocity.label}</strong><small>{velocity.tone === 'muted' ? 'Need more history' : velocity.detail}</small></span>
      <span className="cr-platform-cell">
        {creator.platform ? <><PlatformIcon platform={creator.platform} size={15} /><small>{creator.platformLabel}</small></> : <small>Unavailable</small>}
      </span>
      <span className="cr-row-action" aria-hidden="true">›</span>
    </button>
  );
}

export default function CreatorComparisonTable({ creators, loading, error, page, totalPages, onPageChange, onOpen, onRetry }) {
  return (
    <section className="cr-comparison-panel">
      <div className="cr-comparison-heading">
        <div><h2>Creator comparison</h2><p>{creators.length} matching creators</p></div>
        <span>Click a creator for detail</span>
      </div>
      {loading ? (
        <div className="cr-table-skeleton">{[1, 2, 3, 4, 5, 6].map((key) => <span key={key} />)}</div>
      ) : error ? (
        <div className="cr-table-state error"><strong>Unable to load creator intelligence</strong><p>{error}</p><button type="button" onClick={onRetry}>Try again</button></div>
      ) : !creators.length ? (
        <div className="cr-table-state"><strong>No creators match these filters</strong><p>Try clearing filters or run a pipeline scan to add more content.</p></div>
      ) : (
        <>
          <div className="cr-table-wrap" role="table" aria-label="Creator comparison">
            <div className="cr-table-labels" role="row"><span>#</span><span>Creator</span><span>Content</span><span>Engagement</span><span>Trend dominance</span><span>Opportunity fit</span><span>Avg score</span><span>Growth</span><span>Platform</span><span /></div>
            {creators.map((creator, index) => <CreatorRow key={creator.channel} creator={creator} rank={(page - 1) * 8 + index + 1} onOpen={onOpen} />)}
          </div>
          {totalPages > 1 && (
            <nav className="cr-pagination" aria-label="Creator pages">
              <button type="button" disabled={page === 1} onClick={() => onPageChange(page - 1)}>‹</button>
              {Array.from({ length: totalPages }, (_, index) => index + 1).slice(0, 5).map((item) => <button key={item} type="button" className={page === item ? 'active' : ''} onClick={() => onPageChange(item)}>{item}</button>)}
              <button type="button" disabled={page === totalPages} onClick={() => onPageChange(page + 1)}>›</button>
            </nav>
          )}
        </>
      )}
    </section>
  );
}
