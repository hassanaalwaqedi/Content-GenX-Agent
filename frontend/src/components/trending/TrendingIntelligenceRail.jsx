import { getPlatformColor, getPlatformLabel } from '../../utils/platform';
import { formatCompactNumber, formatPercentage } from './trendingUtils';

function QuickStats({ data }) {
  return <section className="tr-rail-panel"><h3><span>▥</span> Quick Stats</h3><div className="tr-quick-stats"><div><strong>{formatCompactNumber(data.totalViews)}</strong><span>Total views</span><small>↑ Live total</small></div><div><strong className="green">{formatPercentage(data.avgEngagement)}</strong><span>Avg. engagement</span><small>↑ Signal strength</small></div><div><strong className="purple">{data.avgScore.toFixed(2)}</strong><span>Avg. AI score</span><small>↑ Quality index</small></div><div><strong>{data.count.toLocaleString()}</strong><span>Content items</span><small>↑ In this view</small></div></div></section>;
}

function Keywords({ keywords, onKeywordClick }) {
  return <section className="tr-rail-panel"><h3><span>♨</span> Trending Keywords <button onClick={() => onKeywordClick('')}>View all</button></h3>{keywords.length ? <ol className="tr-keyword-rankings">{keywords.map((item, index) => <li key={item.word}><i>{index + 1}</i><button onClick={() => onKeywordClick(item.word)}>{item.word}</button><span>{item.count}</span><strong>↑ {item.momentum}%</strong></li>)}</ol> : <p className="tr-rail-empty">Keywords appear when more content is indexed.</p>}</section>;
}

function PlatformDistribution({ counts, total }) {
  const entries = Object.entries(counts).sort(([, a], [, b]) => b - a);
  const gradient = entries.length ? entries.reduce((segments, [platform, count], index) => { const start = entries.slice(0, index).reduce((sum, [, value]) => sum + (value / total) * 100, 0); const end = start + (count / total) * 100; segments.push(`${getPlatformColor(platform)} ${start}% ${end}%`); return segments; }, []).join(', ') : 'rgba(120, 145, 195, .25) 0 100%';
  return <section className="tr-rail-panel"><h3><span>◌</span> Platform Distribution</h3><div className="tr-donut-layout"><div className="tr-donut" style={{ background: `conic-gradient(${gradient})` }}><div><strong>{total}</strong><span>Total</span></div></div><div className="tr-platform-legend">{entries.map(([platform, count]) => <div key={platform}><i style={{ background: getPlatformColor(platform) }} /><span>{getPlatformLabel(platform)}</span><strong>{Math.round((count / total) * 100)}%</strong></div>)}</div></div></section>;
}

function ContentSignals({ data }) {
  const signals = [['High engagement', Math.min(100, data.avgEngagement * 1200), 'green'], ['Strong hook', Math.min(100, data.avgScore * 115), 'purple'], ['Viral velocity', Math.min(100, data.avgMomentum), 'blue'], ['Re-usable format', Math.min(100, (data.withAdvice / Math.max(data.count, 1)) * 100), 'amber'], ['Low competition', Math.min(100, (data.withGaps / Math.max(data.count, 1)) * 100), 'green']];
  return <section className="tr-rail-panel"><h3><span>◉</span> Content Signals <button>View all</button></h3><div className="tr-signals">{signals.map(([label, value, tone]) => <div key={label}><span>{label}</span><i><b className={tone} style={{ width: `${Math.max(8, value)}%` }} /></i></div>)}</div></section>;
}

export default function TrendingIntelligenceRail({ data, onKeywordClick }) {
  return <aside className="tr-intelligence-rail"><QuickStats data={data} /><Keywords keywords={data.keywords} onKeywordClick={onKeywordClick} /><PlatformDistribution counts={data.platformCounts} total={data.count} /><ContentSignals data={data} /></aside>;
}
