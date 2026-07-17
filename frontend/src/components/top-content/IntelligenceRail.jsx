import { fmt, getPlatformColor, getPlatformLabel } from '../../utils/platform';

function Distribution({ platformCounts, total }) {
  const entries = Object.entries(platformCounts).sort(([, a], [, b]) => b - a);
  const gradient = entries.length ? entries.reduce((segments, [platform, count], index) => {
    const start = entries.slice(0, index).reduce((sum, [, itemCount]) => sum + (itemCount / total) * 100, 0);
    const end = start + (count / total) * 100;
    segments.push(`${getPlatformColor(platform)} ${start}% ${end}%`);
    return segments;
  }, []).join(', ') : 'rgba(126, 153, 201, .18) 0 100%';
  return (
    <div className="tc-rail-card tc-distribution-card">
      <h3><span>▣</span> Platform distribution</h3>
      <div className="tc-distribution-content">
        <div className="tc-donut" style={{ background: `conic-gradient(${gradient})` }}><div><strong>{total}</strong><span>items</span></div></div>
        <div className="tc-distribution-legend">{entries.map(([platform, count]) => <div key={platform}><i style={{ background: getPlatformColor(platform) }} /><span>{getPlatformLabel(platform)}</span><strong>{Math.round((count / total) * 100)}%</strong></div>)}</div>
      </div>
    </div>
  );
}

export default function IntelligenceRail({ data, onKeywordClick }) {
  const total = data?.count || 0;
  const platformCounts = data?.platformCounts || {};
  const signalRows = [
    ['High engagement', Math.min(100, (data?.avgEngagement || 0) * 1000), 'green'],
    ['Strong AI score', Math.min(100, (data?.avgScore || 0) * 120), 'blue'],
    ['Reusable formats', Math.min(100, ((data?.withInsights || 0) / Math.max(total, 1)) * 100), 'purple'],
    ['Creative gaps', Math.min(100, ((data?.withGaps || 0) / Math.max(total, 1)) * 100), 'orange'],
  ];
  return (
    <aside className="tc-intelligence-rail">
      <div className="tc-rail-card tc-quick-stats">
        <h3><span>▥</span> Quick stats</h3>
        <div className="tc-stat-grid">
          <div><strong>{fmt(data?.totalViews || 0)}</strong><span>Total views</span></div><div><strong className="green">{((data?.avgEngagement || 0) * 100).toFixed(1)}%</strong><span>Avg. engagement</span></div><div><strong className="purple">{(data?.avgScore || 0).toFixed(2)}</strong><span>Avg. AI score</span></div><div><strong className="orange">{total.toLocaleString()}</strong><span>Content items</span></div>
        </div>
      </div>
      <div className="tc-rail-card">
        <h3><span>♨</span> Trending keywords</h3>
        {data?.trendingKeywords?.length ? <div className="tc-keyword-list">{data.trendingKeywords.map(({ word, count }) => <button key={word} onClick={() => onKeywordClick(word)}><span>{word}</span><strong>{count}</strong></button>)}</div> : <p className="tc-rail-empty">Keywords appear as more content is indexed.</p>}
      </div>
      <Distribution platformCounts={platformCounts} total={total} />
      <div className="tc-rail-card">
        <h3><span>◉</span> Content signals</h3>
        <div className="tc-signal-list">{signalRows.map(([label, value, tone]) => <div key={label}><span>{label}</span><div className="tc-signal-meter"><i className={tone} style={{ width: `${Math.max(8, value)}%` }} /></div></div>)}</div>
      </div>
    </aside>
  );
}
