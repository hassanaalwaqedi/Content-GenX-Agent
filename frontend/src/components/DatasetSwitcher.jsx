import { useState, useRef, useEffect } from 'react';
import { useDataset } from '../context/DatasetContext';

export default function DatasetSwitcher() {
  const { activeDataset, datasetStats, datasets, switchDataset, loading, datasetId, setAllData, allData } = useDataset();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  // Close on outside click
  useEffect(() => {
    function handleClick(e) {
      if (ref.current && !ref.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const label = allData
    ? '📂 All Historical Data'
    : activeDataset
      ? (activeDataset.dataset_label || `Run #${activeDataset.id}`)
      : 'No Active Dataset';
  const videoCount = datasetStats?.total_videos ?? activeDataset?.videos_stored ?? 0;

  return (
    <div className="dataset-switcher" ref={ref}>
      <button
        className="dataset-switcher-trigger"
        onClick={() => setOpen(!open)}
        disabled={loading}
        id="dataset-switcher-btn"
      >
        <div className="dataset-switcher-info">
          <span className="dataset-switcher-dot" />
          <div className="dataset-switcher-text">
            <span className="dataset-switcher-label">{label}</span>
            <span className="dataset-switcher-meta">
              {videoCount} video{videoCount !== 1 ? 's' : ''} 
              {activeDataset?.config_content_type && activeDataset.config_content_type !== 'all'
                ? ` · ${activeDataset.config_content_type}`
                : ''}
            </span>
          </div>
        </div>
        <span className={`dataset-switcher-arrow ${open ? 'open' : ''}`}>▾</span>
      </button>

      {open && (
        <div className="dataset-switcher-dropdown">
          <div className="dataset-switcher-dropdown-header">Workspace Datasets</div>
          {datasets.length === 0 && (
            <div className="dataset-switcher-empty">
              No completed pipeline runs yet.
            </div>
          )}
          <button
            className={`dataset-switcher-item ${datasetId === null ? 'active' : ''}`}
            onClick={() => { setAllData(); setOpen(false); }}
          >
            <span className="dataset-item-indicator">{datasetId === null ? '🟢' : '⚪'}</span>
            <div className="dataset-item-info">
              <span className="dataset-item-label">📂 All Historical Data</span>
              <span className="dataset-item-meta">View all videos (no scoping)</span>
            </div>
          </button>
          {datasets.map((ds) => (
            <button
              key={ds.id}
              className={`dataset-switcher-item ${ds.is_active_dataset ? 'active' : ''}`}
              onClick={() => {
                switchDataset(ds.id);
                setOpen(false);
              }}
            >
              <span className="dataset-item-indicator">
                {ds.is_active_dataset ? '🟢' : '⚪'}
              </span>
              <div className="dataset-item-info">
                <span className="dataset-item-label">
                  {ds.dataset_label || `Run #${ds.id}`}
                </span>
                <span className="dataset-item-meta">
                  {ds.videos_stored || 0} videos · {new Date(ds.started_at).toLocaleDateString()}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
