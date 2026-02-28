import { Link } from 'react-router-dom';
import type { StudyGuide } from '../api/client';
import './ContinueStudying.css';

interface ContinueStudyingProps {
  studyGuides: StudyGuide[];
  courses: { id: number; name: string }[];
}

function getGuideRoute(guide: StudyGuide): string {
  if (guide.guide_type === 'quiz') return `/study/quiz/${guide.id}`;
  if (guide.guide_type === 'flashcards') return `/study/flashcards/${guide.id}`;
  return `/study/guide/${guide.id}`;
}

function getGuideTypeLabel(guideType: string): string {
  switch (guideType) {
    case 'quiz': return 'Quiz';
    case 'flashcards': return 'Flashcards';
    case 'study_guide': return 'Study Guide';
    default: return guideType.replace('_', ' ');
  }
}

function getGuideIcon(guideType: string): string {
  switch (guideType) {
    case 'quiz': return '\u{2753}';
    case 'flashcards': return '\u{1F0CF}';
    default: return '\u{1F4D6}';
  }
}

export function ContinueStudying({ studyGuides, courses }: ContinueStudyingProps) {
  // Sort by updated_at (or created_at as fallback), most recent first, take 3
  const recentMaterials = [...studyGuides]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 3);

  if (recentMaterials.length === 0) return null;

  const courseMap = new Map(courses.map(c => [c.id, c.name]));

  return (
    <section className="sd-continue-studying">
      <h2 className="sd-section-label">Continue Studying</h2>
      <div className="sd-continue-grid">
        {recentMaterials.map(guide => {
          const courseName = guide.course_id ? courseMap.get(guide.course_id) : null;
          return (
            <Link
              key={guide.id}
              to={getGuideRoute(guide)}
              className="sd-continue-card"
            >
              <span className="sd-continue-icon">{getGuideIcon(guide.guide_type)}</span>
              <div className="sd-continue-info">
                <span className="sd-continue-title">{guide.title}</span>
                <div className="sd-continue-meta">
                  <span className={`sd-continue-type ${guide.guide_type}`}>
                    {getGuideTypeLabel(guide.guide_type)}
                  </span>
                  {courseName && (
                    <span className="sd-continue-course">{courseName}</span>
                  )}
                </div>
              </div>
              <span className="sd-continue-resume">Resume</span>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
