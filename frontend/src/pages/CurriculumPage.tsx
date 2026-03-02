import { useState, useEffect, useCallback } from 'react';
import { DashboardLayout } from '../components/DashboardLayout';
import { curriculumApi } from '../api/curriculum';
import type { CurriculumCourseListItem, CurriculumCourseResponse } from '../api/curriculum';
import './CurriculumPage.css';

export function CurriculumPage() {
  const [courses, setCourses] = useState<CurriculumCourseListItem[]>([]);
  const [selectedCode, setSelectedCode] = useState<string>('');
  const [curriculumData, setCurriculumData] = useState<CurriculumCourseResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [coursesLoading, setCoursesLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedStrands, setExpandedStrands] = useState<Set<string>>(new Set());
  const [searchTimeout, setSearchTimeout] = useState<ReturnType<typeof setTimeout> | null>(null);

  // Load course list on mount
  useEffect(() => {
    setCoursesLoading(true);
    curriculumApi.getCourses()
      .then(setCourses)
      .catch(() => setCourses([]))
      .finally(() => setCoursesLoading(false));
  }, []);

  // Fetch curriculum when selected course changes
  const loadCourse = useCallback(async (code: string, query?: string) => {
    if (!code) {
      setCurriculumData(null);
      return;
    }
    setLoading(true);
    try {
      let data: CurriculumCourseResponse;
      if (query && query.trim()) {
        data = await curriculumApi.searchExpectations(code, query.trim());
      } else {
        data = await curriculumApi.getCourse(code);
      }
      setCurriculumData(data);
      // Expand all strands by default
      setExpandedStrands(new Set(data.strands.map(s => s.name)));
    } catch {
      setCurriculumData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  // Debounced search
  useEffect(() => {
    if (!selectedCode) return;
    if (searchTimeout) clearTimeout(searchTimeout);
    const t = setTimeout(() => {
      loadCourse(selectedCode, searchQuery);
    }, 350);
    setSearchTimeout(t);
    return () => clearTimeout(t);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchQuery, selectedCode]);

  const handleSelectCourse = (code: string) => {
    setSelectedCode(code);
    setSearchQuery('');
    setExpandedStrands(new Set());
    if (code) loadCourse(code);
  };

  const toggleStrand = (strandName: string) => {
    setExpandedStrands(prev => {
      const next = new Set(prev);
      if (next.has(strandName)) next.delete(strandName);
      else next.add(strandName);
      return next;
    });
  };

  const toggleAllStrands = () => {
    if (!curriculumData) return;
    if (expandedStrands.size === curriculumData.strands.length) {
      setExpandedStrands(new Set());
    } else {
      setExpandedStrands(new Set(curriculumData.strands.map(s => s.name)));
    }
  };

  const totalExpectations = curriculumData?.strands.reduce(
    (sum, s) => sum + s.expectations.length, 0
  ) ?? 0;

  const allExpanded = curriculumData ? expandedStrands.size === curriculumData.strands.length : false;

  return (
    <DashboardLayout welcomeSubtitle="Ontario Curriculum Expectations">
      <div className="curriculum-page">
        <div className="curriculum-header">
          <h1 className="curriculum-title">Ontario Curriculum</h1>
          <p className="curriculum-subtitle">
            Browse and search official Ontario curriculum expectations for core OSSD courses.
            These expectations are used to anchor AI-generated study materials.
          </p>
        </div>

        <div className="curriculum-controls">
          {/* Course selector */}
          <div className="curriculum-course-selector">
            <label htmlFor="curriculum-course-select" className="curriculum-label">
              Select Course
            </label>
            <select
              id="curriculum-course-select"
              className="curriculum-select"
              value={selectedCode}
              onChange={(e) => handleSelectCourse(e.target.value)}
              disabled={coursesLoading}
            >
              <option value="">
                {coursesLoading ? 'Loading courses...' : '-- Choose a course --'}
              </option>
              {courses.map(c => (
                <option key={c.course_code} value={c.course_code}>
                  {c.course_code} &nbsp;(Grade {c.grade_level}, {c.expectation_count} expectations)
                </option>
              ))}
            </select>
          </div>

          {/* Search within course */}
          {selectedCode && (
            <div className="curriculum-search-bar">
              <label htmlFor="curriculum-search" className="curriculum-label">
                Search expectations
              </label>
              <input
                id="curriculum-search"
                type="search"
                className="curriculum-search-input"
                placeholder="e.g. functions, trigonometry, evolution..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                disabled={loading}
              />
            </div>
          )}
        </div>

        {/* Curriculum content */}
        {selectedCode && (
          <div className="curriculum-content">
            {loading && (
              <div className="curriculum-loading">
                <p>Loading curriculum expectations...</p>
              </div>
            )}

            {!loading && curriculumData && (
              <>
                <div className="curriculum-course-info">
                  <div className="curriculum-course-meta">
                    <span className="curriculum-course-code">{curriculumData.course_code}</span>
                    <span className="curriculum-grade">Grade {curriculumData.grade_level}</span>
                    <span className="curriculum-count">
                      {curriculumData.strands.length} strand{curriculumData.strands.length !== 1 ? 's' : ''},&nbsp;
                      {totalExpectations} expectation{totalExpectations !== 1 ? 's' : ''}
                      {searchQuery && ' (filtered)'}
                    </span>
                  </div>
                  {curriculumData.strands.length > 0 && (
                    <button className="curriculum-toggle-all-btn" onClick={toggleAllStrands}>
                      {allExpanded ? 'Collapse All' : 'Expand All'}
                    </button>
                  )}
                </div>

                {curriculumData.strands.length === 0 && (
                  <div className="curriculum-empty">
                    <p>No expectations found matching "{searchQuery}".</p>
                    <button
                      className="curriculum-clear-search-btn"
                      onClick={() => setSearchQuery('')}
                    >
                      Clear search
                    </button>
                  </div>
                )}

                <div className="curriculum-strands">
                  {curriculumData.strands.map(strand => (
                    <div key={strand.name} className="curriculum-strand">
                      <button
                        className="curriculum-strand-header"
                        onClick={() => toggleStrand(strand.name)}
                        aria-expanded={expandedStrands.has(strand.name)}
                      >
                        <span className={`curriculum-chevron${expandedStrands.has(strand.name) ? ' expanded' : ''}`}>
                          &#9654;
                        </span>
                        <span className="curriculum-strand-name">{strand.name}</span>
                        <span className="curriculum-strand-count">
                          {strand.expectations.length} expectation{strand.expectations.length !== 1 ? 's' : ''}
                        </span>
                      </button>

                      {expandedStrands.has(strand.name) && (
                        <ul className="curriculum-expectations-list">
                          {strand.expectations.map(exp => (
                            <li key={exp.code} className={`curriculum-expectation ${exp.type === 'overall' ? 'overall' : 'specific'}`}>
                              <span className="curriculum-exp-code">{exp.code}</span>
                              <span className="curriculum-exp-desc">{exp.description}</span>
                              {exp.type === 'overall' && (
                                <span className="curriculum-exp-badge overall">Overall</span>
                              )}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  ))}
                </div>
              </>
            )}

            {!loading && !curriculumData && (
              <div className="curriculum-empty">
                <p>No curriculum data available for {selectedCode}.</p>
              </div>
            )}
          </div>
        )}

        {!selectedCode && !coursesLoading && courses.length > 0 && (
          <div className="curriculum-placeholder">
            <div className="curriculum-placeholder-icon">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
                <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
              </svg>
            </div>
            <h3>Select a course to view curriculum expectations</h3>
            <p>
              Browse official Ontario Ministry of Education curriculum expectations
              for {courses.length} core OSSD course{courses.length !== 1 ? 's' : ''}.
            </p>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
