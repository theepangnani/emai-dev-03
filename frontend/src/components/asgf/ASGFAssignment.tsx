/**
 * ASGFAssignment — Role-aware assignment options + course auto-detection.
 *
 * Shows after quiz completion. Displays role-appropriate assignment options
 * and auto-detects the correct Google Classroom course (85% threshold).
 *
 * Issue: #3402
 */
import { useCallback, useEffect, useState } from 'react';

import {
  type AssignmentOption,
  type AssignmentOptionsResponse,
  type CourseSuggestion,
  asgfApi,
} from '../../api/asgf';

import './ASGFAssignment.css';

interface CourseItem {
  id: string;
  name: string;
}

interface Props {
  sessionId: string;
  /** Available courses for manual selection fallback */
  courses?: CourseItem[];
  /** Called after successful assignment */
  onAssigned?: (result: { assignmentType: string; courseId: string | null }) => void;
}

const AUTO_CONFIDENCE_THRESHOLD = 0.85;

export default function ASGFAssignment({ sessionId, courses = [], onAssigned }: Props) {
  const [data, setData] = useState<AssignmentOptionsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [selectedCourse, setSelectedCourse] = useState<string | null>(null);
  const [dueDate, setDueDate] = useState<string>('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);

  // Fetch assignment options on mount
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    asgfApi
      .getAssignmentOptions(sessionId)
      .then((res) => {
        if (cancelled) return;
        setData(res);

        // Auto-select course if confidence is high
        if (
          res.suggested_course?.course_id &&
          res.suggested_course.confidence >= AUTO_CONFIDENCE_THRESHOLD
        ) {
          setSelectedCourse(res.suggested_course.course_id);
        }
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err?.response?.data?.detail || 'Failed to load assignment options');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  const handleConfirm = useCallback(async () => {
    if (!selectedOption) return;

    setSubmitting(true);
    setError(null);

    try {
      const result = await asgfApi.assignMaterial(sessionId, {
        assignment_type: selectedOption,
        course_id: selectedCourse,
        due_date: dueDate || undefined,
      });

      if (result.success) {
        setSuccess(result.message);
        onAssigned?.({ assignmentType: selectedOption, courseId: selectedCourse });
      } else {
        setError(result.message);
      }
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      setError(msg || 'Failed to assign material');
    } finally {
      setSubmitting(false);
    }
  }, [selectedOption, selectedCourse, dueDate, sessionId, onAssigned]);

  if (loading) {
    return <div className="asgf-assignment__loading">Loading assignment options...</div>;
  }

  if (error && !data) {
    return <div className="asgf-assignment__error">{error}</div>;
  }

  if (success) {
    return <div className="asgf-assignment__success">{success}</div>;
  }

  if (!data) return null;

  const suggested: CourseSuggestion | null = data.suggested_course;
  const isAutoTagged =
    suggested?.course_id != null && suggested.confidence >= AUTO_CONFIDENCE_THRESHOLD;
  const showManualCourseSelect =
    !isAutoTagged && courses.length > 0;

  const showDueDatePicker =
    selectedOption === 'review_task';

  return (
    <div className="asgf-assignment">
      <h3 className="asgf-assignment__title">Save &amp; Assign</h3>

      {/* Course suggestion */}
      {isAutoTagged && suggested && (
        <div className="asgf-assignment__course asgf-assignment__course--auto">
          <span className="asgf-assignment__course-icon" aria-hidden="true">
            &#x2713;
          </span>
          <span>
            Tagged to <strong>{suggested.course_name}</strong>
          </span>
        </div>
      )}

      {showManualCourseSelect && (
        <div className="asgf-assignment__course asgf-assignment__course--manual">
          <span className="asgf-assignment__course-icon" aria-hidden="true">
            ?
          </span>
          <div style={{ flex: 1 }}>
            <span>Select a course (optional)</span>
            <select
              className="asgf-assignment__course-select"
              value={selectedCourse || ''}
              onChange={(e) => setSelectedCourse(e.target.value || null)}
            >
              <option value="">-- No course --</option>
              {courses.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}

      {/* Role-aware options */}
      <div className="asgf-assignment__options">
        {data.options.map((opt: AssignmentOption) => {
          const isSelected = selectedOption === opt.key;
          return (
            <div
              key={opt.key}
              className={`asgf-assignment__option${isSelected ? ' asgf-assignment__option--selected' : ''}`}
              onClick={() => setSelectedOption(opt.key)}
              role="radio"
              aria-checked={isSelected}
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  setSelectedOption(opt.key);
                }
              }}
            >
              <div className="asgf-assignment__option-radio">
                {isSelected && <div className="asgf-assignment__option-radio-dot" />}
              </div>
              <div className="asgf-assignment__option-text">
                <div className="asgf-assignment__option-label">{opt.label}</div>
                <div className="asgf-assignment__option-desc">{opt.description}</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Due date picker for review_task */}
      {showDueDatePicker && (
        <div className="asgf-assignment__due-date">
          <label htmlFor="asgf-due-date">Due Date (optional)</label>
          <input
            id="asgf-due-date"
            type="date"
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
            min={new Date().toISOString().slice(0, 10)}
          />
        </div>
      )}

      {error && <div className="asgf-assignment__error">{error}</div>}

      <button
        className="asgf-assignment__confirm"
        disabled={!selectedOption || submitting}
        onClick={handleConfirm}
        type="button"
      >
        {submitting ? 'Assigning...' : 'Confirm'}
      </button>
    </div>
  );
}
