import ScanConfigPanel from './ScanConfigPanel';
import { REGIONS } from './pipelineUtils';

export default function MarketSelectorPanel({ regions, onToggle }) {
  return (
    <ScanConfigPanel step="1" title="Select Target Markets" helper="Choose up to 5 geographic markets." badge={`${regions.length}/5`}>
      <div className="pi-market-grid">
        {REGIONS.map((region) => {
          const selected = regions.includes(region.code);
          const maxed = !selected && regions.length >= 5;
          return <button type="button" key={region.code} className={selected ? 'selected' : ''} disabled={maxed} onClick={() => onToggle(region.code)}><span>{region.flag}</span>{region.label}</button>;
        })}
      </div>
    </ScanConfigPanel>
  );
}
