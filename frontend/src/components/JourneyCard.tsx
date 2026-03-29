import { useState } from 'react';
import type { Journey } from '../data/journeyData';
import './JourneyCard.css';

interface JourneyCardProps {
  journey: Journey;
  roleBadge: string;
}

export function JourneyCard({ journey, roleBadge }: JourneyCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [diagramError, setDiagramError] = useState(false);

  return (
    <div
      id={`journey-${journey.id}`}
      className={`journey-card${expanded ? ' expanded' : ''}`}
    >
      <button
        className="journey-card-header"
        onClick={() => setExpanded(prev => !prev)}
        aria-expanded={expanded}
      >
        <div className="journey-card-info">
          <h3 className="journey-card-title">
            {journey.id.toUpperCase()} — {journey.title}
          </h3>
          <p className="journey-card-desc">{journey.description}</p>
        </div>
        <span className="journey-card-badge">{roleBadge}</span>
        <span className={`journey-card-chevron${expanded ? ' expanded' : ''}`}>
          &#9654;
        </span>
      </button>

      {expanded && (
        <div className="journey-card-body">
          <div className="journey-card-layout">
            {/* Steps */}
            <div className="journey-steps">
              {journey.steps.map((step, idx) => (
                <div key={idx} className="journey-step">
                  <span className="journey-step-number">{idx + 1}</span>
                  <div className="journey-step-content">
                    <h4 className="journey-step-title">{step.title}</h4>
                    <p className="journey-step-detail">{step.detail}</p>
                    {step.tip && (
                      <div className="journey-step-tip">
                        <span className="journey-step-tip-icon" aria-hidden="true">
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <circle cx="12" cy="12" r="10"/>
                            <line x1="12" y1="16" x2="12" y2="12"/>
                            <line x1="12" y1="8" x2="12.01" y2="8"/>
                          </svg>
                        </span>
                        <span>{step.tip}</span>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Diagram */}
            <div className="journey-diagram-wrap">
              {diagramError ? (
                <div className="journey-diagram-placeholder">
                  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                    <circle cx="8.5" cy="8.5" r="1.5"/>
                    <polyline points="21 15 16 10 5 21"/>
                  </svg>
                  <span>Diagram coming soon</span>
                </div>
              ) : (
                <img
                  src={journey.diagramUrl}
                  alt={`${journey.title} diagram`}
                  className="journey-diagram-img"
                  onError={() => setDiagramError(true)}
                />
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
