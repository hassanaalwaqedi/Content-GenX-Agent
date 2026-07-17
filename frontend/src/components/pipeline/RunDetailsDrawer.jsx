import { useEffect } from 'react';
import { formatDuration, formatRelativeTime, getRunDepth, normalizeRunStatus } from './pipelineUtils';

export default function RunDetailsDrawer({ run, onClose, onRerun }) {
  useEffect(() => {
    if (!run) return undefined;
    const onKeyDown = (event) => { if (event.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [run, onClose]);
  if (!run) return null;
  const status = normalizeRunStatus(run.status);
  const counts = [['Ingested', run.videos_ingested], ['Scored', run.videos_processed], ['AI analyzed', run.videos_enriched], ['Stored', run.videos_stored]];
  return <div className="pi-drawer-backdrop" onMouseDown={onClose} role="presentation"><aside className="pi-run-drawer" onMouseDown={(event) => event.stopPropagation()} aria-label={`Scan ${run.id} details`}><button type="button" className="pi-drawer-close" onClick={onClose} aria-label="Close run details">×</button><p>Pipeline run</p><div className="pi-drawer-title"><h2>Scan #{run.id}</h2><span className={status.tone}>{status.label}</span></div><div className="pi-drawer-meta"><span>Started {formatRelativeTime(run.started_at)}</span><span>{formatDuration(run.elapsed_seconds)}</span><span>{getRunDepth(run)} scan</span><span>{run.triggered_by || 'manual'}</span></div><section><h3>Pipeline counts</h3><div className="pi-drawer-counts">{counts.map(([label, value]) => <div key={label}><small>{label}</small><strong>{value ?? 0}</strong></div>)}</div></section><section><h3>Configuration</h3><p className="pi-drawer-muted">This history endpoint does not expose the saved market, platform, or signal snapshot for previous runs. Use a saved preset or the current configuration to run again.</p></section>{run.error_message && <section><h3>Run message</h3><p className="pi-drawer-error">{run.error_message}</p></section>}<button type="button" className="pi-drawer-rerun" onClick={() => { onClose(); onRerun(run); }}>↻ Rerun current configuration</button></aside></div>;
}
