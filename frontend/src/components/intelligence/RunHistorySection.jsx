import { useState, useMemo } from 'react';

const PLATFORM_NAMES = { youtube: 'YouTube', reddit: 'Reddit', tiktok: 'TikTok', instagram: 'Instagram' };
const PLATFORM_ICONS = { youtube: '▶️', reddit: '💬', tiktok: '🎵', instagram: '📸' };

const STATUS_LABEL = {
  completed: '✓ Completed',
  completed_empty: '⚠ No Results',
  completed_filtered: '⚠ Filtered',
  running: '● Running',
  failed: '✕ Failed',
  crashed: '✕ Crashed',
};

function EnhancedRunCard({ run, onRerun }) {
  const [expanded, setExpanded] = useState(false);
  const runtime = run.elapsed_seconds != null ? `${run.elapsed_seconds.toFixed(1)}s` : '—';
  const date = run.started_at ? new Date(run.started_at) : null;

  // Derive scan depth from metrics
  const ingested = run.videos_ingested ?? 0;
  const depth = ingested > 100 ? 'Deep' : ingested > 30 ? 'Standard' : ingested > 0 ? 'Focused' : '—';

  // Config data if available
  const platforms = run.config_platforms || run.platforms || [];
  const regions = run.config_regions || run.regions || [];
  const keywords = run.config_keywords || run.keywords || [];

  return (
    <div className={`rhs-card ${run.status}`}>
      <div className="rhs-card-top">
        <div className="rhs-card-id-row">
          <span className="rhs-card-id">Scan #{run.id}</span>
          {platforms.length > 0 && (
            <div className="rhs-card-platforms">
              {platforms.map(p => (
                <span key={p} className="rhs-platform-badge" data-platform={p}>
                  {PLATFORM_ICONS[p] || '⚡'}
                </span>
              ))}
            </div>
          )}
        </div>
        <span className={`rhs-card-status ${run.status}`}>{STATUS_LABEL[run.status] || run.status}</span>
      </div>

      <div className="rhs-card-metrics">
        <div className="rhs-metric">
          <div className="rhs-metric-val">{run.videos_ingested ?? '—'}</div>
          <div className="rhs-metric-label">Ingested</div>
        </div>
        <div className="rhs-metric">
          <div className="rhs-metric-val">{run.videos_processed ?? '—'}</div>
          <div className="rhs-metric-label">Scored</div>
        </div>
        <div className="rhs-metric">
          <div className="rhs-metric-val">{run.videos_enriched ?? '—'}</div>
          <div className="rhs-metric-label">AI Analyzed</div>
        </div>
        <div className="rhs-metric">
          <div className="rhs-metric-val">{run.videos_stored ?? '—'}</div>
          <div className="rhs-metric-label">Stored</div>
        </div>
      </div>

      <div className="rhs-card-meta">
        <span className="rhs-meta-item">⏱ {runtime}</span>
        <span className="rhs-meta-item">📊 {depth}</span>
        <span className="rhs-meta-item">{date ? date.toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'}</span>
        <span className="badge badge-purple" style={{ fontSize: '0.55rem' }}>{run.triggered_by || 'manual'}</span>
      </div>

      {/* Expandable details */}
      <div className="rhs-card-actions">
        <button className="rhs-expand-btn" onClick={() => setExpanded(!expanded)}>
          {expanded ? '▾ Less' : '▸ Details'}
        </button>
        {onRerun && run.status !== 'running' && (
          <button className="rhs-rerun-btn" onClick={() => onRerun(run)}>↻ Rerun</button>
        )}
      </div>

      {expanded && (
        <div className="rhs-card-details">
          {regions.length > 0 && (
            <div className="rhs-detail-row">
              <span className="rhs-detail-label">Markets</span>
              <span className="rhs-detail-value">{regions.join(', ')}</span>
            </div>
          )}
          {keywords.length > 0 && (
            <div className="rhs-detail-row">
              <span className="rhs-detail-label">Signals</span>
              <div className="rhs-detail-tags">
                {keywords.map(k => <span key={k} className="rhs-detail-tag">{k}</span>)}
              </div>
            </div>
          )}
          {platforms.length > 0 && (
            <div className="rhs-detail-row">
              <span className="rhs-detail-label">Platforms</span>
              <span className="rhs-detail-value">{platforms.map(p => PLATFORM_NAMES[p] || p).join(', ')}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function RunHistorySection({ history, loading, onRefresh, onRerun }) {
  const [statusFilter, setStatusFilter] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState('newest');

  const filtered = useMemo(() => {
    let items = [...history];
    if (statusFilter !== 'all') {
      items = items.filter(r => {
        if (statusFilter === 'completed') return r.status === 'completed';
        if (statusFilter === 'failed') return r.status === 'failed' || r.status === 'crashed';
        if (statusFilter === 'warning') return r.status === 'completed_empty' || r.status === 'completed_filtered';
        if (statusFilter === 'running') return r.status === 'running';
        return true;
      });
    }
    if (searchTerm.trim()) {
      const q = searchTerm.toLowerCase();
      items = items.filter(r => String(r.id).includes(q) || (r.triggered_by || '').toLowerCase().includes(q));
    }
    if (sortBy === 'oldest') items.reverse();
    if (sortBy === 'runtime') items.sort((a, b) => (b.elapsed_seconds || 0) - (a.elapsed_seconds || 0));
    return items;
  }, [history, statusFilter, searchTerm, sortBy]);

  const statusCounts = useMemo(() => {
    const counts = { all: history.length, completed: 0, failed: 0, warning: 0, running: 0 };
    history.forEach(r => {
      if (r.status === 'completed') counts.completed++;
      else if (r.status === 'failed' || r.status === 'crashed') counts.failed++;
      else if (r.status === 'completed_empty' || r.status === 'completed_filtered') counts.warning++;
      else if (r.status === 'running') counts.running++;
    });
    return counts;
  }, [history]);

  return (
    <div className="rhs-section">
      <div className="rhs-header">
        <h3 className="rhs-title"><span>📋</span> Recent Intelligence Runs</h3>
        <div className="rhs-header-actions">
          <span className="badge badge-blue">{history.length} runs</span>
          <button className="btn btn-secondary" onClick={onRefresh} style={{ fontSize: '0.7rem', padding: '4px 12px' }}>🔄</button>
        </div>
      </div>

      {/* Filter toolbar */}
      {history.length > 0 && (
        <div className="rhs-toolbar">
          <div className="rhs-status-filters">
            {[
              { key: 'all', label: 'All' },
              { key: 'completed', label: '✓ Success', cls: 'green' },
              { key: 'failed', label: '✕ Failed', cls: 'red' },
              { key: 'warning', label: '⚠ Warning', cls: 'orange' },
            ].map(f => (
              <button
                key={f.key}
                className={`rhs-filter-btn ${statusFilter === f.key ? 'active' : ''} ${f.cls || ''}`}
                onClick={() => setStatusFilter(f.key)}
              >
                {f.label} {statusCounts[f.key] > 0 && <span className="rhs-filter-count">{statusCounts[f.key]}</span>}
              </button>
            ))}
          </div>
          <div className="rhs-toolbar-right">
            <input
              className="rhs-search"
              placeholder="Search scans..."
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
            />
            <select className="rhs-sort" value={sortBy} onChange={e => setSortBy(e.target.value)}>
              <option value="newest">Newest</option>
              <option value="oldest">Oldest</option>
              <option value="runtime">Runtime</option>
            </select>
          </div>
        </div>
      )}

      {/* Cards */}
      {loading ? (
        <div className="loading"><div className="spinner" />Loading scan history...</div>
      ) : filtered.length === 0 ? (
        <div className="rhs-empty">
          <span className="rhs-empty-icon">{history.length === 0 ? '🚀' : '🔍'}</span>
          <h4>{history.length === 0 ? 'No intelligence scans yet' : 'No matching scans'}</h4>
          <p>{history.length === 0 ? 'Launch your first scan above to start gathering market intelligence' : 'Try adjusting your filters'}</p>
        </div>
      ) : (
        <div className="rhs-cards">
          {filtered.map(r => <EnhancedRunCard key={r.id} run={r} onRerun={onRerun} />)}
        </div>
      )}
    </div>
  );
}
