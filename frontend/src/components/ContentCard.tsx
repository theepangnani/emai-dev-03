import { lazy, useMemo } from 'react';
import type { ReactNode } from 'react';
import { looksLikeOCR } from '../utils/ocrDetect';
import './ContentCard.css';

/* ── Lazy-loaded Markdown renderer ─────────────────────────────── */

function normalizeContent(content: string) {
  return content
    .replace(/\r\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

export const MarkdownBody = lazy(() =>
  Promise.all([import('react-markdown'), import('remark-gfm')]).then(
    ([md, gfm]) => ({
      default: ({ content }: { content: string }) => {
        const ReactMarkdown = md.default;
        const remarkGfm = gfm.default;
        const normalized = normalizeContent(content);
        return <ReactMarkdown remarkPlugins={[remarkGfm]}>{normalized}</ReactMarkdown>;
      },
    }),
  ),
);

/* ── ContentCard wrapper ───────────────────────────────────────── */

interface ContentCardProps {
  children: ReactNode;
  ocrCheckText?: string;
  className?: string;
}

export function ContentCard({ children, ocrCheckText, className }: ContentCardProps) {
  const isOCR = useMemo(
    () => (ocrCheckText ? looksLikeOCR(ocrCheckText) : false),
    [ocrCheckText],
  );

  return (
    <div className={`content-card${className ? ` ${className}` : ''}`}>
      {isOCR && (
        <div className="content-card-ocr-notice">
          This content appears to have been extracted via OCR and may contain
          formatting errors or inaccuracies. Review before generating study materials.
        </div>
      )}
      <div className="content-card-body">{children}</div>
    </div>
  );
}
