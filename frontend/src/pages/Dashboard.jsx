import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useDataset } from '../context/DatasetContext';
import { fmt } from '../utils/platform';
import DashboardHeader from '../components/dashboard/DashboardHeader';
import WorkspaceContextBar from '../components/dashboard/WorkspaceContextBar';
import MetricCard from '../components/dashboard/MetricCard';
import LiveTrendsSection from '../components/dashboard/LiveTrendsSection';
import OpportunityPanel from '../components/dashboard/OpportunityPanel';
import { NicheDistributionPanel, TrendDistributionPanel } from '../components/dashboard/AnalyticsPanels';
import InsightSignalsPanel from '../components/dashboard/InsightSignalsPanel';
import './Dashboard.css';

function DashboardSkeleton() {
  return (
    <div className="dash-loading-grid" aria-label="Loading intelligence dashboard">
      {[0, 1, 2, 3, 4].map((item) => <span key={item} />)}
    </div>
  );
}

function DashboardError({ onRetry }) {
  return (
    <div className="dash-load-error" role="alert">
      <strong>Dashboard data is unavailable.</strong>
      <p>Check the backend connection, then try again.</p>
      <button onClick={onRetry}>Retry dashboard</button>
    </div>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const { datasetId, activeDataset, datasetStats } = useDataset();
  const [stats, setStats] = useState(null);
  const [health, setHealth] = useState(null);
  const [transcriptStats, setTranscriptStats] = useState(null);
  const [trendsResponse, setTrendsResponse] = useState(null);
  const [opportunitiesResponse, setOpportunitiesResponse] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadError, setLoadError] = useState(false);

  const loadDashboard = useCallback(async (manualRefresh = false) => {
    if (manualRefresh) setRefreshing(true);
    setLoadError(false);
    try {
      const [nextStats, nextHealth, nextTranscriptStats, nextTrends, nextOpportunities] = await Promise.all([
        api.getStats(datasetId),
        api.getHealth(),
        api.getTranscriptStats().catch(() => null),
        api.discoverTrends(365, 12, datasetId).catch(() => ({ trends: [] })),
        api.getOpportunities(365, 8, datasetId).catch(() => ({ opportunities: [] })),
      ]);
      setStats(nextStats);
      setHealth(nextHealth);
      setTranscriptStats(nextTranscriptStats);
      setTrendsResponse(nextTrends);
      setOpportunitiesResponse(nextOpportunities);
    } catch (error) {
      console.error('Dashboard load failed:', error);
      setLoadError(true);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [datasetId]);

  useEffect(() => {
    setLoading(true);
    loadDashboard();
  }, [loadDashboard]);

  const trends = useMemo(() => trendsResponse?.trends || [], [trendsResponse]);
  const opportunities = useMemo(() => opportunitiesResponse?.opportunities || [], [opportunitiesResponse]);
  const totalVideos = datasetStats?.total_videos ?? stats?.total_videos ?? 0;
  const quality = useMemo(() => {
    const niches = Object.values(stats?.niche_stats || {});
    if (niches.length === 0) return null;
    const value = niches.reduce((sum, niche) => sum + (niche.avg_score || 0), 0) / niches.length;
    return value.toFixed(3);
  }, [stats]);
  const trendChartData = useMemo(() => trends.slice(0, 8).map((trend) => ({
    name: trend.trend.length > 17 ? `${trend.trend.slice(0, 17)}…` : trend.trend,
    fullName: trend.trend,
    videos: trend.count || 0,
  })), [trends]);
  const nicheData = useMemo(() => Object.entries(stats?.niche_stats || {}).map(([name, data]) => ({
    name: name.length > 13 ? `${name.slice(0, 13)}…` : name,
    fullName: name,
    videos: data.count || 0,
  })), [stats]);
  const drivers = useMemo(() => [...new Set(opportunities.flatMap((opportunity) => opportunity.reasons || []))], [opportunities]);
  const topOpportunity = opportunities[0];
  const emerging = trends.length > 1 ? trends[1]?.trend : trends[0]?.trend || null;

  return (
    <main className="dashboard-page">
      <DashboardHeader
        refreshing={refreshing}
        onRefresh={() => loadDashboard(true)}
        onOpenPipeline={() => navigate('/pipeline')}
      />

      <WorkspaceContextBar dataset={activeDataset} totalVideos={totalVideos} />

      {loadError && !stats ? <DashboardError onRetry={() => loadDashboard(true)} /> : (
        <>
          {loading && !stats ? <DashboardSkeleton /> : (
            <section className="dash-metrics-grid" aria-label="Intelligence metrics">
              <MetricCard icon="▥" label="Active Trends" value={trends.length} description={`Topics detected from ${trendsResponse?.total_videos_analyzed || 0} content items`} tone="blue" />
              <MetricCard icon="◎" label="Top Opportunity" value={topOpportunity ? `${Math.round((topOpportunity.opportunity_score || 0) * 100)}%` : null} description={topOpportunity?.trend || 'Waiting for opportunity data'} tone="green" />
              <MetricCard icon="★" label="Emerging Trend" value={emerging} description={emerging ? 'Fastest-growing topic' : 'No emerging trend detected'} tone="purple" />
              <MetricCard icon="◇" label="Avg Content Quality" value={quality} description={`Weighted across ${stats?.total_niches || 0} niches`} tone="amber" />
              <MetricCard icon="▤" label="Total Content" value={fmt(totalVideos)} description={stats?.platform_stats ? Object.entries(stats.platform_stats).map(([platform, count]) => `${count} ${platform}`).join(' · ') : 'No platform data yet'} tone="cyan" className="dash-metric-total" />
            </section>
          )}

          <LiveTrendsSection trends={trends} loading={loading && !trendsResponse} onOpenTrend={(trend) => navigate(`/videos?trend=${encodeURIComponent(trend)}`)} />

          <section className="dash-lower-grid">
            <OpportunityPanel opportunities={opportunities} loading={loading && !opportunitiesResponse} />
            <div className="dash-analytics-stack">
              <TrendDistributionPanel data={trendChartData} />
              <NicheDistributionPanel data={nicheData} />
            </div>
            <InsightSignalsPanel drivers={drivers} health={health} transcriptStats={transcriptStats} />
          </section>
        </>
      )}
    </main>
  );
}
