import { useEffect, useState } from 'react';
import { formatDuration, normalizeRunStatus } from './pipelineUtils';

function LiveElapsed({ startedAt }) {
  const [now, setNow] = useState(null);
  useEffect(() => {
    if (!startedAt) return undefined;
    const updateNow = () => setNow(Date.now());
    updateNow();
    const timer = window.setInterval(updateNow, 1000);
    return () => window.clearInterval(timer);
  }, [startedAt]);
  return <strong>{startedAt && now ? formatDuration((now - startedAt) / 1000) : '—'}</strong>;
}

export default function PipelineExecutionPanel({ running, startedAt, observedRun, message, onOpenDashboard, onViewResults, onRerun }) {
  const state = observedRun ? normalizeRunStatus(observedRun.status) : null;
  if (!running && !message && !observedRun) return null;

  if (running) {
    return <section className="pi-execution-panel running" aria-live="polite"><div className="pi-execution-icon"><span /></div><div><h2>Intelligence scan is running</h2><p>The backend has accepted this scan. Live stages and percentages are not exposed by the current API, so this status updates from real run history.</p></div><div className="pi-execution-time"><small>Elapsed</small><LiveElapsed startedAt={startedAt} /></div></section>;
  }

  if (observedRun) {
    const metrics = [['Ingested', observedRun.videos_ingested], ['Scored', observedRun.videos_processed], ['AI analyzed', observedRun.videos_enriched], ['Stored', observedRun.videos_stored]];
    return <section className={`pi-execution-panel ${state?.tone || 'muted'}`} aria-live="polite"><div className="pi-execution-icon">{state?.tone === 'success' ? '✓' : state?.tone === 'warning' ? '!' : '×'}</div><div><h2>{state?.label || 'Scan update'}</h2><p>{observedRun.error_message || message?.text || 'Run status updated from pipeline history.'}</p><div className="pi-execution-metrics">{metrics.map(([label, value]) => <span key={label}><small>{label}</small><strong>{value ?? 0}</strong></span>)}<span><small>Duration</small><strong>{formatDuration(observedRun.elapsed_seconds)}</strong></span></div></div><div className="pi-execution-actions">{state?.tone === 'success' && <button type="button" onClick={onOpenDashboard}>Open Dashboard</button>}{state?.tone === 'success' && <button type="button" onClick={onViewResults}>View Results</button>}{state?.tone !== 'success' && <button type="button" onClick={onRerun}>Rerun current config</button>}</div></section>;
  }

  return <section className={`pi-execution-panel ${message?.type === 'error' ? 'danger' : 'muted'}`} aria-live="polite"><div className="pi-execution-icon">{message?.type === 'error' ? '×' : 'i'}</div><div><h2>{message?.type === 'error' ? 'Unable to launch scan' : 'Scan status'}</h2><p>{message?.text}</p></div></section>;
}
