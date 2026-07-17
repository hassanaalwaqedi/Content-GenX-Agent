import ScanConfigPanel from './ScanConfigPanel';

const FORMATS = [{ value: 'all', icon: '▣', label: 'All Formats' }, { value: 'shorts', icon: 'ϟ', label: 'Shorts' }, { value: 'long', icon: '▤', label: 'Long Form' }];

export default function ContentFormatPanel({ value, onChange }) {
  return (
    <ScanConfigPanel step="5" title="Choose Content Format" helper="Filter content by video length." badge={FORMATS.find((format) => format.value === value)?.label}>
      <div className="pi-format-list">{FORMATS.map((format) => <button type="button" key={format.value} className={value === format.value ? 'selected' : ''} onClick={() => onChange(format.value)}><span>{format.icon}</span>{format.label}{value === format.value && <b>✓</b>}</button>)}</div>
    </ScanConfigPanel>
  );
}
