import { useState, useEffect } from 'react';
import { studyApi, coursesApi } from '../api/client';
import type { StudyGuide } from '../api/client';
import { ReportBugLink } from './ReportBugLink';
import './EditStudyGuideModal.css';

const GUIDE_TYPE_LABELS: Record<string, string> = {
  study_guide: 'Study Guide',
  quiz: 'Quiz',
  flashcards: 'Flashcards',
};

interface CourseOption {
  id: number;
  name: string;
}

interface EditStudyGuideModalProps {
  guide: StudyGuide;
  onClose: () => void;
  onSaved: (updated: StudyGuide) => void;
}

export function EditStudyGuideModal({ guide, onClose, onSaved }: EditStudyGuideModalProps) {
  const [title, setTitle] = useState(guide.title);
  const [courseId, setCourseId] = useState<number | null>(guide.course_id);
  const [courseSearch, setCourseSearch] = useState('');
  const [courses, setCourses] = useState<CourseOption[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    coursesApi.list().then((list: any[]) => {
      setCourses(list.map(c => ({ id: c.id, name: c.name })));
    }).catch(() => {});
  }, []);

  const hasChanges = title !== guide.title || courseId !== guide.course_id;

  const handleSave = async () => {
    if (!title.trim()) { setError('Title is required'); return; }
    setSaving(true);
    setError(null);
    try {
      const data: Record<string, any> = {};
      if (title !== guide.title) data.title = title.trim();
      if (courseId !== guide.course_id) data.course_id = courseId;
      const updated = await studyApi.updateGuide(guide.id, data);
      onSaved(updated);
    } catch {
      setError('Failed to save changes');
      setSaving(false);
    }
  };

  const filteredCourses = courses.filter(c =>
    !courseSearch || c.name.toLowerCase().includes(courseSearch.toLowerCase())
  );

  const currentCourseName = courses.find(c => c.id === courseId)?.name || '';
  const guideTypeLabel = GUIDE_TYPE_LABELS[guide.guide_type] || guide.guide_type;

  return (
    <div className="modal-overlay">
      <div className="modal edit-sg-modal">
        <h2>Edit {guideTypeLabel}</h2>
        <p className="modal-desc">Edit properties of this {guideTypeLabel.toLowerCase()}.</p>
        {error && (
          <div className="modal-error">
            <span className="error-icon">!</span>
            <span className="error-message">{error}</span>
            <button onClick={handleSave} className="retry-btn" disabled={saving}>Try Again</button>
            <ReportBugLink errorMessage={error} />
          </div>
        )}
        <div className="modal-form edit-sg-form">
          <label>
            Title *
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Quiz: Unit B Review"
              autoFocus
              disabled={saving}
            />
          </label>
          <label>
            Type
            <input type="text" value={guideTypeLabel} disabled />
          </label>
          <label>
            Class
            {currentCourseName && (
              <div className="edit-sg-course-current">&#127891; {currentCourseName}</div>
            )}
            <input
              type="text"
              placeholder={currentCourseName ? 'Search to move to another class...' : 'Search to assign a class...'}
              value={courseSearch}
              onChange={(e) => setCourseSearch(e.target.value)}
              disabled={saving}
            />
            {courseSearch && (
              <div className="edit-sg-course-list">
                {filteredCourses.map(c => (
                  <div
                    key={c.id}
                    className={`edit-sg-course-item${courseId === c.id ? ' selected' : ''}${c.id === guide.course_id ? ' current' : ''}`}
                    onClick={() => { setCourseId(c.id); setCourseSearch(''); }}
                  >
                    &#127891; {c.name}{c.id === guide.course_id ? ' (current)' : ''}
                  </div>
                ))}
                {filteredCourses.length === 0 && (
                  <div className="edit-sg-course-item" style={{ color: '#999', cursor: 'default' }}>No matching classes</div>
                )}
              </div>
            )}
          </label>
        </div>
        <div className="modal-actions">
          <button className="cancel-btn" onClick={onClose} disabled={saving}>Cancel</button>
          <button className="generate-btn" disabled={saving || !hasChanges || !title.trim()} onClick={handleSave}>
            {saving ? <><span className="btn-spinner" /> Saving...</> : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  );
}
