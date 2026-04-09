import { useState, useRef, useEffect } from 'react';
import { coursesApi } from '../api/courses';
import { isValidEmail } from '../utils/validation';
import { SearchableSelect, MultiSearchableSelect } from './SearchableSelect';
import type { SearchableOption } from './SearchableSelect';
import { useFocusTrap } from '../hooks/useFocusTrap';
import { ReportBugLink } from './ReportBugLink';
import { useAuth } from '../context/AuthContext';

interface CreateClassModalProps {
  open: boolean;
  onClose: () => void;
  onCreated: (course: { id: number; name: string }) => void;
}

export default function CreateClassModal({ open, onClose, onCreated }: CreateClassModalProps) {
  const { user } = useAuth();
  const isEmailOnlySearch = user?.role === 'parent' || user?.role === 'student';
  const [courseName, setCourseName] = useState('');
  const [courseSubject, setCourseSubject] = useState('');
  const [courseDescription, setCourseDescription] = useState('');
  const [courseRequireApproval, setCourseRequireApproval] = useState(false);
  const [selectedTeacher, setSelectedTeacher] = useState<SearchableOption | null>(null);
  const [selectedStudents, setSelectedStudents] = useState<SearchableOption[]>([]);
  const [showCreateTeacher, setShowCreateTeacher] = useState(false);
  const [newTeacherName, setNewTeacherName] = useState('');
  const [newTeacherEmail, setNewTeacherEmail] = useState('');
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState('');

  const modalRef = useFocusTrap<HTMLDivElement>(open);
  const prevOpenRef = useRef(false);

  // Reset state when modal opens
  useEffect(() => {
    const wasOpen = prevOpenRef.current;
    prevOpenRef.current = open;
    if (!open || wasOpen) return;
    setCourseName('');
    setCourseSubject('');
    setCourseDescription('');
    setCourseRequireApproval(false);
    setSelectedTeacher(null);
    setSelectedStudents([]);
    setShowCreateTeacher(false);
    setNewTeacherName('');
    setNewTeacherEmail('');
    setCreateLoading(false);
    setCreateError('');
  }, [open]);

  const handleSearchTeachers = async (q: string): Promise<SearchableOption[]> => {
    const results = await coursesApi.searchTeachers(q);
    return results.map(t => ({
      id: t.id,
      label: t.name,
      sublabel: t.email || (t.is_shadow ? 'Shadow teacher' : undefined),
    }));
  };

  const handleSearchStudents = async (q: string): Promise<SearchableOption[]> => {
    const results = await coursesApi.searchStudents(q);
    return results.map(s => ({
      id: s.id,
      label: s.name,
      sublabel: s.email,
    }));
  };

  const handleCreate = async () => {
    if (!courseName.trim()) return;
    if (!selectedTeacher && !showCreateTeacher) {
      setCreateError('A teacher is required');
      return;
    }
    if (showCreateTeacher && !newTeacherName.trim()) {
      setCreateError('Teacher name is required');
      return;
    }
    if (newTeacherEmail && !isValidEmail(newTeacherEmail.trim())) {
      setCreateError('Please enter a valid teacher email');
      return;
    }
    setCreateError('');
    setCreateLoading(true);
    try {
      const data: Parameters<typeof coursesApi.create>[0] = {
        name: courseName.trim(),
        subject: courseSubject.trim() || undefined,
        description: courseDescription.trim() || undefined,
        student_ids: selectedStudents.map(s => s.id),
        require_approval: courseRequireApproval,
      };
      if (selectedTeacher) {
        data.teacher_id = selectedTeacher.id;
      } else if (showCreateTeacher) {
        data.new_teacher_name = newTeacherName.trim();
        data.new_teacher_email = newTeacherEmail.trim() || undefined;
      }
      const newCourse = await coursesApi.create(data);
      onCreated({ id: newCourse.id, name: newCourse.name });
      onClose();
    } catch (err: any) {
      setCreateError(err.response?.data?.detail || 'Failed to create class');
    } finally {
      setCreateLoading(false);
    }
  };

  if (!open) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-lg" role="dialog" aria-modal="true" aria-label="Create Class" ref={modalRef} onClick={(e) => e.stopPropagation()}>
        <h2>Create Class</h2>
        <p className="modal-desc">Set up a new class with students and a teacher.</p>
        <div className="modal-form">
          <label>
            Class Name *
            <input
              type="text"
              value={courseName}
              onChange={(e) => { setCourseName(e.target.value); setCreateError(''); }}
              placeholder="e.g. Algebra I"
              disabled={createLoading}
            />
          </label>
          <label>
            Subject
            <input
              type="text"
              value={courseSubject}
              onChange={(e) => setCourseSubject(e.target.value)}
              placeholder="e.g. Mathematics"
              disabled={createLoading}
            />
          </label>
          <label>
            Description
            <textarea
              value={courseDescription}
              onChange={(e) => setCourseDescription(e.target.value)}
              placeholder="Brief description of the class..."
              rows={2}
              disabled={createLoading}
            />
          </label>

          <label>
            Teacher *
          </label>
          {!showCreateTeacher ? (
            <SearchableSelect
              placeholder={isEmailOnlySearch ? "Search teacher by exact email address..." : "Search for a teacher by name or email..."}
              onSearch={handleSearchTeachers}
              onSelect={(opt) => { setSelectedTeacher(opt); setCreateError(''); }}
              selected={selectedTeacher}
              onClear={() => setSelectedTeacher(null)}
              disabled={createLoading}
              createAction={{ label: '+ Create New Teacher', onClick: () => { setSelectedTeacher(null); setShowCreateTeacher(true); } }}
            />
          ) : (
            <div className="create-teacher-inline">
              <div className="create-teacher-inline__header">
                <h4>New Teacher</h4>
                <button type="button" className="create-teacher-inline__cancel" onClick={() => { setShowCreateTeacher(false); setNewTeacherName(''); setNewTeacherEmail(''); }}>
                  Back to search
                </button>
              </div>
              <label>
                Name *
                <input
                  type="text"
                  value={newTeacherName}
                  onChange={(e) => { setNewTeacherName(e.target.value); setCreateError(''); }}
                  placeholder="e.g. Ms. Johnson"
                  disabled={createLoading}
                />
              </label>
              <label>
                Email (optional)
                <input
                  type="email"
                  value={newTeacherEmail}
                  onChange={(e) => setNewTeacherEmail(e.target.value)}
                  placeholder="teacher@school.com"
                  disabled={createLoading}
                />
              </label>
              <p className="shadow-note">
                {newTeacherEmail ? 'An invitation will be sent to join ClassBridge as a teacher.' : 'No email = shadow teacher (can be invited later).'}
              </p>
            </div>
          )}

          <label>
            Students <span style={{ fontWeight: 400, fontSize: '0.8rem', color: '#6b7280' }}>(optional — students can enroll later)</span>
          </label>
          <MultiSearchableSelect
            placeholder="Search students by name or email..."
            onSearch={handleSearchStudents}
            selected={selectedStudents}
            onAdd={(opt) => { setSelectedStudents(prev => [...prev, opt]); setCreateError(''); }}
            onRemove={(id) => setSelectedStudents(prev => prev.filter(s => s.id !== id))}
            disabled={createLoading}
          />

          <label className="toggle-label">
            <input type="checkbox" checked={courseRequireApproval} onChange={(e) => setCourseRequireApproval(e.target.checked)} disabled={createLoading} />
            Require approval to join
          </label>
          {createError && <><p className="link-error">{createError}</p><ReportBugLink errorMessage={createError} /></>}
        </div>
        <div className="modal-actions">
          <button className="cancel-btn" onClick={onClose} disabled={createLoading}>
            Cancel
          </button>
          <button
            className="generate-btn"
            onClick={handleCreate}
            disabled={createLoading || !courseName.trim()}
          >
            {createLoading ? 'Creating...' : 'Create Class'}
          </button>
        </div>
      </div>
    </div>
  );
}
