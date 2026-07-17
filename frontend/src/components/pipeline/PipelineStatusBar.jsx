import { connectorSummary, formatRelativeTime } from './pipelineUtils';

function StatusItem({ label, value, tone = '', detail, onClick }) {
  const content = <><span>{label}</span><strong className={tone}>{tone && <i aria-hidden="true" />} {value}</strong>{detail && <small>{detail}</small>}</>;
  return onClick ? <button type="button" className="pi-status-item clickable" onClick={onClick}>{content}</button> : <div className="pi-status-item">{content}</div>;
}

export default function PipelineStatusBar({ config, connectors, stats, lastRun, apiOnline, onReset, onSavePreset, onToggleConfig, configVisible, onOpenConnectors }) {
  const health = connectorSummary(connectors);
  const activePlatforms = config.platforms.length ? config.platforms.map((platform) => platform[0].toUpperCase() + platform.slice(1)).join(', ') : 'None selected';
  return (
    <section className="pi-status-bar" aria-label="Pipeline operational status">
      <div className="pi-status-grid">
        <StatusItem label="Active platforms" value={activePlatforms} detail={`${config.platforms.length}/4 selected`} />
        <StatusItem label="Connector health" value={`${health.healthy}/${health.total} online`} tone={health.healthy === health.total ? 'good' : health.healthy ? 'warning' : 'danger'} onClick={onOpenConnectors} />
        <StatusItem label="Last scan" value={formatRelativeTime(lastRun?.started_at)} />
        <StatusItem label="Content indexed" value={Number(stats?.total_videos || 0).toLocaleString()} tone="accent" />
        <StatusItem label="API status" value={apiOnline ? 'Operational' : 'Unavailable'} tone={apiOnline ? 'good' : 'danger'} />
      </div>
      <div className="pi-status-actions">
        <button type="button" onClick={onReset}>↻ Reset</button>
        <button type="button" onClick={onSavePreset}>▣ Save Preset</button>
        <button type="button" onClick={onToggleConfig}>{configVisible ? '⌃ Hide Config' : '⌄ Show Config'}</button>
      </div>
    </section>
  );
}
