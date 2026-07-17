import { useMemo, useState } from 'react';
import { formatDuration, formatRelativeTime, getRunDepth, normalizeRunStatus } from './pipelineUtils';

function RunCard({ run, onOpen, onRerun }) {
  const status = normalizeRunStatus(run.status);
  const metrics = [['Ingested', run.videos_ingested], ['Scored', run.videos_processed], ['AI analyzed', run.videos_enriched], ['Stored', run.videos_stored]];
  return <article className={`pi-run-card ${status.tone}`}><header><div><p>Scan #{run.id}</p><small>{formatRelativeTime(run.started_at)}</small></div><span>{status.label}</span></header><div className="pi-run-metrics">{metrics.map(([label, value]) => <div key={label}><strong>{value ?? 0}</strong><small>{label}</small></div>)}</div><footer><span>◴ {formatDuration(run.elapsed_seconds)}</span><span>▤ {getRunDepth(run)}</span><span>{run.triggered_by || 'manual'}</span></footer><div className="pi-run-actions"><button type="button" onClick={() => onOpen(run)}>Details</button>{status.tone !== 'running' && <button type="button" onClick={() => onRerun(run)}>Rerun</button>}</div></article>;
}

export default function RecentRunsPanel({ history, loading, onRefresh, onOpenRun, onRerun }) {
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState('newest');
  const counts = useMemo(() => history.reduce((result, run) => { result.all += 1; const tone = normalizeRunStatus(run.status).tone; result[tone] = (result[tone] || 0) + 1; return result; }, { all: 0, success: 0, warning: 0, danger: 0, running: 0 }), [history]);
  const visible = useMemo(() => {
    const query = search.trim().toLowerCase();
    const items = history.filter((run) => {
      const status = normalizeRunStatus(run.status);
      return (filter === 'all' || status.tone === filter) && (!query || String(run.id).includes(query) || String(run.triggered_by || '').toLowerCase().includes(query));
    });
    return items.sort((left, right) => sort === 'duration' ? Number(right.elapsed_seconds || 0) - Number(left.elapsed_seconds || 0) : sort === 'oldest' ? new Date(left.started_at) - new Date(right.started_at) : new Date(right.started_at) - new Date(left.started_at));
  }, [filter, history, search, sort]);
  return <section className="pi-runs-panel"><header className="pi-runs-heading"><div><h2><span aria-hidden="true">▤</span> Recent Intelligence Runs</h2><p>{history.length} run{history.length === 1 ? '' : 's'} available</p></div><button type="button" onClick={onRefresh}>↻ Refresh</button></header><div className="pi-runs-toolbar"><div>{[['all', 'All'], ['success', 'Success'], ['warning', 'Warning'], ['danger', 'Failed']].map(([value, label]) => <button type="button" key={value} className={filter === value ? 'active' : ''} onClick={() => setFilter(value)}>{label} <span>{counts[value] || 0}</span></button>)}</div><label><span aria-hidden="true">⌕</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search scans…" /></label><select value={sort} onChange={(event) => setSort(event.target.value)} aria-label="Sort runs"><option value="newest">Newest</option><option value="oldest">Oldest</option><option value="duration">Duration</option></select></div>{loading ? <div className="pi-runs-skeleton">{[1, 2, 3].map((item) => <span key={item} />)}</div> : visible.length ? <div className="pi-runs-grid">{visible.slice(0, 6).map((run) => <RunCard key={run.id} run={run} onOpen={onOpenRun} onRerun={onRerun} />)}</div> : <div className="pi-runs-empty"><strong>No matching runs</strong><p>Launch an intelligence scan to build operational history.</p></div>}</section>;
}
