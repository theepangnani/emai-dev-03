import ReactMarkdown from 'react-markdown';
import type { VideoInfo } from './useHelpChat';

interface ChatMessageProps {
  role: 'user' | 'assistant';
  content: string;
  videos?: VideoInfo[];
  sources?: string[];
}

function VideoEmbed({ video }: { video: VideoInfo }) {
  // Extract YouTube video ID for embedding
  const getYouTubeId = (url: string) => {
    const match = url.match(/(?:youtu\.be\/|youtube\.com\/(?:embed\/|v\/|watch\?v=))([^&?#]+)/);
    return match?.[1];
  };

  const ytId = getYouTubeId(video.url);

  if (ytId) {
    return (
      <div className="help-chatbot-video">
        <iframe
          src={`https://www.youtube.com/embed/${ytId}`}
          title={video.title}
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowFullScreen
        />
        <p className="help-chatbot-video-title">{video.title}</p>
      </div>
    );
  }

  return (
    <div className="help-chatbot-video">
      <a href={video.url} target="_blank" rel="noopener noreferrer">
        {video.title}
      </a>
    </div>
  );
}

export function ChatMessage({ role, content, videos, sources }: ChatMessageProps) {
  return (
    <div className={`help-chatbot-message help-chatbot-message--${role}`}>
      <div className="help-chatbot-bubble">
        {role === 'assistant' ? (
          <ReactMarkdown>{content}</ReactMarkdown>
        ) : (
          <p>{content}</p>
        )}

        {videos && videos.length > 0 && (
          <div className="help-chatbot-videos">
            {videos.map((video, i) => (
              <VideoEmbed key={i} video={video} />
            ))}
          </div>
        )}

        {sources && sources.length > 0 && (
          <div className="help-chatbot-sources">
            {sources.map((source, i) => (
              <span key={i} className="help-chatbot-source">{source}</span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
