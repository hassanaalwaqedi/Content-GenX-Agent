function Chip({ children }) {
  return <span className="dash-workspace-chip">{children}</span>;
}

export default function WorkspaceContextBar({ dataset, totalVideos }) {
  const regions = dataset?.config_regions || [];
  const categories = dataset?.config_categories || [];
  const keywords = dataset?.config_keywords || [];
  const contentType = dataset?.config_content_type;

  return (
    <section className="dash-workspace-bar" aria-label="Active workspace">
      <div className="dash-workspace-status">
        <span className="dash-status-dot" />
        Active Workspace
      </div>
      <div className="dash-workspace-divider" />
      <div className="dash-workspace-chips">
        {regions.length > 0 && <Chip><span aria-hidden="true">🌐</span>{regions.join(', ')}</Chip>}
        {categories.length > 0 && <Chip><span aria-hidden="true">🏷</span>{categories.join(', ')}</Chip>}
        {keywords.length > 0 && <Chip><span aria-hidden="true">🔑</span>{keywords.join(', ')}</Chip>}
        {contentType && contentType !== 'all' && <Chip><span aria-hidden="true">◉</span>{contentType}</Chip>}
        <Chip><span aria-hidden="true">▥</span>{totalVideos} content item{totalVideos === 1 ? '' : 's'}</Chip>
      </div>
    </section>
  );
}
