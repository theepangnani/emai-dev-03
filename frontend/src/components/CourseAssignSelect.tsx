import { useState, useEffect } from 'react';
import { coursesApi, studyApi } from '../api/client';

interface Course {
  id: number;
  name: string;
}

interface CourseAssignSelectProps {
  guideId: number;
  currentCourseId: number | null;
  onCourseChanged?: (courseId: number | null) => void;
}

export function CourseAssignSelect({ guideId, currentCourseId, onCourseChanged }: CourseAssignSelectProps) {
  const [courses, setCourses] = useState<Course[]>([]);
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(currentCourseId);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    coursesApi.list().then(setCourses).catch(() => {});
  }, []);

  useEffect(() => {
    setSelectedCourseId(currentCourseId);
  }, [currentCourseId]);

  const handleChange = async (value: string) => {
    const newCourseId = value === '' ? null : parseInt(value);
    if (newCourseId === selectedCourseId) return;

    setSaving(true);
    try {
      await studyApi.updateGuide(guideId, { course_id: newCourseId });
      setSelectedCourseId(newCourseId);
      onCourseChanged?.(newCourseId);
    } catch {
      // revert on failure
    } finally {
      setSaving(false);
    }
  };

  if (courses.length === 0) return null;

  return (
    <select
      value={selectedCourseId ?? ''}
      onChange={(e) => handleChange(e.target.value)}
      disabled={saving}
      title="Assign to course"
      style={{
        padding: '4px 8px',
        borderRadius: '6px',
        border: '1px solid #ddd',
        fontSize: '0.85rem',
        cursor: 'pointer',
        opacity: saving ? 0.6 : 1,
      }}
    >
      <option value="">No course</option>
      {courses.map((c) => (
        <option key={c.id} value={c.id}>{c.name}</option>
      ))}
    </select>
  );
}
