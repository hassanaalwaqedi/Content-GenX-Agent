import { useState } from 'react';
import PlatformIcon from '../PlatformIcon';
import { getContentStatus, getContentThumbnail, platformMeta } from './contentUtils';

export default function ContentMedia({ video, rank, featured = false }) {
  const thumbnail = getContentThumbnail(video);
  const [imageFailed, setImageFailed] = useState(false);
  const status = getContentStatus(video);
  const platform = platformMeta(video?.platform);
  const titleInitial = String(video?.title || 'Content').trim().charAt(0).toUpperCase();

  return (
    <div className={`tc-media ${featured ? 'tc-media-featured' : ''}`}>
      {thumbnail && !imageFailed ? (
        <img
          src={thumbnail}
          alt={video?.title || 'Content thumbnail'}
          loading={featured ? 'eager' : 'lazy'}
          onError={() => setImageFailed(true)}
        />
      ) : (
        <div className="tc-media-fallback" aria-label="Content preview unavailable">
          <span>{titleInitial}</span>
          <small>{platform.label}</small>
        </div>
      )}
      <div className="tc-media-shade" />
      <div className="tc-media-topline">
        {rank && <span className="tc-rank-badge">{rank}</span>}
        <span className={`tc-status-badge tc-status-${status.tone}`}>{status.label}</span>
        <span className="tc-platform-badge">
          <PlatformIcon platform={video?.platform} size={13} />
          {platform.label}
        </span>
      </div>
      <span className="tc-score-badge">AI {Number(video?.score || 0).toFixed(2)}</span>
    </div>
  );
}
