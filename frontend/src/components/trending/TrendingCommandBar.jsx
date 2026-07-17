import { ALL_PLATFORMS, getPlatformIcon, getPlatformLabel } from '../../utils/platform';

function FilterChip({ children, onRemove }) {
  return <span className="tr-filter-chip">{children}<button onClick={onRemove} aria-label={`Remove ${children} filter`}>×</button></span>;
}

export default function TrendingCommandBar({
  searchTerm, onSearchChange, days, onDaysChange, platform, onPlatformChange, minScore, onMinScoreChange,
  category, onCategoryChange, contentType, onContentTypeChange, categories, resultCount, moreFilters, onMoreFilters,
  onClearAll,
}) {
  const chips = [
    <FilterChip key="days" onRemove={() => onDaysChange(90)}>Last {days} days</FilterChip>,
    platform && <FilterChip key="platform" onRemove={() => onPlatformChange('')}>{getPlatformLabel(platform)}</FilterChip>,
    category && <FilterChip key="category" onRemove={() => onCategoryChange('')}>{category}</FilterChip>,
    contentType && <FilterChip key="type" onRemove={() => onContentTypeChange('')}>{contentType}</FilterChip>,
    minScore > 0 && <FilterChip key="score" onRemove={() => onMinScoreChange(0)}>Min score: {minScore.toFixed(2)}</FilterChip>,
    searchTerm && <FilterChip key="search" onRemove={() => onSearchChange('')}>Search: {searchTerm}</FilterChip>,
  ].filter(Boolean);
  return (
    <section className="tr-command-bar" aria-label="Trending content controls">
      <div className="tr-command-main">
        <label className="tr-search"><span>⌕</span><input value={searchTerm} onChange={(event) => onSearchChange(event.target.value)} placeholder="Search by title, creator, keyword, hashtag..." /></label>
        <select value={days} onChange={(event) => onDaysChange(Number(event.target.value))} aria-label="Date range"><option value={7}>Last 7 days</option><option value={14}>Last 14 days</option><option value={30}>Last 30 days</option><option value={60}>Last 60 days</option><option value={90}>Last 90 days</option><option value={180}>Last 180 days</option><option value={365}>Last 365 days</option></select>
        <select value={platform} onChange={(event) => onPlatformChange(event.target.value)} aria-label="Platform"><option value="">All platforms</option>{ALL_PLATFORMS.map((item) => <option key={item} value={item}>{getPlatformIcon(item)} {getPlatformLabel(item)}</option>)}</select>
        <span className="tr-result-badge">{resultCount} trending</span>
        <button className={`tr-more-filters ${moreFilters ? 'active' : ''}`} onClick={onMoreFilters}>More filters <span>☷</span></button>
      </div>
      {moreFilters && <div className="tr-advanced-filters"><select value={category} onChange={(event) => onCategoryChange(event.target.value)} aria-label="Content category"><option value="">All categories</option>{categories.map((item) => <option value={item} key={item}>{item}</option>)}</select><select value={contentType} onChange={(event) => onContentTypeChange(event.target.value)} aria-label="Content type"><option value="">All content types</option><option value="shorts">Shorts</option><option value="video">Videos</option><option value="post">Posts</option></select><label className="tr-score-filter"><span>Minimum AI score <strong>{minScore.toFixed(2)}</strong></span><input type="range" min="0" max="1" step="0.05" value={minScore} onChange={(event) => onMinScoreChange(Number(event.target.value))} /></label></div>}
      <div className="tr-active-filters"><span>Active filters:</span>{chips}<button onClick={onClearAll}>⌫ Clear all</button></div>
    </section>
  );
}
