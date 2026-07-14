import { useEffect, useState, useMemo, useCallback, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import { exportToPDF } from '../api/export';
import VideoCard from '../components/VideoCard';
import TranscriptModal from '../components/TranscriptModal';
import ContentGeneratorModal from '../components/ContentGeneratorModal';
import SkeletonCard from '../components/SkeletonCard';
import { useDataset } from '../context/DatasetContext';
import { getPlatformIcon, getPlatformLabel, fmt, ALL_PLATFORMS } from '../utils/platform';
import PlatformIcon from '../components/PlatformIcon';
// fmt is now imported from utils/platform

function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

export default function TopVideos() {
  const { datasetId } = useDataset();
  const [searchParams, setSearchParams] = useSearchParams();
  const trendFilter = searchParams.get('trend') || '';
  const [niches, setNiches] = useState([]);
  const [selectedNiche, setSelectedNiche] = useState('');
  const [days, setDays] = useState(365);
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [minScore, setMinScore] = useState(0);

  // Local filters (region/category within dataset)
  const [globalFilters, setGlobalFilters] = useState({ region: '', category: '', content_type: '' });
  const [platformFilter, setPlatformFilter] = useState('');

  // Transcript modal
  const [transcriptVideo, setTranscriptVideo] = useState(null);
  const [transcriptData, setTranscriptData] = useState(null);
  const [transcriptLoading, setTranscriptLoading] = useState(false);
  const [transcriptError, setTranscriptError] = useState(null);

  // Content generator modal
  const [generateVideo, setGenerateVideo] = useState(null);

  // Debounced search
  const debouncedSetSearch = useCallback(
    debounce((val) => setDebouncedSearch(val), 300),
    []
  );

  const handleSearchChange = (e) => {
    setSearchTerm(e.target.value);
    debouncedSetSearch(e.target.value);
  };

  // Load niches
  useEffect(() => {
    api.getHealth().then((h) => {
      setNiches(h.niches || []);
    });
  }, []);

  // Load videos (scoped to active dataset)
  useEffect(() => {
    setLoading(true);
    api
      .getTopVideos(selectedNiche || null, days, 50, globalFilters, datasetId)
      .then((data) => setVideos(data.videos || []))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, [selectedNiche, days, globalFilters, datasetId]);

  // Clear trend filter
  const clearTrendFilter = useCallback(() => {
    setSearchParams((prev) => {
      prev.delete('trend');
      return prev;
    });
  }, [setSearchParams]);

  // Filtered videos
  const filteredVideos = useMemo(() => {
    let result = videos;

    // Filter by platform
    if (platformFilter) {
      result = result.filter(v => v.platform === platformFilter);
    }

    // Filter by trend topic (from Dashboard click-through)
    if (trendFilter) {
      const tf = trendFilter.toLowerCase();
      result = result.filter(v => {
        const topics = (v.topics || '').toLowerCase();
        const title = (v.title || '').toLowerCase();
        const niche = (v.niche || '').toLowerCase();
        const desc = (v.description || '').toLowerCase();
        return topics.includes(tf) || title.includes(tf) || niche.includes(tf) || desc.includes(tf);
      });
    }

    if (debouncedSearch.trim()) {
      const q = debouncedSearch.toLowerCase();
      result = result.filter(v =>
        (v.title || '').toLowerCase().includes(q) ||
        (v.channel || '').toLowerCase().includes(q)
      );
    }
    if (minScore > 0) {
      result = result.filter(v => (v.score || 0) >= minScore);
    }
    return result;
  }, [videos, debouncedSearch, minScore, trendFilter, platformFilter]);

  // Sidebar data
  const sidebarData = useMemo(() => {
    if (videos.length === 0) return null;

    // Trending keywords from titles
    const wordFreq = {};
    videos.forEach(v => {
      (v.title || '').replace(/[^\w\s]/g, '').split(/\s+/).filter(w => w.length > 4).forEach(w => {
        const lw = w.toLowerCase();
        wordFreq[lw] = (wordFreq[lw] || 0) + 1;
      });
    });
    const trendingKeywords = Object.entries(wordFreq)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
      .map(([word, count]) => ({ word, count }));

    // Content gaps
    const gaps = videos
      .filter(v => v.content_gap && v.content_gap !== 'Analysis pending')
      .slice(0, 4)
      .map(v => v.content_gap);

    // Top audiences
    const audiences = videos
      .filter(v => v.target_audience && v.target_audience !== 'Analysis pending')
      .slice(0, 3)
      .map(v => v.target_audience);

    // Avg score
    const avgScore = videos.reduce((s, v) => s + (v.score || 0), 0) / videos.length;
    const avgEng = videos.reduce((s, v) => s + (v.engagement_rate || 0), 0) / videos.length;
    const totalViews = videos.reduce((s, v) => s + (v.views || 0), 0);

    return { trendingKeywords, gaps, audiences, avgScore, avgEng, totalViews };
  }, [videos]);

  // Transcript handlers
  const handleTranscript = async (video) => {
    setTranscriptVideo(video);
    setTranscriptLoading(true);
    setTranscriptError(null);
    setTranscriptData(null);
    try {
      const data = await api.fetchTranscript(video.video_id);
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
    setTranscriptVideo(null);
  };

  return (
    <>
      {/* Page Header */}
      <div className="page-header">
        <h2>Content Intelligence</h2>
        <p>Discover high-performing content with AI-powered insights</p>
      </div>

      {/* Trend Filter Banner */}
      {trendFilter && (
        <div className="dataset-meta-panel" style={{ marginBottom: '1rem' }}>
          <div className="dataset-meta-label">
            <span style={{ color: 'var(--color-accent-orange)' }}>🔥</span>
            Filtering by trend
          </div>
          <div className="dataset-meta-tags">
            <span className="dataset-meta-tag" style={{ background: 'var(--color-primary-bg)', borderColor: 'var(--color-primary)', color: 'var(--color-primary)', fontWeight: 700 }}>
              {trendFilter}
            </span>
            <span className="dataset-meta-tag">
              {filteredVideos.length} video{filteredVideos.length !== 1 ? 's' : ''} found
            </span>
          </div>
          <button
            onClick={clearTrendFilter}
            style={{
              marginLeft: 'auto', background: 'none', border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-md)', padding: '0.3rem 0.75rem', cursor: 'pointer',
              color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-xs)', fontWeight: 600,
              transition: 'all 0.15s ease',
            }}
            onMouseEnter={e => { e.target.style.borderColor = 'var(--color-accent-red)'; e.target.style.color = 'var(--color-accent-red)'; }}
            onMouseLeave={e => { e.target.style.borderColor = 'var(--color-border)'; e.target.style.color = 'var(--color-text-secondary)'; }}
          >
            ✕ Clear Filter
          </button>
        </div>
      )}

      {/* Enhanced Filter Bar */}
      <div className="ci-filter-bar">
        <div className="ci-filter-row">
          <div className="ci-search-wrap">
            <span className="ci-search-icon">🔍</span>
            <input
              type="text"
              placeholder="Search content, creators..."
              value={searchTerm}
              onChange={handleSearchChange}
              className="ci-search-input"
            />
            {searchTerm && (
              <button className="ci-search-clear" onClick={() => { setSearchTerm(''); setDebouncedSearch(''); }}>✕</button>
            )}
          </div>

          <select
            className="ci-select"
            value={selectedNiche}
            onChange={(e) => setSelectedNiche(e.target.value)}
          >
            <option value="">All Categories</option>
            {niches.map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>

          <select
            className="ci-select"
            value={days}
            onChange={(e) => setDays(+e.target.value)}
          >
            <option value={7}>7 days</option>
            <option value={30}>30 days</option>
            <option value={90}>90 days</option>
            <option value={180}>180 days</option>
            <option value={365}>365 days</option>
          </select>

          <select
            className="ci-select"
            value={platformFilter}
            onChange={(e) => setPlatformFilter(e.target.value)}
          >
            <option value="">All Platforms</option>
            {ALL_PLATFORMS.map(p => (
              <option key={p} value={p}>{getPlatformIcon(p)} {getPlatformLabel(p)}</option>
            ))}
          </select>

          <div className="ci-score-filter">
            <label className="ci-score-label">
              Min Score: <strong>{minScore.toFixed(1)}</strong>
            </label>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={minScore}
              onChange={(e) => setMinScore(+e.target.value)}
              className="ci-score-slider"
            />
          </div>
        </div>

        <div className="ci-filter-meta">
          <span className="badge badge-blue">{filteredVideos.length} content items</span>
          {debouncedSearch && <span className="badge badge-purple">Filtered</span>}
          {minScore > 0 && <span className="badge badge-orange">Score ≥ {minScore.toFixed(1)}</span>}
          {videos.length > 0 && (
            <button
              className="btn btn-secondary ci-export-btn"
              onClick={() => {
                exportToPDF(
                  `top_content_${selectedNiche.replace(/\s+/g, '_')}.pdf`,
                  'Top Content Report',
                  `${selectedNiche} — Last ${days} days`,
                  ['#', 'Platform', 'Title', 'Creator', 'Views', 'Engagement', 'Score'],
                  filteredVideos.map((v, i) => [
                    i + 1,
                    getPlatformLabel(v.platform),
                    v.title?.slice(0, 50) + (v.title?.length > 50 ? '…' : ''),
                    v.channel || '—',
                    fmt(v.views),
                    (v.engagement_rate * 100).toFixed(1) + '%',
                    v.score?.toFixed(2),
                  ])
                );
              }}
            >
              📄 Export PDF
            </button>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="ci-layout">
        {/* Card Grid */}
        <div className="ci-grid-area">
          {loading ? (
            <div className="ci-video-grid">
              {Array.from({ length: 8 }).map((_, i) => (
                <SkeletonCard key={i} />
              ))}
            </div>
          ) : filteredVideos.length === 0 ? (
            <div className="ci-empty">
              <span style={{ fontSize: '3rem' }}>🔍</span>
              <h3>No videos found</h3>
              <p>Try adjusting your filters or search terms</p>
            </div>
          ) : (
            <div className="ci-video-grid">
              {filteredVideos.map((v) => (
                <VideoCard
                  key={v.video_id}
                  video={v}
                  onTranscript={handleTranscript}
                  onGenerate={setGenerateVideo}
                />
              ))}
            </div>
          )}
        </div>

        {/* Opportunity Sidebar */}
        {sidebarData && !loading && (
          <aside className="ci-sidebar">
            {/* Quick Stats */}
            <div className="ci-sidebar-card">
              <h4 className="ci-sidebar-title">📊 Quick Stats</h4>
              <div className="ci-sidebar-stats">
                <div className="ci-sidebar-stat">
                  <span className="ci-sidebar-stat-value blue">{fmt(sidebarData.totalViews)}</span>
                  <span className="ci-sidebar-stat-label">Total Views</span>
                </div>
                <div className="ci-sidebar-stat">
                  <span className="ci-sidebar-stat-value green">{(sidebarData.avgEng * 100).toFixed(1)}%</span>
                  <span className="ci-sidebar-stat-label">Avg Engagement</span>
                </div>
                <div className="ci-sidebar-stat">
                  <span className="ci-sidebar-stat-value purple">{sidebarData.avgScore.toFixed(3)}</span>
                  <span className="ci-sidebar-stat-label">Avg Score</span>
                </div>
              </div>
            </div>

            {/* Trending Keywords */}
            <div className="ci-sidebar-card">
              <h4 className="ci-sidebar-title">🔥 Trending Keywords</h4>
              <div className="ci-keyword-cloud">
                {sidebarData.trendingKeywords.map((kw, i) => (
                  <span
                    key={i}
                    className="ci-keyword-tag"
                    onClick={() => { setSearchTerm(kw.word); setDebouncedSearch(kw.word); }}
                  >
                    {kw.word}
                    <span className="ci-keyword-count">{kw.count}</span>
                  </span>
                ))}
              </div>
            </div>

            {/* Content Gaps */}
            {sidebarData.gaps.length > 0 && (
              <div className="ci-sidebar-card">
                <h4 className="ci-sidebar-title">💡 Content Gaps</h4>
                <ul className="ci-sidebar-list">
                  {sidebarData.gaps.map((gap, i) => (
                    <li key={i} className="ci-sidebar-list-item">{gap}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Top Audiences */}
            {sidebarData.audiences.length > 0 && (
              <div className="ci-sidebar-card">
                <h4 className="ci-sidebar-title">🎯 Target Audiences</h4>
                <ul className="ci-sidebar-list">
                  {sidebarData.audiences.map((aud, i) => (
                    <li key={i} className="ci-sidebar-list-item">{aud}</li>
                  ))}
                </ul>
              </div>
            )}
          </aside>
        )}
      </div>

      {/* Transcript Modal */}
      {(transcriptLoading || transcriptError || transcriptData) && (
        <TranscriptModal
          video={transcriptVideo}
          data={transcriptData}
          loading={transcriptLoading}
          error={transcriptError}
          onClose={closeModal}
        />
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
