import PlatformIcon from '../PlatformIcon';
import { compactNumber, relativeTime } from './redditData';

export default function RedditPageHeader({ overview, health, refreshing, scanning, onRefresh, onExport, onScan }) {
  const connector = health?.connector;
  return <header className="reddit-page-header">
    <div className="reddit-title-block">
      <span className="reddit-title-icon"><PlatformIcon platform="reddit" size={32} color="#ff5a1f" /></span>
      <div><h1>Reddit Intelligence</h1><p>Discover rising communities, emerging discussions, pain points, and opportunity signals across Reddit.</p><div className="reddit-header-meta"><span className={`status-dot ${connector?.status === 'healthy' ? 'online' : ''}`} /> <span>{connector?.status === 'healthy' ? 'Reddit connector online' : 'Connector status pending'}</span><b>•</b><span>{compactNumber(overview?.posts_analyzed)} indexed posts</span><b>•</b><span>Updated {relativeTime(overview?.last_indexed_at)}</span></div></div>
    </div>
    <div className="reddit-header-actions"><button type="button" onClick={onRefresh} disabled={refreshing}>{refreshing ? '↻ Refreshing' : '↻ Refresh'}</button><button type="button" onClick={onExport}>⇩ Export</button><button className="reddit-scan-button" type="button" onClick={onScan} disabled={scanning}>{scanning ? '◌ Scan accepted' : '✦ Run Reddit Scan'}</button><button className="reddit-more-button" type="button" aria-label="More Reddit actions">⋮</button></div>
  </header>;
}
