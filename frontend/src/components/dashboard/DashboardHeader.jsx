export default function DashboardHeader({ refreshing, onRefresh, onOpenPipeline }) {
  return (
    <header className="dash-header">
      <div>
        <h1>Intelligence Center</h1>
        <p>AI-powered content trend analysis &amp; opportunity detection</p>
      </div>
      <div className="dash-header-actions">
        <button className="dash-action-button" onClick={onRefresh} disabled={refreshing}>
          <span aria-hidden="true">↻</span>
          {refreshing ? 'Refreshing' : 'Refresh'}
        </button>
        <button className="dash-action-button" onClick={onOpenPipeline}>
          <span aria-hidden="true">ϟ</span>
          Pipeline
        </button>
      </div>
    </header>
  );
}
