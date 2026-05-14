import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { api } from '../api/client';
import { useDataset } from '../context/DatasetContext';
import EmptyDataset from '../components/EmptyDataset';

const COLORS = ['#4f8cff', '#34d399', '#f59e0b', '#a78bfa', '#ef4444', '#06b6d4', '#f472b6', '#22d3ee'];

function fmt(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return String(n);
}

// ---------------------------------------------------------------------------
// Skeleton Components
// ---------------------------------------------------------------------------
function SkeletonKPI() {
  return (
    <div className="kpi-card">
      <div className="skeleton-line skeleton-shimmer" style={{ width: '60%', height: 12, marginBottom: 10 }}></div>
      <div className="skeleton-line skeleton-shimmer" style={{ width: '40%', height: 28, marginBottom: 8 }}></div>
      <div className="skeleton-line skeleton-shimmer" style={{ width: '80%', height: 10 }}></div>
    </div>
  );
}

function SkeletonTrendCard() {
  return (
    <div className="db-trend-card">
      <div className="skeleton-line skeleton-shimmer" style={{ width: '65%', height: 14, marginBottom: 10 }}></div>
      <div className="skeleton-row" style={{ gap: 8, marginBottom: 10 }}>
        <div className="skeleton-line skeleton-shimmer" style={{ width: '30%', height: 20, borderRadius: 10 }}></div>
        <div className="skeleton-line skeleton-shimmer" style={{ width: '25%', height: 20, borderRadius: 10 }}></div>
      </div>
      <div className="skeleton-line skeleton-shimmer" style={{ width: '100%', height: 32, borderRadius: 6 }}></div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// TrendCard
// ---------------------------------------------------------------------------
function TrendCard({ trend, onClick }) {
  const score = trend.trend_score || 0;
  const eng = (trend.avg_engagement || 0) * 100;
  let badge = null;
  if (eng > 5 && score > 0.4) badge = { emoji: '🔥', label: 'Trending', cls: 'trend-badge-fire' };
  else if (score > 0.5) badge = { emoji: '🧠', label: 'High Value', cls: 'trend-badge-brain' };
  else if (eng > 3) badge = { emoji: '🚀', label: 'Rising', cls: 'trend-badge-rising' };

  return (
    <div className="db-trend-card" onClick={onClick} title={`View videos about "${trend.trend}"`}>
      <div className="db-trend-header">
        <h4 className="db-trend-name">{trend.trend}</h4>
        {badge && <span className={`db-trend-badge ${badge.cls}`}>{badge.emoji} {badge.label}</span>}
      </div>
      <div className="db-trend-stats">
        <span className="db-trend-stat">
          <strong>{trend.count}</strong> videos
        </span>
        <span className="db-trend-stat">
          <strong>{fmt(trend.total_views || 0)}</strong> views
        </span>
        <span className="db-trend-stat">
          <strong>{eng.toFixed(1)}%</strong> eng
        </span>
      </div>
      <div className="db-trend-score-bar">
        <div className="db-trend-score-fill" style={{ width: `${Math.min(score * 100, 100)}%` }}></div>
      </div>
      <div className="db-trend-score-label">Score: {score.toFixed(3)}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// OpportunityCard
// ---------------------------------------------------------------------------
function OpportunityCard({ op }) {
  const pct = Math.round((op.opportunity_score || 0) * 100);
  return (
    <div className="db-opp-card">
      <div className="db-opp-header">
        <div>
          <h4 className="db-opp-name">{op.trend}</h4>
          <div className="db-opp-reasons">
            {(op.reasons || []).map((r, i) => (
              <span key={i} className="db-opp-reason">{r}</span>
            ))}
          </div>
        </div>
        <div className="db-opp-score-circle">
          <span className="db-opp-score-value">{pct}</span>
          <span className="db-opp-score-unit">%</span>
        </div>
      </div>
      {op.suggested_titles?.length > 0 && (
        <div className="db-opp-titles">
          <span className="db-opp-titles-label">💡 Suggested Titles</span>
          {op.suggested_titles.slice(0, 2).map((t, i) => (
            <p key={i} className="db-opp-title-item">"{t}"</p>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------
export default function Dashboard() {
  const navigate = useNavigate();
  const { datasetId, activeDataset, datasetStats: dsStats } = useDataset();
  const [stats, setStats] = useState(null);
  const [health, setHealth] = useState(null);
  const [transcriptStats, setTranscriptStats] = useState(null);
  const [trends, setTrends] = useState(null);
  const [opportunities, setOpportunities] = useState(null);
  const [nicheData, setNicheData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = useCallback((showLoading = true) => {
    if (showLoading) setLoading(true);
    else setRefreshing(true);

    Promise.all([
      api.getStats(datasetId),
      api.getHealth(),
      api.getTranscriptStats().catch(() => null),
      api.discoverTrends(365, 12, datasetId).catch(() => ({ trends: [] })),
      api.getOpportunities(365, 8, datasetId).catch(() => ({ opportunities: [] })),
    ])
      .then(([s, h, ts, tr, op]) => {
        setStats(s);
        setHealth(h);
        setTranscriptStats(ts);
        setTrends(tr);
        setOpportunities(op);
        if (s?.niche_stats) {
          setNicheData(
            Object.entries(s.niche_stats).map(([name, info]) => ({
              name: name.length > 18 ? name.slice(0, 18) + '...' : name,
              fullName: name,
              videos: info.count || 0,
              avgScore: +(info.avg_score || 0).toFixed(2),
            }))
          );
        }
      })
      .catch((err) => console.error('Dashboard load failed:', err))
      .finally(() => { setLoading(false); setRefreshing(false); });
  }, [datasetId]);

  useEffect(() => { loadData(); }, [loadData]);

  const trendsList = trends?.trends || [];
  const oppsList = opportunities?.opportunities || [];
  const avgScore = stats?.niche_stats
    ? (Object.values(stats.niche_stats).reduce((s, n) => s + (n.avg_score || 0), 0) / Math.max(Object.keys(stats.niche_stats).length, 1)).toFixed(3)
    : '—';
  const topOpp = oppsList.length > 0 ? (oppsList[0].opportunity_score * 100).toFixed(0) : '—';
  const emergingTrend = trendsList.length > 1 ? trendsList[trendsList.length > 2 ? 1 : 0]?.trend : '—';

  // Build trend distribution data for charts
  const trendChartData = trendsList.slice(0, 8).map(t => ({
    name: t.trend.length > 20 ? t.trend.slice(0, 20) + '...' : t.trend,
    fullName: t.trend,
    videos: t.count,
  }));

  // Extract pain points / content gaps
  const painPoints = [];
  if (oppsList.length > 0) {
    oppsList.forEach(op => {
      (op.reasons || []).forEach(r => {
        if (!painPoints.includes(r)) painPoints.push(r);
      });
    });
  }

  return (
    <>
      {/* Page Header + Quick Actions */}
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2>Intelligence Center</h2>
          <p>AI-powered content trend analysis &amp; opportunity detection</p>
        </div>
        <div className="db-actions">
          <button className="btn btn-secondary" onClick={() => loadData(false)} disabled={refreshing}>
            {refreshing ? '⏳' : '🔄'} Refresh
          </button>
          <button className="btn btn-secondary" onClick={() => navigate('/pipeline')}>
            ⚡ Pipeline
          </button>
        </div>
      </div>

      {/* Dataset Context Panel */}
      {activeDataset && (
        <div className="dataset-meta-panel">
          <div className="dataset-meta-label">
            <span className="dataset-meta-dot" />
            Active Workspace
          </div>
          <div className="dataset-meta-tags">
            {activeDataset.config_regions?.length > 0 && (
              <span className="dataset-meta-tag">🌍 {activeDataset.config_regions.join(', ')}</span>
            )}
            {activeDataset.config_categories?.length > 0 && (
              <span className="dataset-meta-tag">📁 {activeDataset.config_categories.join(', ')}</span>
            )}
            {activeDataset.config_content_type && activeDataset.config_content_type !== 'all' && (
              <span className="dataset-meta-tag">🎬 {activeDataset.config_content_type}</span>
            )}
            {activeDataset.config_keywords?.length > 0 && (
              <span className="dataset-meta-tag">🔑 {activeDataset.config_keywords.join(', ')}</span>
            )}
            <span className="dataset-meta-tag">📊 {dsStats?.total_videos ?? stats?.total_videos ?? 0} videos</span>
          </div>
        </div>
      )}

      {/* Intelligence KPI Cards */}
      <div className="kpi-grid">
        {loading ? (
          <>
            <SkeletonKPI /><SkeletonKPI /><SkeletonKPI /><SkeletonKPI /><SkeletonKPI />
          </>
        ) : (
          <>
            <div className="kpi-card">
              <div className="kpi-label">🔥 Active Trends</div>
              <div className="kpi-value blue">{trendsList.length}</div>
              <div className="kpi-sub">Topics detected from {trends?.total_videos_analyzed || 0} videos</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">🚀 Top Opportunity</div>
              <div className="kpi-value green">{topOpp}{topOpp !== '—' ? '%' : ''}</div>
              <div className="kpi-sub">{oppsList[0]?.trend || 'No data yet'}</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">⚠️ Emerging Trend</div>
              <div className="kpi-value purple" style={{ fontSize: emergingTrend.length > 15 ? '1rem' : undefined }}>
                {emergingTrend.length > 22 ? emergingTrend.slice(0, 22) + '…' : emergingTrend}
              </div>
              <div className="kpi-sub">Fastest-growing topic</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">🧠 Avg Content Quality</div>
              <div className="kpi-value orange">{avgScore}</div>
              <div className="kpi-sub">Weighted across {stats?.total_niches || 0} niches</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">📊 Total Content</div>
              <div className="kpi-value" style={{ color: '#22d3ee' }}>{fmt(stats?.total_videos || 0)}</div>
              <div className="kpi-sub">
                {stats?.platform_stats?.youtube ? `🎬 ${stats.platform_stats.youtube}` : ''}
                {stats?.platform_stats?.reddit ? ` • 💬 ${stats.platform_stats.reddit}` : ''}
              </div>
            </div>
          </>
        )}
      </div>

      {/* Live Trends Panel */}
      <div className="card" style={{ marginTop: 'var(--space-xl)' }}>
        <div className="card-header">
          <span className="card-title">🔥 Live Trends Right Now</span>
          <span className="badge badge-blue">{trendsList.length} trends</span>
        </div>
        {loading ? (
          <div className="db-trend-grid">
            {Array.from({ length: 6 }).map((_, i) => <SkeletonTrendCard key={i} />)}
          </div>
        ) : trendsList.length === 0 ? (
          <div className="ci-empty" style={{ padding: '2rem' }}>
            <span style={{ fontSize: '2rem' }}>🔍</span>
            <h3>No trends detected yet</h3>
            <p>Run the pipeline to ingest videos and discover trends</p>
          </div>
        ) : (
          <div className="db-trend-grid">
            {trendsList.slice(0, 9).map((t, i) => (
              <TrendCard
                key={i}
                trend={t}
                onClick={() => navigate(`/videos?trend=${encodeURIComponent(t.trend)}`)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Two-Column: Opportunities + Charts */}
      <div className="grid-2" style={{ marginTop: 'var(--space-xl)' }}>
        {/* Opportunities Panel */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">💡 Best Content Opportunities</span>
            <span className="badge badge-green">{oppsList.length} found</span>
          </div>
          {loading ? (
            <div style={{ padding: 'var(--space-lg)' }}>
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="skeleton-line skeleton-shimmer" style={{ height: 80, borderRadius: 8, marginBottom: 12 }}></div>
              ))}
            </div>
          ) : oppsList.length === 0 ? (
            <div className="ci-empty" style={{ padding: '2rem' }}>
              <span style={{ fontSize: '2rem' }}>💡</span>
              <p>No opportunities found yet</p>
            </div>
          ) : (
            <div className="db-opp-list">
              {oppsList.slice(0, 5).map((op, i) => (
                <OpportunityCard key={i} op={op} />
              ))}
            </div>
          )}
        </div>

        {/* Trend Distribution Chart */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">📊 Trend Distribution</span>
          </div>
          <div className="chart-container">
            {trendChartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={trendChartData} layout="vertical" margin={{ left: 10, right: 20 }}>
                  <XAxis type="number" stroke="#5e6375" fontSize={11} />
                  <YAxis type="category" dataKey="name" width={140} stroke="#5e6375" fontSize={11} tick={{ fill: '#8b90a0' }} />
                  <Tooltip
                    contentStyle={{ background: '#1e2230', border: '1px solid #2a2e3b', borderRadius: 8, color: '#e8eaf0', fontSize: 13 }}
                    labelFormatter={(v, payload) => payload?.[0]?.payload?.fullName || v}
                  />
                  <Bar dataKey="videos" fill="#4f8cff" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="ci-empty" style={{ padding: '2rem' }}><p>No trend data</p></div>
            )}
          </div>
        </div>
      </div>

      {/* Second Row: Niche Pie + Pain Points */}
      <div className="grid-2" style={{ marginTop: 'var(--space-xl)' }}>
        <div className="card">
          <div className="card-header">
            <span className="card-title">🧩 Niche Distribution</span>
          </div>
          <div className="chart-container" style={{ display: 'flex', justifyContent: 'center' }}>
            {nicheData.length > 0 ? (
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie data={nicheData} cx="50%" cy="50%" innerRadius={60} outerRadius={110} paddingAngle={3} dataKey="videos" nameKey="fullName">
                    {nicheData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip contentStyle={{ background: '#1e2230', border: '1px solid #2a2e3b', borderRadius: 8, color: '#e8eaf0', fontSize: 13 }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="ci-empty" style={{ padding: '2rem' }}><p>No niche data</p></div>
            )}
          </div>
        </div>

        {/* Insight Signals */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">🎯 Insight Signals</span>
          </div>
          <div style={{ padding: 'var(--space-lg)' }}>
            {/* Pain Point Tags */}
            {painPoints.length > 0 && (
              <div style={{ marginBottom: 'var(--space-xl)' }}>
                <h4 className="db-section-label">Opportunity Drivers</h4>
                <div className="db-pain-cloud">
                  {painPoints.map((p, i) => (
                    <span key={i} className="db-pain-tag">{p}</span>
                  ))}
                </div>
              </div>
            )}
            {/* System Status */}
            <div style={{ marginBottom: 'var(--space-xl)' }}>
              <h4 className="db-section-label">System Status</h4>
              <div className="db-status-row">
                <span className={`health-dot ${health?.status === 'healthy' ? 'online' : 'offline'}`}></span>
                <span>{health?.status === 'healthy' ? 'All Systems Operational' : 'Degraded'}</span>
              </div>
            </div>
            {/* Transcript Coverage */}
            {transcriptStats && (
              <div>
                <h4 className="db-section-label">📝 Transcript Coverage</h4>
                <div className="db-coverage-bar-wrap">
                  <div className="db-coverage-bar">
                    <div
                      className="db-coverage-fill"
                      style={{
                        width: `${Math.min(transcriptStats.coverage_pct || 0, 100)}%`,
                        background: (transcriptStats.coverage_pct || 0) >= 50 ? '#34d399' : '#f59e0b',
                      }}
                    ></div>
                  </div>
                  <span className="db-coverage-label">{transcriptStats.coverage_pct || 0}%</span>
                </div>
                <p className="kpi-sub">{transcriptStats.with_transcript || 0} / {transcriptStats.total_youtube || 0} videos</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
