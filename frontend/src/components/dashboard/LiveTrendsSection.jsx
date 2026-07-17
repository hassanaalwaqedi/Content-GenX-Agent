import { fmt } from '../../utils/platform';

function trendStatus(trend) {
  const engagement = (trend.avg_engagement || 0) * 100;
  if (engagement >= 5) return 'Trending';
  if ((trend.trend_score || 0) >= 0.45) return 'Rising';
  return 'Watching';
}

function LiveTrendCard({ trend, onOpen }) {
  const score = Math.max(0, Math.min(1, trend.trend_score || 0));
  return (
    <button className="dash-trend-card" onClick={onOpen} title={`View content for ${trend.trend}`}>
      <div className="dash-trend-card-top">
        <strong>{trend.trend}</strong>
        <span className="dash-trend-status">↗ {trendStatus(trend)}</span>
      </div>
      <div className="dash-trend-stats">
        <span>{trend.count || 0} items</span>
        <span>{fmt(trend.total_views || 0)} views</span>
        <span>{((trend.avg_engagement || 0) * 100).toFixed(1)}% eng</span>
      </div>
      <div className="dash-trend-progress"><span style={{ width: `${score * 100}%` }} /></div>
      <small>Score: {score.toFixed(3)}</small>
    </button>
  );
}

export default function LiveTrendsSection({ trends, loading, onOpenTrend }) {
  return (
    <section className="dash-panel dash-live-panel">
      <div className="dash-panel-heading">
        <h2><span aria-hidden="true">🔥</span> Live Trends Right Now</h2>
        <span className="dash-count-badge">{trends.length} trend{trends.length === 1 ? '' : 's'}</span>
      </div>
      {loading ? (
        <div className="dash-trends-grid dash-trends-skeleton" aria-label="Loading trends">
          {[0, 1, 2, 3].map((item) => <span className="dash-skeleton-card" key={item} />)}
        </div>
      ) : trends.length > 0 ? (
        <div className="dash-trends-grid">
          {trends.slice(0, 4).map((trend, index) => (
            <LiveTrendCard key={`${trend.trend}-${index}`} trend={trend} onOpen={() => onOpenTrend(trend.trend)} />
          ))}
        </div>
      ) : (
        <div className="dash-empty-inline">
          <span aria-hidden="true">⌕</span>
          <div><strong>No live trends detected</strong><p>Run a new intelligence scan to collect more signals.</p></div>
        </div>
      )}
    </section>
  );
}
