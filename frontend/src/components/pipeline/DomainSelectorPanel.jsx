import ScanConfigPanel from './ScanConfigPanel';
import { DOMAINS } from './pipelineUtils';

export default function DomainSelectorPanel({ categories, onToggle, onClear }) {
  return (
    <ScanConfigPanel step="3" title="Focus Content Domains" helper="Leave clear to scan all categories." badge={categories.length ? `${categories.length} selected` : 'All domains'}>
      <div className="pi-domain-grid">
        {DOMAINS.map((domain) => <button type="button" key={domain} className={categories.includes(domain) ? 'selected' : ''} onClick={() => onToggle(domain)}>{domain}</button>)}
      </div>
      {categories.length > 0 && <button type="button" className="pi-clear-selection" onClick={onClear}>Clear domain filter</button>}
    </ScanConfigPanel>
  );
}
