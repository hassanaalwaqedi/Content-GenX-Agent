import { Link } from 'react-router-dom';

export default function ContentActions({ video, onGenerate, onTranscript, featured = false }) {
  return (
    <div className={`tc-content-actions ${featured ? 'tc-content-actions-featured' : ''}`}>
      <Link to={`/video/${video.video_id}`} className="tc-button tc-button-secondary">View details</Link>
      <button className="tc-button tc-button-primary" onClick={() => onGenerate(video)}>✦ Generate similar</button>
      {video.platform === 'youtube' && onTranscript && (
        <button className="tc-icon-button" onClick={() => onTranscript(video)} title="View transcript" aria-label="View transcript">▤</button>
      )}
    </div>
  );
}
