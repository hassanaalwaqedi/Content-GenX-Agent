import { getContentMetrics } from './contentUtils';

export default function ContentMetrics({ video, compact = false }) {
  const metrics = getContentMetrics(video);
  return (
    <div className={`tc-metrics ${compact ? 'tc-metrics-compact' : ''}`}>
      {metrics.map((metric) => (
        <div className="tc-metric" key={metric.label} title={metric.label}>
          <span>{metric.icon}</span>
          <strong>{metric.value}</strong>
          {!compact && <small>{metric.label}</small>}
        </div>
      ))}
    </div>
  );
}
