import { useEffect, useState } from 'react';

function ConfidenceGauge({ label, value, maxLabel, icon }) {
  const pct = Math.min(Math.max(value, 0), 100);
  const color = pct >= 75 ? 'var(--color-accent-green)' : pct >= 40 ? 'var(--color-accent-orange)' : 'var(--color-accent-red)';
  return (
    <div className="icf-gauge">
      <div className="icf-gauge-header">
        <span className="icf-gauge-icon">{icon}</span>
        <span className="icf-gauge-label">{label}</span>
      </div>
      <div className="icf-gauge-bar">
        <div className="icf-gauge-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <div className="icf-gauge-footer">
        <span className="icf-gauge-pct" style={{ color }}>{pct}%</span>
        <span className="icf-gauge-max">{maxLabel}</span>
      </div>
    </div>
  );
}

export default function IntelligenceConfidence({ lastRun, connectorData }) {
  const [currentTime, setCurrentTime] = useState(0);

  useEffect(() => {
    const updateTime = () => setCurrentTime(Date.now());
    const timer = window.setTimeout(updateTime, 0);
    const interval = window.setInterval(updateTime, 60_000);
    return () => {
      window.clearTimeout(timer);
      window.clearInterval(interval);
    };
  }, []);

  const ingested = lastRun?.videos_ingested || 0;
  const enriched = lastRun?.videos_enriched || 0;
  const stored = lastRun?.videos_stored || 0;
  const scanQuality = ingested > 0 ? Math.round((stored / ingested) * 100) : 0;
  const aiCoverage = ingested > 0 ? Math.round((enriched / ingested) * 100) : 0;
  const connectors = connectorData?.connectors || {};
  const healthyCount = Object.values(connectors).filter(c => c.status === 'healthy').length;
  const connectorConfidence = Math.round((healthyCount / 4) * 100);
  const available = connectorData?.available || [];
  const platformDiversity = Math.round((available.length / 4) * 100);
  let freshness = 0;
  if (lastRun?.started_at && currentTime) {
    const h = (currentTime - new Date(lastRun.started_at).getTime()) / 3600000;
    freshness = h < 1 ? 100 : h < 6 ? 80 : h < 24 ? 60 : h < 72 ? 35 : 10;
  }
  const gauges = [
    { label: 'Scan Quality', value: scanQuality, maxLabel: 'stored/ingested', icon: '🎯' },
    { label: 'Data Freshness', value: freshness, maxLabel: 'time since scan', icon: '⏰' },
    { label: 'Connector Health', value: connectorConfidence, maxLabel: `${healthyCount}/4 online`, icon: '🔌' },
    { label: 'AI Enrichment', value: aiCoverage, maxLabel: 'enriched/ingested', icon: '🧠' },
    { label: 'Platform Coverage', value: platformDiversity, maxLabel: `${available.length}/4 active`, icon: '📡' },
  ];
  return (
    <div className="icf-section">
      <div className="icf-header">
        <h3 className="icf-title"><span>📈</span> Intelligence Confidence</h3>
      </div>
      <div className="icf-grid">
        {gauges.map(g => <ConfidenceGauge key={g.label} {...g} />)}
      </div>
    </div>
  );
}
