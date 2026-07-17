import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { formatPercentage } from './trendingUtils';

function ChartTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const item = payload[0].payload;
  return <div className="tr-chart-tooltip"><strong>{item.fullName}</strong><span>Engagement {formatPercentage(item.engagement / 100)}</span><small>{item.viewsLabel} views</small></div>;
}

export default function EngagementChartPanel({ videos, sortMode, onSortModeChange }) {
  const data = videos.slice(0, 10).map((video, index) => ({
    name: `${index + 1}. ${String(video.title || 'Untitled').slice(0, 15)}`,
    fullName: video.title || 'Untitled content',
    engagement: Number((Number(video.engagement_rate || 0) * 100).toFixed(2)),
    viewsLabel: Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 }).format(Number(video.views || 0)),
  }));
  const summary = data.length ? `Engagement chart for ${data.length} trending items. Peak engagement is ${Math.max(...data.map((item) => item.engagement)).toFixed(1)} percent.` : 'No trending engagement data is available for the selected filters.';
  return <section className="tr-panel tr-chart-panel" aria-label="Top 10 Engagement Rates"><div className="tr-panel-header"><div><h2>Top 10 Engagement Rates <button className="tr-info" title="Content is ordered by the current trend sort.">i</button></h2><span className="sr-only">{summary}</span></div><label className="tr-chart-sort">Sort by:<select value={sortMode} onChange={(event) => onSortModeChange(event.target.value)}><option value="engagement">Engagement rate</option><option value="momentum">Momentum</option><option value="score">AI score</option></select></label></div><div className="tr-chart-wrap">{data.length ? <ResponsiveContainer width="100%" height="100%"><AreaChart data={data} margin={{ top: 14, right: 10, left: -14, bottom: 10 }}><defs><linearGradient id="tr-engagement-area" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#2dd4a4" stopOpacity=".26" /><stop offset="1" stopColor="#2dd4a4" stopOpacity="0" /></linearGradient></defs><CartesianGrid stroke="rgba(105,135,190,.13)" vertical={false} /><XAxis dataKey="name" tickLine={false} axisLine={false} interval={0} tick={{ fill: '#8091b2', fontSize: 9 }} tickFormatter={(value) => `${value.slice(0, 11)}…`} minTickGap={20} /><YAxis tickLine={false} axisLine={false} tick={{ fill: '#8091b2', fontSize: 10 }} tickFormatter={(value) => `${value}%`} width={35} /><Tooltip content={<ChartTooltip />} cursor={{ stroke: 'rgba(125,169,255,.3)' }} /><Area type="monotone" dataKey="engagement" stroke="#34d9a6" strokeWidth={2} fill="url(#tr-engagement-area)" dot={{ r: 3.5, fill: '#52e7b7', strokeWidth: 0 }} activeDot={{ r: 5 }} /></AreaChart></ResponsiveContainer> : <div className="tr-chart-empty">No engagement data for these filters.</div>}</div></section>;
}
