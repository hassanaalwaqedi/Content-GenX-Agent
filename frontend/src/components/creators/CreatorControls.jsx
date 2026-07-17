import { CREATOR_TABS } from './creatorUtils';

export default function CreatorControls({
  activeTab, onTabChange, searchTerm, onSearchChange, selectedTrend, onTrendChange, trends,
  sortMode, onSortChange, moreFilters, onToggleMoreFilters, minVideos, onMinVideosChange,
  minEngagement, onMinEngagementChange, onClearFilters,
}) {
  return (
    <section className="cr-controls" aria-label="Creator filters and views">
      <div className="cr-tabs" role="tablist" aria-label="Creator intelligence views">
        {CREATOR_TABS.map((tab) => (
          <button key={tab.id} role="tab" type="button" aria-selected={activeTab === tab.id} className={activeTab === tab.id ? 'active' : ''} onClick={() => onTabChange(tab.id)}>{tab.label}</button>
        ))}
      </div>
      <div className="cr-controls-main">
        <label className="cr-search-control">
          <span aria-hidden="true">⌕</span>
          <input value={searchTerm} onChange={(event) => onSearchChange(event.target.value)} placeholder="Search creators or topics…" aria-label="Search creators or topics" />
        </label>
        <select value={selectedTrend} onChange={(event) => onTrendChange(event.target.value)} aria-label="Filter by trend">
          <option value="">All trends</option>
          {trends.map((trend) => <option key={trend} value={trend}>{trend}</option>)}
        </select>
        <select value={sortMode} onChange={(event) => onSortChange(event.target.value)} aria-label="Sort creators">
          <option value="score">AI score</option>
          <option value="engagement">Engagement</option>
          <option value="dominance">Trend dominance</option>
          <option value="opportunity">Opportunity fit</option>
          <option value="growth">Growth signal</option>
          <option value="views">Views</option>
        </select>
        <button className={`cr-filter-toggle ${moreFilters ? 'active' : ''}`} type="button" onClick={onToggleMoreFilters}>☷ Filters</button>
      </div>
      {moreFilters && (
        <div className="cr-advanced-controls">
          <label>Minimum content
            <select value={minVideos} onChange={(event) => onMinVideosChange(Number(event.target.value))}>
              <option value="1">1+ items</option>
              <option value="2">2+ items</option>
              <option value="3">3+ items</option>
              <option value="5">5+ items</option>
            </select>
          </label>
          <label>Minimum engagement
            <select value={minEngagement} onChange={(event) => onMinEngagementChange(Number(event.target.value))}>
              <option value="0">Any rate</option>
              <option value="0.02">2%+</option>
              <option value="0.05">5%+</option>
              <option value="0.1">10%+</option>
            </select>
          </label>
          <button type="button" onClick={onClearFilters}>Clear filters</button>
        </div>
      )}
    </section>
  );
}
