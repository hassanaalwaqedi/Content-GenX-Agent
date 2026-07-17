import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';
import { exportToPDF } from '../api/export';
import CreatorComparisonTable from '../components/creators/CreatorComparisonTable';
import CreatorControls from '../components/creators/CreatorControls';
import CreatorDetailDrawer from '../components/creators/CreatorDetailDrawer';
import CreatorIntelligenceRail from '../components/creators/CreatorIntelligenceRail';
import CreatorKpiCards from '../components/creators/CreatorKpiCards';
import CreatorPageHeader from '../components/creators/CreatorPageHeader';
import RisingCreators from '../components/creators/RisingCreators';
import {
  buildCreatorPlatformMap,
  buildOpportunityNiches,
  buildPlatformLeaders,
  formatCompactNumber,
  formatPercent,
  formatScore,
  getCreatorSortValue,
  normalizeCreator,
  tabSortMode,
} from '../components/creators/creatorUtils';
import { useDataset } from '../context/DatasetContext';
import { getPlatformLabel } from '../utils/platform';
import './Creators.css';

const PAGE_SIZE = 8;

export default function Creators() {
  const { datasetId, activeDataset } = useDataset();
  const [creators, setCreators] = useState([]);
  const [risingCreators, setRisingCreators] = useState([]);
  const [topVideos, setTopVideos] = useState([]);
  const [trends, setTrends] = useState([]);
  const [loading, setLoading] = useState(true);
  const [risingLoading, setRisingLoading] = useState(true);
  const [requestError, setRequestError] = useState('');
  const [lastUpdated, setLastUpdated] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedTrend, setSelectedTrend] = useState('');
  const [sortMode, setSortMode] = useState('score');
  const [moreFilters, setMoreFilters] = useState(false);
  const [minVideos, setMinVideos] = useState(1);
  const [minEngagement, setMinEngagement] = useState(0);
  const [page, setPage] = useState(1);
  const [selectedCreator, setSelectedCreator] = useState(null);
  const [creatorVideos, setCreatorVideos] = useState([]);
  const [creatorVideosLoading, setCreatorVideosLoading] = useState(false);

  const loadCreatorData = useCallback(async () => {
    setLoading(true);
    setRisingLoading(true);
    setRequestError('');
    try {
      const [intelligence, rising, trendData, contentData] = await Promise.all([
        api.getCreatorIntelligence(365, 100, minVideos, datasetId),
        api.getRisingCreators(90, 12, datasetId),
        api.discoverTrends(365, 20, datasetId),
        api.getTopVideos(null, 365, 100, {}, datasetId),
      ]);
      const videos = contentData.videos || [];
      const platformMap = buildCreatorPlatformMap(videos);
      const normalizedCreators = (intelligence.creators || []).map((creator) => normalizeCreator(creator, platformMap));
      const creatorLookup = new Map(normalizedCreators.map((creator) => [creator.channel, creator]));
      const normalizedRising = (rising.creators || []).map((creator) => normalizeCreator({
        ...(creatorLookup.get(creator.channel) || {}),
        ...creator,
      }, platformMap));

      setCreators(normalizedCreators);
      setRisingCreators(normalizedRising);
      setTopVideos(videos);
      setTrends((trendData.trends || []).map((trend) => trend.trend).filter(Boolean));
      setLastUpdated(new Date());
    } catch (error) {
      console.error('Unable to load creator intelligence:', error);
      setCreators([]);
      setRisingCreators([]);
      setTopVideos([]);
      setTrends([]);
      setRequestError(error.message || 'Unable to load creator intelligence right now.');
    } finally {
      setLoading(false);
      setRisingLoading(false);
    }
  }, [datasetId, minVideos]);

  useEffect(() => { loadCreatorData(); }, [loadCreatorData]);
  useEffect(() => { setPage(1); }, [activeTab, searchTerm, selectedTrend, sortMode, minEngagement, minVideos]);

  const filteredCreators = useMemo(() => {
    const query = searchTerm.trim().toLowerCase();
    const trendQuery = selectedTrend.toLowerCase();
    const filtered = creators.filter((creator) => {
      const haystack = [creator.channel, ...(creator.top_topics || [])].join(' ').toLowerCase();
      const matchesSearch = !query || haystack.includes(query);
      const matchesTrend = !trendQuery || creator.top_topics.some((topic) => String(topic).toLowerCase().includes(trendQuery));
      return matchesSearch && matchesTrend && creator.video_count >= minVideos && creator.avg_engagement >= minEngagement;
    });

    return filtered.sort((left, right) => {
      const delta = getCreatorSortValue(right, sortMode) - getCreatorSortValue(left, sortMode);
      return delta || right.total_views - left.total_views || left.channel.localeCompare(right.channel);
    });
  }, [creators, minEngagement, minVideos, searchTerm, selectedTrend, sortMode]);

  const pageCount = Math.max(1, Math.ceil(filteredCreators.length / PAGE_SIZE));
  const visibleCreators = filteredCreators.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const railData = useMemo(() => ({
    platformLeaders: buildPlatformLeaders(topVideos),
    opportunityNiches: buildOpportunityNiches(filteredCreators),
  }), [filteredCreators, topVideos]);

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    setSortMode(tabSortMode(tab));
  };

  const resetFilters = useCallback(() => {
    setActiveTab('overview');
    setSearchTerm('');
    setSelectedTrend('');
    setSortMode('score');
    setMinVideos(1);
    setMinEngagement(0);
    setMoreFilters(false);
  }, []);

  const openCreator = useCallback(async (creator) => {
    setSelectedCreator(creator);
    setCreatorVideos([]);
    setCreatorVideosLoading(true);
    try {
      const data = await api.getCreatorVideos(creator.channel, 20);
      setCreatorVideos(data.videos || []);
    } catch (error) {
      console.error('Unable to load creator content:', error);
      setCreatorVideos([]);
    } finally {
      setCreatorVideosLoading(false);
    }
  }, []);

  const handleExport = useCallback(() => {
    exportToPDF(
      'creator_intelligence_report.pdf',
      'Creator Intelligence Report',
      `Workspace creator analysis — ${filteredCreators.length} matching creators`,
      ['#', 'Creator', 'Content', 'Views', 'Engagement', 'Trend dominance', 'Opportunity fit', 'AI score', 'Platform'],
      filteredCreators.map((creator, index) => [
        index + 1,
        creator.channel,
        creator.video_count,
        formatCompactNumber(creator.total_views),
        formatPercent(creator.avg_engagement),
        formatPercent(creator.trend_dominance_score),
        formatPercent(creator.opportunity_alignment, 0),
        formatScore(creator.avg_score),
        creator.platform ? getPlatformLabel(creator.platform) : 'Unavailable',
      ]),
    );
  }, [filteredCreators]);

  return (
    <div className="cr-page-shell">
      <CreatorPageHeader activeDataset={activeDataset} lastUpdated={lastUpdated} onRefresh={loadCreatorData} onExport={handleExport} onReset={resetFilters} />
      <CreatorKpiCards creators={filteredCreators} loading={loading} />
      <CreatorControls
        activeTab={activeTab} onTabChange={handleTabChange} searchTerm={searchTerm} onSearchChange={setSearchTerm}
        selectedTrend={selectedTrend} onTrendChange={setSelectedTrend} trends={trends} sortMode={sortMode} onSortChange={setSortMode}
        moreFilters={moreFilters} onToggleMoreFilters={() => setMoreFilters((current) => !current)} minVideos={minVideos}
        onMinVideosChange={setMinVideos} minEngagement={minEngagement} onMinEngagementChange={setMinEngagement} onClearFilters={resetFilters}
      />
      <div className="cr-main-grid">
        <main className="cr-main-content">
          <RisingCreators creators={risingCreators} loading={risingLoading} onOpen={openCreator} />
          <CreatorComparisonTable creators={visibleCreators} loading={loading} error={requestError} page={page} totalPages={pageCount} onPageChange={setPage} onOpen={openCreator} onRetry={loadCreatorData} />
        </main>
        <CreatorIntelligenceRail creators={filteredCreators} {...railData} />
      </div>
      <CreatorDetailDrawer creator={selectedCreator} videos={creatorVideos} loading={creatorVideosLoading} onClose={() => setSelectedCreator(null)} />
    </div>
  );
}
