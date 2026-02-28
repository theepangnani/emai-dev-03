import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { gradesApi } from '../api/grades';
import type { ChildGradeSummary } from '../api/grades';
import './GradesSummaryCard.css';

interface GradesSummaryCardProps {
  selectedChildId?: number;
  onViewDetails?: () => void;
}

export function GradesSummaryCard({ selectedChildId, onViewDetails }: GradesSummaryCardProps) {
  const [children, setChildren] = useState<ChildGradeSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const loadGrades = useCallback(async (studentId?: number) => {
    setLoading(true);
    setError(false);
    try {
      const data = await gradesApi.summary(studentId);
      setChildren(data.children);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadGrades(selectedChildId);
  }, [selectedChildId, loadGrades]);

  if (loading) {
    return (
      <div className="grades-card" aria-busy="true">
        <div className="grades-card-loading">
          <div className="skeleton grades-skeleton-bar" />
          <div className="skeleton grades-skeleton-bar short" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="grades-card">
        <p className="grades-card-empty">Unable to load grades. Please try again later.</p>
      </div>
    );
  }

  if (children.length === 0 || children.every(c => c.courses.length === 0)) {
    return (
      <div className="grades-card">
        <div className="grades-card-empty">
          <span className="grades-empty-icon" aria-hidden="true">&#128218;</span>
          <p>No grades available yet. Grades will appear here once synced from Google Classroom.</p>
          <Link to="/grades" className="grades-view-link">View Grades Page</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="grades-card">
      {children.map(child => (
        <div key={child.student_id} className="grades-child-block">
          {children.length > 1 && (
            <div className="grades-child-header">
              <span className="grades-child-name">{child.student_name}</span>
              <span className={`grades-overall-badge grades-color-${child.color}`}>
                {child.letter_grade} ({child.overall_average}%)
              </span>
            </div>
          )}
          {children.length === 1 && (
            <div className="grades-single-overall">
              <span className={`grades-overall-badge large grades-color-${child.color}`}>
                {child.letter_grade}
              </span>
              <span className="grades-overall-pct">{child.overall_average}% overall</span>
            </div>
          )}
          <div className="grades-course-list">
            {child.courses.map(course => (
              <Link
                key={course.course_id}
                to={`/grades?course=${course.course_id}&student=${child.student_id}`}
                className="grades-course-row"
              >
                <span className="grades-course-name">{course.course_name}</span>
                <span className="grades-course-info">
                  <span className={`grades-letter grades-color-${course.color}`}>
                    {course.letter_grade}
                  </span>
                  <span className="grades-course-pct">{course.average_grade}%</span>
                  <span className="grades-course-count">
                    {course.graded_count}/{course.assignment_count}
                  </span>
                </span>
              </Link>
            ))}
          </div>
        </div>
      ))}
      <div className="grades-card-footer">
        <Link to="/grades" className="grades-view-link" onClick={onViewDetails}>
          View All Grades
        </Link>
      </div>
    </div>
  );
}
