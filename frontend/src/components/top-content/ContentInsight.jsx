import { getContentInsight } from './contentUtils';

export default function ContentInsight({ video, compact = false }) {
  const insight = getContentInsight(video);
  return (
    <div className={`tc-content-insight ${compact ? 'tc-content-insight-compact' : ''}`}>
      <span aria-hidden="true">✦</span>
      <div>
        {!compact && <small>AI insight</small>}
        <p>{insight}</p>
      </div>
    </div>
  );
}
