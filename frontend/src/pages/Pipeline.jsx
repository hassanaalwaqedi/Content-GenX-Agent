import { useEffect, useState, useCallback, useRef } from 'react';
import { api } from '../api/client';
import IntelligenceStatusBar from '../components/intelligence/IntelligenceStatusBar';
import ConnectorHealthCards from '../components/intelligence/ConnectorHealthCards';
import ScanFlowVisualization from '../components/intelligence/ScanFlowVisualization';
import RunHistorySection from '../components/intelligence/RunHistorySection';
import RunningPipelineUX from '../components/intelligence/RunningPipelineUX';
import IntelligenceConfidence from '../components/intelligence/IntelligenceConfidence';
import './Pipeline.css';
import '../components/intelligence/intelligence.css';

/* ── Constants ── */
const ALL_REGIONS = [
  // Americas
  { code: 'US', label: '🇺🇸 United States' },
  { code: 'CA', label: '🇨🇦 Canada' },
  { code: 'BR', label: '🇧🇷 Brazil' },
  { code: 'MX', label: '🇲🇽 Mexico' },
  // Europe
  { code: 'GB', label: '🇬🇧 United Kingdom' },
  { code: 'DE', label: '🇩🇪 Germany' },
  { code: 'FR', label: '🇫🇷 France' },
  { code: 'NL', label: '🇳🇱 Netherlands' },
  { code: 'ES', label: '🇪🇸 Spain' },
  { code: 'IT', label: '🇮🇹 Italy' },
  { code: 'SE', label: '🇸🇪 Sweden' },
  { code: 'CH', label: '🇨🇭 Switzerland' },
  { code: 'PL', label: '🇵🇱 Poland' },
  { code: 'NO', label: '🇳🇴 Norway' },
  // Middle East
  { code: 'AE', label: '🇦🇪 UAE' },
  { code: 'SA', label: '🇸🇦 Saudi Arabia' },
  { code: 'KW', label: '🇰🇼 Kuwait' },
  { code: 'QA', label: '🇶🇦 Qatar' },
  { code: 'BH', label: '🇧🇭 Bahrain' },
  { code: 'EG', label: '🇪🇬 Egypt' },
  { code: 'TR', label: '🇹🇷 Turkey' },
  // Asia-Pacific
  { code: 'AU', label: '🇦🇺 Australia' },
  { code: 'JP', label: '🇯🇵 Japan' },
  { code: 'KR', label: '🇰🇷 South Korea' },
  { code: 'SG', label: '🇸🇬 Singapore' },
];

const ALL_CATEGORIES = [
  'music', 'gaming', 'sports', 'entertainment', 'education',
  'science & technology', 'news & politics', 'comedy', 'howto & style',
  'people & blogs', 'film & animation', 'travel & events',
];

const SUGGESTED_SIGNALS = ['AI', 'ChatGPT', 'Claude', 'Finance', 'Gaming', 'Startups', 'Marketing', 'SaaS', 'Crypto', 'Fitness'];

const DEFAULT_CONFIG = {
  name: 'Custom',
  regions: ['US', 'GB', 'CA', 'DE', 'FR', 'AU', 'AE', 'SA'],
  platforms: ['youtube'],
  categories: [],
  keywords: [],
  content_type: 'all',
  is_preset: false,
};

const PLATFORM_NAMES = { youtube: 'YouTube', reddit: 'Reddit', tiktok: 'TikTok', instagram: 'Instagram' };

/* ── Helpers ── */
function estimateRuntime(config) {
  const total = 15 + config.regions.length * 4 + config.platforms.length * 5 + config.keywords.length * 2;
  if (total < 30) return '~20 sec';
  if (total < 60) return '~40 sec';
  if (total < 120) return '~1–2 min';
  return '~2–3 min';
}

function estimateDepth(config) {
  const factors = config.regions.length + config.keywords.length + config.categories.length;
  if (factors <= 3) return 'Focused';
  if (factors <= 8) return 'Standard';
  return 'Deep Scan';
}

