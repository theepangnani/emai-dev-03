import { useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import './HelpStudyMenu.css';

export interface HelpStudyMenuProps {
  studentId: number;
  courseId?: number;
  courseContentId?: number;
  assignmentId?: number;
  onClose: () => void;
  onGenerate?: (type: 'study_guide' | 'quiz' | 'flashcards') => void;
}

interface MenuItem {
  icon: string;
  label: string;
  description: string;
  action: () => void;
  section?: 'create' | 'responsible';
}

export function HelpStudyMenu({
  studentId,
  courseId,
  courseContentId,
  assignmentId,
  onClose,
  onGenerate,
}: HelpStudyMenuProps) {
  const navigate = useNavigate();
  const menuRef = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('mousedown', handleClick);
    document.addEventListener('keydown', handleEsc);
    return () => {
      document.removeEventListener('mousedown', handleClick);
      document.removeEventListener('keydown', handleEsc);
    };
  }, [onClose]);

  const buildMaterialUrl = useCallback((tab?: string) => {
    if (courseContentId) {
      const params = new URLSearchParams();
      if (tab) params.set('tab', tab);
      return `/course-materials/${courseContentId}${params.toString() ? '?' + params.toString() : ''}`;
    }
    // Fallback: go to course materials list filtered by course
    if (courseId) return `/course-materials?courseId=${courseId}`;
    return '/course-materials';
  }, [courseContentId, courseId]);

  const createItems: MenuItem[] = [
    {
      icon: '\u{1F4DD}',
      label: 'Create Study Guide',
      description: 'Generate notes for this topic',
      action: () => { if (onGenerate) { onGenerate('study_guide'); } else { navigate(buildMaterialUrl('guide')); } onClose(); },
    },
    {
      icon: '\u2753',
      label: 'Create Quiz',
      description: 'Test knowledge with questions',
      action: () => { if (onGenerate) { onGenerate('quiz'); } else { navigate(buildMaterialUrl('quiz')); } onClose(); },
    },
    {
      icon: '\u{1F0CF}',
      label: 'Create Flashcards',
      description: 'Quick review cards',
      action: () => { if (onGenerate) { onGenerate('flashcards'); } else { navigate(buildMaterialUrl('flashcards')); } onClose(); },
    },
  ];

  const responsibleItems: MenuItem[] = [
    {
      icon: '\u{1F4CA}',
      label: 'Check Readiness',
      description: 'Is my kid ready for this test?',
      action: () => {
        const params = new URLSearchParams({ studentId: String(studentId) });
        if (courseId) params.set('courseId', String(courseId));
        if (assignmentId) params.set('assignmentId', String(assignmentId));
        navigate(`/readiness-check?${params.toString()}`);
        onClose();
      },
    },
    {
      icon: '\u{1F50D}',
      label: 'Find Weak Spots',
      description: 'What topics need more work?',
      action: () => {
        const params = new URLSearchParams({ studentId: String(studentId) });
        if (courseId) params.set('courseId', String(courseId));
        navigate(`/ai-tools?${params.toString()}`);
        onClose();
      },
    },
    {
      icon: '\u270F\uFE0F',
      label: 'Practice Problems',
      description: 'Generate practice exercises',
      action: () => { navigate(buildMaterialUrl('quiz')); onClose(); },
    },
    {
      icon: '\u{1F4AC}',
      label: 'Conversation Starters',
      description: 'Dinner table discussion prompts',
      action: () => {
        const params = new URLSearchParams({ student_id: String(studentId) });
        navigate(`/my-kids?${params.toString()}`);
        onClose();
      },
    },
    {
      icon: '\u{1F4CB}',
      label: 'Parent Briefing',
      description: 'Understand the topic yourself',
      action: () => {
        const params = new URLSearchParams({ studentId: String(studentId) });
        if (courseId) params.set('courseId', String(courseId));
        navigate(`/parent-briefing-notes?${params.toString()}`);
        onClose();
      },
    },
  ];

  return (
    <div className="hsm-overlay">
      <div className="hsm-menu" ref={menuRef} role="menu" aria-label="Help Study">
        <div className="hsm-header">
          <span className="hsm-title">Help Study</span>
          <button className="hsm-close" onClick={onClose} aria-label="Close menu" type="button">
            &times;
          </button>
        </div>

        <div className="hsm-section">
          {createItems.map((item) => (
            <button
              key={item.label}
              className="hsm-item"
              onClick={item.action}
              type="button"
              role="menuitem"
            >
              <span className="hsm-item-icon" aria-hidden="true">{item.icon}</span>
              <div className="hsm-item-text">
                <span className="hsm-item-label">{item.label}</span>
                <span className="hsm-item-desc">{item.description}</span>
              </div>
            </button>
          ))}
        </div>

        <div className="hsm-divider" />

        <div className="hsm-section-label">
          <span className="hsm-section-label-icon" aria-hidden="true">{'\u{1F3AF}'}</span>
          Responsible AI Tools
        </div>

        <div className="hsm-section">
          {responsibleItems.map((item) => (
            <button
              key={item.label}
              className="hsm-item"
              onClick={item.action}
              type="button"
              role="menuitem"
            >
              <span className="hsm-item-icon" aria-hidden="true">{item.icon}</span>
              <div className="hsm-item-text">
                <span className="hsm-item-label">{item.label}</span>
                <span className="hsm-item-desc">{item.description}</span>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
