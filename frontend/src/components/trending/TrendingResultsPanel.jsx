import { Link } from 'react-router-dom';
import PlatformIcon from '../PlatformIcon';
import ContentThumbnail from './ContentThumbnail';
import { formatCompactNumber, formatPercentage, formatPublishedAt, getAvatarLabel, getContentTags, getMomentum, getTrendStatus } from './trendingUtils';

function CreatorIdentity({ video }) {
  return <div className="tr-creator"><span className="tr-avatar">{getAvatarLabel(video)}</span><div><strong>{video.channel || 'Unknown creator'}</strong><small>{video.source_region ? `${video.source_region} market` : 'Content creator'}</small></div></div>;
}

function MetricCell({ label, value, tone = '' }) {
  return <div className={`tr-metric-cell ${tone}`}><small>{label}</small><strong>{value}</strong></div>;
}

function TrendRow({ video, rank, onGenerate, onTranscript }) {
  const status = getTrendStatus(video);
  const tags = getContentTags(video, 3);
  const momentum = getMomentum(video);
  return <article className="tr-result-row">
    <span className={`tr-rank tr-rank-${rank <= 3 ? rank : 'rest'}`}>{rank}</span>
    <Link className="tr-row-content" to={`/video/${video.video_id}`}><ContentThumbnail video={video} /><div><strong>{video.title || 'Untitled content'}</strong><div className="tr-row-tags">{tags.map((tag) => <span key={tag}>#{tag}</span>)}</div></div></Link>
    <CreatorIdentity video={video} />
    <div className="tr-platform-cell"><PlatformIcon platform={video.platform} size={18} /><span>{video.platform || 'unknown'}</span></div>
    <MetricCell label="Views" value={formatCompactNumber(video.views)} />
    <MetricCell label="Engagement" value={formatPercentage(video.engagement_rate)} tone="green" />
    <MetricCell label="AI score" value={Number(video.score || 0).toFixed(2)} tone="blue" />
    <MetricCell label="Momentum" value={`+${momentum}%`} tone="green" />
    <MetricCell label="Published" value={formatPublishedAt(video.published_at)} />
    <div className="tr-row-actions"><span className={`tr-row-status ${status.tone}`}>{status.label}</span>{video.platform === 'youtube' && <button onClick={() => onTranscript(video)} aria-label="View transcript">▤</button>}<button onClick={() => onGenerate(video)} aria-label="Generate similar content">✦</button><button aria-label="More actions">•••</button></div>
  </article>;
}

function TrendGridCard({ video, rank, onGenerate, onTranscript }) {
  const status = getTrendStatus(video);
  return <article className="tr-grid-card"><div className="tr-grid-card-media"><ContentThumbnail video={video} large /><span className={`tr-rank tr-rank-${rank <= 3 ? rank : 'rest'}`}>{rank}</span><span className={`tr-row-status ${status.tone}`}>{status.label}</span></div><div className="tr-grid-card-body"><p><PlatformIcon platform={video.platform} size={14} /> {video.channel || 'Unknown creator'}</p><Link to={`/video/${video.video_id}`}>{video.title || 'Untitled content'}</Link><div className="tr-grid-metrics"><span>{formatCompactNumber(video.views)} views</span><strong>{formatPercentage(video.engagement_rate)} engagement</strong><span>AI {Number(video.score || 0).toFixed(2)}</span></div><div className="tr-grid-card-actions"><Link to={`/video/${video.video_id}`}>Details</Link>{video.platform === 'youtube' && <button onClick={() => onTranscript(video)}>Transcript</button>}<button onClick={() => onGenerate(video)}>✦ Generate</button></div></div></article>;
}

export function TrendingSkeleton() {
  return <div className="tr-skeleton-list">{Array.from({ length: 6 }).map((_, index) => <div className="tr-result-skeleton" key={index} />)}</div>;
}

export function TrendingEmptyState() {
  return <div className="tr-results-empty"><span>⌕</span><h3>No trending content matches this view</h3><p>Adjust the filters or run a new intelligence scan to discover momentum signals.</p></div>;
}

export function TrendingErrorState({ message, onRetry }) {
  return <div className="tr-results-empty tr-results-error"><span>⚠</span><h3>Trending data is unavailable</h3><p>{message}</p><button onClick={onRetry}>Try again</button></div>;
}

export default function TrendingResultsPanel({ videos, viewMode, onViewModeChange, sortMode, onSortModeChange, loading, error, onRetry, onGenerate, onTranscript }) {
  return <section className="tr-panel tr-results-panel"><div className="tr-results-header"><div><h2>Trending Content</h2><span>{videos.length} results</span></div><div className="tr-results-controls"><div className="tr-mode-toggle"><button onClick={() => onViewModeChange('grid')} className={viewMode === 'grid' ? 'active' : ''}>▦ Grid</button><button onClick={() => onViewModeChange('list')} className={viewMode === 'list' ? 'active' : ''}>☷ List</button></div><label>Sort by:<select value={sortMode} onChange={(event) => onSortModeChange(event.target.value)}><option value="engagement">Engagement rate</option><option value="momentum">Momentum</option><option value="score">AI score</option><option value="views">Views</option><option value="recent">Most recent</option></select></label></div></div>{loading ? <TrendingSkeleton /> : error ? <TrendingErrorState message={error} onRetry={onRetry} /> : !videos.length ? <TrendingEmptyState /> : viewMode === 'grid' ? <div className="tr-results-grid">{videos.map((video, index) => <TrendGridCard video={video} rank={index + 1} key={video.video_id} onGenerate={onGenerate} onTranscript={onTranscript} />)}</div> : <div className="tr-list"><div className="tr-list-labels"><span>#</span><span>Content</span><span>Creator</span><span>Platform</span><span>Views</span><span>Engagement</span><span>AI score</span><span title="Derived from the current AI score and engagement rate">Momentum</span><span>Published</span><span /></div>{videos.map((video, index) => <TrendRow video={video} rank={index + 1} key={video.video_id} onGenerate={onGenerate} onTranscript={onTranscript} />)}</div>}</section>;
}
