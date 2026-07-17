import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import ConnectorHealthDrawer from '../components/pipeline/ConnectorHealthDrawer';
import IntelligenceConfidencePanel from '../components/pipeline/IntelligenceConfidencePanel';
import PipelineExecutionPanel from '../components/pipeline/PipelineExecutionPanel';
import PipelineHeader from '../components/pipeline/PipelineHeader';
import PipelineStatusBar from '../components/pipeline/PipelineStatusBar';
import RecentRunsPanel from '../components/pipeline/RecentRunsPanel';
import RunDetailsDrawer from '../components/pipeline/RunDetailsDrawer';
import ScanConfigurationSummary from '../components/pipeline/ScanConfigurationSummary';
import ScanConfigurationWorkspace from '../components/pipeline/ScanConfigurationWorkspace';
import {
  DEFAULT_PIPELINE_CONFIG,
  SIGNAL_SUGGESTIONS,
  normalizePipelineConfig,
  validatePipelineConfig,
} from '../components/pipeline/pipelineUtils';
import './Pipeline.css';

export default function Pipeline() {
  const navigate = useNavigate();
  const [config, setConfig] = useState(DEFAULT_PIPELINE_CONFIG);
  const [history, setHistory] = useState([]);
  const [savedConfigs, setSavedConfigs] = useState([]);
  const [connectors, setConnectors] = useState({});
  const [stats, setStats] = useState(null);
  const [apiOnline, setApiOnline] = useState(true);
  const [loading, setLoading] = useState(true);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [healthRefreshing, setHealthRefreshing] = useState(false);
  const [configVisible, setConfigVisible] = useState(true);
  const [showPresetSave, setShowPresetSave] = useState(false);
  const [presetName, setPresetName] = useState('');
  const [keywordInput, setKeywordInput] = useState('');
  const [keywordError, setKeywordError] = useState('');
  const [message, setMessage] = useState(null);
  const [triggering, setTriggering] = useState(false);
  const [triggerStartedAt, setTriggerStartedAt] = useState(null);
  const [observedRun, setObservedRun] = useState(null);
  const [selectedRun, setSelectedRun] = useState(null);
  const [connectorDrawerOpen, setConnectorDrawerOpen] = useState(false);
  const activeConfigId = useRef(null);

  const loadHistory = useCallback(async (withLoading = true) => {
    if (withLoading) setHistoryLoading(true);
    try {
      const data = await api.getPipelineHistory(30);
      setHistory(data.runs || []);
      return data.runs || [];
    } catch (error) {
      console.error('Unable to load pipeline history:', error);
      setMessage((current) => current?.type === 'error' ? current : { type: 'error', text: 'Unable to refresh pipeline history.' });
      return [];
    } finally {
      if (withLoading) setHistoryLoading(false);
    }
  }, []);

  const loadConfigs = useCallback(async () => {
    try {
      const data = await api.listPipelineConfigs();
      setSavedConfigs(data.configs || []);
    } catch (error) {
      console.error('Unable to load pipeline presets:', error);
    }
  }, []);

  const loadLastUsed = useCallback(async () => {
    try {
      const data = await api.getLastUsedConfig();
      if (data.config) {
        setConfig(normalizePipelineConfig(data.config));
        activeConfigId.current = data.config.id || null;
      }
    } catch (error) {
      console.error('Unable to load last pipeline configuration:', error);
    }
  }, []);

  const loadConnectors = useCallback(async () => {
    setHealthRefreshing(true);
    try {
      const data = await api.getConnectorHealth();
      setConnectors(data.connectors || {});
      return data.connectors || {};
    } catch (error) {
      console.error('Unable to load connector health:', error);
      return {};
    } finally {
      setHealthRefreshing(false);
    }
  }, []);

  const loadStats = useCallback(async () => {
    try {
      const data = await api.getStats();
      setStats(data);
      setApiOnline(true);
    } catch (error) {
      console.error('Unable to load pipeline stats:', error);
      setApiOnline(false);
    }
  }, []);

  const refreshOperationalData = useCallback(async () => {
    await Promise.all([loadHistory(false), loadConfigs(), loadConnectors(), loadStats()]);
  }, [loadConfigs, loadConnectors, loadHistory, loadStats]);

  useEffect(() => {
    Promise.all([loadHistory(), loadConfigs(), loadLastUsed(), loadConnectors(), loadStats()]).finally(() => setLoading(false));
  }, [loadConfigs, loadConnectors, loadHistory, loadLastUsed, loadStats]);

  useEffect(() => {
    if (!triggering) return undefined;
    const interval = window.setInterval(() => loadHistory(false), 4000);
    return () => window.clearInterval(interval);
  }, [loadHistory, triggering]);

  useEffect(() => {
    if (!triggering || !triggerStartedAt) return;
    const currentRun = history.find((run) => new Date(run.started_at || 0).getTime() >= triggerStartedAt - 15000);
    if (!currentRun) return;
    setObservedRun(currentRun);
    if (currentRun.status !== 'running') {
      setTriggering(false);
      loadStats();
    }
  }, [history, loadStats, triggerStartedAt, triggering]);

  const validation = useMemo(() => validatePipelineConfig(config, connectors), [config, connectors]);
  const lastCompletedRun = useMemo(() => history.find((run) => run.status === 'completed'), [history]);
  const presets = useMemo(() => savedConfigs.filter((item) => item.is_preset), [savedConfigs]);
  const suggestions = useMemo(() => SIGNAL_SUGGESTIONS.filter((signal) => !config.keywords.some((keyword) => keyword.toLowerCase() === signal.toLowerCase())), [config.keywords]);

  const updateConfig = (updater) => setConfig((current) => normalizePipelineConfig(typeof updater === 'function' ? updater(current) : updater));

  const toggleRegion = (region) => updateConfig((current) => ({
    ...current,
    regions: current.regions.includes(region)
      ? current.regions.filter((item) => item !== region)
      : current.regions.length < 5 ? [...current.regions, region] : current.regions,
  }));

  const togglePlatform = (platform) => updateConfig((current) => ({
    ...current,
    platforms: current.platforms.includes(platform)
      ? current.platforms.length > 1 ? current.platforms.filter((item) => item !== platform) : current.platforms
      : [...current.platforms, platform],
  }));

  const toggleCategory = (category) => updateConfig((current) => ({
    ...current,
    categories: current.categories.includes(category) ? current.categories.filter((item) => item !== category) : [...current.categories, category],
  }));

  const addKeyword = (value = keywordInput) => {
    const keyword = String(value || '').trim().replace(/[^\w\s-]/g, '');
    if (!keyword) { setKeywordError('Enter a signal before adding it.'); return; }
    if (config.keywords.some((item) => item.toLowerCase() === keyword.toLowerCase())) { setKeywordError('That signal is already selected.'); return; }
    if (config.keywords.length >= 10) { setKeywordError('A scan can include up to 10 trend signals.'); return; }
    updateConfig((current) => ({ ...current, keywords: [...current.keywords, keyword] }));
    setKeywordInput('');
    setKeywordError('');
  };

  const handleReset = () => {
    setConfig(DEFAULT_PIPELINE_CONFIG);
    activeConfigId.current = null;
    setKeywordInput('');
    setKeywordError('');
    setMessage(null);
  };

  const handleLoadConfig = (preset) => {
    setConfig(normalizePipelineConfig({ ...preset, is_preset: false }));
    activeConfigId.current = preset.id || null;
    setMessage({ type: 'success', text: `Loaded preset “${preset.name}”.` });
  };

  const handleDeletePreset = async (id) => {
    try {
      await api.deletePipelineConfig(id);
      if (activeConfigId.current === id) activeConfigId.current = null;
      await loadConfigs();
    } catch (error) {
      setMessage({ type: 'error', text: error.message || 'Unable to delete preset.' });
    }
  };

  const handleSavePreset = async () => {
    if (!presetName.trim()) { setMessage({ type: 'error', text: 'Enter a name for this preset.' }); return; }
    try {
      await api.savePipelineConfig({ ...config, name: presetName.trim(), is_preset: true });
      setPresetName('');
      setShowPresetSave(false);
      await loadConfigs();
      setMessage({ type: 'success', text: 'Preset saved successfully.' });
    } catch (error) {
      setMessage({ type: 'error', text: error.message || 'Unable to save preset.' });
    }
  };

  const handleTrigger = async () => {
    if (!validation.valid || triggering) return;
    setMessage(null);
    setObservedRun(null);
    const startedAt = Date.now();
    setTriggerStartedAt(startedAt);
    setTriggering(true);
    try {
      const saveResult = await api.savePipelineConfig({ ...config, is_preset: false });
      const configId = saveResult.id;
      activeConfigId.current = configId;
      const result = await api.triggerPipeline(null, configId);
      setMessage({ type: 'success', text: result.message || 'Intelligence scan accepted by the pipeline.' });
      await Promise.all([loadConfigs(), loadHistory(false)]);
    } catch (error) {
      setTriggering(false);
      setMessage({ type: 'error', text: error.message || 'Unable to launch the intelligence scan.' });
    }
  };

  return (
    <div className="pi-page-shell">
      <PipelineStatusBar config={config} connectors={connectors} stats={stats} lastRun={lastCompletedRun || history[0]} apiOnline={apiOnline} onReset={handleReset} onSavePreset={() => setShowPresetSave((current) => !current)} onToggleConfig={() => setConfigVisible((current) => !current)} configVisible={configVisible} onOpenConnectors={() => setConnectorDrawerOpen(true)} />
      <PipelineHeader config={config} validation={validation} />

      {showPresetSave && <section className="pi-preset-save"><label>Preset name<input value={presetName} onChange={(event) => setPresetName(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') handleSavePreset(); }} placeholder="Name this configuration" maxLength={100} /></label><button type="button" onClick={handleSavePreset}>Save preset</button><button type="button" onClick={() => setShowPresetSave(false)}>Cancel</button></section>}
      {presets.length > 0 && <section className="pi-preset-row"><span>Quick presets</span>{presets.map((preset) => <div key={preset.id} className={activeConfigId.current === preset.id ? 'active' : ''}><button type="button" onClick={() => handleLoadConfig(preset)}>{preset.name}</button><button type="button" onClick={() => handleDeletePreset(preset.id)} aria-label={`Delete ${preset.name}`}>×</button></div>)}</section>}

      {configVisible && <ScanConfigurationWorkspace config={config} connectors={connectors} keywordInput={keywordInput} keywordError={keywordError} suggestions={suggestions} onToggleRegion={toggleRegion} onTogglePlatform={togglePlatform} onToggleCategory={toggleCategory} onClearCategories={() => updateConfig((current) => ({ ...current, categories: [] }))} onKeywordInputChange={(value) => { setKeywordInput(value); setKeywordError(''); }} onAddKeyword={addKeyword} onRemoveKeyword={(keyword) => updateConfig((current) => ({ ...current, keywords: current.keywords.filter((item) => item !== keyword) }))} onContentTypeChange={(contentType) => updateConfig((current) => ({ ...current, content_type: contentType }))} />}

      <ScanConfigurationSummary config={config} validation={validation} running={triggering} onLaunch={handleTrigger} />
      <PipelineExecutionPanel running={triggering} startedAt={triggerStartedAt} observedRun={observedRun} message={message} onOpenDashboard={() => navigate('/')} onViewResults={() => navigate('/videos')} onRerun={handleTrigger} />

      <div className="pi-operational-grid">
        <IntelligenceConfidencePanel lastRun={lastCompletedRun} connectors={connectors} config={config} />
        <RecentRunsPanel history={history} loading={loading || historyLoading} onRefresh={() => refreshOperationalData()} onOpenRun={setSelectedRun} onRerun={handleTrigger} />
      </div>

      <RunDetailsDrawer run={selectedRun} onClose={() => setSelectedRun(null)} onRerun={handleTrigger} />
      <ConnectorHealthDrawer open={connectorDrawerOpen} connectors={connectors} onClose={() => setConnectorDrawerOpen(false)} onRefresh={loadConnectors} refreshing={healthRefreshing} />
    </div>
  );
}
