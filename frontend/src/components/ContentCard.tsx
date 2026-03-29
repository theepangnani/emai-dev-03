import { Component, lazy, useMemo, useState, useEffect, useCallback } from 'react';
import type { ReactNode } from 'react';
import { looksLikeOCR } from '../utils/ocrDetect';
import { api } from '../api/client';
import './ContentCard.css';

/* ── Image metadata returned by the backend ────────────────────── */

interface ContentImage {
  id: number;
  position_index: number;
}

/* ── AuthImage: fetches image via Axios (with Bearer token) ───── */

function AuthImage({ src, alt }: { src: string; alt?: string }) {
  const [objectUrl, setObjectUrl] = useState<string>('');
  const [error, setError] = useState(false);

  useEffect(() => {
    let revoke = '';
    let cancelled = false;
    api
      .get(src, { responseType: 'blob' })
      .then((res) => {
        if (cancelled) return;
        const url = URL.createObjectURL(res.data);
        revoke = url;
        setObjectUrl(url);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });
    return () => {
      cancelled = true;
      if (revoke) URL.revokeObjectURL(revoke);
    };
  }, [src]);

  if (error) return null;
  if (!objectUrl)
    return <span className="image-placeholder">{alt || 'Loading image\u2026'}</span>;
  return (
    <figure className="study-guide-image-figure">
      <img src={objectUrl} alt={alt || ''} className="study-guide-image" />
      {alt && <figcaption className="study-guide-image-caption">{alt}</figcaption>}
    </figure>
  );
}

/* ── Lazy-loaded Markdown renderer ─────────────────────────────── */

function normalizeContent(content: string) {
  return content
    .replace(/\r\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

/** Replace {{IMG-N}} markers AND relative markdown image refs with real API image URLs. */
function resolveImageMarkers(
  content: string,
  courseContentId: number,
  images: ContentImage[],
): string {
  const sorted = [...images].sort((a, b) => a.position_index - b.position_index);

  // 1. Replace {{IMG-N}} markers
  let result = content.replace(/\{\{IMG-(\d+)\}\}/g, (_match, n) => {
    const idx = parseInt(n, 10) - 1; // IMG-1 → index 0
    const img = sorted[idx];
    if (!img) return _match; // leave unresolved marker as-is
    return `/api/course-contents/${courseContentId}/images/${img.id}`;
  });

  // 2. Replace relative/broken markdown image refs like ![alt](filename)
  //    where the URL doesn't start with http or /api/
  let imageIndex = 0;
  result = result.replace(
    /!\[([^\]]*)\]\((?!https?:\/\/)(?!\/api\/)([^)]+)\)/g,
    (match, alt) => {
      const img = sorted[imageIndex];
      if (!img) return match;
      imageIndex++;
      return `![${alt}](/api/course-contents/${courseContentId}/images/${img.id})`;
    },
  );

  return result;
}

/**
 * Strip \hline from LaTeX math blocks that are NOT inside
 * \begin{array} or \begin{tabular} environments.
 * These are common AI-generation artifacts that cause KaTeX parse errors.
 */
function sanitizeLatex(content: string): string {
  // 1. Display math: $$...$$
  let result = content.replace(/\$\$([\s\S]*?)\$\$/g, (_match, inner: string) => {
    if (/\\begin\{(array|tabular)\}/.test(inner)) return _match;
    const cleaned = inner.replace(/\\hline\s*/g, '');
    if (cleaned !== inner) return `$$${cleaned}$$`;
    return _match;
  });
  // 2. Inline math: $...$ (single $, not preceded/followed by another $)
  result = result.replace(/(?<!\$)\$(?!\$)((?:[^$\\]|\\.)+)\$(?!\$)/g, (_match, inner: string) => {
    if (/\\begin\{(array|tabular)\}/.test(inner)) return _match;
    const cleaned = inner.replace(/\\hline\s*/g, '');
    if (cleaned !== inner) return `$${cleaned}$`;
    return _match;
  });
  return result;
}

const loadMarkdown = () =>
  Promise.all([
    import('react-markdown'),
    import('remark-gfm'),
    import('remark-math'),
    import('rehype-raw'),
    import('rehype-katex'),
    import('katex/dist/katex.min.css'),
  ]).then(([md, gfm, math, raw, katex]) => {
    const ReactMarkdown = md.default;
    const remarkGfm = gfm.default;
    const remarkMath = math.default;
    const rehypeRaw = raw.default;
    const rehypeKatex = katex.default;

      function MarkdownRenderer({
        content,
        courseContentId,
      }: {
        content: string;
        courseContentId?: number;
      }) {
        const [images, setImages] = useState<ContentImage[]>([]);

        useEffect(() => {
          if (!courseContentId) return;
          let cancelled = false;
          api
            .get<ContentImage[]>(`/api/course-contents/${courseContentId}/images`)
            .then((res) => {
              if (!cancelled) setImages(res.data);
            })
            .catch(() => {});
          return () => {
            cancelled = true;
          };
        }, [courseContentId]);

        const resolved = useMemo(() => {
          let text = normalizeContent(content);
          if (courseContentId && images.length > 0) {
            text = resolveImageMarkers(text, courseContentId, images);
          }
          text = sanitizeLatex(text);
          return text;
        }, [content, courseContentId, images]);

        /* Custom img renderer: use AuthImage for API-served images */
        const imgComponent = useCallback(
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          (props: any) => {
            const { src, alt } = props;
            if (src && src.startsWith('/api/')) {
              return <AuthImage src={src} alt={alt} />;
            }
            return <img src={src} alt={alt} style={{ maxWidth: '100%' }} />;
          },
          [],
        );

        return (
          <ReactMarkdown
            remarkPlugins={[remarkGfm, remarkMath]}
            rehypePlugins={[rehypeRaw, [rehypeKatex, { throwOnError: false }]]}
            components={{ img: imgComponent }}
          >
            {resolved}
          </ReactMarkdown>
        );
      }

      return { default: MarkdownRenderer };
    },
  );

export const MarkdownBody = lazy(() =>
  loadMarkdown().catch(() => {
    const reloaded = sessionStorage.getItem('chunk_reload');
    if (!reloaded) {
      sessionStorage.setItem('chunk_reload', '1');
      window.location.reload();
      return new Promise(() => {});
    }
    sessionStorage.removeItem('chunk_reload');
    return loadMarkdown();
  }),
);

/* ── Error boundary for MarkdownBody ───────────────────────────── */

interface MarkdownErrorBoundaryState {
  hasError: boolean;
}

export class MarkdownErrorBoundary extends Component<{ children: ReactNode; fallback?: ReactNode }, MarkdownErrorBoundaryState> {
  state: MarkdownErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): MarkdownErrorBoundaryState {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback || (
        <div style={{ padding: '1rem', color: 'var(--color-ink-muted, #64748b)', fontStyle: 'italic' }}>
          This content could not be rendered. Try reloading the page.
        </div>
      );
    }
    return this.props.children;
  }
}

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
