import ScanConfigPanel from './ScanConfigPanel';

export default function TrendSignalsPanel({ keywords, input, onInputChange, onAdd, onRemove, suggestions, error }) {
  return (
    <ScanConfigPanel step="4" title="Add Trend Signals" helper="Prioritize content matching these topics." badge={keywords.length ? `${keywords.length} signals` : 'Optional'}>
      <div className="pi-signal-input"><input value={input} onChange={(event) => onInputChange(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') { event.preventDefault(); onAdd(); } }} maxLength={50} placeholder={'e.g. “AI”, “Elon Musk”…'} aria-label="Trend signal" /><button type="button" onClick={() => onAdd()}>+ Add</button></div>
      {error && <p className="pi-signal-error" role="alert">{error}</p>}
      {keywords.length > 0 && <div className="pi-signal-tags">{keywords.map((keyword) => <span key={keyword}>{keyword}<button type="button" aria-label={`Remove ${keyword}`} onClick={() => onRemove(keyword)}>×</button></span>)}</div>}
      <div className="pi-suggestions"><p>Trending suggestions</p><div>{suggestions.slice(0, 7).map((signal) => <button type="button" key={signal} onClick={() => onAdd(signal)}>+ {signal}</button>)}</div></div>
    </ScanConfigPanel>
  );
}
