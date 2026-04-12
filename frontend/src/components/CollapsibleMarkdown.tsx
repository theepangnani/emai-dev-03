import { Suspense, useMemo } from 'react';
import { MarkdownBody, MarkdownErrorBoundary } from './ContentCard';
import { CollapsibleSection } from './CollapsibleSection';
import { generateHeadingId, deduplicateIds } from '../utils/headingId';

interface MarkdownSection {
  id: string;
  title: string;
  content: string;
}

/** Split markdown content into sections at H2 boundaries */
function splitAtH2(markdown: string): { preamble: string; sections: MarkdownSection[] } {
  const lines = markdown.split('\n');
  let preamble = '';
  const sections: MarkdownSection[] = [];
  let current: { title: string; id: string; lines: string[] } | null = null;

  let inCodeBlock = false;
  for (const line of lines) {
    if (line.trim().startsWith('```')) {
      inCodeBlock = !inCodeBlock;
    }
    const match = !inCodeBlock && line.match(/^##\s+(.+)/);
    if (match) {
      // Flush previous section
      if (current) {
        sections.push({ id: current.id, title: current.title, content: current.lines.join('\n') });
      }
      const title = match[1].replace(/[*_`~]/g, '').trim();
      current = { title, id: generateHeadingId(title), lines: [] };
    } else if (current) {
      current.lines.push(line);
    } else {
      preamble += line + '\n';
    }
  }
  // Flush last section
  if (current) {
    sections.push({ id: current.id, title: current.title, content: current.lines.join('\n') });
  }

  return { preamble: preamble.trimEnd(), sections: deduplicateIds(sections) };
}

interface CollapsibleMarkdownProps {
  content: string;
  guideId: string | number;
  courseContentId?: number;
}

export function CollapsibleMarkdown({ content, guideId, courseContentId }: CollapsibleMarkdownProps) {
  const { preamble, sections } = useMemo(() => splitAtH2(content), [content]);

  // If fewer than 2 H2 sections, render normally without collapsible wrappers
  if (sections.length < 2) {
    return (
      <MarkdownErrorBoundary>
        <Suspense fallback={<div className="content-card-render-loading">Formatting study guide...</div>}>
          <MarkdownBody content={content} courseContentId={courseContentId} />
        </Suspense>
      </MarkdownErrorBoundary>
    );
  }

  return (
    <div className="sg-collapsible-markdown">
      {preamble && (
        <MarkdownErrorBoundary>
          <Suspense fallback={<div className="content-card-render-loading">Formatting...</div>}>
            <MarkdownBody content={preamble} courseContentId={courseContentId} />
          </Suspense>
        </MarkdownErrorBoundary>
      )}
      {sections.map((section, i) => (
        <CollapsibleSection key={`${section.id}-${i}`} id={section.id} title={section.title} guideId={guideId}>
          <MarkdownErrorBoundary>
            <Suspense fallback={<div className="content-card-render-loading">Formatting...</div>}>
              <MarkdownBody content={section.content} courseContentId={courseContentId} />
            </Suspense>
          </MarkdownErrorBoundary>
        </CollapsibleSection>
      ))}
    </div>
  );
}
