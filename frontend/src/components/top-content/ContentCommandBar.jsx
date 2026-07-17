import { ALL_PLATFORMS, getPlatformIcon, getPlatformLabel } from '../../utils/platform';

function FilterChip({ children, onRemove }) {
  return <span className="tc-filter-chip">{children}<button onClick={onRemove} aria-label={`Remove ${children} filter`}>×</button></span>;
}

export default function ContentCommandBar({
  searchTerm, onSearchChange, selectedNiche, onNicheChange, niches, days, onDaysChange,
  platformFilter, onPlatformChange, minScore, onMinScoreChange, viewMode, onViewModeChange,
  sortMode, onSortModeChange, trendFilter, onClearTrend, onReset,
}) {
  const activeFilters = [
    trendFilter && <FilterChip key="trend" onRemove={onClearTrend}>Trend: {trendFilter}</FilterChip>,
    selectedNiche && <FilterChip key="niche" onRemove={() => onNicheChange('')}>Category: {selectedNiche}</FilterChip>,
    platformFilter && <FilterChip key="platform" onRemove={() => onPlatformChange('')}>{getPlatformLabel(platformFilter)}</FilterChip>,
    minScore > 0 && <FilterChip key="score" onRemove={() => onMinScoreChange(0)}>Score ≥ {minScore.toFixed(2)}</FilterChip>,
    searchTerm && <FilterChip key="search" onRemove={() => onSearchChange('')}>Search: {searchTerm}</FilterChip>,
  ].filter(Boolean);

  return (
    <section className="tc-command-bar" aria-label="Top content controls">
      <div className="tc-command-main">
        <label className="tc-search-field"><span>⌕</span><input value={searchTerm} onChange={(event) => onSearchChange(event.target.value)} placeholder="Search by title, creator, keyword, hashtag..." /></label>
        <select value={selectedNiche} onChange={(event) => onNicheChange(event.target.value)} aria-label="Category">
          <option value="">All categories</option>
          {niches.map((niche) => <option key={niche} value={niche}>{niche}</option>)}
        </select>
        <select value={days} onChange={(event) => onDaysChange(Number(event.target.value))} aria-label="Date range">
          <option value={7}>Last 7 days</option><option value={30}>Last 30 days</option><option value={90}>Last 90 days</option><option value={180}>Last 180 days</option><option value={365}>Last 365 days</option>
        </select>
        <select value={platformFilter} onChange={(event) => onPlatformChange(event.target.value)} aria-label="Platform">
          <option value="">All platforms</option>
          {ALL_PLATFORMS.map((platform) => <option key={platform} value={platform}>{getPlatformIcon(platform)} {getPlatformLabel(platform)}</option>)}
        </select>
        <label className="tc-score-control"><span>Min score <strong>{minScore.toFixed(2)}</strong></span><input type="range" min="0" max="1" step="0.05" value={minScore} onChange={(event) => onMinScoreChange(Number(event.target.value))} /></label>
      </div>
      <div className="tc-command-footer">
        <div className="tc-active-filters">
          <span>Active filters:</span>{activeFilters.length ? activeFilters : <em>None</em>}
          {activeFilters.length > 0 && <button onClick={onReset}>Clear all</button>}
        </div>
        <div className="tc-view-controls">
          <select value={sortMode} onChange={(event) => onSortModeChange(event.target.value)} aria-label="Sort content"><option value="score">Sort: AI score</option><option value="views">Sort: Views</option><option value="engagement">Sort: Engagement</option><option value="recent">Sort: Most recent</option></select>
          <div className="tc-view-switch" aria-label="Display mode"><button onClick={() => onViewModeChange('grid')} className={viewMode === 'grid' ? 'active' : ''} aria-label="Grid view">▦ Grid</button><button onClick={() => onViewModeChange('list')} className={viewMode === 'list' ? 'active' : ''} aria-label="List view">☷ List</button></div>
        </div>
      </div>
    </section>
  );
}
