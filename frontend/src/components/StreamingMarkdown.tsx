import React, { useEffect, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import './StreamingMarkdown.css';

interface StreamingMarkdownProps {
  content: string;
  isStreaming: boolean;
  className?: string;
}

function GeneratingBadge() {
  return (
    <div className="streaming-generating-badge">
      <span className="streaming-generating-dot" aria-hidden="true" />
      Generating...
    </div>
  );
}

function StreamingMarkdownInner({
  content,
  isStreaming,
  className,
}: StreamingMarkdownProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const userScrolledRef = useRef(false);

  const handleScroll = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    userScrolledRef.current = !atBottom;
  }, []);

  useEffect(() => {
    if (!isStreaming) {
      userScrolledRef.current = false;
      return;
    }
    const el = containerRef.current;
    if (!el || userScrolledRef.current) return;
    el.scrollTop = el.scrollHeight;
  }, [content, isStreaming]);

  const remarkPlugins = isStreaming
    ? [remarkGfm]
    : [remarkGfm, remarkMath];

  const rehypePlugins = isStreaming
    ? []
    : [[rehypeKatex, { throwOnError: false }] as const];

  return (
    <div>
      {isStreaming && <GeneratingBadge />}
      <div
        ref={containerRef}
        className={`streaming-markdown ${className ?? ''}`}
        onScroll={handleScroll}
      >
        <ReactMarkdown
          remarkPlugins={remarkPlugins}
          /* eslint-disable-next-line @typescript-eslint/no-explicit-any */
          rehypePlugins={rehypePlugins as any}
        >
          {content}
        </ReactMarkdown>
        {isStreaming && <span className="streaming-cursor">▊</span>}
      </div>
    </div>
  );
}

export const StreamingMarkdown = React.memo(StreamingMarkdownInner);
