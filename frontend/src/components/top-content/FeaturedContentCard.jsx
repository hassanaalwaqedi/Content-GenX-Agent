import PlatformIcon from '../PlatformIcon';
import ContentActions from './ContentActions';
import ContentInsight from './ContentInsight';
import ContentMedia from './ContentMedia';
import ContentMetrics from './ContentMetrics';
import { formatPublishedAt, getContentTags } from './contentUtils';

export default function FeaturedContentCard({ video, onGenerate, onTranscript }) {
  if (!video) return null;
  const tags = getContentTags(video, 5);
  return (
    <section className="tc-featured-card" aria-label="Featured top-performing content">
      <ContentMedia video={video} rank={1} featured />
      <div className="tc-featured-main">
        <div className="tc-section-kicker">Featured opportunity <span>Highest AI score</span></div>
        <h2>{video.title || 'Untitled content'}</h2>
        <p className="tc-featured-creator"><PlatformIcon platform={video.platform} size={17} /> {video.channel || 'Unknown creator'} <span>•</span> {formatPublishedAt(video.published_at)}</p>
        <ContentMetrics video={video} />
        <div className="tc-tag-row tc-featured-tags">{tags.map((tag) => <span key={tag}>#{tag}</span>)}</div>
      </div>
      <div className="tc-featured-insight">
        <ContentInsight video={video} />
        <ContentActions video={video} onGenerate={onGenerate} onTranscript={onTranscript} featured />
      </div>
    </section>
  );
}
