export default function TopContentHeader({ activeDataset, count, onRefresh, onExport, loading }) {
  const workspace = activeDataset?.name || activeDataset?.label || 'All historical data';
  return (
    <header className="tc-page-header">
      <div>
        <p className="tc-eyebrow">Content discovery</p>
        <h1>Top Content</h1>
        <p>Discover the highest-performing content, emerging formats, and reusable creative opportunities.</p>
      </div>
      <div className="tc-header-actions">
        <div className="tc-workspace-control" title={workspace}>
          <span className="tc-live-dot" />
          <div><small>Active workspace</small><strong>{workspace}</strong></div>
          <span>⌄</span>
        </div>
        <div className="tc-header-count"><strong>{count.toLocaleString()}</strong><span>content items</span></div>
        <button className="tc-header-button" onClick={onRefresh} disabled={loading}>⟳ <span>{loading ? 'Refreshing' : 'Refresh'}</span></button>
        <button className="tc-header-button" onClick={onExport} disabled={!count}>▤ <span>Export PDF</span></button>
      </div>
    </header>
  );
}
