export default function SkeletonCard() {
  return (
    <div className="vcard skeleton-card">
      <div className="skeleton-thumb skeleton-shimmer"></div>
      <div className="vcard-body">
        <div className="skeleton-line skeleton-shimmer" style={{ width: '85%', height: 16 }}></div>
        <div className="skeleton-line skeleton-shimmer" style={{ width: '55%', height: 12, marginTop: 8 }}></div>
        <div className="skeleton-row" style={{ marginTop: 12 }}>
          <div className="skeleton-line skeleton-shimmer" style={{ width: '30%', height: 12 }}></div>
          <div className="skeleton-line skeleton-shimmer" style={{ width: '25%', height: 12 }}></div>
          <div className="skeleton-line skeleton-shimmer" style={{ width: '20%', height: 12 }}></div>
        </div>
        <div className="skeleton-row" style={{ marginTop: 12 }}>
          <div className="skeleton-line skeleton-shimmer" style={{ width: '40%', height: 24, borderRadius: 6 }}></div>
          <div className="skeleton-line skeleton-shimmer" style={{ width: '35%', height: 24, borderRadius: 6 }}></div>
        </div>
      </div>
    </div>
  );
}
