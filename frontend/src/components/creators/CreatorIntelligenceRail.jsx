import { buildEngagementDistribution, formatPercent } from './creatorUtils';
import PlatformIcon from '../PlatformIcon';

function EngagementDistribution({ creators }) {
  const tiers = buildEngagementDistribution(creators);
  const total = creators.length || 1;
  const { stops } = tiers.reduce((result, tier) => {
    const start = (result.cursor / total) * 100;
    const end = ((result.cursor + tier.count) / total) * 100;
    return {
      cursor: result.cursor + tier.count,
      stops: [...result.stops, `${tier.color} ${start}% ${end}%`],
    };
  }, { cursor: 0, stops: [] });

  return (
    <section className="cr-rail-panel">
      <h2><span aria-hidden="true">♥</span> Engagement Distribution</h2>
      <div className="cr-donut-layout">
        <div className="cr-donut" style={{ background: `conic-gradient(${stops.join(', ') || '#263852 0 100%'})` }}><div><strong>{creators.length}</strong><small>creators</small></div></div>
        <div className="cr-donut-legend">
          {tiers.map((tier) => <div key={tier.key}><i style={{ background: tier.color }} /><span>{tier.label}</span><strong>{Math.round((tier.count / total) * 100)}%</strong></div>)}
        </div>
      </div>
    </section>
  );
}

function PlatformLeaders({ leaders }) {
  const maxCreators = Math.max(...leaders.map((leader) => leader.creators), 1);
  return (
    <section className="cr-rail-panel">
      <h2><span aria-hidden="true">◫</span> Platform Leaders</h2>
      <p className="cr-rail-caption">Derived from available top content</p>
      {leaders.length ? <div className="cr-platform-leaders">
        {leaders.slice(0, 4).map((leader) => <div key={leader.platform}>
          <div><PlatformIcon platform={leader.platform} size={16} /><span><strong>{leader.label}</strong><small>{leader.creators} {leader.creators === 1 ? 'creator' : 'creators'}</small></span><em>{formatPercent(leader.avgEngagement)}</em></div>
          <i><b style={{ width: `${(leader.creators / maxCreators) * 100}%`, background: leader.color }} /></i>
        </div>)}
      </div> : <p className="cr-rail-empty">Platform data appears when creator content is available.</p>}
    </section>
  );
}

function OpportunityNiches({ niches }) {
  return (
    <section className="cr-rail-panel">
      <h2><span aria-hidden="true">✦</span> Opportunity Niches</h2>
      {niches.length ? <ol className="cr-niche-list">{niches.map((niche) => <li key={niche.label}><span>{niche.label}</span><strong>{formatPercent(niche.averageFit, 0)}</strong><small>{niche.creatorCount} {niche.creatorCount === 1 ? 'creator' : 'creators'}</small></li>)}</ol> : <p className="cr-rail-empty">Topic coverage becomes available after enrichment.</p>}
    </section>
  );
}

export default function CreatorIntelligenceRail({ creators, platformLeaders, opportunityNiches }) {
  return <aside className="cr-intelligence-rail"><EngagementDistribution creators={creators} /><PlatformLeaders leaders={platformLeaders} /><OpportunityNiches niches={opportunityNiches} /></aside>;
}
