import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../api/client';

function fmt(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return String(n);
}

export default function VideoDetail() {
  const { id } = useParams();
  const [video, setVideo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .getVideo(id)
      .then(setVideo)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="loading"><div className="spinner"></div>Loading video...</div>;
  if (error) return <div className="card" style={{ color: '#ef4444' }}>Error: {error}</div>;
  if (!video) return null;

  const isPending = (val) => !val || val === 'Analysis pending';

  return (
    <>
      <Link to="/videos" className="back-link">&#8592; Back to Videos</Link>

      <div className="page-header">
        <h2>{video.title}</h2>
        <p>
          <span className="badge badge-purple">{video.niche}</span>
          {video.channel && <span style={{ marginLeft: '0.75rem', color: '#8b90a0' }}>by {video.channel}</span>}
        </p>
      </div>

      {/* Metrics Row */}
      <div className="kpi-grid" style={{ marginBottom: '2rem' }}>
        <div className="kpi-card">
          <div className="kpi-label">Views</div>
          <div className="kpi-value blue">{fmt(video.views)}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Likes</div>
          <div className="kpi-value green">{fmt(video.likes)}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Comments</div>
          <div className="kpi-value orange">{fmt(video.comments)}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Engagement Rate</div>
          <div className="kpi-value" style={{ color: video.engagement_rate > 0.05 ? '#34d399' : '#f59e0b' }}>
            {(video.engagement_rate * 100).toFixed(2)}%
          </div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Quality Score</div>
          <div className="kpi-value purple">{video.score?.toFixed(3)}</div>
        </div>
      </div>

      {/* Strategic Insights */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="card-header">
          <span className="card-title">Strategic AI Insights</span>
          {isPending(video.target_audience) && <span className="badge badge-orange">Pending</span>}
        </div>

        <div className="insight-grid">
          <div className="insight-panel" style={{ margin: 0 }}>
            <div className="insight-label">Target Audience</div>
            <div className="insight-text">
              {isPending(video.target_audience) ? (
                <span style={{ color: '#5e6375', fontStyle: 'italic' }}>Analysis pending - run pipeline to generate</span>
              ) : (
                video.target_audience
              )}
            </div>
          </div>

          <div className="insight-panel" style={{ margin: 0 }}>
            <div className="insight-label">Content Gap</div>
            <div className="insight-text">
              {isPending(video.content_gap) ? (
                <span style={{ color: '#5e6375', fontStyle: 'italic' }}>Analysis pending</span>
              ) : (
                video.content_gap
              )}
            </div>
          </div>
        </div>

        {!isPending(video.strategic_advice) && (
          <div className="insight-panel" style={{ marginBottom: 0, marginTop: '1rem' }}>
            <div className="insight-label">Strategic Advice</div>
            <div className="insight-text">{video.strategic_advice}</div>
          </div>
        )}
      </div>

      {/* Description */}
      {video.description && (
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <div className="card-header">
            <span className="card-title">Description</span>
          </div>
          <p style={{ color: '#8b90a0', lineHeight: 1.8, whiteSpace: 'pre-wrap', fontSize: '0.8125rem' }}>
            {video.description}
          </p>
        </div>
      )}

      {/* Metadata */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Metadata</span>
        </div>
        <table className="data-table">
          <tbody>
            <tr><td style={{ fontWeight: 600, width: 160 }}>Video ID</td><td>{video.video_id}</td></tr>
            <tr><td style={{ fontWeight: 600 }}>Platform</td><td>{video.platform}</td></tr>
            <tr>
              <td style={{ fontWeight: 600 }}>Published</td>
              <td>{video.published_at ? new Date(video.published_at).toLocaleDateString('de-DE', { year: 'numeric', month: 'long', day: 'numeric' }) : '—'}</td>
            </tr>
            <tr>
              <td style={{ fontWeight: 600 }}>YouTube Link</td>
              <td><a href={`https://www.youtube.com/watch?v=${video.video_id}`} target="_blank" rel="noopener noreferrer">Open on YouTube ↗</a></td>
            </tr>
            <tr><td style={{ fontWeight: 600 }}>Last Updated</td><td>{video.updated_at ? new Date(video.updated_at).toLocaleString('de-DE') : '—'}</td></tr>
          </tbody>
        </table>
      </div>
    </>
  );
}
