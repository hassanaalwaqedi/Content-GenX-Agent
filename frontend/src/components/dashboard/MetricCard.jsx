export default function MetricCard({ icon, label, value, description, tone = 'blue', className = '' }) {
  const empty = value === null || value === undefined || value === '';
  return (
    <article className={`dash-metric dash-metric-${tone} ${className}`}>
      <div className="dash-metric-label"><span aria-hidden="true">{icon}</span>{label}</div>
      <div className={`dash-metric-value${empty ? ' is-empty' : ''}`}>
        {empty ? 'Waiting for data' : value}
      </div>
      <p>{description}</p>
      <span className="dash-metric-spark" aria-hidden="true" />
    </article>
  );
}
