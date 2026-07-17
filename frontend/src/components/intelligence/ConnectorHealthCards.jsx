import { useEffect, useState, useCallback } from 'react';
import { api } from '../../api/client';
import PlatformIcon from '../PlatformIcon';

const PLATFORM_META = {
  youtube: { label: 'YouTube', accent: '#ff4444', accentBg: 'rgba(255,68,68,0.08)' },
  reddit: { label: 'Reddit', accent: '#ff6633', accentBg: 'rgba(255,102,51,0.08)' },
  tiktok: { label: 'TikTok', accent: '#ff2d75', accentBg: 'rgba(255,45,117,0.08)' },
  instagram: { label: 'Instagram', accent: '#c837ab', accentBg: 'rgba(200,55,171,0.08)' },
};

const STATUS_CONFIG = {
  healthy: { label: 'Operational', cls: 'chc-status-healthy', dot: 'online' },
  degraded: { label: 'Degraded', cls: 'chc-status-degraded', dot: 'degraded' },
  unavailable: { label: 'Unavailable', cls: 'chc-status-unavailable', dot: 'offline' },
  disabled: { label: 'Disabled', cls: 'chc-status-disabled', dot: 'disabled' },
  unknown: { label: 'Unknown', cls: 'chc-status-disabled', dot: 'disabled' },
};

function ConnectorCard({ platformId, health }) {
  const meta = PLATFORM_META[platformId] || { label: platformId, accent: '#4f8cff', accentBg: 'rgba(79,140,255,0.08)' };
  const statusCfg = STATUS_CONFIG[health?.status] || STATUS_CONFIG.unknown;

  return (
    <div className={`chc-card ${health?.status || 'unknown'}`} style={{ '--platform-accent': meta.accent, '--platform-accent-bg': meta.accentBg }}>
      <div className="chc-card-header">
        <div className="chc-card-icon"><PlatformIcon platform={platformId} size={20} color={meta.accent} /></div>
        <div className="chc-card-name">{meta.label}</div>
        <div className={`chc-card-status ${statusCfg.cls}`}>
          <span className={`chc-dot ${statusCfg.dot}`} />
          {statusCfg.label}
        </div>
      </div>
      <div className="chc-card-metrics">
        <div className="chc-metric">
          <span className="chc-metric-val">{health?.latency_ms ? `${health.latency_ms}ms` : '—'}</span>
          <span className="chc-metric-label">Latency</span>
        </div>
        <div className="chc-metric">
          <span className="chc-metric-val">{health?.credentials_configured ? '✓' : '✕'}</span>
          <span className="chc-metric-label">Credentials</span>
        </div>
        <div className="chc-metric">
          <span className="chc-metric-val">{health?.last_check ? new Date(health.last_check).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—'}</span>
          <span className="chc-metric-label">Last Check</span>
        </div>
      </div>
      {health?.error_message && health.status !== 'healthy' && health.status !== 'disabled' && (
        <div className="chc-card-error">
          ⚠ {health.error_message.length > 80 ? health.error_message.slice(0, 80) + '…' : health.error_message}
        </div>
      )}
    </div>
  );
}

export default function ConnectorHealthCards() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadHealth = useCallback(() => {
    setLoading(true);
    api.getConnectorHealth()
      .then(setData)
      .catch((err) => console.error('Connector health failed:', err))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(loadHealth, 0);
    return () => window.clearTimeout(timer);
  }, [loadHealth]);

  const connectors = data?.connectors || {};
  const platforms = ['youtube', 'reddit', 'tiktok', 'instagram'];

  return (
    <div className="chc-section">
      <div className="chc-header">
        <h3 className="chc-title"><span>🔌</span> Connector Health</h3>
        <button className="btn btn-secondary" onClick={loadHealth} style={{ fontSize: '0.7rem', padding: '4px 12px' }}>
          🔄 Refresh
        </button>
      </div>
      <div className="chc-grid">
        {loading ? (
          platforms.map(p => (
            <div key={p} className="chc-card skeleton">
              <div className="skeleton-line skeleton-shimmer" style={{ width: '60%', height: 14, marginBottom: 12 }} />
              <div className="skeleton-line skeleton-shimmer" style={{ width: '100%', height: 40, marginBottom: 8 }} />
              <div className="skeleton-line skeleton-shimmer" style={{ width: '40%', height: 10 }} />
            </div>
          ))
        ) : (
          platforms.map(p => (
            <ConnectorCard key={p} platformId={p} health={connectors[p]} />
          ))
        )}
      </div>
    </div>
  );
}
