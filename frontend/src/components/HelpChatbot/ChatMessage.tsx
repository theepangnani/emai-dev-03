import { useState } from 'react';
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


function FeedbackButtons() {
  const [feedback, setFeedback] = useState<'yes' | 'no' | null>(null);
  if (feedback) {
    return (
      <div className="help-chatbot-feedback-thanks">
        {feedback === 'yes' ? 'Glad it helped!' : 'Sorry about that. Try rephrasing your question.'}
      </div>
    );
  }
  return (
    <div className="help-chatbot-feedback">
      <span className="help-chatbot-feedback-label">Was this helpful?</span>
      <button className="help-chatbot-feedback-btn" onClick={() => setFeedback('yes')} aria-label="Yes, helpful">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14z"/><path d="M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg>
      </button>
      <button className="help-chatbot-feedback-btn" onClick={() => setFeedback('no')} aria-label="No, not helpful">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10z"/><path d="M17 2h3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-3"/></svg>
      </button>
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
        {role === 'assistant' && <FeedbackButtons />}
      </div>
    </div>
  );
}
