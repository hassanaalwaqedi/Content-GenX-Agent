export default function PipelineHeader({ config, validation }) {
  const readiness = validation.valid ? 'Ready to launch' : validation.issues[0] || 'Configuration needs attention';
  return (
    <header className="pi-header">
      <div className="pi-header-mark" aria-hidden="true"><span>AI</span><i /><i /><i /></div>
      <div>
        <h1>AI Market Intelligence</h1>
        <p>Configure and launch an AI-powered scan of trending content across global markets.</p>
        <div className={`pi-readiness ${validation.valid ? 'ready' : 'attention'}`}><span aria-hidden="true">●</span>{readiness}<small>{config.regions.length} market{config.regions.length === 1 ? '' : 's'} · {config.platforms.length} platform{config.platforms.length === 1 ? '' : 's'}</small></div>
      </div>
    </header>
  );
}
