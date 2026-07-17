import { useEffect } from 'react';
import PlatformIcon from '../PlatformIcon';
import { PLATFORM_IDS } from './pipelineUtils';

export default function ConnectorHealthDrawer({ open, connectors, onClose, onRefresh, refreshing }) {
  useEffect(() => {
    if (!open) return undefined;
    const onKeyDown = (event) => { if (event.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open, onClose]);
  if (!open) return null;
  return <div className="pi-drawer-backdrop" onMouseDown={onClose} role="presentation"><aside className="pi-connector-drawer" onMouseDown={(event) => event.stopPropagation()} aria-label="Connector health"><header><div><p>Operational status</p><h2>Connector Health</h2></div><button type="button" onClick={onClose} aria-label="Close connector health">×</button></header><button type="button" className="pi-connector-refresh" onClick={onRefresh} disabled={refreshing}>{refreshing ? 'Refreshing…' : '↻ Refresh health'}</button><div>{PLATFORM_IDS.map((platform) => { const connector = connectors?.[platform]; return <article key={platform} className={connector?.status || 'unknown'}><PlatformIcon platform={platform} size={20} /><div><strong>{platform[0].toUpperCase() + platform.slice(1)}</strong><small>{connector?.status || 'Unknown'} · {connector?.credentials_configured ? 'Credentials configured' : 'Credentials unavailable'}</small>{connector?.error_message && <em>{connector.error_message}</em>}</div><span>{connector?.latency_ms ? `${Math.round(connector.latency_ms)}ms` : '—'}</span></article>; })}</div></aside></div>;
}
