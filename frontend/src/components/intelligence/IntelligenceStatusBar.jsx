import { useEffect, useState, useCallback } from 'react';
import { api } from '../../api/client';

const PLATFORM_ICONS = { youtube: '▶️', reddit: '💬', tiktok: '🎵', instagram: '📸' };

export default function IntelligenceStatusBar() {
  const [connectorData, setConnectorData] = useState(null);
  const [lastRun, setLastRun] = useState(null);
  const [stats, setStats] = useState(null);
  const [currentTime, setCurrentTime] = useState(0);

  const loadStatus = useCallback(() => {
    Promise.all([
      api.getConnectorHealth().catch(() => null),
      api.getPipelineHistory(5).catch(() => null),
      api.getStats().catch(() => null),
    ]).then(([ch, hist, st]) => {
      setConnectorData(ch);
      if (hist?.runs?.length > 0) {
        const lastSuccess = hist.runs.find(r => r.status === 'completed');
        setLastRun(lastSuccess || hist.runs[0]);
      }
      setStats(st);
    });
  }, []);

  useEffect(() => { loadStatus(); }, [loadStatus]);

  useEffect(() => {
    const updateTime = () => setCurrentTime(Date.now());
    const timer = window.setTimeout(updateTime, 0);
    const interval = window.setInterval(updateTime, 60_000);
    return () => {
      window.clearTimeout(timer);
      window.clearInterval(interval);
    };
  }, []);

  const connectors = connectorData?.connectors || {};
  const available = connectorData?.available || [];
  const healthyCount = Object.values(connectors).filter(c => c.status === 'healthy').length;
  const totalConnectors = Object.keys(connectors).length || 4;

  const activePlatforms = available.map(p => (
    <span key={p} className="isb-platform-badge" data-platform={p}>
      {PLATFORM_ICONS[p] || '⚡'} {p}
    </span>
  ));

  const timeSince = (dateStr) => {
    if (!dateStr) return '—';
    if (!currentTime) return 'â€”';
    const diff = currentTime - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
  };

  return (
    <div className="isb">
      <div className="isb-grid">
        <div className="isb-cell">
          <span className="isb-label">Active Platforms</span>
          <div className="isb-platforms">
            {activePlatforms.length > 0 ? activePlatforms : <span className="isb-muted">None detected</span>}
          </div>
        </div>
        <div className="isb-cell">
          <span className="isb-label">Connector Health</span>
          <div className="isb-health-indicator">
            <span className={`isb-health-dot ${healthyCount === totalConnectors ? 'all-good' : healthyCount > 0 ? 'partial' : 'offline'}`} />
            <span className="isb-health-text">{healthyCount}/{totalConnectors} Online</span>
          </div>
        </div>
        <div className="isb-cell">
          <span className="isb-label">Last Scan</span>
          <span className="isb-value">{timeSince(lastRun?.started_at)}</span>
        </div>
        <div className="isb-cell">
          <span className="isb-label">Content Indexed</span>
          <span className="isb-value isb-value-accent">{stats?.total_videos?.toLocaleString() ?? '—'}</span>
        </div>
        <div className="isb-cell">
          <span className="isb-label">API Status</span>
          <div className="isb-health-indicator">
            <span className="isb-health-dot all-good" />
            <span className="isb-health-text">Operational</span>
          </div>
        </div>
      </div>
    </div>
  );
}
