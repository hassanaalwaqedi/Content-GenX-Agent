const FLOW_STAGES = [
  { icon: '🌍', label: 'Markets', sub: 'Target regions' },
  { icon: '📡', label: 'Platforms', sub: 'Data sources' },
  { icon: '🔎', label: 'Signals', sub: 'Trend detection' },
  { icon: '🧠', label: 'AI Analysis', sub: 'Enrichment' },
  { icon: '💾', label: 'Storage', sub: 'Intelligence DB' },
  { icon: '📊', label: 'Dashboard', sub: 'Live insights' },
];

export default function ScanFlowVisualization({ isRunning = false, activeStage = -1 }) {
  return (
    <div className={`sfv ${isRunning ? 'sfv-running' : ''}`}>
      <div className="sfv-label">Intelligence Pipeline Flow</div>
      <div className="sfv-track">
        {FLOW_STAGES.map((stage, i) => {
          let stageClass = '';
          if (isRunning) {
            if (i < activeStage) stageClass = 'completed';
            else if (i === activeStage) stageClass = 'active';
          }
          return (
            <div key={stage.label} className="sfv-node-wrap">
              {i > 0 && <div className={`sfv-connector ${stageClass === 'completed' ? 'sfv-connector-done' : stageClass === 'active' ? 'sfv-connector-active' : ''}`}>
                <div className="sfv-connector-line" />
                {isRunning && (stageClass === 'active' || stageClass === 'completed') && <div className="sfv-connector-dot" />}
              </div>}
              <div className={`sfv-node ${stageClass}`}>
                <div className="sfv-node-icon">{stage.icon}</div>
                <div className="sfv-node-text">
                  <span className="sfv-node-label">{stage.label}</span>
                  <span className="sfv-node-sub">{stage.sub}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
