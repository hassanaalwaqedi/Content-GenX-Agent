import { useEffect, useState } from 'react';
import { api } from '../api/client';

export default function Pipeline() {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [message, setMessage] = useState(null);

  const loadHistory = () => {
    api
      .getPipelineHistory(20)
      .then((data) => setHistory(data.runs || []))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadHistory(); }, []);

  const handleTrigger = async () => {
    setTriggering(true);
    setMessage(null);
    try {
      await api.triggerPipeline();
      setMessage({ type: 'success', text: 'Pipeline triggered successfully! Refresh in ~60s to see results.' });
      setTimeout(loadHistory, 5000);
    } catch (err) {
      setMessage({ type: 'error', text: err.message });
    } finally {
      setTriggering(false);
    }
  };

  const statusBadge = (status) => {
    const map = {
      completed: 'badge-green',
      completed_empty: 'badge-orange',
      completed_filtered: 'badge-orange',
      running: 'badge-blue',
      failed: 'badge-red',
      crashed: 'badge-red',
    };
    return map[status] || 'badge-purple';
  };

  return (
    <>
      <div className="page-header">
        <h2>Pipeline Control</h2>
        <p>Trigger data collection and view execution history</p>
      </div>

      {/* Trigger Section */}
      <div className="card" style={{ marginBottom: 'var(--space-xl)' }}>
        <div className="card-header">
          <span className="card-title">Run Pipeline</span>
        </div>
        <p style={{ color: '#8b90a0', fontSize: '0.8125rem', marginBottom: '1rem' }}>
          Triggers the full ETL pipeline: Ingest from YouTube &rarr; Process &amp; Score &rarr; AI Enrichment &rarr; Database.
          Runs in the background. Only one run can be active at a time.
        </p>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <button
            className="btn btn-primary"
            onClick={handleTrigger}
            disabled={triggering}
          >
            {triggering ? (
              <><span className="spinner" style={{ width: 14, height: 14, borderWidth: 2, marginRight: 6 }}></span>Running...</>
            ) : (
              <>&#9654; Run Pipeline</>
            )}
          </button>
          <button className="btn btn-secondary" onClick={loadHistory}>
            &#8635; Refresh History
          </button>
        </div>
        {message && (
          <div
            style={{
              marginTop: '1rem',
              padding: '0.75rem 1rem',
              borderRadius: 8,
              fontSize: '0.8125rem',
              fontWeight: 500,
              background: message.type === 'success' ? 'rgba(52,211,153,0.08)' : 'rgba(239,68,68,0.08)',
              color: message.type === 'success' ? '#34d399' : '#ef4444',
              border: `1px solid ${message.type === 'success' ? 'rgba(52,211,153,0.2)' : 'rgba(239,68,68,0.2)'}`,
            }}
          >
            {message.text}
          </div>
        )}
      </div>

      {/* History Table */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Execution History</span>
          <span className="badge badge-blue">{history.length} runs</span>
        </div>
        {loading ? (
          <div className="loading"><div className="spinner"></div>Loading history...</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Status</th>
                <th>Started</th>
                <th>Duration</th>
                <th>Ingested</th>
                <th>Processed</th>
                <th>Enriched</th>
                <th>Stored</th>
                <th>Triggered By</th>
              </tr>
            </thead>
            <tbody>
              {history.map((r) => (
                <tr key={r.id}>
                  <td className="number-cell">#{r.id}</td>
                  <td>
                    <span className={`badge ${statusBadge(r.status)}`}>
                      {r.status}
                    </span>
                  </td>
                  <td style={{ color: '#8b90a0', fontSize: '0.75rem' }}>
                    {r.started_at ? new Date(r.started_at).toLocaleString('de-DE') : '—'}
                  </td>
                  <td className="number-cell">
                    {r.elapsed_seconds != null ? `${r.elapsed_seconds.toFixed(1)}s` : '—'}
                  </td>
                  <td className="number-cell">{r.videos_ingested ?? '—'}</td>
                  <td className="number-cell">{r.videos_processed ?? '—'}</td>
                  <td className="number-cell">{r.videos_enriched ?? '—'}</td>
                  <td className="number-cell">{r.videos_stored ?? '—'}</td>
                  <td>
                    <span className="badge badge-purple">{r.triggered_by || 'manual'}</span>
                  </td>
                </tr>
              ))}
              {history.length === 0 && (
                <tr><td colSpan={9} style={{ textAlign: 'center', color: '#5e6375' }}>No pipeline runs recorded yet</td></tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
