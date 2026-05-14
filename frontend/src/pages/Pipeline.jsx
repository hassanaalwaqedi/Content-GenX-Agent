import { useEffect, useState, useCallback } from 'react';
import { api } from '../api/client';

const ALL_REGIONS = [
  { code: 'US', label: '🇺🇸 United States' },
  { code: 'GB', label: '🇬🇧 United Kingdom' },
  { code: 'CA', label: '🇨🇦 Canada' },
  { code: 'DE', label: '🇩🇪 Germany' },
  { code: 'FR', label: '🇫🇷 France' },
  { code: 'AU', label: '🇦🇺 Australia' },
  { code: 'AE', label: '🇦🇪 UAE' },
  { code: 'JP', label: '🇯🇵 Japan' },
  { code: 'KR', label: '🇰🇷 South Korea' },
  { code: 'BR', label: '🇧🇷 Brazil' },
  { code: 'MX', label: '🇲🇽 Mexico' },
  { code: 'SA', label: '🇸🇦 Saudi Arabia' },
  { code: 'TR', label: '🇹🇷 Turkey' },
];

const ALL_CATEGORIES = [
  'music', 'gaming', 'sports', 'entertainment', 'education',
  'science & technology', 'news & politics', 'comedy', 'howto & style',
  'people & blogs', 'film & animation', 'travel & events',
];

const DEFAULT_CONFIG = {
  name: 'Custom',
  regions: ['US', 'GB', 'CA', 'DE', 'FR', 'AU', 'AE'],
  platforms: ['youtube'],
  categories: [],
  keywords: [],
  content_type: 'all',
  is_preset: false,
};

