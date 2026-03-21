import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import type { VideoInfo, SearchResult } from './useHelpChat';
import { SearchResultCards } from './SearchResultCard';

const AI_UNCERTAINTY_PHRASES = [
  "i'm not sure",
  "i don't know",
  "could you clarify",
  "not clear",
  "doesn't appear",
  "cannot find",
  "i don't have",
  "unclear",
  "i'm unable to",
  "i cannot determine",
  "not enough information",
  "i'm not certain",
];

function hasUncertainty(text: string): boolean {
  const lower = text.toLowerCase();
  return AI_UNCERTAINTY_PHRASES.some(phrase => lower.includes(phrase));
}

interface ChatMessageProps {
  role: 'user' | 'assistant';
  content: string;
  videos?: VideoInfo[];
  sources?: string[];
  search_results?: SearchResult[];
  mode?: 'help' | 'study_qa';
  credits_used?: number;
  onSaveAsGuide?: (content: string) => Promise<unknown>;
  onSaveAsMaterial?: (content: string) => Promise<unknown>;
  hasCourseId?: boolean;
}

function VideoEmbed({ video }: { video: VideoInfo }) {
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

function QASaveActions({
  content, onSaveAsGuide, onSaveAsMaterial, hasCourseId, isUncertain,
}: {
  content: string;
  onSaveAsGuide?: (content: string) => Promise<unknown>;
  onSaveAsMaterial?: (content: string) => Promise<unknown>;
  hasCourseId?: boolean;
  isUncertain?: boolean;
}) {
  const [saving, setSaving] = useState<'guide' | 'material' | null>(null);
  const [saved, setSaved] = useState<'guide' | 'material' | null>(null);

  const handleSave = async (type: 'guide' | 'material') => {
    setSaving(type);
    try {
      if (type === 'guide' && onSaveAsGuide) {
        await onSaveAsGuide(content);
      } else if (type === 'material' && onSaveAsMaterial) {
        await onSaveAsMaterial(content);
      }
      setSaved(type);
    } catch {
      /* error handled by caller */
    } finally {
      setSaving(null);
    }
  };

  if (isUncertain) {
    return (
      <div className="help-chatbot-qa-actions">
        <span className="help-chatbot-qa-uncertain">This response may be uncertain and cannot be saved as a guide.</span>
      </div>
    );
  }

  return (
    <div className="help-chatbot-qa-actions">
      <button
        className={`help-chatbot-qa-action ${saved === 'guide' ? 'help-chatbot-qa-action--saved' : ''}`}
        onClick={() => handleSave('guide')}
        disabled={saving !== null || saved === 'guide'}
      >
        {saved === 'guide' ? 'Saved as Guide' : saving === 'guide' ? 'Saving...' : 'Save as Study Guide'}
      </button>
      {hasCourseId && (
        <button
          className={`help-chatbot-qa-action ${saved === 'material' ? 'help-chatbot-qa-action--saved' : ''}`}
          onClick={() => handleSave('material')}
          disabled={saving !== null || saved === 'material'}
        >
          {saved === 'material' ? 'Saved as Material' : saving === 'material' ? 'Saving...' : 'Save as Class Material'}
        </button>
      )}
    </div>
  );
}

export function ChatMessage({
  role, content, videos, sources, search_results,
  mode, credits_used, onSaveAsGuide, onSaveAsMaterial, hasCourseId,
}: ChatMessageProps) {
  const navigate = useNavigate();
  const isUncertain = useMemo(() => role === 'assistant' && hasUncertainty(content), [role, content]);

  return (
    <div className={`help-chatbot-message help-chatbot-message--${role}`}>
      <div className="help-chatbot-bubble">
        {role === 'assistant' ? (
          <ReactMarkdown components={{
            a: ({ href, children }) => {
              if (href && href.startsWith('/')) {
                return (
                  <a
                    href={href}
                    onClick={(e) => {
                      e.preventDefault();
                      navigate(href);
                    }}
                    style={{ color: '#1a73e8', textDecoration: 'underline', cursor: 'pointer' }}
                  >
                    {children}
                  </a>
                );
              }
              return (
                <a href={href} target="_blank" rel="noopener noreferrer">
                  {children}
                </a>
              );
            },
          }}>{content}</ReactMarkdown>
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

        {search_results && search_results.length > 0 && (
          <SearchResultCards results={search_results} />
        )}

        {role === 'assistant' && mode === 'study_qa' && content && (
          <QASaveActions
            content={content}
            onSaveAsGuide={onSaveAsGuide}
            onSaveAsMaterial={onSaveAsMaterial}
            hasCourseId={hasCourseId}
            isUncertain={isUncertain}
          />
        )}

        {role === 'assistant' && mode !== 'study_qa' && <FeedbackButtons />}

        {credits_used != null && credits_used > 0 && (
          <div className="help-chatbot-credits-badge">{credits_used} credit used</div>
        )}
      </div>
    </div>
  );
}
