import { useState, useCallback } from 'react';
import { api } from '../api/client';

/* ── Copy helper ── */
function useCopy() {
  const [copiedId, setCopiedId] = useState(null);
  const copy = useCallback((text, id) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 1800);
    });
  }, []);
  return { copiedId, copy };
}

/* ── CopyButton ── */
function CopyBtn({ text, id, copiedId, copy, label }) {
  const isCopied = copiedId === id;
  return (
    <button
      onClick={() => copy(text, id)}
      style={{
        background: isCopied ? 'var(--color-accent-green-bg)' : 'var(--color-bg-input)',
        border: `1px solid ${isCopied ? 'var(--color-accent-green)' : 'var(--color-border)'}`,
        color: isCopied ? 'var(--color-accent-green)' : 'var(--color-text-secondary)',
        padding: '3px 10px', borderRadius: 100, fontSize: 'var(--font-size-xs)',
        fontWeight: 600, cursor: 'pointer', transition: 'all 0.15s ease',
        fontFamily: 'var(--font-family)',
      }}
    >
      {isCopied ? '✓ Copied' : (label || '📋 Copy')}
    </button>
  );
}

/* ── Hashtag Chip ── */
function HashtagChip({ tag, copiedId, copy }) {
  return (
    <span
      onClick={() => copy(tag, `tag-${tag}`)}
      style={{
        background: copiedId === `tag-${tag}` ? 'var(--color-primary-bg)' : 'var(--color-bg-input)',
        color: copiedId === `tag-${tag}` ? 'var(--color-primary)' : 'var(--color-text-secondary)',
        padding: '4px 12px', borderRadius: 100, fontSize: 'var(--font-size-xs)',
        fontWeight: 600, cursor: 'pointer', border: '1px solid var(--color-border)',
        transition: 'all 0.15s ease',
      }}
    >
      {tag}
    </span>
  );
}

/* ── Spinner ── */
function GeneratingSpinner() {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', padding: '3rem 1rem', gap: 16,
    }}>
      <div style={{
        width: 48, height: 48, border: '3px solid var(--color-border)',
        borderTopColor: 'var(--color-primary)', borderRadius: '50%',
        animation: 'spin 0.8s linear infinite',
      }} />
      <p style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-sm)' }}>
        AI is generating your content...
      </p>
      <p style={{ color: 'var(--color-text-muted)', fontSize: 'var(--font-size-xs)' }}>
        This usually takes 3-8 seconds
      </p>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════
   MAIN MODAL
   ══════════════════════════════════════════════════════════════════ */
