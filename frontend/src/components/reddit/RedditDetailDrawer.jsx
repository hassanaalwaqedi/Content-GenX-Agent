import { compactNumber, formatPercent, formatScore, relativeTime, sentimentMeta, subredditLabel } from './redditData';

export default function RedditDetailDrawer({ item, type, onClose }) {
  if (!item) return null;
  const isDiscussion = type === 'discussion';
  const sentiment = sentimentMeta(item.sentiment);
  const drawerTitle = item.title || item.statement || item.name || (type === 'connector' ? 'Reddit Connector Health' : 'Reddit intelligence detail');
  const drawerLabel = isDiscussion ? subredditLabel(item.subreddit) : type === 'pain' ? 'Community pain point' : type === 'connector' ? 'Connector status' : 'Discussion cluster';

  return <div className="reddit-drawer-backdrop" role="presentation" onMouseDown={onClose}>
    <aside className="reddit-detail-drawer" role="dialog" aria-modal="true" aria-label="Reddit intelligence details" onMouseDown={(event) => event.stopPropagation()}>
      <header><div><span>{isDiscussion ? '◉' : '⌁'}</span><p>{drawerLabel}</p></div><button type="button" onClick={onClose} aria-label="Close details">×</button></header>
      <div className="reddit-drawer-content">
        <h2>{drawerTitle}</h2>
        {isDiscussion ? <>
          <p className="reddit-drawer-body">{item.body || 'The source did not retain a Reddit post body.'}</p>
          <dl>
            <div><dt>Author</dt><dd>{item.author ? `u/${item.author.replace(/^u\//, '')}` : 'Unavailable'}</dd></div>
            <div><dt>Published</dt><dd>{relativeTime(item.created_at)}</dd></div>
            <div><dt>Upvotes</dt><dd>{compactNumber(item.upvotes)}</dd></div>
            <div><dt>Comments</dt><dd>{compactNumber(item.comments)}</dd></div>
            <div><dt>Upvote ratio</dt><dd>{formatPercent(item.upvote_ratio)}</dd></div>
            <div><dt>Velocity</dt><dd>{item.velocity == null ? '—' : `${compactNumber(item.velocity)}/h`}</dd></div>
          </dl>
          <div className="reddit-drawer-insights"><span style={{ '--sentiment': sentiment.color }}>{sentiment.label}</span><span>Opportunity {formatScore(item.opportunity_score)}</span><span>{item.opportunity_source === 'enrichment' ? 'AI-enriched' : 'Engagement-derived'}</span></div>
          {item.source_url && <a href={item.source_url} target="_blank" rel="noreferrer">Open source discussion ↗</a>}
        </> : <p>This analytical item is built from retained Reddit metadata and enrichment. Use the surrounding views to explore the linked discussions.</p>}
      </div>
    </aside>
  </div>;
}
