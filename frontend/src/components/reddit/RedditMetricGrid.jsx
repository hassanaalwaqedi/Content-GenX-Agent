import { compactNumber, formatPercent, formatScore } from './redditData';

function Metric({ icon, label, value, detail, tone = 'blue' }) {
  return <article className={`reddit-metric ${tone}`}><span className="reddit-metric-icon" aria-hidden="true">{icon}</span><div><p>{label}</p><strong>{value}</strong><small>{detail}</small></div><i aria-hidden="true" /></article>;
}

export default function RedditMetricGrid({ overview }) {
  const topic = overview?.fastest_growing_topic;
  return <section className="reddit-metric-grid" aria-label="Reddit intelligence metrics">
    <Metric icon="▣" label="Total Posts Analyzed" value={compactNumber(overview?.posts_analyzed)} detail={overview?.posts_analyzed ? 'Indexed Reddit posts' : 'No indexed Reddit posts'} tone="blue" />
    <Metric icon="◉" label="Active Subreddits" value={compactNumber(overview?.active_subreddits)} detail="Communities with retained metadata" tone="cyan" />
    <Metric icon="◌" label="Total Comments" value={compactNumber(overview?.total_comments)} detail="Comments across indexed discussions" tone="purple" />
    <Metric icon="↑" label="Avg Upvote Ratio" value={formatPercent(overview?.avg_upvote_ratio)} detail={overview?.avg_upvote_ratio == null ? 'Unavailable from current records' : 'Across posts that expose a ratio'} tone="green" />
    <Metric icon="⌁" label="Fastest Growing Topic" value={topic?.name || '—'} detail={topic ? `${compactNumber(topic.velocity)} interactions / hour` : 'Awaiting topic-enriched discussions'} tone="violet" />
    <Metric icon="◎" label="Opportunity Score" value={formatScore(overview?.opportunity_score)} detail={overview?.opportunity_score == null ? 'No scored Reddit discussions yet' : 'Derived from enrichment and engagement'} tone="orange" />
  </section>;
}
