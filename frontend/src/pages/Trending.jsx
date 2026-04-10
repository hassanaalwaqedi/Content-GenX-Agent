import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { api } from '../api/client';
import { exportToPDF } from '../api/export';

function fmt(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return String(n);
}

export default function Trending() {
  const [days, setDays] = useState(30);
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .getTrending(days, 30)
      .then((data) => setVideos(data.videos || []))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, [days]);

  // Build engagement chart data from top 10
  const chartData = videos.slice(0, 10).map((v, i) => ({
    name: v.title?.slice(0, 20) + '...',
    engagement: +(v.engagement_rate * 100).toFixed(2),
    views: v.views,
  }));

  return (
    <>
      <div className="page-header">
        <h2>Trending Videos</h2>
        <p>Fastest-growing content gaining traction right now</p>
      </div>

      <div className="filters-bar">
        <select
          className="select-input"
          value={days}
          onChange={(e) => setDays(+e.target.value)}
        >
          <option value={7}>Last 7 days</option>
          <option value={14}>Last 14 days</option>
          <option value={30}>Last 30 days</option>
          <option value={60}>Last 60 days</option>
          <option value={90}>Last 90 days</option>
        </select>
        <span className="badge badge-green">{videos.length} trending</span>
        {videos.length > 0 && (
          <button
            className="btn btn-secondary"
            onClick={() => {
              exportToPDF(
                `trending_videos_${days}d.pdf`,
                'Trending Videos Report',
                `Fastest-growing content — Last ${days} days`,
                ['#', 'Title', 'Channel', 'Views', 'Engagement', 'Score', 'Published'],
                videos.map((v, i) => [
                  i + 1,
                  v.title?.slice(0, 55) + (v.title?.length > 55 ? '…' : ''),
                  v.channel || '—',
                  fmt(v.views),
                  (v.engagement_rate * 100).toFixed(1) + '%',
                  v.score?.toFixed(2),
                  v.published_at ? new Date(v.published_at).toLocaleDateString('en-US') : '—',
                ])
              );
            }}
          >
            📄 Export PDF
          </button>
        )}
      </div>

      {/* Engagement Chart */}
      {chartData.length > 0 && (
        <div className="card" style={{ marginBottom: 'var(--space-xl)' }}>
          <div className="card-header">
            <span className="card-title">Top 10 Engagement Rates</span>
          </div>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={chartData} margin={{ left: 10, right: 20 }}>
                <XAxis dataKey="name" stroke="#5e6375" fontSize={10} tick={{ fill: '#8b90a0' }} />
                <YAxis stroke="#5e6375" fontSize={11} unit="%" tick={{ fill: '#8b90a0' }} />
                <Tooltip
                  contentStyle={{ background: '#1e2230', border: '1px solid #2a2e3b', borderRadius: 8, color: '#e8eaf0', fontSize: 13 }}
                  formatter={(v) => v + '%'}
                />
                <Line type="monotone" dataKey="engagement" stroke="#34d399" strokeWidth={2} dot={{ fill: '#34d399', r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {loading ? (
        <div className="loading"><div className="spinner"></div>Loading trending...</div>
      ) : (
        <div className="card">
          <table className="data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Title</th>
                <th>Channel</th>
                <th>Views</th>
                <th>Engagement</th>
                <th>Score</th>
                <th>Published</th>
              </tr>
            </thead>
            <tbody>
              {videos.map((v, i) => (
                <tr key={v.video_id}>
                  <td className="number-cell">{i + 1}</td>
                  <td>
                    <Link to={`/video/${v.video_id}`} className="title-cell" style={{ color: 'var(--color-text)' }}>
                      <span title={v.platform === 'reddit' ? 'Reddit' : 'YouTube'} style={{ marginRight: 6 }}>
                        {v.platform === 'reddit' ? '💬' : '🎬'}
                      </span>
                      {v.title}
                    </Link>
                  </td>
                  <td>{v.channel || '—'}</td>
                  <td className="number-cell">{fmt(v.views)}</td>
                  <td>
                    <span className={`badge ${v.engagement_rate > 0.05 ? 'badge-green' : v.engagement_rate > 0.02 ? 'badge-orange' : 'badge-red'}`}>
                      {(v.engagement_rate * 100).toFixed(1)}%
                    </span>
                  </td>
                  <td className="number-cell" style={{ fontWeight: 700, color: '#4f8cff' }}>
                    {v.score?.toFixed(2)}
                  </td>
                  <td style={{ color: '#8b90a0' }}>
                    {v.published_at ? new Date(v.published_at).toLocaleDateString('de-DE') : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
