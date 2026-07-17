export default function ScanConfigPanel({ step, title, helper, badge, children, className = '' }) {
  return (
    <section className={`pi-config-panel ${className}`}>
      <header>
        <span className="pi-step-number">{step}</span>
        <div><h2>{title}</h2><p>{helper}</p></div>
        {badge && <span className="pi-panel-badge">{badge}</span>}
      </header>
      <div className="pi-config-body">{children}</div>
    </section>
  );
}
