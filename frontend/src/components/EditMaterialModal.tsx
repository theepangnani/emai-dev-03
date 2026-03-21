import { useState, useEffect } from 'react';
import { courseContentsApi, type CourseContentItem } from '../api/client';
import { coursesApi } from '../api/courses';
import { ReportBugLink } from './ReportBugLink';
import './EditMaterialModal.css';

const CONTENT_TYPES = [
  { value: 'notes', label: 'Notes' },
  { value: 'syllabus', label: 'Syllabus' },
  { value: 'labs', label: 'Labs' },
  { value: 'assignments', label: 'Assignments' },
  { value: 'readings', label: 'Readings' },
  { value: 'resources', label: 'Resources' },
  { value: 'other', label: 'Other' },
];

interface CourseOption {
  id: number;
  name: string;
}

interface EditMaterialModalProps {
  material: CourseContentItem;
  courses?: CourseOption[];
  onClose: () => void;
  onSaved: (updated: CourseContentItem) => void;
}

export function EditMaterialModal({ material, courses: externalCourses, onClose, onSaved }: EditMaterialModalProps) {
  const [title, setTitle] = useState(material.title);
  const [description, setDescription] = useState(material.description || '');
  const [contentType, setContentType] = useState(material.content_type);
  const [referenceUrl, setReferenceUrl] = useState(material.reference_url || '');
  const [googleClassroomUrl, setGoogleClassroomUrl] = useState(material.google_classroom_url || '');
  const [courseId, setCourseId] = useState<number>(material.course_id);
  const [courseSearch, setCourseSearch] = useState('');
  const [courses, setCourses] = useState<CourseOption[]>(externalCourses || []);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!externalCourses) {
      coursesApi.list().then((list: any[]) => {
        setCourses(list.map(c => ({ id: c.id, name: c.name })));
      }).catch(() => {});
    }
  }, [externalCourses]);

  const hasChanges = title !== material.title
    || description !== (material.description || '')
    || contentType !== material.content_type
    || referenceUrl !== (material.reference_url || '')
    || googleClassroomUrl !== (material.google_classroom_url || '')
    || courseId !== material.course_id;

  const handleSave = async () => {
    if (!title.trim()) { setError('Title is required'); return; }
    setSaving(true);
    setError(null);
    try {
      const data: Record<string, any> = {};
      if (title !== material.title) data.title = title.trim();
      if (description !== (material.description || '')) data.description = description.trim() || null;
      if (contentType !== material.content_type) data.content_type = contentType;
      if (referenceUrl !== (material.reference_url || '')) data.reference_url = referenceUrl.trim() || null;
      if (googleClassroomUrl !== (material.google_classroom_url || '')) data.google_classroom_url = googleClassroomUrl.trim() || null;
      if (courseId !== material.course_id) data.course_id = courseId;
      const updated = await courseContentsApi.update(material.id, data);
      onSaved(updated);
    } catch {
      setError('Failed to save changes');
      setSaving(false);
    }
  };

  const filteredCourses = courses.filter(c =>
    !courseSearch || c.name.toLowerCase().includes(courseSearch.toLowerCase())
  );

  const currentCourseName = courses.find(c => c.id === courseId)?.name || material.course_name || '';

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal edit-material-modal" onClick={(e) => e.stopPropagation()}>
        <h2>Edit Material</h2>
        <p className="modal-desc">Edit material details or move to a different class.</p>
        {error && (
          <div className="modal-error">
            <span className="error-icon">!</span>
            <span className="error-message">{error}</span>
            <button onClick={handleSave} className="retry-btn" disabled={saving}>Try Again</button>
            <ReportBugLink errorMessage={error} />
          </div>
        )}
        <div className="modal-form edit-mat-form">
          <label>
            Title *
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Chapter 5 Notes"
              autoFocus
              disabled={saving}
            />
          </label>
          <label>
            Type
            <select value={contentType} onChange={(e) => setContentType(e.target.value)} disabled={saving}>
              {CONTENT_TYPES.map(ct => (
                <option key={ct.value} value={ct.value}>{ct.label}</option>
              ))}
            </select>
          </label>
          <label>
            Description (optional)
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief description..."
              rows={2}
              disabled={saving}
            />
          </label>
          <label>
            Reference URL (optional)
            <input
              type="url"
              value={referenceUrl}
              onChange={(e) => setReferenceUrl(e.target.value)}
              placeholder="https://..."
              disabled={saving}
            />
          </label>
          <label>
            Google Classroom URL (optional)
            <input
              type="url"
              value={googleClassroomUrl}
              onChange={(e) => setGoogleClassroomUrl(e.target.value)}
              placeholder="https://classroom.google.com/..."
              disabled={saving}
            />
          </label>
          <label>
            Class
            <div className="edit-mat-course-current">&#127891; {currentCourseName}</div>
            <input
              type="text"
              placeholder="Search to move to another class..."
              value={courseSearch}
              onChange={(e) => setCourseSearch(e.target.value)}
              disabled={saving}
            />
            {courseSearch && (
              <div className="categorize-list edit-mat-course-list">
                {filteredCourses.map(c => (
                  <div
                    key={c.id}
                    className={`categorize-item${courseId === c.id ? ' selected' : ''}${c.id === material.course_id ? ' current' : ''}`}
                    onClick={() => { setCourseId(c.id); setCourseSearch(''); }}
                  >
                    &#127891; {c.name}{c.id === material.course_id ? ' (original)' : ''}
                  </div>
                ))}
                {filteredCourses.length === 0 && (
                  <div className="categorize-item" style={{ color: '#999', cursor: 'default' }}>No matching classes</div>
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