/* ── Step Card ── */
function StepCard({ number, title, description, badge, badgeType, hasSelection, children }) {
  return (
    <div className={`scan-step${hasSelection ? ' has-selection' : ''}`}>
      <div className="scan-step-header">
        <div className="scan-step-number">{number}</div>
        <div className="scan-step-info">
          <div className="scan-step-title">{title}</div>
          <div className="scan-step-desc">{description}</div>
        </div>
        {badge && <span className={`scan-step-badge${badgeType === 'optional' ? ' optional' : ''}`}>{badge}</span>}
      </div>
      <div className="scan-step-body">{children}</div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════
   MAIN PAGE
   ══════════════════════════════════════════════════════════════════ */
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
  const [config, setConfig] = useState({ ...DEFAULT_CONFIG });
  const [connectorData, setConnectorData] = useState(null);
  const [scanSection, setScanSection] = useState(true);
  const triggerTimeRef = useRef(null);

  /* ── Data Loading ── */
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

  const loadConnectors = useCallback(() => {
    api.getConnectorHealth()
      .then(setConnectorData)
      .catch(() => {});
  }, []);

  useEffect(() => {
    loadHistory();
    loadConfigs();
    loadLastUsed();
    loadConnectors();
  }, [loadHistory, loadConfigs, loadLastUsed, loadConnectors]);

  /* ── Actions ── */
  const handleTrigger = async () => {
    setTriggering(true);
    setMessage(null);
    triggerTimeRef.current = Date.now();
    try {
      const saveResult = await api.savePipelineConfig(config);
      const configId = saveResult.id;
      setActiveConfigId(configId);
      await api.triggerPipeline(null, configId);
      setMessage({ type: 'success', text: 'Intelligence scan launched successfully. Dashboard will update automatically.' });
      loadConfigs();
      setTimeout(loadHistory, 5000);
      setTimeout(() => setTriggering(false), 35000);
    } catch (err) {
      setMessage({ type: 'error', text: err.message });
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
        : prev.regions.length < 10 ? [...prev.regions, code] : prev.regions;
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

  const addKeyword = (kw) => {
    const clean = (kw || keywordInput).trim().replace(/[^\w\s-]/g, '');
    if (clean && !config.keywords.includes(clean) && config.keywords.length < 10) {
      setConfig((prev) => ({ ...prev, keywords: [...prev.keywords, clean] }));
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

  /* ── Derived ── */
  const presets = savedConfigs.filter((c) => c.is_preset);
  const availableSuggestions = SUGGESTED_SIGNALS.filter(s => !config.keywords.includes(s));
  const lastSuccessRun = history.find(r => r.status === 'completed');

  const summaryItems = [
    { label: 'Target Markets', value: config.regions.length > 0 ? config.regions.length <= 2 ? config.regions.map(r => ALL_REGIONS.find(x => x.code === r)?.label?.replace(/^..\s/, '') || r).join(', ') : `${config.regions.length} markets` : 'None selected' },
    { label: 'Platforms', value: config.platforms.map(p => PLATFORM_NAMES[p] || p).join(' + ') || 'None' },
    { label: 'Content Format', value: config.content_type === 'all' ? 'All Formats' : config.content_type === 'shorts' ? 'Shorts (<60s)' : 'Long Form (≥60s)' },
    { label: 'Trend Signals', value: config.keywords.length > 0 ? config.keywords.join(', ') : 'Auto-detect' },
    { label: 'Est. Runtime', value: estimateRuntime(config) },
    { label: 'Scan Depth', value: estimateDepth(config), highlight: true },
  ];

  return (
    <>
      {/* ══════════ INTELLIGENCE STATUS BAR ══════════ */}
      <IntelligenceStatusBar />

      {/* ── Hero Header ── */}
      <div className="scan-hero">
        <div className="scan-hero-text">
          <h2>AI Market Intelligence</h2>
          <p>Configure and launch an AI-powered scan of trending content across global markets</p>
        </div>
        <div className="scan-hero-actions">
          <button className="btn btn-secondary" onClick={handleReset} style={{ fontSize: '0.75rem' }}>↺ Reset</button>
          <button className="btn btn-secondary" onClick={() => setShowPresetSave(!showPresetSave)} style={{ fontSize: '0.75rem' }}>💾 Save Preset</button>
          <button className="btn btn-secondary" onClick={() => setScanSection(!scanSection)} style={{ fontSize: '0.75rem' }}>
            {scanSection ? '▾ Hide Config' : '▸ Show Config'}
          </button>
        </div>
      </div>

      {/* ══════════ CONNECTOR HEALTH ══════════ */}
      <ConnectorHealthCards />

      {/* ══════════ SCAN FLOW ══════════ */}
      <ScanFlowVisualization isRunning={triggering} activeStage={triggering ? Math.min(Math.floor((Date.now() - (triggerTimeRef.current || Date.now())) / 6000), 5) : -1} />

      {/* ── Preset Save ── */}
      {showPresetSave && (
        <div className="scan-preset-save">
          <input className="text-input" placeholder="Name your preset..." value={presetName} onChange={(e) => setPresetName(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && handleSavePreset()} />
          <button className="btn btn-primary" onClick={handleSavePreset} style={{ fontSize: '0.75rem' }}>Save</button>
        </div>
      )}

      {/* ── Presets ── */}
      {presets.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap', marginBottom: 'var(--space-lg)' }}>
          <span style={{ fontSize: 'var(--font-size-xs)', fontWeight: 700, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Quick Presets</span>
          {presets.map((p) => (
            <div key={p.id} className={`pc-preset-chip${activeConfigId === p.id ? ' active' : ''}`}>
              <button className="pc-preset-btn" onClick={() => handleLoadConfig(p)}>{p.name}</button>
              <button className="pc-preset-del" onClick={() => handleDeleteConfig(p.id)}>×</button>
            </div>
          ))}
        </div>
      )}

      {/* ══════════ GUIDED STEPS (collapsible) ══════════ */}
      {scanSection && (
        <div className="scan-steps">
          {/* STEP 1 — Markets */}
          <StepCard number="1" title="Select Target Markets" description="Choose up to 10 geographic markets to scan." badge={`${config.regions.length} selected`} hasSelection={config.regions.length > 0}>
            <div className="scan-chip-grid">
              {ALL_REGIONS.map((r) => (
                <button key={r.code} className={`scan-chip${config.regions.includes(r.code) ? ' selected' : ''}`} onClick={() => toggleRegion(r.code)}>
                  {config.regions.includes(r.code) && <span className="scan-chip-check">✓</span>}
                  {r.label}
                </button>
              ))}
            </div>
          </StepCard>

          {/* STEP 2 — Platforms */}
          <StepCard number="2" title="Choose Platforms" description="Select which content platforms to scan." badge={config.platforms.map(p => PLATFORM_NAMES[p] || p).join(', ')} hasSelection={config.platforms.length > 0}>
            <div className="scan-chip-grid">
              {[
                { id: 'youtube', label: '▶️ YouTube', desc: 'Trending videos, shorts & creators' },
                { id: 'reddit', label: '💬 Reddit', desc: 'Community discussions & viral posts' },
                { id: 'tiktok', label: '🎵 TikTok', desc: 'Viral short-form video trends' },
                { id: 'instagram', label: '📸 Instagram', desc: 'Reels, posts & hashtag trends' },
              ].map((p) => (
                <button key={p.id} className={`scan-chip${config.platforms.includes(p.id) ? ' selected' : ''}${(p.id === 'tiktok' || p.id === 'instagram') ? ' experimental' : ''}`} onClick={() => togglePlatform(p.id)} style={{ padding: '10px 20px' }}>
                  {config.platforms.includes(p.id) && <span className="scan-chip-check">✓</span>}
                  <span>{p.label}</span>
                  {(p.id === 'tiktok' || p.id === 'instagram') && <span className="scan-chip-beta">BETA</span>}
                </button>
              ))}
            </div>
          </StepCard>

          {/* STEP 3 — Content Domains */}
          <StepCard number="3" title="Focus Content Domains" description="Narrow the scan to specific categories. Leave empty for all." badge={config.categories.length > 0 ? `${config.categories.length} selected` : 'All domains'} badgeType={config.categories.length > 0 ? 'active' : 'optional'} hasSelection={config.categories.length > 0}>
            <div className="scan-chip-grid">
              {ALL_CATEGORIES.map((c) => (
                <button key={c} className={`scan-chip${config.categories.includes(c) ? ' selected' : ''}`} onClick={() => toggleCategory(c)} style={{ textTransform: 'capitalize' }}>
                  {config.categories.includes(c) && <span className="scan-chip-check">✓</span>}
                  {c}
                </button>
              ))}
            </div>
          </StepCard>

          {/* STEP 4 — Trend Signals */}
          <StepCard number="4" title="Add Trend Signals" description="Add keywords to target. AI will prioritize matching content." badge={config.keywords.length > 0 ? `${config.keywords.length} signals` : 'Auto-detect'} badgeType={config.keywords.length > 0 ? 'active' : 'optional'} hasSelection={config.keywords.length > 0}>
            <div className="scan-keyword-area">
              <div className="scan-keyword-input-row">
                <input className="scan-keyword-input" placeholder='e.g. "AI", "growth hacking"...' value={keywordInput} onChange={(e) => setKeywordInput(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && addKeyword()} maxLength={50} />
                <button className="scan-keyword-add-btn" onClick={() => addKeyword()}>+ Add</button>
              </div>
              {config.keywords.length > 0 && (
                <div className="scan-keyword-tags">
                  {config.keywords.map((kw) => (
                    <span key={kw} className="scan-keyword-tag">{kw}<button className="scan-keyword-remove" onClick={() => removeKeyword(kw)}>×</button></span>
                  ))}
                </div>
              )}
              {availableSuggestions.length > 0 && (
                <div className="scan-suggestions">
                  <span className="scan-suggestions-label">💡 Trending:</span>
                  {availableSuggestions.slice(0, 7).map((s) => (
                    <button key={s} className="scan-suggestion-chip" onClick={() => addKeyword(s)}>+ {s}</button>
                  ))}
                </div>
              )}
            </div>
          </StepCard>

          {/* STEP 5 — Content Format */}
          <StepCard number="5" title="Choose Content Format" description="Filter by video length." badge={config.content_type === 'all' ? 'All formats' : config.content_type === 'shorts' ? 'Shorts' : 'Long form'} badgeType="optional" hasSelection={config.content_type !== 'all'}>
            <div className="scan-chip-grid">
              {[
                { val: 'all', label: '📺 All Formats' },
                { val: 'shorts', label: '⚡ Shorts' },
                { val: 'long', label: '🎥 Long Form' },
              ].map((ct) => (
                <button key={ct.val} className={`scan-chip${config.content_type === ct.val ? ' selected' : ''}`} onClick={() => setConfig((prev) => ({ ...prev, content_type: ct.val }))} style={{ padding: '10px 20px' }}>
                  {config.content_type === ct.val && <span className="scan-chip-check">✓</span>}
                  {ct.label}
                </button>
              ))}
            </div>
          </StepCard>
        </div>
      )}

      {/* ══════════ INTELLIGENCE SUMMARY ══════════ */}
      <div className="scan-summary">
        <div className="scan-summary-title"><span>🧠</span> Scan Configuration Summary</div>
        <div className="scan-summary-grid">
          {summaryItems.map((item) => (
            <div key={item.label} className="scan-summary-item">
              <span className="scan-summary-label">{item.label}</span>
              <span className={`scan-summary-value${item.highlight ? ' highlight' : ''}`}>{item.value}</span>
            </div>
          ))}
        </div>
      </div>

      {/* ══════════ LAUNCH AREA ══════════ */}
      <div className="scan-launch-area">
        <button className="scan-launch-btn" onClick={handleTrigger} disabled={triggering || config.regions.length === 0}>
          {triggering ? (<><span className="spinner" />Scanning...</>) : (<>🚀 Launch Intelligence Scan</>)}
        </button>
        {config.regions.length === 0 && <span className="scan-launch-error">Select at least one target market to begin</span>}
        {!triggering && config.regions.length > 0 && (
          <span className="scan-launch-hint">
            This will scan {config.regions.length} market{config.regions.length > 1 ? 's' : ''} across {config.platforms.map(p => PLATFORM_NAMES[p] || p).join(' & ')} · Est. {estimateRuntime(config)}
          </span>
        )}
      </div>

      {/* ── Status Message ── */}
      {message && (
        <div className={`scan-message ${message.type}`}>
          {message.type === 'success' ? '✓' : '✕'} {message.text}
        </div>
      )}

      {/* ── Pipeline Progress (while running) ── */}
      {triggering && <RunningPipelineUX startTime={triggerTimeRef.current} platforms={config.platforms.map(p => PLATFORM_NAMES[p] || p)} />}

      {/* ══════════ INTELLIGENCE CONFIDENCE ══════════ */}
      <IntelligenceConfidence lastRun={lastSuccessRun} connectorData={connectorData} />

      {/* ══════════ RECENT INTELLIGENCE RUNS ══════════ */}
      <RunHistorySection history={history} loading={loading} onRefresh={loadHistory} onRerun={(run) => { /* future: reload config and trigger */ }} />
    </>
  );
}
