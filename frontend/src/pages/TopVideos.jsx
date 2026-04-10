import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { exportToPDF } from '../api/export';

function fmt(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return String(n);
}

export default function TopVideos() {
  const [niches, setNiches] = useState([]);
  const [selectedNiche, setSelectedNiche] = useState('');
  const [days, setDays] = useState(365);
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(true);

  // Load niches on mount
  useEffect(() => {
    api.getHealth().then((h) => {
      setNiches(h.niches || []);
      if (h.niches?.length > 0) setSelectedNiche(h.niches[0]);
    });
  }, []);

  // Load videos when niche/days change
  useEffect(() => {
    if (!selectedNiche) return;
    setLoading(true);
    api
      .getTopVideos(selectedNiche, days, 50)
      .then((data) => setVideos(data.videos || []))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, [selectedNiche, days]);

  return (
    <>
      <div className="page-header">
        <h2>Top Videos</h2>
        <p>Highest-scoring content per niche with strategic AI insights</p>
      </div>

      <div className="filters-bar">
        <select
          className="select-input"
          value={selectedNiche}
          onChange={(e) => setSelectedNiche(e.target.value)}
        >
          {niches.map((n) => (
            <option key={n} value={n}>{n}</option>
          ))}
        </select>
        <select
          className="select-input"
          value={days}
          onChange={(e) => setDays(+e.target.value)}
        >
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
          <option value={180}>Last 180 days</option>
          <option value={365}>Last 365 days</option>
        </select>
        <span className="badge badge-blue">{videos.length} videos</span>
        {videos.length > 0 && (
          <button
            className="btn btn-secondary"
            onClick={() => {
              exportToPDF(
                `top_videos_${selectedNiche.replace(/\s+/g, '_')}.pdf`,
                'Top Videos Report',
                `${selectedNiche} — Last ${days} days`,
                ['#', 'Title', 'Channel', 'Views', 'Engagement', 'Score', 'Target Audience'],
                videos.map((v, i) => [
                  i + 1,
                  v.title?.slice(0, 55) + (v.title?.length > 55 ? '…' : ''),
                  v.channel || '—',
                  fmt(v.views),
                  (v.engagement_rate * 100).toFixed(1) + '%',
                  v.score?.toFixed(2),
                  v.target_audience || 'Pending',
                ])
              );
            }}
          >
            📄 Export PDF
          </button>
        )}
      </div>

      {loading ? (
        <div className="loading"><div className="spinner"></div>Loading videos...</div>
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
                <th>Audience</th>
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
                  <td style={{ maxWidth: 180, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {v.target_audience && v.target_audience !== 'Analysis pending'
                      ? v.target_audience
                      : <span className="badge badge-orange">Pending</span>}
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