export default function Pipeline() {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [message, setMessage] = useState(null);
  const [savedConfigs, setSavedConfigs] = useState([]);
  const [activeConfigId, setActiveConfigId] = useState(null);
  const [keywordInput, setKeywordInput] = useState('');
  const [presetName, setPresetName] = useState('');
  const [showPresetSave, setShowPresetSave] = useState(false);

  // Config form state
  const [config, setConfig] = useState({ ...DEFAULT_CONFIG });

  const loadHistory = useCallback(() => {
    api.getPipelineHistory(20)
      .then((data) => setHistory(data.runs || []))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, []);

  const loadConfigs = useCallback(() => {
    api.listPipelineConfigs()
      .then((data) => setSavedConfigs(data.configs || []))
      .catch((err) => console.error(err));
  }, []);

  const loadLastUsed = useCallback(() => {
    api.getLastUsedConfig()
      .then((data) => {
        if (data.config) {
          setConfig(data.config);
          setActiveConfigId(data.config.id);
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    loadHistory();
    loadConfigs();
    loadLastUsed();
  }, [loadHistory, loadConfigs, loadLastUsed]);

  const handleTrigger = async () => {
    setTriggering(true);
    setMessage(null);
    try {
      // Save config first, then run pipeline with that config
      const saveResult = await api.savePipelineConfig(config);
      const configId = saveResult.id;
      setActiveConfigId(configId);
      await api.triggerPipeline(null, configId);
      setMessage({ type: 'success', text: `Pipeline triggered with config #${configId}. Refresh in ~60s.` });
      loadConfigs();
      setTimeout(loadHistory, 5000);
    } catch (err) {
      setMessage({ type: 'error', text: err.message });
    } finally {
      setTriggering(false);
    }
  };

  const handleSavePreset = async () => {
    if (!presetName.trim()) return;
    try {
      await api.savePipelineConfig({ ...config, name: presetName.trim(), is_preset: true });
      setShowPresetSave(false);
      setPresetName('');
      loadConfigs();
      setMessage({ type: 'success', text: `Preset "${presetName}" saved!` });
    } catch (err) {
      setMessage({ type: 'error', text: err.message });
    }
  };

  const handleLoadConfig = (cfg) => {
    setConfig({
      regions: cfg.regions || DEFAULT_CONFIG.regions,
      platforms: cfg.platforms || DEFAULT_CONFIG.platforms,
      categories: cfg.categories || [],
      keywords: cfg.keywords || [],
      content_type: cfg.content_type || 'all',
      name: cfg.name || 'Custom',
      is_preset: false,
    });
    setActiveConfigId(cfg.id);
  };

  const handleDeleteConfig = async (id) => {
    try {
      await api.deletePipelineConfig(id);
      loadConfigs();
      if (activeConfigId === id) setActiveConfigId(null);
    } catch (err) {
      setMessage({ type: 'error', text: err.message });
    }
  };

  const toggleRegion = (code) => {
    setConfig((prev) => {
      const regions = prev.regions.includes(code)
        ? prev.regions.filter((r) => r !== code)
        : prev.regions.length < 5
          ? [...prev.regions, code]
          : prev.regions;
      return { ...prev, regions };
    });
  };

  const toggleCategory = (cat) => {
    setConfig((prev) => {
      const categories = prev.categories.includes(cat)
        ? prev.categories.filter((c) => c !== cat)
        : [...prev.categories, cat];
      return { ...prev, categories };
    });
  };

  const togglePlatform = (p) => {
    setConfig((prev) => {
      const platforms = prev.platforms.includes(p)
        ? prev.platforms.filter((x) => x !== p)
        : [...prev.platforms, p];
      return { ...prev, platforms: platforms.length > 0 ? platforms : prev.platforms };
    });
  };

  const addKeyword = () => {
    const kw = keywordInput.trim().replace(/[^\w\s-]/g, '');
    if (kw && !config.keywords.includes(kw) && config.keywords.length < 10) {
      setConfig((prev) => ({ ...prev, keywords: [...prev.keywords, kw] }));
      setKeywordInput('');
    }
  };

  const removeKeyword = (kw) => {
    setConfig((prev) => ({ ...prev, keywords: prev.keywords.filter((k) => k !== kw) }));
  };

  const handleReset = () => {
    setConfig({ ...DEFAULT_CONFIG });
    setActiveConfigId(null);
  };

  const statusBadge = (status) => {
    const map = {
      completed: 'badge-green', completed_empty: 'badge-orange',
      completed_filtered: 'badge-orange', running: 'badge-blue',
      failed: 'badge-red', crashed: 'badge-red',
    };
    return map[status] || 'badge-purple';
  };

  const configSummaryParts = [];
  if (config.regions.length > 0) configSummaryParts.push(`${config.regions.length} region${config.regions.length > 1 ? 's' : ''}`);
  if (config.platforms.length > 0) configSummaryParts.push(config.platforms.join(', '));
  if (config.categories.length > 0) configSummaryParts.push(`${config.categories.length} categories`);
  if (config.keywords.length > 0) configSummaryParts.push(`${config.keywords.length} keywords`);
  if (config.content_type !== 'all') configSummaryParts.push(config.content_type);

  const presets = savedConfigs.filter((c) => c.is_preset);

  return (
    <>
      <div className="page-header">
        <h2>Pipeline Control</h2>
        <p>Configure filters, run the pipeline, and view execution history</p>
      </div>

      {/* Config Form */}
      <div className="card" style={{ marginBottom: 'var(--space-xl)' }}>
        <div className="card-header">
          <span className="card-title">⚙️ Pipeline Configuration</span>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button className="btn btn-secondary" onClick={handleReset} style={{ fontSize: '0.75rem' }}>
              ↺ Reset
            </button>
            <button className="btn btn-secondary" onClick={() => setShowPresetSave(!showPresetSave)} style={{ fontSize: '0.75rem' }}>
              💾 Save Preset
            </button>
          </div>
        </div>

        {/* Preset Save */}
        {showPresetSave && (
          <div className="pc-preset-save">
            <input
              className="text-input"
              placeholder="Preset name..."
              value={presetName}
              onChange={(e) => setPresetName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSavePreset()}
              style={{ flex: 1 }}
            />
            <button className="btn btn-primary" onClick={handleSavePreset} style={{ fontSize: '0.75rem' }}>Save</button>
          </div>
        )}

        {/* Saved Presets */}
        {presets.length > 0 && (
          <div className="pc-section">
            <label className="pc-label">📁 Saved Presets</label>
            <div className="pc-preset-list">
              {presets.map((p) => (
                <div key={p.id} className={`pc-preset-chip${activeConfigId === p.id ? ' active' : ''}`}>
                  <button className="pc-preset-btn" onClick={() => handleLoadConfig(p)}>{p.name}</button>
                  <button className="pc-preset-del" onClick={() => handleDeleteConfig(p.id)}>×</button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Regions */}
        <div className="pc-section">
          <label className="pc-label">🌍 Regions <span className="pc-hint">(max 5)</span></label>
          <div className="pc-chip-grid">
            {ALL_REGIONS.map((r) => (
              <button
                key={r.code}
                className={`pc-chip${config.regions.includes(r.code) ? ' selected' : ''}`}
                onClick={() => toggleRegion(r.code)}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>

        {/* Platforms */}
        <div className="pc-section">
          <label className="pc-label">📡 Platforms</label>
          <div className="pc-chip-grid">
            {['youtube', 'reddit'].map((p) => (
              <button
                key={p}
                className={`pc-chip${config.platforms.includes(p) ? ' selected' : ''}`}
                onClick={() => togglePlatform(p)}
              >
                {p === 'youtube' ? '▶️ YouTube' : '💬 Reddit'}
              </button>
            ))}
          </div>
        </div>

        {/* Categories */}
        <div className="pc-section">
          <label className="pc-label">🏷️ Categories <span className="pc-hint">(leave empty for all)</span></label>
          <div className="pc-chip-grid">
            {ALL_CATEGORIES.map((c) => (
              <button
                key={c}
                className={`pc-chip${config.categories.includes(c) ? ' selected' : ''}`}
                onClick={() => toggleCategory(c)}
              >
                {c}
              </button>
            ))}
          </div>
        </div>

        {/* Keywords */}
        <div className="pc-section">
          <label className="pc-label">🔑 Keywords <span className="pc-hint">(max 10, enables hybrid search)</span></label>
          <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem' }}>
            <input
              className="text-input"
              placeholder="Add keyword..."
              value={keywordInput}
              onChange={(e) => setKeywordInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && addKeyword()}
              style={{ flex: 1 }}
            />
            <button className="btn btn-primary" onClick={addKeyword} style={{ fontSize: '0.75rem' }}>+ Add</button>
          </div>
          {config.keywords.length > 0 && (
            <div className="pc-chip-grid">
              {config.keywords.map((kw) => (
                <span key={kw} className="pc-keyword-tag">
                  {kw}
                  <button className="pc-keyword-del" onClick={() => removeKeyword(kw)}>×</button>
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Content Type */}
        <div className="pc-section">
          <label className="pc-label">📏 Content Type</label>
          <div className="pc-chip-grid">
            {[
              { val: 'all', label: '📺 All' },
              { val: 'shorts', label: '⚡ Shorts (<60s)' },
              { val: 'long', label: '🎥 Long Form (≥60s)' },
            ].map((ct) => (
              <button
                key={ct.val}
                className={`pc-chip${config.content_type === ct.val ? ' selected' : ''}`}
                onClick={() => setConfig((prev) => ({ ...prev, content_type: ct.val }))}
              >
                {ct.label}
              </button>
            ))}
          </div>
        </div>

        {/* Config Summary */}
        <div className="pc-summary">
          <span className="pc-summary-label">Config Summary:</span>
          <span className="pc-summary-text">{configSummaryParts.join(' · ') || 'Default settings'}</span>
        </div>

        {/* Run Button */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginTop: '1rem' }}>
          <button className="btn btn-primary" onClick={handleTrigger} disabled={triggering || config.regions.length === 0}>
            {triggering ? (
              <><span className="spinner" style={{ width: 14, height: 14, borderWidth: 2, marginRight: 6 }}></span>Running...</>
            ) : (
              <>&#9654; Run Pipeline</>
            )}
          </button>
          <button className="btn btn-secondary" onClick={loadHistory}>&#8635; Refresh History</button>
          {config.regions.length === 0 && (
            <span style={{ color: '#ef4444', fontSize: '0.75rem' }}>Select at least one region</span>
          )}
        </div>
        {message && (
          <div style={{
            marginTop: '1rem', padding: '0.75rem 1rem', borderRadius: 8,
            fontSize: '0.8125rem', fontWeight: 500,
            background: message.type === 'success' ? 'rgba(52,211,153,0.08)' : 'rgba(239,68,68,0.08)',
            color: message.type === 'success' ? '#34d399' : '#ef4444',
            border: `1px solid ${message.type === 'success' ? 'rgba(52,211,153,0.2)' : 'rgba(239,68,68,0.2)'}`,
          }}>
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
                <th>ID</th><th>Status</th><th>Started</th><th>Duration</th>
                <th>Ingested</th><th>Processed</th><th>Enriched</th><th>Stored</th><th>Triggered By</th>
              </tr>
            </thead>
            <tbody>
              {history.map((r) => (
                <tr key={r.id}>
                  <td className="number-cell">#{r.id}</td>
                  <td><span className={`badge ${statusBadge(r.status)}`}>{r.status}</span></td>
                  <td style={{ color: '#8b90a0', fontSize: '0.75rem' }}>
                    {r.started_at ? new Date(r.started_at).toLocaleString('de-DE') : '—'}
                  </td>
                  <td className="number-cell">{r.elapsed_seconds != null ? `${r.elapsed_seconds.toFixed(1)}s` : '—'}</td>
                  <td className="number-cell">{r.videos_ingested ?? '—'}</td>
                  <td className="number-cell">{r.videos_processed ?? '—'}</td>
                  <td className="number-cell">{r.videos_enriched ?? '—'}</td>
                  <td className="number-cell">{r.videos_stored ?? '—'}</td>
                  <td><span className="badge badge-purple">{r.triggered_by || 'manual'}</span></td>
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
