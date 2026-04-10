import { useEffect, useState, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../api/client';

function fmt(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return String(n);
}

function wordCount(text) {
  if (!text) return 0;
  return text.trim().split(/\s+/).filter(Boolean).length;
}

export default function VideoDetail() {
  const { id } = useParams();
  const [video, setVideo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [transcriptExpanded, setTranscriptExpanded] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    api
      .getVideo(id)
      .then(setVideo)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id]);

  // Highlight search matches in transcript
  const highlightedTranscript = useMemo(() => {
    if (!video?.transcript || !searchTerm.trim()) return null;
    const term = searchTerm.trim();
    const regex = new RegExp(`(${term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    const parts = video.transcript.split(regex);
    return parts.map((part, i) =>
      regex.test(part)
        ? <mark key={i} style={{ background: '#f59e0b33', color: '#f59e0b', borderRadius: 2, padding: '0 2px' }}>{part}</mark>
        : part
    );
  }, [video?.transcript, searchTerm]);

  const matchCount = useMemo(() => {
    if (!video?.transcript || !searchTerm.trim()) return 0;
    const term = searchTerm.trim();
    const regex = new RegExp(term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
    return (video.transcript.match(regex) || []).length;
  }, [video?.transcript, searchTerm]);

  const handleCopy = async () => {
    if (!video?.transcript) return;
    try {
      await navigator.clipboard.writeText(video.transcript);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers
      const ta = document.createElement('textarea');
      ta.value = video.transcript;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (loading) return <div className="loading"><div className="spinner"></div>Loading video...</div>;
  if (error) return <div className="card" style={{ color: '#ef4444' }}>Error: {error}</div>;
  if (!video) return null;

  const isPending = (val) => !val || val === 'Analysis pending';
  const wc = wordCount(video.transcript);
  const charCount = video.transcript?.length || 0;

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
          <p style={{ color: 'var(--color-text-secondary, #8b90a0)', lineHeight: 1.8, whiteSpace: 'pre-wrap', fontSize: '0.8125rem' }}>
            {video.description}
          </p>
        </div>
      )}

      {/* Transcript */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="card-header" style={{ flexWrap: 'wrap', gap: '0.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flex: '1 1 auto' }}>
            <span className="card-title">📝 Transcript</span>
            {video.transcript ? (
              <>
                <span className="badge badge-green">Available</span>
                <span style={{ fontSize: '0.7rem', color: '#8b90a0' }}>
                  {wc.toLocaleString()} words • {charCount.toLocaleString()} chars
                </span>
              </>
            ) : (
              <span className="badge badge-orange">
                {video.platform === 'reddit' ? 'N/A (Text post)' : 'Not available'}
              </span>
            )}
          </div>
          {video.transcript && (
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <button
                onClick={handleCopy}
                className="btn btn-secondary"
                style={{ fontSize: '0.75rem', padding: '4px 10px' }}
              >
                {copied ? '✓ Copied!' : '📋 Copy'}
              </button>
              <button
                onClick={() => setTranscriptExpanded(!transcriptExpanded)}
                className="btn btn-secondary"
                style={{ fontSize: '0.75rem', padding: '4px 10px' }}
              >
                {transcriptExpanded ? '▲ Collapse' : '▼ Expand'}
              </button>
            </div>
          )}
        </div>

        {video.transcript && (
          <div style={{ marginBottom: '0.75rem' }}>
            <div style={{ position: 'relative' }}>
              <input
                type="text"
                placeholder="Search in transcript..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="select-input"
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  fontSize: '0.8125rem',
                  background: 'var(--color-surface, #1a1d28)',
                  border: '1px solid var(--color-border, #2a2e3b)',
                  borderRadius: 8,
                  color: 'var(--color-text, #e8eaf0)',
                }}
              />
              {searchTerm && (
                <span style={{
                  position: 'absolute',
                  right: 12,
                  top: '50%',
                  transform: 'translateY(-50%)',
                  fontSize: '0.7rem',
                  color: matchCount > 0 ? '#34d399' : '#ef4444',
                  fontWeight: 600,
                }}>
                  {matchCount} match{matchCount !== 1 ? 'es' : ''}
                </span>
              )}
            </div>
          </div>
        )}

        {video.transcript ? (
          <div style={{
            color: 'var(--color-text-secondary, #8b90a0)',
            lineHeight: 1.8,
            fontSize: '0.8125rem',
            maxHeight: transcriptExpanded ? 'none' : 300,
            overflowY: transcriptExpanded ? 'visible' : 'auto',
            paddingRight: 8,
            whiteSpace: 'pre-wrap',
            transition: 'max-height 0.3s ease',
          }}>
            {highlightedTranscript || video.transcript}
          </div>
        ) : (
          <p style={{ color: 'var(--color-text-muted, #5e6375)', fontStyle: 'italic', fontSize: '0.8125rem' }}>
            {video.platform === 'reddit'
              ? 'Transcripts are not applicable for Reddit posts.'
              : 'No transcript available for this video. Captions may be disabled or not yet extracted.'}
          </p>
        )}
      </div>

      {/* Metadata */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Metadata</span>
        </div>
        <table className="data-table">
          <tbody>
            <tr><td style={{ fontWeight: 600, width: 160 }}>Video ID</td><td>{video.video_id}</td></tr>
            <tr><td style={{ fontWeight: 600 }}>Platform</td><td>{video.platform === 'reddit' ? '💬 Reddit' : '🎬 YouTube'}</td></tr>
            <tr>
              <td style={{ fontWeight: 600 }}>Published</td>
              <td>{video.published_at ? new Date(video.published_at).toLocaleDateString('de-DE', { year: 'numeric', month: 'long', day: 'numeric' }) : '—'}</td>
            </tr>
            <tr>
              <td style={{ fontWeight: 600 }}>Transcript</td>
              <td>
                {video.transcript
                  ? <span style={{ color: '#34d399' }}>✓ {wc.toLocaleString()} words extracted</span>
                  : <span style={{ color: '#5e6375' }}>Not available</span>
                }
              </td>
            </tr>
            <tr>
              <td style={{ fontWeight: 600 }}>Source Link</td>
              <td>
                {video.platform === 'reddit' ? (
                  <a href={`https://www.reddit.com/search/?q=${encodeURIComponent(video.title)}`} target="_blank" rel="noopener noreferrer">Search on Reddit ↗</a>
                ) : (
                  <a href={`https://www.youtube.com/watch?v=${video.video_id}`} target="_blank" rel="noopener noreferrer">Open on YouTube ↗</a>
                )}
              </td>
            </tr>
            <tr><td style={{ fontWeight: 600 }}>Last Updated</td><td>{video.updated_at ? new Date(video.updated_at).toLocaleString('de-DE') : '—'}</td></tr>
          </tbody>
        </table>
      </div>
    </>
  );
}
