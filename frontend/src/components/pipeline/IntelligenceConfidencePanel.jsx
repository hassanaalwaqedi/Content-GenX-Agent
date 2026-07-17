import { connectorSummary, formatRelativeTime, getFreshnessScore } from './pipelineUtils';

function ConfidenceMetric({ icon, label, value, detail, tone = 'green', unavailable }) {
  const safeValue = Math.max(0, Math.min(100, value || 0));
  return <article className={`pi-confidence-card ${tone}`}><span aria-hidden="true">{icon}</span><p>{label}</p><strong>{unavailable ? '—' : `${safeValue}%`}</strong><i aria-label={unavailable ? `${label} unavailable` : `${label}: ${safeValue}%`}><b style={{ width: `${safeValue}%` }} /></i><small>{detail}</small></article>;
}

export default function IntelligenceConfidencePanel({ lastRun, connectors, config }) {
  const health = connectorSummary(connectors);
  const ingested = Number(lastRun?.videos_ingested || 0);
  const stored = Number(lastRun?.videos_stored || 0);
  const enriched = Number(lastRun?.videos_enriched || 0);
  const freshness = getFreshnessScore(lastRun?.started_at);
  const metrics = [
    { icon: '◎', label: 'Scan Quality', value: ingested ? Math.round((stored / ingested) * 100) : 0, detail: ingested ? 'stored / ingested' : 'No completed scan yet', tone: 'green', unavailable: !ingested },
    { icon: '◴', label: 'Data Freshness', value: freshness, detail: lastRun ? formatRelativeTime(lastRun.started_at) : 'No completed scan yet', tone: freshness >= 75 ? 'green' : freshness >= 40 ? 'amber' : 'red', unavailable: !lastRun },
    { icon: '⌁', label: 'Connector Health', value: Math.round((health.healthy / health.total) * 100), detail: `${health.healthy}/${health.total} online`, tone: health.healthy === health.total ? 'green' : health.healthy ? 'amber' : 'red' },
    { icon: '✦', label: 'AI Enrichment', value: ingested ? Math.round((enriched / ingested) * 100) : 0, detail: ingested ? 'enriched / ingested' : 'No completed scan yet', tone: 'purple', unavailable: !ingested },
    { icon: '◫', label: 'Platform Coverage', value: Math.round((config.platforms.length / health.total) * 100), detail: `${config.platforms.length}/${health.total} selected`, tone: 'blue' },
  ];
  return <section className="pi-confidence-panel"><header><h2><span aria-hidden="true">✦</span> Intelligence Confidence</h2><p>Operational quality from the latest available data.</p></header><div>{metrics.map((metric) => <ConfidenceMetric key={metric.label} {...metric} />)}</div></section>;
}
