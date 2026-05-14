import { useState, useEffect } from 'react';
import { api } from '../api/client';

const REGIONS = [
  { code: '', label: 'All Regions' },
  { code: 'US', label: '🇺🇸 United States' },
  { code: 'GB', label: '🇬🇧 United Kingdom' },
  { code: 'CA', label: '🇨🇦 Canada' },
  { code: 'DE', label: '🇩🇪 Germany' },
  { code: 'FR', label: '🇫🇷 France' },
  { code: 'AU', label: '🇦🇺 Australia' },
  { code: 'AE', label: '🇦🇪 UAE' },
  { code: 'IN', label: '🇮🇳 India' },
  { code: 'JP', label: '🇯🇵 Japan' },
  { code: 'KR', label: '🇰🇷 South Korea' },
  { code: 'BR', label: '🇧🇷 Brazil' },
  { code: 'SA', label: '🇸🇦 Saudi Arabia' },
];

const CONTENT_TYPES = [
  { code: '', label: 'All Types' },
  { code: 'shorts', label: '⚡ Shorts' },
  { code: 'long', label: '🎬 Long-form' },
];

export default function GlobalFilterBar({ filters, onChange }) {
  const [niches, setNiches] = useState([]);

  useEffect(() => {
    api.getHealth().then((h) => setNiches(h.niches || [])).catch(() => {});
  }, []);

  const update = (key, value) => {
    onChange({ ...filters, [key]: value || '' });
  };

  const activeCount = [filters.region, filters.category, filters.content_type].filter(Boolean).length;

  return (
    <div className="gfb">
      <div className="gfb-row">
        <span className="gfb-icon">🔎</span>

        <select
          className="gfb-select"
          value={filters.region || ''}
          onChange={(e) => update('region', e.target.value)}
        >
          {REGIONS.map((r) => (
            <option key={r.code} value={r.code}>{r.label}</option>
          ))}
        </select>

        <select
          className="gfb-select"
          value={filters.category || ''}
          onChange={(e) => update('category', e.target.value)}
        >
          <option value="">All Categories</option>
          {niches.map((n) => (
            <option key={n} value={n}>{n}</option>
          ))}
        </select>

        <select
          className="gfb-select"
          value={filters.content_type || ''}
          onChange={(e) => update('content_type', e.target.value)}
        >
          {CONTENT_TYPES.map((t) => (
            <option key={t.code} value={t.code}>{t.label}</option>
          ))}
        </select>

        {activeCount > 0 && (
          <button
            className="gfb-clear"
            onClick={() => onChange({ region: '', category: '', content_type: '' })}
          >
            ✕ Clear ({activeCount})
          </button>
        )}
      </div>

      {activeCount > 0 && (
        <div className="gfb-active">
          {filters.region && <span className="gfb-chip">{REGIONS.find(r => r.code === filters.region)?.label || filters.region}</span>}
          {filters.category && <span className="gfb-chip">📂 {filters.category}</span>}
          {filters.content_type && <span className="gfb-chip">{CONTENT_TYPES.find(t => t.code === filters.content_type)?.label || filters.content_type}</span>}
        </div>
      )}
    </div>
  );
}
