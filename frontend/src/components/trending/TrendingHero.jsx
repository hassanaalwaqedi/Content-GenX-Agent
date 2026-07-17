import { getRisingTopic } from './trendingUtils';

function Sparkline() {
  return <svg className="tr-sparkline" viewBox="0 0 132 54" role="img" aria-label="Rising momentum sparkline"><defs><linearGradient id="tr-spark-area" x1="0" x2="0" y1="0" y2="1"><stop stopColor="#2dd4a4" stopOpacity=".35" /><stop offset="1" stopColor="#2dd4a4" stopOpacity="0" /></linearGradient></defs><path d="M2 44 L18 31 L34 36 L48 19 L62 27 L78 9 L94 23 L111 5 L130 13 L130 52 L2 52Z" fill="url(#tr-spark-area)" /><path d="M2 44 L18 31 L34 36 L48 19 L62 27 L78 9 L94 23 L111 5 L130 13" fill="none" stroke="#2dd4a4" strokeWidth="2" /><circle cx="78" cy="9" r="3" fill="#2dd4a4" /><circle cx="111" cy="5" r="3" fill="#b287ff" /></svg>;
}

export default function TrendingHero({ videos, activeDataset, lastUpdated, onRefresh, onExport, onRunScan, loading }) {
  const rising = getRisingTopic(videos);
  const platforms = new Set(videos.map((video) => video.platform).filter(Boolean)).size;
  const workspace = activeDataset?.name || activeDataset?.label || 'All historical data';
  return (
    <header className="tr-hero">
      <div className="tr-hero-copy">
        <p className="tr-eyebrow">Momentum intelligence</p>
        <h1><span aria-hidden="true">🔥</span> Trending Content</h1>
        <p>Discover content gaining momentum before it peaks.</p>
        <div className="tr-hero-meta"><span><i className="tr-live-dot" /> {videos.length} trending videos</span><span>⌁ {platforms || 0} platforms</span><span>◷ {lastUpdated ? 'Updated just now' : 'Fetching latest signals'}</span></div>
      </div>
      <section className="tr-rising-topic" aria-label="Fastest rising topic">
        <div><span>◉ Fastest rising topic</span><strong>{rising.name}</strong><small>+{rising.momentum}% momentum index</small></div>
        <Sparkline />
      </section>
      <div className="tr-hero-actions">
        <div className="tr-workspace"><i className="tr-live-dot" /><div><small>Active workspace</small><strong>{workspace}</strong></div><span>⌄</span></div>
        <div className="tr-hero-action-row"><button className="tr-action-button" onClick={onRefresh} disabled={loading}>⟳ <span>{loading ? 'Refreshing' : 'Refresh'}</span></button><button className="tr-action-button" onClick={onExport} disabled={!videos.length}>▤ <span>Export PDF</span></button></div>
        <button className="tr-scan-button" onClick={onRunScan}>ϟ Run Trend Scan</button>
      </div>
    </header>
  );
}
