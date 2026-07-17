import ContentFormatPanel from './ContentFormatPanel';
import DomainSelectorPanel from './DomainSelectorPanel';
import MarketSelectorPanel from './MarketSelectorPanel';
import PlatformSelectorPanel from './PlatformSelectorPanel';
import TrendSignalsPanel from './TrendSignalsPanel';

export default function ScanConfigurationWorkspace({ config, connectors, keywordInput, keywordError, suggestions, onToggleRegion, onTogglePlatform, onToggleCategory, onClearCategories, onKeywordInputChange, onAddKeyword, onRemoveKeyword, onContentTypeChange }) {
  return (
    <section className="pi-config-workspace" aria-label="Scan configuration">
      <MarketSelectorPanel regions={config.regions} onToggle={onToggleRegion} />
      <PlatformSelectorPanel platforms={config.platforms} connectors={connectors} onToggle={onTogglePlatform} />
      <DomainSelectorPanel categories={config.categories} onToggle={onToggleCategory} onClear={onClearCategories} />
      <TrendSignalsPanel keywords={config.keywords} input={keywordInput} onInputChange={onKeywordInputChange} onAdd={onAddKeyword} onRemove={onRemoveKeyword} suggestions={suggestions} error={keywordError} />
      <ContentFormatPanel value={config.content_type} onChange={onContentTypeChange} />
    </section>
  );
}
