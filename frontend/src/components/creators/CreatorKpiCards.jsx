import { formatPercent, formatScore, getInitials } from './creatorUtils';

function KpiCard({ icon, label, value, detail, tone = 'blue', creator }) {
  return (
    <article className={`cr-kpi-card cr-kpi-${tone}`}>
      <p><span aria-hidden="true">{icon}</span> {label}</p>
      <div className="cr-kpi-value-row">
        <strong>{value}</strong>
        {creator && <span className="cr-kpi-avatar" aria-hidden="true">{getInitials(creator.channel)}</span>}
      </div>
      <small>{detail}</small>
    </article>
  );
}

export default function CreatorKpiCards({ creators, loading }) {
  const count = creators.length;
  const topCreator = [...creators].sort((left, right) => right.avg_score - left.avg_score)[0];
  const average = (field) => count ? creators.reduce((sum, creator) => sum + Number(creator[field] || 0), 0) / count : 0;

  const cards = [
    { icon: '◉', label: 'Total creators', value: loading ? '—' : count.toLocaleString(), detail: 'Analyzed in this workspace', tone: 'purple' },
    { icon: '♛', label: 'Top creator', value: loading ? '—' : (topCreator?.channel || '—'), detail: topCreator ? `AI score: ${formatScore(topCreator.avg_score)}` : 'No creator data yet', tone: 'purple', creator: topCreator },
    { icon: '⌁', label: 'Avg trend dominance', value: loading ? '—' : formatPercent(average('trend_dominance_score')), detail: 'Presence in top-ranked content', tone: 'orange' },
    { icon: '◈', label: 'Avg opportunity fit', value: loading ? '—' : formatPercent(average('opportunity_alignment')), detail: 'Topic alignment with opportunities', tone: 'green' },
    { icon: '◌', label: 'Avg engagement', value: loading ? '—' : formatPercent(average('avg_engagement')), detail: 'Across analyzed creators', tone: 'blue' },
  ];

  return <section className="cr-kpi-grid" aria-label="Creator intelligence summary">{cards.map((card) => <KpiCard key={card.label} {...card} />)}</section>;
}
