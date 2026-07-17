import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { exportToPDF } from '../api/export';
import ContentGeneratorModal from '../components/ContentGeneratorModal';
import TranscriptModal from '../components/TranscriptModal';
import EngagementChartPanel from '../components/trending/EngagementChartPanel';
import TrendingCommandBar from '../components/trending/TrendingCommandBar';
import TrendingHero from '../components/trending/TrendingHero';
import TrendingIntelligenceRail from '../components/trending/TrendingIntelligenceRail';
import TrendingResultsPanel from '../components/trending/TrendingResultsPanel';
import { buildKeywordRanks, formatCompactNumber, formatPercentage, getMomentum } from '../components/trending/trendingUtils';
import { useDataset } from '../context/DatasetContext';
import { getPlatformLabel } from '../utils/platform';
import './Trending.css';

const DEFAULT_FILTERS = { region: '', category: '', content_type: '' };

export default function Trending() {
  const { datasetId, activeDataset } = useDataset();
  const navigate = useNavigate();
  const [days, setDays] = useState(90);
  const [videos, setVideos] = useState([]);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [niches, setNiches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [requestError, setRequestError] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [platformFilter, setPlatformFilter] = useState('');
  const [minScore, setMinScore] = useState(0);
  const [category, setCategory] = useState('');
  const [contentType, setContentType] = useState('');
  const [moreFilters, setMoreFilters] = useState(false);
  const [sortMode, setSortMode] = useState('engagement');
  const [viewMode, setViewMode] = useState('list');
  const [transcriptVideo, setTranscriptVideo] = useState(null);
  const [transcriptData, setTranscriptData] = useState(null);
  const [transcriptLoading, setTranscriptLoading] = useState(false);
  const [transcriptError, setTranscriptError] = useState(null);
  const [generateVideo, setGenerateVideo] = useState(null);

  const globalFilters = useMemo(() => ({ ...DEFAULT_FILTERS, category, content_type: contentType }), [category, contentType]);

  useEffect(() => {
    const timeout = window.setTimeout(() => setDebouncedSearch(searchTerm), 250);
    return () => window.clearTimeout(timeout);
  }, [searchTerm]);

  const loadNiches = useCallback(async () => {
    try {
      const health = await api.getHealth();
      setNiches(health.niches || []);
    } catch (error) {
      console.error('Unable to load trending categories:', error);
    }
  }, []);

  const loadTrending = useCallback(async () => {
    setLoading(true);
    setRequestError('');
    try {
      const data = await api.getTrending(days, 50, globalFilters, datasetId);
      setVideos(data.videos || []);
      setLastUpdated(new Date());
    } catch (error) {
      console.error('Unable to load trending content:', error);
      setRequestError(error.message || 'Unable to load trending content right now.');
      setVideos([]);
    } finally {
      setLoading(false);
    }
  }, [datasetId, days, globalFilters]);

  useEffect(() => { loadNiches(); }, [loadNiches]);
  useEffect(() => { loadTrending(); }, [loadTrending]);

  const filteredVideos = useMemo(() => {
    let result = [...videos];
    if (platformFilter) result = result.filter((video) => video.platform === platformFilter);
    if (debouncedSearch.trim()) {
      const query = debouncedSearch.toLowerCase();
      result = result.filter((video) => [video.title, video.channel, video.niche, video.description, video.topics].some((value) => String(value || '').toLowerCase().includes(query)));
    }
    if (minScore > 0) result = result.filter((video) => Number(video.score || 0) >= minScore);
    const sorters = {
      engagement: (a, b) => Number(b.engagement_rate || 0) - Number(a.engagement_rate || 0),
      momentum: (a, b) => getMomentum(b) - getMomentum(a),
      score: (a, b) => Number(b.score || 0) - Number(a.score || 0),
      views: (a, b) => Number(b.views || 0) - Number(a.views || 0),
      recent: (a, b) => new Date(b.published_at || 0) - new Date(a.published_at || 0),
    };
    return result.sort(sorters[sortMode]);
  }, [videos, platformFilter, debouncedSearch, minScore, sortMode]);

  const intelligenceData = useMemo(() => {
    const count = filteredVideos.length;
    const platformCounts = filteredVideos.reduce((accumulator, video) => {
      const platform = video.platform || 'unknown';
      accumulator[platform] = (accumulator[platform] || 0) + 1;
      return accumulator;
    }, {});
    return {
      count,
      totalViews: filteredVideos.reduce((total, video) => total + Number(video.views || 0), 0),
      avgEngagement: count ? filteredVideos.reduce((total, video) => total + Number(video.engagement_rate || 0), 0) / count : 0,
      avgScore: count ? filteredVideos.reduce((total, video) => total + Number(video.score || 0), 0) / count : 0,
      avgMomentum: count ? filteredVideos.reduce((total, video) => total + getMomentum(video), 0) / count : 0,
      withAdvice: filteredVideos.filter((video) => video.strategic_advice && video.strategic_advice !== 'Analysis pending').length,
      withGaps: filteredVideos.filter((video) => video.content_gap && video.content_gap !== 'Analysis pending').length,
      keywords: buildKeywordRanks(filteredVideos),
      platformCounts,
    };
  }, [filteredVideos]);

  const resetFilters = useCallback(() => {
    setDays(90);
    setSearchTerm('');
    setDebouncedSearch('');
    setPlatformFilter('');
    setMinScore(0);
    setCategory('');
    setContentType('');
  }, []);

  const handleExport = useCallback(() => {
    exportToPDF(
      `trending_content_${days}d.pdf`,
      'Trending Content Report',
      `Momentum analysis — Last ${days} days`,
      ['#', 'Platform', 'Title', 'Creator', 'Views', 'Engagement', 'AI Score', 'Momentum', 'Published'],
      filteredVideos.map((video, index) => [
        index + 1,
        getPlatformLabel(video.platform),
        String(video.title || 'Untitled').slice(0, 54),
        video.channel || '—',
        formatCompactNumber(video.views),
        formatPercentage(video.engagement_rate),
        Number(video.score || 0).toFixed(2),
        `+${getMomentum(video)}%`,
        video.published_at ? new Date(video.published_at).toLocaleDateString() : '—',
      ]),
    );
  }, [days, filteredVideos]);

  const handleTranscript = async (video) => {
    setTranscriptVideo(video);
    setTranscriptLoading(true);
    setTranscriptError(null);
    setTranscriptData(null);
    try {
      setTranscriptData(await api.fetchTranscript(video.video_id));
    } catch (error) {
      setTranscriptError(error.message || 'Failed to load transcript');
    } finally {
      setTranscriptLoading(false);
    }
  };

  const closeTranscript = () => {
    setTranscriptVideo(null);
    setTranscriptData(null);
    setTranscriptError(null);
  };

  return (
    <div className="tr-page-shell">
      <TrendingHero
        videos={filteredVideos}
        activeDataset={activeDataset}
        lastUpdated={lastUpdated}
        loading={loading}
        onRefresh={() => { loadNiches(); loadTrending(); }}
        onExport={handleExport}
        onRunScan={() => navigate('/pipeline')}
      />
      <TrendingCommandBar
        searchTerm={searchTerm} onSearchChange={setSearchTerm} days={days} onDaysChange={setDays}
        platform={platformFilter} onPlatformChange={setPlatformFilter} minScore={minScore} onMinScoreChange={setMinScore}
        category={category} onCategoryChange={setCategory} contentType={contentType} onContentTypeChange={setContentType}
        categories={niches} resultCount={filteredVideos.length} moreFilters={moreFilters} onMoreFilters={() => setMoreFilters((current) => !current)} onClearAll={resetFilters}
      />
      <div className="tr-main-grid">
        <main className="tr-main-content">
          <EngagementChartPanel videos={filteredVideos} sortMode={sortMode} onSortModeChange={setSortMode} />
          <TrendingResultsPanel videos={filteredVideos} viewMode={viewMode} onViewModeChange={setViewMode} sortMode={sortMode} onSortModeChange={setSortMode} loading={loading} error={requestError} onRetry={loadTrending} onGenerate={setGenerateVideo} onTranscript={handleTranscript} />
        </main>
        <TrendingIntelligenceRail data={intelligenceData} onKeywordClick={setSearchTerm} />
      </div>
      {(transcriptLoading || transcriptError || transcriptData) && <TranscriptModal video={transcriptVideo} data={transcriptData} loading={transcriptLoading} error={transcriptError} onClose={closeTranscript} />}
      {generateVideo && <ContentGeneratorModal video={generateVideo} onClose={() => setGenerateVideo(null)} />}
    </div>
  );
}
