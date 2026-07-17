import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useDataset } from '../context/DatasetContext';
import { redditApi } from '../api/client';
import CommunityPainPointsPanel from '../components/reddit/CommunityPainPointsPanel';
import DiscussionClustersSection from '../components/reddit/DiscussionClustersSection';
import EmergingDiscussionsTable from '../components/reddit/EmergingDiscussionsTable';
import RedditDetailDrawer from '../components/reddit/RedditDetailDrawer';
import RedditFilterBar from '../components/reddit/RedditFilterBar';
import RedditIntelligenceRail from '../components/reddit/RedditIntelligenceRail';
import RedditMetricGrid from '../components/reddit/RedditMetricGrid';
import RedditPageHeader from '../components/reddit/RedditPageHeader';
import { RedditErrorState } from '../components/reddit/RedditStates';
import TrendingSubredditsSection from '../components/reddit/TrendingSubredditsSection';
import './RedditIntelligence.css';

const DEFAULT_FILTERS = { days: 30, search: '', subreddit: '', sentiment: '', min_upvotes: 0, min_comments: 0, min_opportunity: 0, sort_by: 'velocity' };
const DISCUSSION_PAGE_SIZE = 10;

export default function RedditIntelligence() {
  const { datasetId } = useDataset();
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [data, setData] = useState({ overview: null, subreddits: [], discussions: [], painPoints: [], clusters: [], sentiment: null, opportunities: [], contributors: [], health: null });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [selected, setSelected] = useState(null);
  const [discussionPage, setDiscussionPage] = useState(1);
  const requestId = useRef(0);

  const load = useCallback(async ({ showRefresh = false } = {}) => {
    const currentRequest = ++requestId.current;
    if (showRefresh) setRefreshing(true); else setLoading(true);
    setError('');
    try {
      const [overview, subredditResult, discussionResult, painResult, clusterResult, sentiment, opportunityResult, contributorResult, health] = await Promise.all([
        redditApi.getOverview(filters.days, datasetId),
        redditApi.getTrendingSubreddits(filters.days, 8, datasetId),
        redditApi.getDiscussions({ ...filters, limit: 50 }, datasetId),
        redditApi.getPainPoints(filters.days, 10, datasetId),
        redditApi.getClusters(filters.days, 10, datasetId),
        redditApi.getSentiment(filters.days, datasetId),
        redditApi.getOpportunities(filters.days, 10, datasetId),
        redditApi.getContributors(filters.days, 10, datasetId),
        redditApi.getHealth(datasetId),
      ]);
      if (currentRequest !== requestId.current) return;
      setData({
        overview,
        subreddits: subredditResult.subreddits || [],
        discussions: discussionResult.discussions || [],
        painPoints: painResult.pain_points || [],
        clusters: clusterResult.clusters || [],
        sentiment,
        opportunities: opportunityResult.opportunities || [],
        contributors: contributorResult.contributors || [],
        health,
      });
    } catch (requestError) {
      if (currentRequest === requestId.current) setError(requestError.message || 'The Reddit intelligence service could not be reached.');
    } finally {
      if (currentRequest === requestId.current) { setLoading(false); setRefreshing(false); }
    }
  }, [datasetId, filters]);

  useEffect(() => {
    const timeout = window.setTimeout(() => load(), filters.search ? 250 : 0);
    return () => { requestId.current += 1; window.clearTimeout(timeout); };
  }, [load, filters.search]);

  const uniqueSubreddits = useMemo(() => data.subreddits, [data.subreddits]);
  const visibleDiscussions = useMemo(() => data.discussions.slice((discussionPage - 1) * DISCUSSION_PAGE_SIZE, discussionPage * DISCUSSION_PAGE_SIZE), [data.discussions, discussionPage]);
  const open = (item, type = 'discussion') => item && setSelected({ item, type });
  const changeFilters = (nextFilters) => { setDiscussionPage(1); setFilters(nextFilters); };
  const resetFilters = () => { setDiscussionPage(1); setFilters(DEFAULT_FILTERS); };

  const runScan = async () => {
    if (scanning) return;
    setScanning(true);
    setNotice('');
    try {
      const response = await redditApi.runScan({ regions: ['US'], name: 'Reddit Intelligence Scan' });
      setNotice(response.message || 'Reddit scan accepted. This page will update when the run completes.');
    } catch (scanError) {
      setError(scanError.message || 'Unable to launch the Reddit scan.');
    } finally {
      setScanning(false);
    }
  };

  return <div className="reddit-page">
    <RedditPageHeader overview={data.overview} health={data.health} refreshing={refreshing} scanning={scanning} onRefresh={() => load({ showRefresh: true })} onExport={() => window.print()} onScan={runScan} />
    {notice && <div className="reddit-notice" role="status"><span>✓</span>{notice}</div>}
    {error && <RedditErrorState message={error} onRetry={() => load({ showRefresh: true })} />}
    <RedditMetricGrid overview={data.overview} />
    <div className="reddit-layout-grid">
      <main className="reddit-main-column">
        <TrendingSubredditsSection items={data.subreddits} loading={loading} onOpen={(item) => open(item, 'subreddit')} />
        <RedditFilterBar filters={filters} subreddits={uniqueSubreddits} onChange={changeFilters} onReset={resetFilters} />
        <EmergingDiscussionsTable items={visibleDiscussions} total={data.discussions.length} page={discussionPage} pageSize={DISCUSSION_PAGE_SIZE} loading={loading} onOpen={(item) => open(item, 'discussion')} onPageChange={setDiscussionPage} onScan={runScan} />
        <div className="reddit-analysis-grid"><CommunityPainPointsPanel items={data.painPoints} loading={loading} onOpen={(item) => open(item, 'pain')} onScan={runScan} /><DiscussionClustersSection items={data.clusters} loading={loading} onOpen={(item) => open(item, 'cluster')} /></div>
      </main>
      <RedditIntelligenceRail sentiment={data.sentiment} health={data.health} opportunities={data.opportunities} contributors={data.contributors} loading={loading} onConnector={() => setSelected({ item: data.health?.connector, type: 'connector' })} />
    </div>
    <RedditDetailDrawer item={selected?.item} type={selected?.type} onClose={() => setSelected(null)} />
  </div>;
}
