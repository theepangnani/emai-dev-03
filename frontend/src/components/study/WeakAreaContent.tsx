import { useCallback, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './WeakAreaContent.css';

interface WeakAreaContentProps {
  /** Full markdown analysis content */
  content: string;
  /** JSON string of weak topic labels, e.g. '["Fractions","Algebra"]' */
  weakTopics?: string | null;
}

export default function WeakAreaContent({ content, weakTopics }: WeakAreaContentProps) {
  const topics: string[] = useMemo(() => {
    if (!weakTopics) return [];
    try {
      const parsed = JSON.parse(weakTopics);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }, [weakTopics]);

  const handlePrint = useCallback(() => {
    window.print();
  }, []);

  const handleDownloadPdf = useCallback(() => {
    // No dedicated PDF export utility available; falls back to browser print dialog
    window.print();
  }, []);

  return (
    <div className="weak-area-container">
      {topics.length > 0 && (
        <div className="weak-area-topics">
          {topics.map((topic) => (
            <span key={topic} className="weak-area-topic-pill">
              {topic}
            </span>
          ))}
        </div>
      )}

      <div className="weak-area-analysis">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </div>

      <div className="weak-area-actions">
        <button type="button" onClick={handlePrint}>
          Print
        </button>
        <button type="button" onClick={handleDownloadPdf}>
          Save as PDF
        </button>
      </div>
    </div>
  );
}
