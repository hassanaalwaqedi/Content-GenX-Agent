import { useEffect, useState, useCallback } from 'react';
import { api } from '../api/client';
import { useDataset } from '../context/DatasetContext';
import { getPlatformIcon, getPlatformLabel, fmt } from '../utils/platform';
/* ── helpers ── */
// fmt is now imported from utils/platform
function pct(v) { return ((v || 0) * 100).toFixed(1) + '%'; }
function scoreColor(v) {
  if (v >= 0.6) return 'var(--color-accent-green)';
  if (v >= 0.3) return 'var(--color-accent-orange)';
  return 'var(--color-accent-red)';
}
function velSign(v) {
  if (v > 0) return { label: `+${v.toFixed(3)}`, color: 'var(--color-accent-green)' };
  if (v < 0) return { label: v.toFixed(3), color: 'var(--color-accent-red)' };
  return { label: '0.000', color: 'var(--color-text-muted)' };
}

/* ── Skeleton Loader ── */
function SkeletonCard() {
  return (
    <div className="card" style={{ padding: 'var(--space-xl)', animation: 'pulse 1.5s infinite' }}>
      <div style={{ height: 18, width: '60%', background: 'var(--color-bg-input)', borderRadius: 6, marginBottom: 12 }} />
      <div style={{ height: 12, width: '40%', background: 'var(--color-bg-input)', borderRadius: 4, marginBottom: 8 }} />
      <div style={{ height: 12, width: '80%', background: 'var(--color-bg-input)', borderRadius: 4, marginBottom: 8 }} />
      <div style={{ display: 'flex', gap: 6, marginTop: 12 }}>
        <div style={{ height: 22, width: 60, background: 'var(--color-bg-input)', borderRadius: 12 }} />
        <div style={{ height: 22, width: 80, background: 'var(--color-bg-input)', borderRadius: 12 }} />
      </div>
    </div>
  );
}

