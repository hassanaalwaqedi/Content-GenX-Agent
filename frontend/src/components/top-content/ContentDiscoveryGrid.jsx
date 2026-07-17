import ContentCard from './ContentCard';

export default function ContentDiscoveryGrid({ videos, viewMode, loading, onGenerate, onTranscript }) {
  if (loading) {
    return <div className={`tc-discovery-grid tc-discovery-grid-${viewMode}`}>{Array.from({ length: 8 }).map((_, index) => <div className="tc-content-skeleton" key={index} />)}</div>;
  }
  if (!videos.length) {
    return <div className="tc-empty-state"><span>⌕</span><h3>No content matches this view</h3><p>Clear a filter or use a broader search to discover more content.</p></div>;
  }
  return (
    <div className={`tc-discovery-grid tc-discovery-grid-${viewMode}`}>
      {videos.map((video, index) => (
        <ContentCard
          key={video.video_id}
          video={video}
          rank={index + 2}
          viewMode={viewMode}
          onGenerate={onGenerate}
          onTranscript={onTranscript}
        />
      ))}
    </div>
  );
}
