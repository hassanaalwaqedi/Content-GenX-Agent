import { useEffect, useState } from 'react';

const PIPELINE_STAGES = [
  { key: 'ingest', icon: '📡', label: 'Ingesting Content', sub: 'Scanning platforms for trending content...', color: 'var(--color-primary)' },
  { key: 'process', icon: '⚡', label: 'Processing Signals', sub: 'Calculating scores and engagement metrics...', color: 'var(--color-accent-orange)' },
  { key: 'enrich', icon: '🧠', label: 'AI Enrichment', sub: 'Analyzing trends, audiences, and content gaps...', color: 'var(--color-accent-purple)' },
  { key: 'trends', icon: '📊', label: 'Trend Analysis', sub: 'Discovering patterns and opportunities...', color: 'var(--color-accent-green)' },
  { key: 'done', icon: '✅', label: 'Updating Dashboard', sub: 'Intelligence data is now live.', color: 'var(--color-accent-green)' },
];

export default function RunningPipelineUX({ startTime, platforms = [] }) {
  const [activeIdx, setActiveIdx] = useState(0);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const timers = [
      setTimeout(() => setActiveIdx(1), 4000),
      setTimeout(() => setActiveIdx(2), 10000),
      setTimeout(() => setActiveIdx(3), 18000),
      setTimeout(() => setActiveIdx(4), 25000),
    ];
    return () => timers.forEach(clearTimeout);
  }, [startTime]);

  useEffect(() => {
    const interval = setInterval(() => {
      if (startTime) setElapsed(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [startTime]);

  const formatTime = (s) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
  };

  return (
    <div className="rpux">
      <div className="rpux-header">
        <div className="rpux-header-left">
          <span className="rpux-spinner" />
          <div>
            <div className="rpux-title">Intelligence Scan in Progress</div>
            <div className="rpux-sub">
              {platforms.length > 0 && <span>Scanning {platforms.join(', ')}</span>}
            </div>
          </div>
        </div>
        <div className="rpux-timer">
          <span className="rpux-timer-icon">⏱</span>
          {formatTime(elapsed)}
        </div>
      </div>

      <div className="rpux-stages">
        {PIPELINE_STAGES.map((stage, i) => {
          let cls = '';
          if (i < activeIdx) cls = 'completed';
          else if (i === activeIdx) cls = 'active';
          return (
            <div key={stage.key} className={`rpux-stage ${cls}`}>
              <div className="rpux-stage-track">
                <div className="rpux-stage-icon">{stage.icon}</div>
                {i < PIPELINE_STAGES.length - 1 && <div className="rpux-stage-line" />}
              </div>
              <div className="rpux-stage-content">
                <div className="rpux-stage-label">{stage.label}</div>
                <div className="rpux-stage-sub">{stage.sub}</div>
              </div>
              {cls === 'active' && <div className="rpux-stage-pulse" />}
              {cls === 'completed' && <span className="rpux-stage-check">✓</span>}
            </div>
          );
        })}
      </div>
    </div>
  );
}
