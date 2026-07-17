import { useState } from 'react';
import PlatformIcon from '../PlatformIcon';
import { getContentThumbnail, getDurationLabel } from './trendingUtils';

function ThumbnailImage({ thumbnail, video }) {
  const [failed, setFailed] = useState(false);
  if (!thumbnail || failed) return <ThumbnailFallback video={video} />;
  return <img src={thumbnail} alt={video?.title || 'Trending content thumbnail'} loading="lazy" onError={() => setFailed(true)} />;
}

function ThumbnailFallback({ video }) {
  return (
    <div className={`tr-thumbnail-fallback tr-thumbnail-${video?.platform || 'unknown'}`}>
      <PlatformIcon platform={video?.platform} size={21} color="#f4f7ff" />
      <span>{video?.platform || 'content'}</span>
    </div>
  );
}

export default function ContentThumbnail({ video, large = false }) {
  const thumbnail = getContentThumbnail(video);
  const duration = getDurationLabel(video);
  return (
    <div className={`tr-content-thumbnail ${large ? 'tr-content-thumbnail-large' : ''}`}>
      <ThumbnailImage key={thumbnail} thumbnail={thumbnail} video={video} />
      <span className="tr-thumbnail-shade" />
      {duration && <span className="tr-duration">{duration}</span>}
    </div>
  );
}