export default function ContentGeneratorModal({ video, onClose }) {
  const [platform, setPlatform] = useState('youtube');
  const [tone, setTone] = useState('professional');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const { copiedId, copy } = useCopy();

  if (!video) return null;

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await api.generateContent(video.video_id, platform, tone);
      setResult(data);
    } catch (err) {
      setError(err.message || 'Failed to generate content');
    } finally {
      setLoading(false);
    }
  };

  const handleCopyAll = () => {
    if (!result) return;
    const full = [
      `💡 IDEA: ${result.idea}`,
      '',
      '📝 TITLES:',
      ...result.titles.map((t, i) => `${i + 1}. ${t}`),
      '',
      '🎣 HOOKS:',
      ...result.hooks.map((h, i) => `${i + 1}. ${h}`),
      '',
      '🎬 SCRIPT:',
      result.script,
      '',
      `🎯 AUDIENCE: ${result.target_audience}`,
      '',
      `📊 STRATEGY: ${result.strategy}`,
      '',
      `# HASHTAGS: ${result.hashtags.join(' ')}`,
    ].join('\n');
    copy(full, 'all');
  };

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(6px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 'var(--space-lg)',
      }}
      onClick={onClose}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: 'var(--color-bg-card)', borderRadius: 'var(--radius-lg)',
          maxWidth: 780, width: '100%', maxHeight: '90vh', overflow: 'auto',
          boxShadow: '0 20px 60px rgba(0,0,0,0.5)', border: '1px solid var(--color-border)',
          padding: 'var(--space-2xl)',
        }}
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-xl)' }}>
          <div>
            <h2 style={{
              fontSize: 'var(--font-size-xl)', fontWeight: 800,
              color: 'var(--color-text)', marginBottom: 4,
              display: 'flex', alignItems: 'center', gap: 8,
            }}>
              <span style={{ fontSize: '1.4rem' }}>✨</span> AI Content Generator
            </h2>
            <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)', maxWidth: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              Based on: {video.title}
            </p>
          </div>
          <button onClick={onClose} style={{
            background: 'var(--color-bg-input)', border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-sm)', color: 'var(--color-text)', cursor: 'pointer',
            fontSize: 18, width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>×</button>
        </div>

        {/* Controls */}
        {!result && !loading && (
          <div style={{ marginBottom: 'var(--space-xl)' }}>
            <div style={{ display: 'flex', gap: 'var(--space-md)', marginBottom: 'var(--space-lg)', flexWrap: 'wrap' }}>
              <div style={{ flex: 1, minWidth: 160 }}>
                <label style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', fontWeight: 600, display: 'block', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Platform
                </label>
                <select className="select-input" value={platform} onChange={e => setPlatform(e.target.value)} style={{ width: '100%' }}>
                  <option value="youtube">📺 YouTube</option>
                  <option value="tiktok">🎵 TikTok</option>
                  <option value="linkedin">💼 LinkedIn</option>
                </select>
              </div>
              <div style={{ flex: 1, minWidth: 160 }}>
                <label style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', fontWeight: 600, display: 'block', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Tone
                </label>
                <select className="select-input" value={tone} onChange={e => setTone(e.target.value)} style={{ width: '100%' }}>
                  <option value="professional">🎯 Professional</option>
                  <option value="casual">😎 Casual</option>
                  <option value="aggressive">🔥 Aggressive</option>
                </select>
              </div>
            </div>
            <button
              className="btn btn-primary"
              onClick={handleGenerate}
              style={{ width: '100%', padding: '12px', fontSize: 'var(--font-size-base)', justifyContent: 'center' }}
            >
              ✨ Generate Content
            </button>
          </div>
        )}

        {/* Loading */}
        {loading && <GeneratingSpinner />}

        {/* Error */}
        {error && (
          <div style={{
            background: 'var(--color-accent-red-bg)', border: '1px solid var(--color-accent-red)',
            borderRadius: 'var(--radius-sm)', padding: 'var(--space-lg)',
            color: 'var(--color-accent-red)', fontSize: 'var(--font-size-sm)',
            marginBottom: 'var(--space-lg)',
          }}>
            ⚠️ {error}
            <button
              className="btn btn-secondary"
              style={{ marginTop: 8, display: 'block' }}
              onClick={handleGenerate}
            >
              Retry
            </button>
          </div>
        )}

        {/* Result */}
        {result && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-lg)' }}>
            {/* Top bar */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', gap: 6 }}>
                <span className="badge badge-blue">{result.platform}</span>
                <span className="badge badge-purple">{result.tone}</span>
                {result.cached && <span className="badge badge-green">Cached</span>}
                <span className="badge badge-orange">{result.source}</span>
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                <CopyBtn text="" id="all" copiedId={copiedId} copy={() => handleCopyAll()} label="📋 Copy All" />
                <button
                  className="btn btn-secondary"
                  style={{ padding: '3px 10px', fontSize: 'var(--font-size-xs)' }}
                  onClick={() => { setResult(null); setError(null); }}
                >
                  🔄 Regenerate
                </button>
              </div>
            </div>

            {/* Idea */}
            <div style={{
              background: 'linear-gradient(135deg, rgba(79,140,255,0.08), rgba(167,139,250,0.08))',
              border: '1px solid var(--color-primary)', borderRadius: 'var(--radius-md)',
              padding: 'var(--space-xl)', position: 'relative',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <span style={{ fontSize: 'var(--font-size-xs)', fontWeight: 700, color: 'var(--color-primary)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                    💡 Viral Idea
                  </span>
                  <p style={{ fontSize: 'var(--font-size-base)', color: 'var(--color-text)', fontWeight: 600, marginTop: 6, lineHeight: 1.6 }}>
                    {result.idea}
                  </p>
                </div>
                <CopyBtn text={result.idea} id="idea" copiedId={copiedId} copy={copy} />
              </div>
            </div>

            {/* Titles */}
            <Section title="📝 High-CTR Titles">
              {result.titles.map((t, i) => (
                <ItemRow key={i} text={t} id={`title-${i}`} copiedId={copiedId} copy={copy} index={i + 1} />
              ))}
            </Section>

            {/* Hooks */}
            <Section title="🎣 Hooks">
              {result.hooks.map((h, i) => (
                <ItemRow key={i} text={h} id={`hook-${i}`} copiedId={copiedId} copy={copy} index={i + 1} />
              ))}
            </Section>

            {/* Script */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <span style={{ fontSize: 'var(--font-size-xs)', fontWeight: 700, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  🎬 Script
                </span>
                <CopyBtn text={result.script} id="script" copiedId={copiedId} copy={copy} />
              </div>
              <div style={{
                background: 'var(--color-bg)', border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-sm)', padding: 'var(--space-lg)',
                fontSize: 'var(--font-size-sm)', color: 'var(--color-text)', lineHeight: 1.8,
                whiteSpace: 'pre-wrap', fontFamily: 'var(--font-family)',
              }}>
                {result.script}
              </div>
            </div>

            {/* Audience & Strategy */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-md)' }}>
              <InfoBox icon="🎯" label="Target Audience" text={result.target_audience} id="audience" copiedId={copiedId} copy={copy} />
              <InfoBox icon="📊" label="Strategy" text={result.strategy} id="strategy" copiedId={copiedId} copy={copy} />
            </div>

            {/* Hashtags */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <span style={{ fontSize: 'var(--font-size-xs)', fontWeight: 700, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  # Hashtags
                </span>
                <CopyBtn text={result.hashtags.join(' ')} id="hashtags-all" copiedId={copiedId} copy={copy} label="Copy All" />
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {result.hashtags.map(tag => (
                  <HashtagChip key={tag} tag={tag} copiedId={copiedId} copy={copy} />
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Sub-components ── */
function Section({ title, children }) {
  return (
    <div>
      <span style={{ fontSize: 'var(--font-size-xs)', fontWeight: 700, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', display: 'block', marginBottom: 8 }}>
        {title}
      </span>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {children}
      </div>
    </div>
  );
}

function ItemRow({ text, id, copiedId, copy, index }) {
  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      background: 'var(--color-bg)', border: '1px solid var(--color-border)',
      borderRadius: 'var(--radius-sm)', padding: '8px 12px',
    }}>
      <span style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text)', flex: 1 }}>
        <span style={{ color: 'var(--color-text-muted)', marginRight: 8, fontWeight: 700 }}>{index}.</span>
        {text}
      </span>
      <CopyBtn text={text} id={id} copiedId={copiedId} copy={copy} />
    </div>
  );
}

function InfoBox({ icon, label, text, id, copiedId, copy }) {
  return (
    <div style={{
      background: 'var(--color-bg)', border: '1px solid var(--color-border)',
      borderRadius: 'var(--radius-sm)', padding: 'var(--space-md)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <span style={{ fontSize: 'var(--font-size-xs)', fontWeight: 700, color: 'var(--color-text-muted)', textTransform: 'uppercase' }}>
          {icon} {label}
        </span>
        <CopyBtn text={text} id={id} copiedId={copiedId} copy={copy} />
      </div>
      <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text)', lineHeight: 1.6 }}>{text}</p>
    </div>
  );
}