/* ── Metric Bar (mini progress bar) ── */
function MetricBar({ value, max = 1, color, label, tooltip }) {
  const widthPct = Math.min((value / max) * 100, 100);
  return (
    <div style={{ marginBottom: 8 }} title={tooltip}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
        <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', fontWeight: 600 }}>{label}</span>
        <span style={{ fontSize: 'var(--font-size-xs)', color, fontWeight: 700 }}>{typeof value === 'number' ? (value * 100).toFixed(0) + '%' : value}</span>
      </div>
      <div style={{ height: 4, background: 'var(--color-bg-input)', borderRadius: 4, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${widthPct}%`, background: color, borderRadius: 4, transition: 'width 0.6s ease' }} />
      </div>
    </div>
  );
}

/* ── Creator Card ── */
function CreatorCard({ creator, onClick }) {
  const vel = velSign(creator.recent_velocity);
  return (
    <div
      onClick={() => onClick(creator)}
      className="card"
      style={{
        padding: 'var(--space-xl)',
        cursor: 'pointer',
        transition: 'all 0.25s ease',
        position: 'relative',
        overflow: 'hidden',
      }}
      onMouseEnter={e => {
        e.currentTarget.style.transform = 'translateY(-4px) scale(1.01)';
        e.currentTarget.style.boxShadow = 'var(--shadow-card-hover)';
      }}
      onMouseLeave={e => {
        e.currentTarget.style.transform = '';
        e.currentTarget.style.boxShadow = '';
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h3 style={{
            fontSize: 'var(--font-size-md)', fontWeight: 700, color: 'var(--color-text)',
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', marginBottom: 2,
          }}>
            {creator.channel || 'Unknown'}
          </h3>
          <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
            {creator.video_count} content items · {fmt(creator.total_views)} views
          </span>
        </div>
        <div style={{
          fontSize: 'var(--font-size-xs)', fontWeight: 700, color: vel.color,
          background: vel.color === 'var(--color-accent-green)' ? 'var(--color-accent-green-bg)' : vel.color === 'var(--color-accent-red)' ? 'var(--color-accent-red-bg)' : 'var(--color-bg-input)',
          padding: '2px 8px', borderRadius: 100,
        }}>
          {vel.label}
        </div>
      </div>

      {/* Metrics */}
      <MetricBar value={creator.trend_dominance_score || 0} color="var(--color-accent-purple)" label="🔥 Trend Dominance" tooltip="How much this creator appears in top trending videos" />
      <MetricBar value={creator.opportunity_alignment || 0} color="var(--color-accent-green)" label="🎯 Opportunity Fit" tooltip="Overlap with high-opportunity trend topics" />
      <MetricBar value={Math.min(creator.avg_engagement || 0, 0.1) * 10} color="var(--color-primary)" label="📊 Engagement" tooltip={`Avg engagement: ${pct(creator.avg_engagement)}`} />

      {/* Score */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--color-border)' }}>
        <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>Avg Score</span>
        <span style={{ fontSize: 'var(--font-size-md)', fontWeight: 800, color: scoreColor(creator.avg_score || 0) }}>
          {(creator.avg_score || 0).toFixed(2)}
        </span>
      </div>

      {/* Topics */}
      {creator.top_topics?.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 10 }}>
          {creator.top_topics.slice(0, 4).map(topic => (
            <span key={topic} style={{
              background: 'var(--color-bg-input)', color: 'var(--color-text-secondary)',
              padding: '2px 8px', borderRadius: 100, fontSize: 'var(--font-size-xs)', fontWeight: 500,
              border: '1px solid var(--color-border)',
            }}>
              {topic}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Rising Creator Card (compact) ── */
function RisingCard({ creator, onClick }) {
  const vel = velSign(creator.recent_velocity);
  return (
    <div
      onClick={() => onClick(creator)}
      className="card"
      style={{ padding: 'var(--space-lg)', cursor: 'pointer', transition: 'all 0.2s ease' }}
      onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.boxShadow = 'var(--shadow-card-hover)'; }}
      onMouseLeave={e => { e.currentTarget.style.transform = ''; e.currentTarget.style.boxShadow = ''; }}
    >
      <h4 style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600, color: 'var(--color-text)', marginBottom: 4, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
        {creator.channel}
      </h4>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
          {creator.video_count} content items
        </span>
        <span style={{ fontSize: 'var(--font-size-sm)', fontWeight: 700, color: vel.color }}>
          {vel.label} growth
        </span>
      </div>
      <div style={{ marginTop: 6 }}>
        <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
          Engagement: <strong style={{ color: 'var(--color-primary)' }}>{pct(creator.avg_engagement)}</strong>
        </span>
      </div>
    </div>
  );
}

/* ── Creator Insight Modal ── */
function CreatorModal({ creator, videos, loading, onClose }) {
  if (!creator) return null;

  const vel = velSign(creator.recent_velocity);

  // Infer content strategy
  const strategy = [];
  if (creator.avg_engagement > 0.04) strategy.push('Strong audience engagement — content resonates deeply');
  if (creator.trend_dominance_score > 0.03) strategy.push('Consistently appears in top trending videos');
  if (creator.opportunity_alignment > 0.5) strategy.push('Topics align well with high-opportunity trends');
  if (creator.video_count > 10) strategy.push('High output volume — frequency-based growth model');
  if (creator.recent_velocity > 0) strategy.push('Momentum is positive — currently accelerating');
  if (strategy.length === 0) strategy.push('Niche-focused creator with targeted content');

  // Why they win
  const whyWin = [];
  if (creator.avg_score > 0.3) whyWin.push(`Above-average content score (${(creator.avg_score).toFixed(2)})`);
  if (creator.total_views > 100000) whyWin.push(`Massive reach: ${fmt(creator.total_views)} total views`);
  if (creator.top_topics?.length > 2) whyWin.push(`Multi-topic coverage: ${creator.top_topics.slice(0, 3).join(', ')}`);
  if (creator.avg_engagement > 0.03) whyWin.push(`High engagement rate: ${pct(creator.avg_engagement)}`);
  if (whyWin.length === 0) whyWin.push('Consistent content production');

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 'var(--space-xl)',
    }} onClick={onClose}>
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: 'var(--color-bg-card)', borderRadius: 'var(--radius-lg)',
          maxWidth: 720, width: '100%', maxHeight: '85vh', overflow: 'auto',
          boxShadow: '0 20px 60px rgba(0,0,0,0.5)', border: '1px solid var(--color-border)',
          padding: 'var(--space-2xl)',
        }}
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-xl)' }}>
          <div>
            <h2 style={{ fontSize: 'var(--font-size-xl)', fontWeight: 800, color: 'var(--color-text)', marginBottom: 4 }}>
              {creator.channel}
            </h2>
            <span style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>
              {creator.video_count} videos · {fmt(creator.total_views)} views · Velocity: <span style={{ color: vel.color, fontWeight: 700 }}>{vel.label}</span>
            </span>
          </div>
          <button onClick={onClose} style={{
            background: 'var(--color-bg-input)', border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-sm)', color: 'var(--color-text)', cursor: 'pointer',
            fontSize: 18, width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>×</button>
        </div>

        {/* KPI row */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--space-md)', marginBottom: 'var(--space-xl)' }}>
          {[
            { label: 'Dominance', value: pct(creator.trend_dominance_score), color: 'var(--color-accent-purple)' },
            { label: 'Opportunity', value: pct(creator.opportunity_alignment), color: 'var(--color-accent-green)' },
            { label: 'Engagement', value: pct(creator.avg_engagement), color: 'var(--color-primary)' },
            { label: 'Avg Score', value: (creator.avg_score || 0).toFixed(2), color: scoreColor(creator.avg_score) },
          ].map(kpi => (
            <div key={kpi.label} style={{
              background: 'var(--color-bg)', padding: 'var(--space-md)',
              borderRadius: 'var(--radius-sm)', textAlign: 'center', border: '1px solid var(--color-border)',
            }}>
              <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', fontWeight: 600, marginBottom: 4 }}>{kpi.label}</div>
              <div style={{ fontSize: 'var(--font-size-lg)', fontWeight: 800, color: kpi.color }}>{kpi.value}</div>
            </div>
          ))}
        </div>

        {/* Topics */}
        {creator.top_topics?.length > 0 && (
          <div style={{ marginBottom: 'var(--space-xl)' }}>
            <h4 style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
              Top Topics
            </h4>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {creator.top_topics.map(t => (
                <span key={t} style={{
                  background: 'var(--color-accent-purple-bg)', color: 'var(--color-accent-purple)',
                  padding: '4px 12px', borderRadius: 100, fontSize: 'var(--font-size-xs)', fontWeight: 600,
                }}>{t}</span>
              ))}
            </div>
          </div>
        )}

        {/* Content Strategy */}
        <div style={{ marginBottom: 'var(--space-xl)' }}>
          <h4 style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
            📋 Content Strategy
          </h4>
          <ul style={{ listStyle: 'none', padding: 0 }}>
            {strategy.map((s, i) => (
              <li key={i} style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)', padding: '4px 0', borderBottom: '1px solid var(--color-border)' }}>
                <span style={{ color: 'var(--color-accent-green)', marginRight: 8 }}>✓</span> {s}
              </li>
            ))}
          </ul>
        </div>

        {/* Why They Win */}
        <div style={{ marginBottom: 'var(--space-xl)' }}>
          <h4 style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
            🏆 Why They Win
          </h4>
          <ul style={{ listStyle: 'none', padding: 0 }}>
            {whyWin.map((w, i) => (
              <li key={i} style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)', padding: '4px 0' }}>
                <span style={{ color: 'var(--color-accent-orange)', marginRight: 8 }}>★</span> {w}
              </li>
            ))}
          </ul>
        </div>

        {/* Top Videos */}
        <h4 style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
          🎨 Top Performing Content
        </h4>
        {loading ? (
          <div className="loading"><div className="spinner"></div>Loading videos...</div>
        ) : videos.length === 0 ? (
          <p style={{ color: 'var(--color-text-muted)', fontSize: 'var(--font-size-sm)' }}>No videos found</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {videos.slice(0, 8).map(v => (
              <div key={v.video_id} style={{
                display: 'flex', gap: 12, padding: '10px', background: 'var(--color-bg)',
                borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)',
                alignItems: 'center',
              }}>
                <img
                  src={v.thumbnail_url}
                  alt=""
                  style={{ width: 80, height: 45, objectFit: 'cover', borderRadius: 4, flexShrink: 0 }}
                  onError={e => { e.target.style.display = 'none'; }}
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontSize: 'var(--font-size-sm)', fontWeight: 600, color: 'var(--color-text)',
                    whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                  }}>{v.title}</div>
                  <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', marginTop: 2 }}>
                    {fmt(v.views)} views · {pct(v.engagement_rate)} eng · Score: <strong style={{ color: scoreColor(v.score) }}>{v.score?.toFixed(2)}</strong>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════
   MAIN PAGE
   ══════════════════════════════════════════════════════════════════ */
export default function Creators() {
  const { datasetId } = useDataset();
  const [creators, setCreators] = useState([]);
  const [rising, setRising] = useState([]);
  const [trends, setTrends] = useState([]);
  const [selectedTrend, setSelectedTrend] = useState('');
  const [loading, setLoading] = useState(true);
  const [risingLoading, setRisingLoading] = useState(true);

  // Modal state
  const [modalCreator, setModalCreator] = useState(null);
  const [modalVideos, setModalVideos] = useState([]);
  const [modalLoading, setModalLoading] = useState(false);

  // Load creators + rising + trends (scoped to active dataset)
  useEffect(() => {
    setLoading(true);
    setRisingLoading(true);
    Promise.all([
      api.getCreatorIntelligence(365, 30, 1, datasetId),
      api.getRisingCreators(90, 8, datasetId),
      api.discoverTrends(365, 20, datasetId),
    ])
      .then(([intData, risData, trendData]) => {
        setCreators(intData.creators || []);
        setRising(risData.creators || []);
        setTrends((trendData.trends || []).map(t => t.trend));
      })
      .catch(err => console.error('Failed to load creator intelligence:', err))
      .finally(() => { setLoading(false); setRisingLoading(false); });
  }, [datasetId]);

  // Filter by trend
  const handleTrendFilter = useCallback((trend) => {
    setSelectedTrend(trend);
    if (!trend) {
      setLoading(true);
      api.getCreatorIntelligence(365, 30, 1, datasetId)
        .then(d => setCreators(d.creators || []))
        .catch(err => console.error(err))
        .finally(() => setLoading(false));
    } else {
      setLoading(true);
      api.getCreatorsByTrend(trend, 365, 30, datasetId)
        .then(d => setCreators(d.creators || []))
        .catch(err => console.error(err))
        .finally(() => setLoading(false));
    }
  }, [datasetId]);

  // Open modal
  const openCreatorModal = useCallback((creator) => {
    setModalCreator(creator);
    setModalLoading(true);
    setModalVideos([]);
    api.getCreatorVideos(creator.channel, 10)
      .then(d => setModalVideos(d.videos || []))
      .catch(err => console.error(err))
      .finally(() => setModalLoading(false));
  }, []);

  const closeModal = useCallback(() => {
    setModalCreator(null);
    setModalVideos([]);
  }, []);

  // KPI calculations
  const avgDominance = creators.length ? (creators.reduce((s, c) => s + (c.trend_dominance_score || 0), 0) / creators.length) : 0;
  const avgAlignment = creators.length ? (creators.reduce((s, c) => s + (c.opportunity_alignment || 0), 0) / creators.length) : 0;
  const topCreator = creators[0];

  return (
    <>
      {/* Header */}
      <div className="page-header">
        <h2>Creator Intelligence</h2>
        <p>Discover who dominates trends, find rising stars, and learn winning strategies</p>
      </div>

      {/* KPI Cards */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-label">Total Creators</div>
          <div className="kpi-value blue">{loading ? '—' : creators.length}</div>
          <div className="kpi-sub">Analyzed in database</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Top Creator</div>
          <div className="kpi-value purple" style={{ fontSize: 'var(--font-size-lg)' }}>
            {loading ? '—' : (topCreator?.channel?.slice(0, 18) || '—')}
          </div>
          <div className="kpi-sub">{topCreator ? `Score: ${topCreator.avg_score?.toFixed(2)}` : ''}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Avg Trend Dominance</div>
          <div className="kpi-value orange">{loading ? '—' : pct(avgDominance)}</div>
          <div className="kpi-sub">Presence in top 100 videos</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Avg Opportunity Fit</div>
          <div className="kpi-value green">{loading ? '—' : pct(avgAlignment)}</div>
          <div className="kpi-sub">Topic alignment with trends</div>
        </div>
      </div>

      {/* Rising Creators Section */}
      <div style={{ marginBottom: 'var(--space-2xl)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)', marginBottom: 'var(--space-lg)' }}>
          <h3 style={{ fontSize: 'var(--font-size-lg)', fontWeight: 700 }}>🚀 Rising Creators</h3>
          <span className="badge badge-green">{rising.length} rising</span>
        </div>
        {risingLoading ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 'var(--space-md)' }}>
            {[1, 2, 3, 4].map(i => <SkeletonCard key={i} />)}
          </div>
        ) : rising.length === 0 ? (
          <p style={{ color: 'var(--color-text-muted)', fontSize: 'var(--font-size-sm)' }}>No rising creators detected yet</p>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 'var(--space-md)' }}>
            {rising.map(c => <RisingCard key={c.channel} creator={c} onClick={openCreatorModal} />)}
          </div>
        )}
      </div>

      {/* Trend Filter + Creator Count */}
      <div className="filters-bar">
        <h3 style={{ fontSize: 'var(--font-size-lg)', fontWeight: 700 }}>🧠 Creator Intelligence</h3>
        <select
          className="select-input"
          value={selectedTrend}
          onChange={e => handleTrendFilter(e.target.value)}
          style={{ minWidth: 200 }}
        >
          <option value="">All Trends</option>
          {trends.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <span className="badge badge-purple">{creators.length} creators</span>
        {selectedTrend && (
          <span className="badge badge-blue">Filtered: {selectedTrend}</span>
        )}
      </div>

      {/* Creator Cards Grid */}
      {loading ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 'var(--space-xl)' }}>
          {[1, 2, 3, 4, 5, 6].map(i => <SkeletonCard key={i} />)}
        </div>
      ) : creators.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: 'var(--space-3xl)', color: 'var(--color-text-muted)' }}>
          <p style={{ fontSize: 'var(--font-size-md)' }}>No creators found{selectedTrend ? ` for "${selectedTrend}"` : ''}</p>
          <p style={{ fontSize: 'var(--font-size-sm)', marginTop: 8 }}>Try selecting a different trend or run the pipeline to ingest data</p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 'var(--space-xl)' }}>
          {creators.map(c => (
            <CreatorCard key={c.channel} creator={c} onClick={openCreatorModal} />
          ))}
        </div>
      )}

      {/* Modal */}
      {modalCreator && (
        <CreatorModal
          creator={modalCreator}
          videos={modalVideos}
          loading={modalLoading}
          onClose={closeModal}
        />
      )}
    </>
  );
}
