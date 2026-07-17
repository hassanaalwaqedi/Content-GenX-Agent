import { formatPercent, formatScore, getAvatarTone, getInitials, getVelocityDisplay } from './creatorUtils';

function RisingCard({ creator, index, onOpen }) {
  const velocity = getVelocityDisplay(creator);
  const topics = creator.top_topics?.slice(0, 2) || [];

  return (
    <button type="button" className="cr-rising-card" onClick={() => onOpen(creator)}>
      <span className="cr-rising-rank">{index + 1}</span>
      <div className="cr-rising-card-top">
        <span className="cr-creator-avatar" style={{ '--avatar-color': getAvatarTone(creator.channel) }}>{getInitials(creator.channel)}</span>
        <span className={`cr-velocity-pill ${velocity.tone}`}>{velocity.label}</span>
      </div>
      <strong title={creator.channel}>{creator.channel}</strong>
      <small>{creator.video_count} {creator.video_count === 1 ? 'content item' : 'content items'}</small>
      <div className="cr-rising-metrics">
        <span>Engagement <b>{formatPercent(creator.avg_engagement)}</b></span>
        <span>Score <b>{formatScore(creator.avg_score)}</b></span>
      </div>
      <div className="cr-rising-topics">
        {topics.length ? topics.map((topic) => <span key={topic}>#{topic}</span>) : <span>Topics unavailable</span>}
      </div>
    </button>
  );
}

export default function RisingCreators({ creators, loading, onOpen }) {
  return (
    <section className="cr-rising-section">
      <div className="cr-section-heading">
        <div><h2><span aria-hidden="true">↗</span> Rising Creators</h2><p>Creators with the strongest available recent score signal.</p></div>
        <span className="cr-count-badge">{creators.length} tracked</span>
      </div>
      {loading ? (
        <div className="cr-rising-grid cr-loading-cards">{[1, 2, 3, 4, 5].map((key) => <span key={key} />)}</div>
      ) : creators.length ? (
        <div className="cr-rising-grid">{creators.slice(0, 5).map((creator, index) => <RisingCard key={creator.channel} creator={creator} index={index} onOpen={onOpen} />)}</div>
      ) : (
        <div className="cr-empty-inline">No rising creators have enough scored history in this workspace yet.</div>
      )}
    </section>
  );
}
