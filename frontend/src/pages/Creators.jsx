import { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { api } from '../api/client';
import { exportToPDF } from '../api/export';

function fmt(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return String(n);
}

export default function Creators() {
  const [creators, setCreators] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .getTopCreators(30, 2)
      .then((data) => setCreators(data.creators || []))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, []);

  const chartData = creators.slice(0, 10).map((c) => ({
    name: c.channel?.length > 14 ? c.channel.slice(0, 14) + '...' : c.channel,
    videos: c.video_count,
    avgScore: +(c.avg_score || 0).toFixed(2),
  }));

  return (
    <>
      <div className="page-header">
        <h2>Top Creators</h2>
        <p>Content creators ranked by aggregate performance and consistency</p>
      </div>

      <div className="filters-bar">
        <span className="badge badge-purple">{creators.length} creators</span>
        {creators.length > 0 && (
          <button
            className="btn btn-secondary"
            onClick={() => {
              exportToPDF(
                'top_creators.pdf',
                'Top Creators Report',
                'Ranked by aggregate performance and consistency',
                ['#', 'Channel', 'Videos', 'Total Views', 'Avg Engagement', 'Avg Score', 'Total Score'],
                creators.map((c, i) => [
                  i + 1,
                  c.channel || '—',
                  c.video_count,
                  fmt(c.total_views),
                  (c.avg_engagement_rate * 100).toFixed(1) + '%',
                  c.avg_score?.toFixed(2),
                  c.total_score?.toFixed(2),
                ])
              );
            }}
          >
            📄 Export PDF
          </button>
        )}
      </div>

      {loading ? (
        <div className="loading"><div className="spinner"></div>Loading creators...</div>
      ) : (
        <>
          {/* Chart */}
          {chartData.length > 0 && (
            <div className="card" style={{ marginBottom: 'var(--space-xl)' }}>
              <div className="card-header">
                <span className="card-title">Top 10 Creators by Video Count</span>
              </div>
              <div className="chart-container">
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={chartData} margin={{ left: 10, right: 20 }}>
                    <XAxis dataKey="name" stroke="#5e6375" fontSize={10} tick={{ fill: '#8b90a0' }} angle={-20} textAnchor="end" height={50} />
                    <YAxis stroke="#5e6375" fontSize={11} tick={{ fill: '#8b90a0' }} />
                    <Tooltip
                      contentStyle={{ background: '#1e2230', border: '1px solid #2a2e3b', borderRadius: 8, color: '#e8eaf0', fontSize: 13 }}
                    />
                    <Bar dataKey="videos" fill="#a78bfa" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Table */}
          <div className="card">
            <table className="data-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Channel</th>
                  <th>Videos</th>
                  <th>Total Views</th>
                  <th>Avg Engagement</th>
                  <th>Avg Score</th>
                </tr>
              </thead>
              <tbody>
                {creators.map((c, i) => (
                  <tr key={c.channel || i}>
                    <td className="number-cell">{i + 1}</td>
                    <td className="title-cell">{c.channel || 'Unknown'}</td>
                    <td className="number-cell">
                      <span className="badge badge-blue">{c.video_count}</span>
                    </td>
                    <td className="number-cell">{fmt(c.total_views)}</td>
                    <td>
                      <span className={`badge ${c.avg_engagement_rate > 0.05 ? 'badge-green' : c.avg_engagement_rate > 0.02 ? 'badge-orange' : 'badge-red'}`}>
                        {(c.avg_engagement_rate * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td className="number-cell" style={{ fontWeight: 700, color: '#4f8cff' }}>
                      {c.avg_score?.toFixed(2)}
                    </td>
                  </tr>
                ))}
                {creators.length === 0 && (
                  <tr><td colSpan={6} style={{ textAlign: 'center', color: '#5e6375' }}>No creators found</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}
