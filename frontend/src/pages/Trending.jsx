import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { api } from '../api/client';
import { exportToPDF } from '../api/export';
import ContentGeneratorModal from '../components/ContentGeneratorModal';
import { useDataset } from '../context/DatasetContext';
import { getPlatformIcon, getPlatformLabel, fmt, ALL_PLATFORMS } from '../utils/platform';
// fmt is now imported from utils/platform

const DEFAULT_THUMBNAIL = 'https://via.placeholder.com/320x180.png?text=No+Thumbnail';

export default function Trending() {
  const { datasetId } = useDataset();
  const [days, setDays] = useState(90);
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(true);

  // Transcript modal state
  const [transcriptData, setTranscriptData] = useState(null);
  const [transcriptLoading, setTranscriptLoading] = useState(false);
  const [transcriptError, setTranscriptError] = useState(null);

  // Content generator
  const [generateVideo, setGenerateVideo] = useState(null);

  // Local filters
  const [globalFilters, setGlobalFilters] = useState({ region: '', category: '', content_type: '' });
  const [platformFilter, setPlatformFilter] = useState('');

  useEffect(() => {
    setLoading(true);
    api
      .getTrending(days, 30, globalFilters, datasetId)
      .then((data) => setVideos(data.videos || []))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, [days, globalFilters, datasetId]);

  // Build engagement chart data from top 10
  const filteredVideos = platformFilter
    ? videos.filter(v => v.platform === platformFilter)
    : videos;

  const chartData = filteredVideos.slice(0, 10).map((v, i) => ({
    name: v.title?.slice(0, 20) + '...',
    engagement: +(v.engagement_rate * 100).toFixed(2),
    views: v.views,
  }));

  const fetchTranscript = async (videoId) => {
    setTranscriptLoading(true);
    setTranscriptError(null);
    setTranscriptData(null);
    try {
      const data = await api.fetchTranscript(videoId);
      setTranscriptData(data);
    } catch (err) {
      setTranscriptError(err.message || 'Failed to load transcript');
    } finally {
      setTranscriptLoading(false);
    }
  };

  const closeModal = () => {
    setTranscriptData(null);
    setTranscriptError(null);
  };

  return (
    <>
      <div className="page-header">
        <h2>Trending Content</h2>
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
          <option value={180}>Last 180 days</option>
          <option value={365}>Last 365 days</option>
        </select>
        <select
          className="select-input"
          value={platformFilter}
          onChange={(e) => setPlatformFilter(e.target.value)}
        >
          <option value="">All Platforms</option>
          {ALL_PLATFORMS.map(p => (
            <option key={p} value={p}>{getPlatformIcon(p)} {getPlatformLabel(p)}</option>
          ))}
        </select>
        <span className="badge badge-green">{filteredVideos.length} trending</span>
        {filteredVideos.length > 0 && (
          <button
            className="btn btn-secondary"
            onClick={() => {
              exportToPDF(
                `trending_content_${days}d.pdf`,
                'Trending Content Report',
                `Fastest-growing content — Last ${days} days`,
                ['#', 'Platform', 'Title', 'Creator', 'Views', 'Engagement', 'Score', 'Published'],
                filteredVideos.map((v, i) => [
                  i + 1,
                  getPlatformLabel(v.platform),
                  v.title?.slice(0, 50) + (v.title?.length > 50 ? '…' : ''),
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
                <th>Platform</th>
                <th>Title</th>
                <th>Creator</th>
                <th>Views</th>
                <th>Engagement</th>
                <th>Score</th>
                <th>Published</th>
                <th>Transcript</th>
                <th>AI</th>
              </tr>
            </thead>
            <tbody>
              {filteredVideos.map((v, i) => (
                <tr key={v.video_id}>
                  <td className="number-cell">{i + 1}</td>
                  <td>
                    <span title={getPlatformLabel(v.platform)} style={{ fontSize: '1.1rem' }}>
                      {getPlatformIcon(v.platform)}
                    </span>
                  </td>
                  <td>
                    <Link to={`/video/${v.video_id}`} className="title-cell video-title-cell" style={{ color: 'var(--color-text)' }}>
                      <img
                        src={v.thumbnail_url || DEFAULT_THUMBNAIL}
                        alt="thumbnail"
                        className="video-thumbnail"
                        onError={(e) => { e.target.src = DEFAULT_THUMBNAIL; }}
                      />
                      <span className="video-title-text">
                        {v.title}
                      </span>
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
                  <td>
                    {v.platform === 'youtube' && (
                      <button
                        className="btn-transcript"
                        onClick={(e) => { e.preventDefault(); fetchTranscript(v.video_id); }}
                      >
                        📝 Transcript
                      </button>
                    )}
                  </td>
                  <td>
                    <button
                      className="btn-transcript"
                      onClick={(e) => { e.preventDefault(); setGenerateVideo(v); }}
                      style={{ background: 'var(--color-accent-purple-bg)', color: 'var(--color-accent-purple)' }}
                    >
                      ✨ Generate
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Transcript Loading Overlay */}
      {transcriptLoading && (
        <div className="transcript-modal-overlay">
          <div className="transcript-modal">
            <div className="loading"><div className="spinner"></div>Fetching transcript...</div>
          </div>
        </div>
      )}

      {/* Transcript Error Modal */}
      {transcriptError && (
        <div className="transcript-modal-overlay" onClick={closeModal}>
          <div className="transcript-modal" onClick={(e) => e.stopPropagation()}>
            <div className="transcript-modal-header">
              <h3 className="transcript-modal-title">Transcript Unavailable</h3>
              <button className="transcript-modal-close" onClick={closeModal}>✕</button>
            </div>
            <div className="transcript-error">
              <span style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>⚠️</span>
              <p>{transcriptError}</p>
            </div>
          </div>
        </div>
      )}

      {/* Transcript Data Modal */}
      {transcriptData && (
        <div className="transcript-modal-overlay" onClick={closeModal}>
          <div className="transcript-modal" onClick={(e) => e.stopPropagation()}>
            <div className="transcript-modal-header">
              <h3 className="transcript-modal-title">
                📝 Video Transcript
                {transcriptData.cached && <span className="badge badge-green" style={{ marginLeft: 8 }}>Cached</span>}
              </h3>
              <button className="transcript-modal-close" onClick={closeModal}>✕</button>
            </div>

            <div className="transcript-section">
              <h4 className="transcript-section-title">⏱️ First 30 Seconds</h4>
              <p className="transcript-preview">{transcriptData.transcript_30s || 'N/A'}</p>
            </div>

            <div className="transcript-section">
              <h4 className="transcript-section-title">📄 Full Transcript</h4>
              <div className="transcript-full">
                {transcriptData.transcript || 'No transcript content.'}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Content Generator Modal */}
      {generateVideo && (
        <ContentGeneratorModal
          video={generateVideo}
          onClose={() => setGenerateVideo(null)}
        />
      )}
    </>
  );
}
