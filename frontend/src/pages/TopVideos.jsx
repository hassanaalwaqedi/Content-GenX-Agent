import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import { exportToPDF } from '../api/export';
import ContentCommandBar from '../components/top-content/ContentCommandBar';
import ContentDiscoveryGrid from '../components/top-content/ContentDiscoveryGrid';
import FeaturedContentCard from '../components/top-content/FeaturedContentCard';
import IntelligenceRail from '../components/top-content/IntelligenceRail';
import TopContentHeader from '../components/top-content/TopContentHeader';
import TranscriptModal from '../components/TranscriptModal';
import ContentGeneratorModal from '../components/ContentGeneratorModal';
import { useDataset } from '../context/DatasetContext';
import { fmt, getPlatformLabel } from '../utils/platform';
import './TopVideos.css';

const DEFAULT_GLOBAL_FILTERS = { region: '', category: '', content_type: '' };

export default function TopVideos() {
  const { datasetId, activeDataset } = useDataset();
  const [searchParams, setSearchParams] = useSearchParams();
  const trendFilter = searchParams.get('trend') || '';
  const [niches, setNiches] = useState([]);
  const [selectedNiche, setSelectedNiche] = useState('');
  const [days, setDays] = useState(365);
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [requestError, setRequestError] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [minScore, setMinScore] = useState(0);
  const [platformFilter, setPlatformFilter] = useState('');
  const [sortMode, setSortMode] = useState('score');
  const [viewMode, setViewMode] = useState('grid');
  const [transcriptVideo, setTranscriptVideo] = useState(null);
  const [transcriptData, setTranscriptData] = useState(null);
  const [transcriptLoading, setTranscriptLoading] = useState(false);
  const [transcriptError, setTranscriptError] = useState(null);
  const [generateVideo, setGenerateVideo] = useState(null);

  useEffect(() => {
    const timeout = window.setTimeout(() => setDebouncedSearch(searchTerm), 250);
    return () => window.clearTimeout(timeout);
  }, [searchTerm]);

  const loadNiches = useCallback(async () => {
    try {
      const health = await api.getHealth();
      setNiches(health.niches || []);
    } catch (error) {
      console.error('Unable to load content categories:', error);
    }
  }, []);

  const loadVideos = useCallback(async () => {
    setLoading(true);
    setRequestError('');
    try {
      const data = trendFilter
        ? await api.getTrendVideos(trendFilter, days, 500, { platform: platformFilter }, datasetId)
        : await api.getTopVideos(selectedNiche || null, days, 50, { ...DEFAULT_GLOBAL_FILTERS, platform: platformFilter }, datasetId);
      setVideos(data.videos || []);
    } catch (error) {
      console.error('Unable to load top content:', error);
      setRequestError(error.message || 'Unable to load content right now.');
      setVideos([]);
    } finally {
      setLoading(false);
    }
  }, [datasetId, days, platformFilter, selectedNiche, trendFilter]);

  useEffect(() => {
    loadNiches();
  }, [loadNiches]);

  useEffect(() => {
    loadVideos();
  }, [loadVideos]);

  const clearTrendFilter = useCallback(() => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.delete('trend');
      return next;
    });
  }, [setSearchParams]);

  const resetFilters = useCallback(() => {
    setSearchTerm('');
    setDebouncedSearch('');
    setSelectedNiche('');
    setPlatformFilter('');
    setMinScore(0);
    clearTrendFilter();
  }, [clearTrendFilter]);

  const filteredVideos = useMemo(() => {
    let result = [...videos];
    if (platformFilter) result = result.filter((video) => video.platform === platformFilter);
    if (debouncedSearch.trim()) {
      const query = debouncedSearch.toLowerCase();
      result = result.filter((video) => [video.title, video.channel, video.niche, video.topics].some((value) => String(value || '').toLowerCase().includes(query)));
    }
    if (minScore > 0) result = result.filter((video) => Number(video.score || 0) >= minScore);

    const sorters = {
      score: (a, b) => Number(b.score || 0) - Number(a.score || 0),
      views: (a, b) => Number(b.views || 0) - Number(a.views || 0),
      engagement: (a, b) => Number(b.engagement_rate || 0) - Number(a.engagement_rate || 0),
      recent: (a, b) => new Date(b.published_at || 0) - new Date(a.published_at || 0),
    };
    return result.sort(sorters[sortMode]);
  }, [videos, debouncedSearch, minScore, platformFilter, sortMode]);

  const railData = useMemo(() => {
    const count = filteredVideos.length;
    const platformCounts = filteredVideos.reduce((counts, video) => {
      const platform = video.platform || 'unknown';
      counts[platform] = (counts[platform] || 0) + 1;
      return counts;
    }, {});
    const wordFrequency = {};
    filteredVideos.forEach((video) => {
      `${video.title || ''} ${video.niche || ''}`.replace(/[^\w\s]/g, '').split(/\s+/).filter((word) => word.length > 3).forEach((word) => {
        const key = word.toLowerCase();
        wordFrequency[key] = (wordFrequency[key] || 0) + 1;
      });
    });
    return {
      count,
      totalViews: filteredVideos.reduce((sum, video) => sum + Number(video.views || 0), 0),
      avgEngagement: count ? filteredVideos.reduce((sum, video) => sum + Number(video.engagement_rate || 0), 0) / count : 0,
      avgScore: count ? filteredVideos.reduce((sum, video) => sum + Number(video.score || 0), 0) / count : 0,
      withInsights: filteredVideos.filter((video) => video.strategic_advice && video.strategic_advice !== 'Analysis pending').length,
      withGaps: filteredVideos.filter((video) => video.content_gap && video.content_gap !== 'Analysis pending').length,
      platformCounts,
      trendingKeywords: Object.entries(wordFrequency).sort(([, a], [, b]) => b - a).slice(0, 6).map(([word, countValue]) => ({ word, count: countValue })),
    };
  }, [filteredVideos]);

  const handleExport = useCallback(() => {
    exportToPDF(
      `top_content_${selectedNiche.replace(/\s+/g, '_') || 'all'}_${days}_days.pdf`,
      'Top Content Report',
      `${selectedNiche || 'All categories'} — Last ${days} days`,
      ['#', 'Platform', 'Title', 'Creator', 'Views', 'Engagement', 'Score'],
      filteredVideos.map((video, index) => [
        index + 1,
        getPlatformLabel(video.platform),
        `${video.title || 'Untitled'}`.slice(0, 56),
        video.channel || '—',
        fmt(video.views),
        `${(Number(video.engagement_rate || 0) * 100).toFixed(1)}%`,
        Number(video.score || 0).toFixed(2),
      ]),
    );
  }, [days, filteredVideos, selectedNiche]);

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
    setTranscriptData(null);
    setTranscriptError(null);
    setTranscriptVideo(null);
  };

  const featuredVideo = filteredVideos[0];
  const discoveryVideos = filteredVideos.slice(1);

  return (
    <div className="tc-page-shell">
      <TopContentHeader activeDataset={activeDataset} count={filteredVideos.length} onRefresh={() => { loadNiches(); loadVideos(); }} onExport={handleExport} loading={loading} />
      <ContentCommandBar
        searchTerm={searchTerm} onSearchChange={setSearchTerm} selectedNiche={selectedNiche} onNicheChange={setSelectedNiche}
        niches={niches} days={days} onDaysChange={setDays} platformFilter={platformFilter} onPlatformChange={setPlatformFilter}
        minScore={minScore} onMinScoreChange={setMinScore} viewMode={viewMode} onViewModeChange={setViewMode}
        sortMode={sortMode} onSortModeChange={setSortMode} trendFilter={trendFilter} onClearTrend={clearTrendFilter} onReset={resetFilters}
      />
      {requestError && <div className="tc-error-banner">⚠ {requestError} <button onClick={loadVideos}>Try again</button></div>}
      <div className="tc-content-layout">
        <main className="tc-content-main">
          {featuredVideo && !loading && <FeaturedContentCard video={featuredVideo} onGenerate={setGenerateVideo} onTranscript={handleTranscript} />}
          <section className="tc-discovery-section">
            <div className="tc-discovery-heading"><div><h2>Top performing content</h2><span>{filteredVideos.length.toLocaleString()} results</span></div><p>Ranked by {sortMode === 'score' ? 'AI score' : sortMode}</p></div>
            <ContentDiscoveryGrid videos={discoveryVideos} viewMode={viewMode} loading={loading} onGenerate={setGenerateVideo} onTranscript={handleTranscript} />
          </section>
        </main>
        <IntelligenceRail data={railData} onKeywordClick={setSearchTerm} />
      </div>
      {(transcriptLoading || transcriptError || transcriptData) && <TranscriptModal video={transcriptVideo} data={transcriptData} loading={transcriptLoading} error={transcriptError} onClose={closeTranscript} />}
      {generateVideo && <ContentGeneratorModal video={generateVideo} onClose={() => setGenerateVideo(null)} />}
    </div>
  );
}
