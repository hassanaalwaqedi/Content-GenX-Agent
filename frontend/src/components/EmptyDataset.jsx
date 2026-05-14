import { useNavigate } from 'react-router-dom';

export default function EmptyDataset({ message, datasetLabel }) {
  const navigate = useNavigate();

  return (
    <div className="empty-dataset">
      <div className="empty-dataset-icon">📭</div>
      <h3 className="empty-dataset-title">No Data in Current Workspace</h3>
      {datasetLabel && (
        <p className="empty-dataset-label">Dataset: {datasetLabel}</p>
      )}
      <p className="empty-dataset-message">
        {message || 'Your current workspace has no processed videos. Try running the pipeline with broader settings.'}
      </p>
      <div className="empty-dataset-tips">
        <span>💡 Tips:</span>
        <ul>
          <li>Add more regions in pipeline config</li>
          <li>Remove restrictive keyword filters</li>
          <li>Enable both shorts and long-form content</li>
          <li>Switch to a different dataset workspace</li>
        </ul>
      </div>
      <div className="empty-dataset-actions">
        <button className="btn-primary" onClick={() => navigate('/pipeline')}>
          Run Pipeline
        </button>
      </div>
    </div>
  );
}
