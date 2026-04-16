import { Suspense, useState, useCallback } from 'react';
import { MarkdownBody, MarkdownErrorBoundary } from '../ContentCard';
import './ASGFSlideCard.css';

export interface SlideData {
  slideNumber: number;
  title: string;
  body: string;
  vocabularyTerms?: string[];
  sourceAttribution?: string;
  readMoreContent?: string;
  bloomTier?: string;
}

interface ASGFSlideCardProps {
  slide: SlideData;
  totalSlides: number;
}

export function ASGFSlideCard({ slide, totalSlides }: ASGFSlideCardProps) {
  const [readMoreOpen, setReadMoreOpen] = useState(false);

  const toggleReadMore = useCallback(() => {
    setReadMoreOpen(prev => !prev);
  }, []);

  return (
    <div className="asgf-slide-card" role="region" aria-label={`Slide ${slide.slideNumber} of ${totalSlides}: ${slide.title}`}>
      {/* Title bar */}
      <div className="asgf-slide-header">
        <h3 className="asgf-slide-title">{slide.title}</h3>
        <span className="asgf-slide-number">{slide.slideNumber} of {totalSlides}</span>
      </div>

      {/* Body */}
      <div className="asgf-slide-body">
        <MarkdownErrorBoundary>
          <Suspense fallback={<div style={{ padding: '1rem', color: 'var(--color-ink-muted)', textAlign: 'center' }}>Loading content...</div>}>
            <MarkdownBody content={slide.body} />
          </Suspense>
        </MarkdownErrorBoundary>
      </div>

      {/* Vocabulary terms */}
      {slide.vocabularyTerms && slide.vocabularyTerms.length > 0 && (
        <div className="asgf-slide-vocab" aria-label="Vocabulary terms">
          {slide.vocabularyTerms.map(term => (
            <span key={term} className="asgf-slide-vocab-term">{term}</span>
          ))}
        </div>
      )}

      {/* Source attribution */}
      {slide.sourceAttribution && (
        <div className="asgf-slide-source">
          <span className="asgf-slide-source-badge">
            <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path d="M2 3h12v10H2V3z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
              <path d="M5 7h6M5 9.5h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            {slide.sourceAttribution}
          </span>
        </div>
      )}

      {/* Bloom tier */}
      {slide.bloomTier && (
        <div className="asgf-slide-bloom">
          <span className="asgf-slide-bloom-badge">{slide.bloomTier}</span>
        </div>
      )}

      {/* Read more */}
      {slide.readMoreContent && (
        <div className="asgf-slide-readmore">
          <button
            className="asgf-slide-readmore-toggle"
            onClick={toggleReadMore}
            aria-expanded={readMoreOpen}
            type="button"
          >
            <svg
              className={`asgf-slide-readmore-chevron${readMoreOpen ? ' asgf-slide-readmore-chevron--open' : ''}`}
              width="14"
              height="14"
              viewBox="0 0 16 16"
              fill="none"
              aria-hidden="true"
            >
              <path d="M6 4l4 4-4 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Read more
          </button>
          <div className={`asgf-slide-readmore-content${readMoreOpen ? ' asgf-slide-readmore-content--open' : ''}`}>
            <MarkdownErrorBoundary>
              <Suspense fallback={<div style={{ color: 'var(--color-ink-muted)' }}>Loading...</div>}>
                <MarkdownBody content={slide.readMoreContent} />
              </Suspense>
            </MarkdownErrorBoundary>
          </div>
        </div>
      )}
    </div>
  );
}
