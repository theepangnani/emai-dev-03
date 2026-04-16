import { useState, useEffect, useCallback, useRef } from 'react';
import { ASGFSlideCard } from './ASGFSlideCard';
import type { SlideData } from './ASGFSlideCard';
import './ASGFSlideRenderer.css';

export type { SlideData };

export interface ASGFSlideRendererProps {
  slides: SlideData[];
  isGenerating?: boolean;
  onSlideChange?: (slideIndex: number) => void;
}

export function ASGFSlideRenderer({ slides, isGenerating, onSlideChange }: ASGFSlideRendererProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [direction, setDirection] = useState<'next' | 'prev'>('next');
  const [transitioning, setTransitioning] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const prevSlideCountRef = useRef(slides.length);

  const totalSlides = slides.length;

  // Auto-advance to newest slide when a new one is generated
  useEffect(() => {
    if (isGenerating && totalSlides > prevSlideCountRef.current) {
      setCurrentIndex(totalSlides - 1);
    }
    prevSlideCountRef.current = totalSlides;
  }, [totalSlides, isGenerating]);

  // Notify parent of slide changes
  useEffect(() => {
    onSlideChange?.(currentIndex);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentIndex]);

  const goTo = useCallback((index: number) => {
    if (index < 0 || index >= totalSlides || index === currentIndex || transitioning) return;
    setDirection(index > currentIndex ? 'next' : 'prev');
    setTransitioning(true);

    // Brief transition delay for animation
    requestAnimationFrame(() => {
      setCurrentIndex(index);
      setTimeout(() => setTransitioning(false), 260);
    });
  }, [currentIndex, totalSlides, transitioning]);

  const goPrev = useCallback(() => goTo(currentIndex - 1), [goTo, currentIndex]);
  const goNext = useCallback(() => goTo(currentIndex + 1), [goTo, currentIndex]);

  // Keyboard navigation
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      // Don't capture keys when user is typing in an input
      const target = e.target as HTMLElement;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) return;

      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        goPrev();
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        goNext();
      }
    }

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [goPrev, goNext]);

  if (totalSlides === 0 && !isGenerating) {
    return null;
  }

  const slide = slides[currentIndex];

  const enterClass = transitioning
    ? direction === 'next'
      ? ' asgf-slide-wrapper--entering'
      : ' asgf-slide-wrapper--entering-prev'
    : ' asgf-slide-wrapper--active';

  return (
    <div className="asgf-slide-renderer" ref={containerRef} aria-label="Mini-lesson slides" role="region">
      {/* Slide viewport */}
      <div className="asgf-slide-viewport">
        {slide && (
          <div className={`asgf-slide-wrapper${enterClass}`} key={currentIndex}>
            <ASGFSlideCard slide={slide} totalSlides={totalSlides} />
          </div>
        )}

        {/* Show loading state when generating and no slides yet */}
        {totalSlides === 0 && isGenerating && (
          <div className="asgf-slide-generating" style={{ padding: '3rem 0' }}>
            <div className="asgf-slide-generating-spinner" />
            <span>Generating lesson...</span>
          </div>
        )}
      </div>

      {/* Navigation */}
      {totalSlides > 1 && (
        <nav className="asgf-slide-nav" aria-label="Slide navigation">
          <button
            className="asgf-slide-nav-btn"
            onClick={goPrev}
            disabled={currentIndex === 0}
            aria-label="Previous slide"
            type="button"
          >
            <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path d="M10 4L6 8l4 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>

          <div className="asgf-slide-dots" role="tablist" aria-label="Slide indicators">
            {slides.map((_, i) => (
              <button
                key={i}
                className={`asgf-slide-dot${i === currentIndex ? ' asgf-slide-dot--active' : ''}`}
                onClick={() => goTo(i)}
                role="tab"
                aria-selected={i === currentIndex}
                aria-label={`Go to slide ${i + 1}`}
                type="button"
              />
            ))}
            {isGenerating && (
              <span className="asgf-slide-dot asgf-slide-dot--generating" aria-hidden="true" />
            )}
          </div>

          <button
            className="asgf-slide-nav-btn"
            onClick={goNext}
            disabled={currentIndex === totalSlides - 1}
            aria-label="Next slide"
            type="button"
          >
            <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path d="M6 4l4 4-4 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </nav>
      )}

      {/* Generating indicator below nav */}
      {isGenerating && totalSlides > 0 && (
        <div className="asgf-slide-generating">
          <div className="asgf-slide-generating-spinner" />
          <span>Generating more slides...</span>
        </div>
      )}
    </div>
  );
}
