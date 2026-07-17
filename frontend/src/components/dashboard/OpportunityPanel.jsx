function score(opportunity) {
  return Math.round(Math.max(0, Math.min(1, opportunity.opportunity_score || 0)) * 100);
}

function OpportunityRow({ opportunity, index }) {
  const titles = opportunity.suggested_titles || [];
  const reasons = opportunity.reasons || [];
  return (
    <article className="dash-opportunity-row">
      <span className={`dash-opportunity-icon icon-${index % 4}`} aria-hidden="true">✦</span>
      <div className="dash-opportunity-copy">
        <div className="dash-opportunity-title-row">
          <h3>{opportunity.trend}</h3>
          <div className="dash-opportunity-tags">
            {reasons.slice(0, 3).map((reason) => <span key={reason}>{reason}</span>)}
          </div>
        </div>
        {titles.length > 0 ? (
          <p title={titles[0]}><small>Suggested title</small>{titles[0]}</p>
        ) : <p className="dash-opportunity-no-title">Content angle ready for review</p>}
      </div>
      <div className="dash-opportunity-score" aria-label={`${score(opportunity)} percent opportunity score`}>
        <strong>{score(opportunity)}%</strong>
      </div>
    </article>
  );
}

export default function OpportunityPanel({ opportunities, loading }) {
  return (
    <section className="dash-panel dash-opportunity-panel">
      <div className="dash-panel-heading">
        <h2><span aria-hidden="true">🏆</span> Best Content Opportunities</h2>
        <span className="dash-found-badge">{opportunities.length} found</span>
      </div>
      <div className="dash-opportunity-list">
        {loading ? [0, 1, 2, 3].map((item) => <span className="dash-skeleton-row" key={item} />) :
          opportunities.length > 0 ? opportunities.slice(0, 6).map((opportunity, index) => (
            <OpportunityRow key={`${opportunity.trend}-${index}`} opportunity={opportunity} index={index} />
          )) : (
            <div className="dash-empty-panel"><span aria-hidden="true">💡</span><strong>No opportunities found yet</strong><p>More content is needed to identify gaps and high-potential topics.</p></div>
          )}
      </div>
    </section>
  );
}
