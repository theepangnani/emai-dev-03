import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { StudyGuide } from '../api/study';
import './SubGuidesPanel.css';

interface SubGuidesPanelProps {
  childGuides: StudyGuide[];
  /** Parent guide ID — reserved for future use */
  parentGuideId?: number;
}

const GUIDE_TYPE_TAB_MAP: Record<string, string> = {
  study_guide: 'guide',
  quiz: 'quiz',
  flashcards: 'flashcards',
  mind_map: 'mindmap',
};

const GUIDE_TYPE_LABELS: Record<string, string> = {
  study_guide: 'Study Guide',
  quiz: 'Quiz',
  flashcards: 'Flashcards',
  mind_map: 'Mind Map',
};

function GuideTypeIcon({ guideType }: { guideType: string }) {
  if (guideType === 'study_guide') {
    return (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <path d="M2 3a1 1 0 011-1h4l1 1h5a1 1 0 011 1v8a1 1 0 01-1 1H3a1 1 0 01-1-1V3z" stroke="currentColor" strokeWidth="1.4"/>
        <path d="M5 7h6M5 9.5h4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
      </svg>
    );
  }
  if (guideType === 'quiz') {
    return (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.4"/>
        <path d="M6 6.2a2.2 2.2 0 114 1.3c0 .8-.8 1-1.2 1.3-.2.2-.3.4-.3.7" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
        <circle cx="8.5" cy="11.2" r="0.6" fill="currentColor"/>
      </svg>
    );
  }
  if (guideType === 'flashcards') {
    return (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <rect x="1.5" y="3" width="10" height="8" rx="1.5" stroke="currentColor" strokeWidth="1.3"/>
        <rect x="4.5" y="5" width="10" height="8" rx="1.5" stroke="currentColor" strokeWidth="1.3" fill="var(--color-surface, #fff)"/>
        <path d="M7 8.5h5M7 10.5h3" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round"/>
      </svg>
    );
  }
  // Default/mind_map icon
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <circle cx="8" cy="8" r="2.5" stroke="currentColor" strokeWidth="1.3"/>
      <circle cx="3" cy="3.5" r="1.5" stroke="currentColor" strokeWidth="1.1"/>
      <circle cx="13" cy="3.5" r="1.5" stroke="currentColor" strokeWidth="1.1"/>
      <path d="M6.2 6.2L4.2 4.5M9.8 6.2L11.8 4.5" stroke="currentColor" strokeWidth="1" strokeLinecap="round"/>
    </svg>
  );
}

export function SubGuidesPanel({ childGuides }: SubGuidesPanelProps) {
  const [collapsed, setCollapsed] = useState(childGuides.length === 0);

  if (childGuides.length === 0) {
    return (
      <div className="subguides-panel" data-testid="sub-guides-panel">
        <button
          className="subguides-panel-toggle"
          onClick={() => setCollapsed(v => !v)}
          aria-expanded={!collapsed}
        >
          <span className={`subguides-chevron${!collapsed ? ' expanded' : ''}`}>&#9654;</span>
          <span className="subguides-panel-title">Sub-Guides (0)</span>
        </button>
        {!collapsed && (
          <div className="subguides-panel-empty" data-testid="sub-guides-empty">
            No sub-guides yet
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="subguides-panel" data-testid="sub-guides-panel">
      <button
        className="subguides-panel-toggle"
        onClick={() => setCollapsed(v => !v)}
        aria-expanded={!collapsed}
      >
        <span className={`subguides-chevron${!collapsed ? ' expanded' : ''}`}>&#9654;</span>
        <span className="subguides-panel-title">Sub-Guides ({childGuides.length})</span>
      </button>
      {!collapsed && (
        <div className="subguides-panel-list" data-testid="sub-guides-list">
          {childGuides.map(child => {
            const targetUrl = child.course_content_id
              ? `/course-materials/${child.course_content_id}?tab=${GUIDE_TYPE_TAB_MAP[child.guide_type] || 'guide'}`
              : `/study/guide/${child.id}`;

            return (
              <div key={child.id} className="subguides-panel-item" data-testid={`sub-guide-item-${child.id}`}>
                <span className="subguides-panel-item-icon">
                  <GuideTypeIcon guideType={child.guide_type} />
                </span>
                <div className="subguides-panel-item-info">
                  <span className="subguides-panel-item-name">{child.title}</span>
                  <span className="subguides-panel-item-meta">
                    {GUIDE_TYPE_LABELS[child.guide_type] || child.guide_type}
                    {' \u00B7 '}
                    {new Date(child.created_at).toLocaleDateString()}
                  </span>
                </div>
                <Link to={targetUrl} className="subguides-panel-view-btn">
                  View
                </Link>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
