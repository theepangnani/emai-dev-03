import { memo, useEffect, useRef, useState, lazy, Suspense } from 'react';
import './StreamingMarkdown.css';

/**
 * Lazy-load markdown renderer with only remarkGfm during streaming
 * (avoids incomplete LaTeX parse errors), full plugins after streaming.
 */
const StreamingRenderer = lazy(() =>
  Promise.all([
    import('react-markdown'),
    import('remark-gfm'),
  ]).then(([md, gfm]) => {
    const ReactMarkdown = md.default;
    const remarkGfm = gfm.default;

    function Renderer({ content }: { content: string }) {
      return (
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {content}
        </ReactMarkdown>
      );
    }
    return { default: Renderer };
  })
);

const FullRenderer = lazy(() =>
  Promise.all([
    import('react-markdown'),
    import('remark-gfm'),
    import('remark-math'),
    import('rehype-katex'),
    import('katex/dist/katex.min.css'),
  ]).then(([md, gfm, math, katex]) => {
    const ReactMarkdown = md.default;
    const remarkGfm = gfm.default;
    const remarkMath = math.default;
    const rehypeKatex = katex.default;

    function Renderer({ content }: { content: string }) {
      return (
        <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>
          {content}
        </ReactMarkdown>
      );
    }
    return { default: Renderer };
  })
);

interface StreamingMarkdownProps {
  content: string;
  isStreaming: boolean;
  className?: string;
}

export const StreamingMarkdown = memo(function StreamingMarkdown({
  content,
  isStreaming,
  className,
}: StreamingMarkdownProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [userScrolledUp, setUserScrolledUp] = useState(false);
  const prevScrollTop = useRef(0);

  // Auto-scroll to bottom during streaming, unless user scrolled up
  useEffect(() => {
    if (!isStreaming || userScrolledUp) return;
    const el = containerRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [content, isStreaming, userScrolledUp]);

  // Detect user scrolling up to pause auto-scroll
  useEffect(() => {
    const el = containerRef.current;
    if (!el || !isStreaming) return;
    const handleScroll = () => {
      const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
      if (el.scrollTop < prevScrollTop.current && !atBottom) {
        setUserScrolledUp(true);
      } else if (atBottom) {
        setUserScrolledUp(false);
      }
      prevScrollTop.current = el.scrollTop;
    };
    el.addEventListener('scroll', handleScroll, { passive: true });
    return () => {
      el.removeEventListener('scroll', handleScroll);
      // Reset scroll lock when streaming stops (cleanup runs on isStreaming change)
      setUserScrolledUp(false);
    };
  }, [isStreaming]);

  return (
    <div className={`streaming-markdown${className ? ` ${className}` : ''}`}>
      {isStreaming && (
        <div className="streaming-markdown-badge">Generating...</div>
      )}
      <div className="streaming-markdown-body" ref={containerRef}>
        <Suspense fallback={<div className="streaming-markdown-loading">Loading...</div>}>
          {isStreaming ? (
            <>
              <StreamingRenderer content={content} />
              <span className="streaming-cursor" />
            </>
          ) : (
            <FullRenderer content={content} />
          )}
        </Suspense>
      </div>
    </div>
  );
});
