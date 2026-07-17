import PlatformIcon from '../PlatformIcon';
import { estimateDepth, estimateRuntime, getRegionLabel } from './pipelineUtils';

export default function ScanConfigurationSummary({ config, validation, running, onLaunch }) {
  const format = config.content_type === 'all' ? 'All formats' : config.content_type === 'shorts' ? 'Shorts' : 'Long form';
  const marketValue = config.regions.length <= 2 ? config.regions.map(getRegionLabel).join(', ') : `${config.regions.length} markets`;
  return (
    <section className="pi-summary-panel">
      <div className="pi-summary-heading"><h2><span aria-hidden="true">✦</span> Scan Configuration Summary</h2><p>{validation.valid ? 'Configuration is ready for launch.' : validation.issues[0]}</p></div>
      <div className="pi-summary-body">
        <div className="pi-summary-grid">
          <div><small>Target markets</small><strong>{marketValue}</strong></div>
          <div><small>Platforms</small><strong className="pi-summary-platforms">{config.platforms.map((platform) => <span key={platform}><PlatformIcon platform={platform} size={13} />{platform}</span>)}</strong></div>
          <div><small>Content format</small><strong>{format}</strong></div>
          <div><small>Trend signals</small><strong>{config.keywords.length ? config.keywords.join(', ') : 'Auto-detect'}</strong></div>
          <div><small>Est. runtime</small><strong>{estimateRuntime(config)}</strong></div>
          <div><small>Scan depth</small><strong className="highlight">{estimateDepth(config)}</strong></div>
        </div>
        <div className="pi-launch-block">
          <button type="button" disabled={!validation.valid || running} onClick={onLaunch}>{running ? <><span className="pi-button-spinner" /> Scan running</> : <>↗ Launch Intelligence Scan</>}</button>
          <p>{validation.valid ? `This will scan ${config.regions.length} market${config.regions.length === 1 ? '' : 's'} across ${config.platforms.length} platform${config.platforms.length === 1 ? '' : 's'} · Est. ${estimateRuntime(config)}` : validation.issues[0]}</p>
        </div>
      </div>
    </section>
  );
}
