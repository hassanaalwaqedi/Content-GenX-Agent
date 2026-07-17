import { compactNumber, formatScore, relativeTime, sentimentMeta, subredditLabel } from './redditData';
import { RedditEmptyState, RedditSkeleton } from './RedditStates';

export default function EmergingDiscussionsTable({ items, total, page, pageSize, loading, onOpen, onPageChange, onScan }) {
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const start = total ? ((page - 1) * pageSize) + 1 : 0;
  const end = Math.min(page * pageSize, total);

  return <section className="reddit-panel reddit-discussions">
    <header>
      <div><h2>Emerging Discussions</h2><span>{total} results</span></div>
      <button type="button" onClick={() => onOpen?.(items[0])} disabled={!items.length}>View discussion</button>
    </header>
    {loading ? <RedditSkeleton rows={5} /> : !items.length ? <RedditEmptyState title="No Reddit discussions match these filters" detail="Run a Reddit scan or broaden the date range to populate emerging discussions." actionLabel="Run Reddit Scan" onAction={onScan} /> : <>
      <div className="reddit-table-wrap">
        <table>
          <thead><tr><th>Discussion</th><th>Subreddit</th><th>Upvotes</th><th>Comments</th><th>Age</th><th>Velocity</th><th>Sentiment</th><th>Opportunity</th><th aria-label="Actions" /></tr></thead>
          <tbody>{items.map((item) => {
            const sentiment = sentimentMeta(item.sentiment);
            return <tr key={item.id} tabIndex="0" onClick={() => onOpen(item)} onKeyDown={(event) => { if (event.key === 'Enter') onOpen(item); }}>
              <td><div className="reddit-discussion-title"><span aria-hidden="true">↑</span><div><strong>{item.title || 'Untitled Reddit discussion'}</strong><small>{item.flair && <em>{item.flair}</em>}{item.author ? `u/${item.author.replace(/^u\//, '')}` : 'Author unavailable'}</small></div></div></td>
              <td><span className="reddit-community-cell">◉ {subredditLabel(item.subreddit)}</span></td>
              <td>{compactNumber(item.upvotes)}</td><td>{compactNumber(item.comments)}</td><td>{relativeTime(item.created_at)}</td>
              <td className="reddit-velocity">↑ {item.velocity == null ? '—' : `${compactNumber(item.velocity)}/h`}</td>
              <td><span className="reddit-sentiment" style={{ '--sentiment': sentiment.color }}>{sentiment.label}</span></td>
              <td><span className="reddit-opportunity-score">{formatScore(item.opportunity_score)}</span></td>
              <td><button type="button" aria-label={`Open ${item.title || 'discussion'} details`} onClick={(event) => { event.stopPropagation(); onOpen(item); }}>•••</button></td>
            </tr>;
          })}</tbody>
        </table>
      </div>
      {pageCount > 1 && <footer className="reddit-pagination" aria-label="Discussion pages">
        <span>Showing {start}–{end} of {total}</span>
        <div><button type="button" onClick={() => onPageChange(page - 1)} disabled={page === 1}>Previous</button><b>{page}</b><span>of {pageCount}</span><button type="button" onClick={() => onPageChange(page + 1)} disabled={page === pageCount}>Next</button></div>
      </footer>}
    </>}
  </section>;
}
