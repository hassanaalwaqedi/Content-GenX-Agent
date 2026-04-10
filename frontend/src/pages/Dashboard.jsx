import { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { api } from '../api/client';

const COLORS = ['#4f8cff', '#34d399', '#f59e0b', '#a78bfa', '#ef4444', '#06b6d4'];

function formatNumber(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return String(n);
}

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [health, setHealth] = useState(null);
  const [nicheData, setNicheData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.getStats(), api.getHealth()])
      .then(([s, h]) => {
        setStats(s);
        setHealth(h);
        // Build niche distribution from niche_stats
        if (s.niche_stats) {
          const data = Object.entries(s.niche_stats).map(([name, info]) => ({
            name: name.length > 18 ? name.slice(0, 18) + '...' : name,
            fullName: name,
            videos: info.count || 0,
            avgScore: +(info.avg_score || 0).toFixed(2),
          }));
          setNicheData(data);
        }
      })
      .catch((err) => console.error('Dashboard load failed:', err))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner"></div>Loading dashboard...
      </div>
    );
  }

  return (
    <>
      <div className="page-header">
        <h2>Dashboard</h2>
        <p>GenX Leadership Academy &mdash; Content Intelligence overview</p>
      </div>

      {/* KPI Cards */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-label">Total Content</div>
          <div className="kpi-value blue">{formatNumber(stats?.total_videos || 0)}</div>
          <div className="kpi-sub">
            {stats?.platform_stats?.youtube ? `🎬 ${stats.platform_stats.youtube} YouTube` : ''}
            {stats?.platform_stats?.youtube && stats?.platform_stats?.reddit ? '  •  ' : ''}
            {stats?.platform_stats?.reddit ? `💬 ${stats.platform_stats.reddit} Reddit` : ''}
            {!stats?.platform_stats?.youtube && !stats?.platform_stats?.reddit ? 'Across all platforms' : ''}
          </div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Active Niches</div>
          <div className="kpi-value green">{stats?.total_niches || 0}</div>
          <div className="kpi-sub">Content categories tracked</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">System Status</div>
          <div className="kpi-value" style={{ color: health?.status === 'healthy' ? '#34d399' : '#ef4444' }}>
            {health?.status === 'healthy' ? 'Healthy' : 'Degraded'}
          </div>
          <div className="kpi-sub">
            <span className={`health-dot ${health?.status === 'healthy' ? 'online' : 'offline'}`}></span>
            Database {health?.database || 'unknown'}
          </div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Avg Score</div>
          <div className="kpi-value orange">
            {stats?.niche_stats
              ? (Object.values(stats.niche_stats).reduce((s, n) => s + (n.avg_score || 0), 0) / Math.max(Object.keys(stats.niche_stats).length, 1)).toFixed(2)
              : '—'}
          </div>
          <div className="kpi-sub">Weighted content quality</div>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid-2">
        <div className="card">
          <div className="card-header">
            <span className="card-title">Videos per Niche</span>
          </div>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={nicheData} layout="vertical" margin={{ left: 10, right: 20 }}>
                <XAxis type="number" stroke="#5e6375" fontSize={11} />
                <YAxis type="category" dataKey="name" width={130} stroke="#5e6375" fontSize={11} tick={{ fill: '#8b90a0' }} />
                <Tooltip
                  contentStyle={{ background: '#1e2230', border: '1px solid #2a2e3b', borderRadius: 8, color: '#e8eaf0', fontSize: 13 }}
                  labelFormatter={(v, payload) => payload?.[0]?.payload?.fullName || v}
                />
                <Bar dataKey="videos" fill="#4f8cff" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <span className="card-title">Niche Distribution</span>
          </div>
          <div className="chart-container" style={{ display: 'flex', justifyContent: 'center' }}>
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie
                  data={nicheData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={110}
                  paddingAngle={3}
                  dataKey="videos"
                  nameKey="fullName"
                >
                  {nicheData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ background: '#1e2230', border: '1px solid #2a2e3b', borderRadius: 8, color: '#e8eaf0', fontSize: 13 }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Niches Table */}
      {health?.niches?.length > 0 && (
        <div className="card" style={{ marginTop: 'var(--space-xl)' }}>
          <div className="card-header">
            <span className="card-title">Tracked Niches</span>
            <span className="badge badge-blue">{health.niches.length} niches</span>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
            {health.niches.map((n) => (
              <span key={n} className="badge badge-purple">{n}</span>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
