import { compactNumber, subredditLabel } from './redditData';
import { RedditEmptyState, RedditSkeleton } from './RedditStates';

function ActivityBars({ points = [] }) {
  const maximum = Math.max(...points, 1);
  return <div className="reddit-activity-bars" aria-label="Seven-day activity"><span className="sr-only">Seven-day activity trend</span>{points.map((point, index) => <i key={index} style={{ height: `${Math.max(10, (point / maximum) * 100)}%` }} />)}</div>;
}

export default function TrendingSubredditsSection({ items, loading, onOpen }) {
  return <section className="reddit-panel reddit-subreddits"><header><h2>🔥 Trending Subreddits</h2><button type="button" onClick={() => onOpen?.(items[0])} disabled={!items.length}>View all</button></header>{loading ? <RedditSkeleton rows={4} /> : !items.length ? <RedditEmptyState title="No subreddit metadata yet" detail="New Reddit scans retain subreddit details so community momentum can be analyzed." /> : <div className="reddit-subreddit-row">{items.map((item) => <button type="button" className="reddit-subreddit-card" key={item.name} onClick={() => onOpen(item)}><span className="reddit-subreddit-avatar">r/</span><div><strong>{subredditLabel(item.name)}</strong><small>{item.member_count ? `${compactNumber(item.member_count)} members` : 'Member count unavailable'}</small></div><dl><div><dt>Momentum</dt><dd>↑ {compactNumber(item.momentum)}/h</dd></div><div><dt>Posts ({item.posts})</dt><dd>{compactNumber(item.comments)} comments</dd></div></dl><ActivityBars points={item.activity} />{item.topics?.[0] && <em>{item.topics[0].replaceAll('_', ' ')}</em>}</button>)}</div>}</section>;
}
