/**
 * CB-CMCP-001 M3-F 3F-1 (#4656) — Curriculum browser.
 *
 * Lets teachers and curriculum admins browse the seeded Ontario CEG and
 * multi-pick SE codes. Backs 3F-2 (generation request flow integration).
 *
 * Surface
 * -------
 *   ┌────────────┬────────────────────────────────────┐
 *   │  Subjects  │  [Tree view] [Table view]          │
 *   │  ────────  │                                    │
 *   │  • MATH    │  ▼ Strand A — Number               │
 *   │  • LANG    │     ☐ A1.1  Read and represent…    │
 *   │  …         │     ☐ A1.2  Compare and order…     │
 *   │            │  ▶ Strand B — Algebra              │
 *   ├────────────┴────────────────────────────────────┤
 *   │  Selected (2): [A1.1 ×] [B2.3 ×]                │
 *   └────────────────────────────────────────────────┘
 *
 * Behaviour
 * ---------
 * - Mounts and calls ``GET /api/curriculum/courses`` to populate the
 *   subject column. Subjects are filtered by the optional ``grade`` prop:
 *   the courses-list endpoint reports ``max(grade)`` per subject, so we
 *   keep subjects whose ``grade_level >= grade`` (a defensive lower bound;
 *   most subjects span multiple grades on the seeded CEG).
 * - When a subject is picked, calls ``GET /api/curriculum/{course_code}``
 *   and renders the strand → expectation tree (or the same data as a flat
 *   table — toggleable via the view buttons).
 * - Each expectation has a checkbox; toggling it adds / removes the
 *   ministry code from ``selection``. ``onSelectionChange`` is fired
 *   whenever the selection changes, with the next deduped list of codes.
 * - The chip area shows the running selection across ALL subjects; users
 *   can switch subjects without losing chips, and individual chips can be
 *   removed via their ``×`` button.
 *
 * Stable typed exports
 * --------------------
 *   <CurriculumBrowser
 *      onSelectionChange={(codes: string[]) => void}
 *      initialSelection={string[]?}
 *      grade={number?}
 *   />
 *
 * The component is a controlled-on-output, uncontrolled-on-input shape:
 * it accepts ``initialSelection`` once at mount and then owns selection
 * state internally. Parents that want full control can hold their own
 * state and re-mount the component when it should reset (the standard
 * React pattern for this shape).
 *
 * Out of scope (per #4656)
 * ------------------------
 * - Free-text search against expectation_text. The existing M0-B
 *   ``GET /{course_code}/search`` endpoint is wrapped by the SE-tag
 *   editor; this stripe deliberately reuses tree+table browse instead.
 * - Editing / creating SEs (curriculum admin territory; deferred).
 *
 * Tokens / styling
 * ----------------
 * Uses existing global tokens (--color-*, --radius-*, --font-*) defined
 * in index.css / THEME.md (Bridge theme). No new tokens are introduced.
 */
import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react';

import {
  curriculumBrowserApi,
  type CourseListItem,
  type CurriculumCourse,
} from '../../api/curriculumBrowser';
import './CurriculumBrowser.css';

export interface CurriculumBrowserProps {
  /** Called whenever the selected SE codes change (dedup, insertion-order). */
  onSelectionChange: (codes: string[]) => void;
  /** Optional starting selection. Owned internally after mount. */
  initialSelection?: string[];
  /**
   * Optional grade lower bound. Subjects whose ``grade_level`` (max grade
   * in the seed) is below this value are filtered out of the subject list.
   */
  grade?: number;
}

type ViewMode = 'tree' | 'table';

export function CurriculumBrowser({
  onSelectionChange,
  initialSelection,
  grade,
}: CurriculumBrowserProps) {
  // Stable component-level prefix used to scope checkbox ids so multiple
  // <CurriculumBrowser /> instances on the same page do not collide.
  const checkboxIdPrefix = useId();
  // ── Subject list ─────────────────────────────────────────────────────
  const [courses, setCourses] = useState<CourseListItem[]>([]);
  const [coursesLoading, setCoursesLoading] = useState(true);
  const [coursesError, setCoursesError] = useState<string | null>(null);

  // ── Per-subject detail (cached so flipping back keeps tree expansion) ─
  const [activeCourseCode, setActiveCourseCode] = useState<string | null>(null);
  const [coursesById, setCoursesById] = useState<Record<string, CurriculumCourse>>(
    {},
  );
  // Mirror of ``coursesById`` kept in a ref so the per-subject fetch
  // effect can read the cache without depending on the state itself.
  // Depending on ``coursesById`` would re-fire the effect after every
  // successful fetch (the very setState that caused the cache hit), an
  // unnecessary render-loop hop. The ref is updated via ``useEffect``
  // below so React's render-state and ref-state stay in sync.
  const coursesByIdRef = useRef(coursesById);
  useEffect(() => {
    coursesByIdRef.current = coursesById;
  }, [coursesById]);
  // Per-subject error map. Keeping the error keyed by code (rather than a
  // single scalar) avoids a stale-error race when the user flips subjects
  // mid-fetch — switching to a healthy subject silently clears the prior
  // subject's error from the visible message.
  const [detailErrors, setDetailErrors] = useState<Record<string, string>>({});

  // ── Tree expansion (per subject) ──────────────────────────────────────
  const [expandedStrands, setExpandedStrands] = useState<Record<string, boolean>>(
    {},
  );

  // ── View mode ─────────────────────────────────────────────────────────
  const [viewMode, setViewMode] = useState<ViewMode>('tree');

  // ── Selection (running across all subjects) ──────────────────────────
  // Stored as an array to preserve insertion order; a Set is derived for
  // O(1) lookup during render.
  const [selection, setSelection] = useState<string[]>(
    initialSelection ? Array.from(new Set(initialSelection)) : [],
  );
  const selectionSet = useMemo(() => new Set(selection), [selection]);

  // ── Initial subject fetch ────────────────────────────────────────────
  // setCoursesLoading is initialized to true at declaration; setting it
  // again synchronously here would trigger react-hooks/set-state-in-effect.
  // The promise chain owns all subsequent state transitions.
  useEffect(() => {
    let cancelled = false;
    curriculumBrowserApi
      .listCourses()
      .then((rows) => {
        if (cancelled) return;
        setCourses(rows);
        setCoursesError(null);
        setCoursesLoading(false);
      })
      .catch(() => {
        if (cancelled) return;
        setCourses([]);
        setCoursesError('Could not load curriculum subjects.');
        setCoursesLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Filter the subject list by the optional grade lower bound. Calculated
  // outside an effect so the render is purely derived.
  const filteredCourses = useMemo(() => {
    if (typeof grade !== 'number') return courses;
    return courses.filter((c) => c.grade_level >= grade);
  }, [courses, grade]);

  // Auto-pick the first subject once the filtered list is known so the
  // user doesn't need an extra click on first paint. Derived rather than
  // stored: when the user has not explicitly selected a subject yet, fall
  // through to the first filtered course. Once they click a subject,
  // ``activeCourseCode`` takes precedence and this fallback is ignored.
  const effectiveActiveCourseCode =
    activeCourseCode ?? filteredCourses[0]?.course_code ?? null;

  // ── Per-subject detail fetch (cached) ─────────────────────────────────
  // Like the courses fetch, no synchronous setState in the effect body —
  // loading state is derived from the cache below. The cache check reads
  // ``coursesByIdRef.current`` so the effect deps don't include the cache
  // map (which would re-fire the effect after every successful fetch).
  useEffect(() => {
    if (!effectiveActiveCourseCode) return;
    if (coursesByIdRef.current[effectiveActiveCourseCode]) return; // cache hit

    let cancelled = false;
    const code = effectiveActiveCourseCode;
    curriculumBrowserApi
      .getCourse(code)
      .then((course) => {
        if (cancelled) return;
        setCoursesById((prev) => ({ ...prev, [code]: course }));
        // Default: expand all strands for the freshly-loaded subject.
        setExpandedStrands((prev) => {
          const next = { ...prev };
          for (const s of course.strands) {
            const key = `${code}::${s.name}`;
            if (!(key in next)) next[key] = true;
          }
          return next;
        });
        setDetailErrors((prev) => {
          if (!(code in prev)) return prev;
          const next = { ...prev };
          delete next[code];
          return next;
        });
      })
      .catch(() => {
        if (cancelled) return;
        setDetailErrors((prev) => ({
          ...prev,
          [code]: `Could not load ${code} expectations.`,
        }));
      });
    return () => {
      cancelled = true;
    };
  }, [effectiveActiveCourseCode]);

  // Derived loading / error state for the active subject.
  const detailError = effectiveActiveCourseCode
    ? detailErrors[effectiveActiveCourseCode] ?? null
    : null;
  const detailLoading =
    !!effectiveActiveCourseCode &&
    !coursesById[effectiveActiveCourseCode] &&
    !detailError;

  // ── Selection handlers ───────────────────────────────────────────────
  // Compute the next list outside the functional updater so the parent
  // ``onSelectionChange`` callback fires exactly once per user interaction.
  // Calling the parent callback inside a functional updater would invoke
  // it twice in StrictMode (React intentionally double-invokes updaters
  // in dev) — confusing for parents that have side-effects in the
  // callback (analytics, logging).
  const toggleCode = useCallback(
    (code: string) => {
      const idx = selection.indexOf(code);
      const next =
        idx === -1 ? [...selection, code] : selection.filter((c) => c !== code);
      setSelection(next);
      onSelectionChange(next);
    },
    [selection, onSelectionChange],
  );

  const removeCode = useCallback(
    (code: string) => {
      const next = selection.filter((c) => c !== code);
      setSelection(next);
      onSelectionChange(next);
    },
    [selection, onSelectionChange],
  );

  const toggleStrand = useCallback((subject: string, strand: string) => {
    const key = `${subject}::${strand}`;
    setExpandedStrands((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);

  // ── Render ────────────────────────────────────────────────────────────
  const activeCourse = effectiveActiveCourseCode
    ? coursesById[effectiveActiveCourseCode] ?? null
    : null;

  return (
    <div className="cmcp-curriculum-browser" data-testid="cmcp-curriculum-browser">
      {/* Subject column */}
      <aside
        className="cmcp-curriculum-browser-subjects"
        aria-label="Curriculum subjects"
      >
        <h3 className="cmcp-curriculum-browser-subjects-heading">Subjects</h3>
        {coursesLoading && (
          <div className="cmcp-curriculum-browser-loading" aria-live="polite">
            Loading subjects…
          </div>
        )}
        {!coursesLoading && coursesError && (
          <div className="cmcp-curriculum-browser-error" role="alert">
            {coursesError}
          </div>
        )}
        {!coursesLoading && !coursesError && filteredCourses.length === 0 && (
          <div className="cmcp-curriculum-browser-empty">
            No subjects available.
          </div>
        )}
        {filteredCourses.map((c) => {
          const isActive = c.course_code === effectiveActiveCourseCode;
          return (
            <button
              key={c.course_code}
              type="button"
              className={
                'cmcp-curriculum-browser-subject-button' +
                (isActive
                  ? ' cmcp-curriculum-browser-subject-button-active'
                  : '')
              }
              aria-pressed={isActive}
              onClick={() => setActiveCourseCode(c.course_code)}
            >
              <span>{c.course_code}</span>
              <span className="cmcp-curriculum-browser-subject-count">
                {c.expectation_count}
              </span>
            </button>
          );
        })}
      </aside>

      {/* Detail column */}
      <section
        className="cmcp-curriculum-browser-detail"
        aria-label="Curriculum expectations"
      >
        <header className="cmcp-curriculum-browser-detail-header">
          <h3 className="cmcp-curriculum-browser-detail-title">
            {effectiveActiveCourseCode ?? 'Select a subject'}
          </h3>
          <div
            className="cmcp-curriculum-browser-view-toggle"
            role="group"
            aria-label="View mode"
          >
            <button
              type="button"
              className={
                'cmcp-curriculum-browser-view-toggle-btn' +
                (viewMode === 'tree'
                  ? ' cmcp-curriculum-browser-view-toggle-btn-active'
                  : '')
              }
              aria-pressed={viewMode === 'tree'}
              onClick={() => setViewMode('tree')}
            >
              Tree
            </button>
            <button
              type="button"
              className={
                'cmcp-curriculum-browser-view-toggle-btn' +
                (viewMode === 'table'
                  ? ' cmcp-curriculum-browser-view-toggle-btn-active'
                  : '')
              }
              aria-pressed={viewMode === 'table'}
              onClick={() => setViewMode('table')}
            >
              Table
            </button>
          </div>
        </header>

        {detailLoading && (
          <div className="cmcp-curriculum-browser-loading" aria-live="polite">
            Loading expectations…
          </div>
        )}
        {!detailLoading && detailError && (
          <div className="cmcp-curriculum-browser-error" role="alert">
            {detailError}
          </div>
        )}

        {!detailLoading && !detailError && activeCourse && viewMode === 'tree' && (
          <ul
            className="cmcp-curriculum-browser-tree"
            aria-label={`${activeCourse.course_code} expectations (tree view)`}
          >
            {activeCourse.strands.map((strand) => {
              const key = `${activeCourse.course_code}::${strand.name}`;
              const expanded = expandedStrands[key] ?? true;
              return (
                <li key={key} className="cmcp-curriculum-browser-strand">
                  <button
                    type="button"
                    className="cmcp-curriculum-browser-strand-toggle"
                    aria-expanded={expanded}
                    onClick={() =>
                      toggleStrand(activeCourse.course_code, strand.name)
                    }
                  >
                    <span
                      className="cmcp-curriculum-browser-strand-caret"
                      aria-hidden="true"
                    >
                      {expanded ? '▼' : '▶'}
                    </span>
                    <span>{strand.name}</span>
                    <span className="cmcp-curriculum-browser-strand-count">
                      {strand.expectations.length}
                    </span>
                  </button>
                  {expanded && (
                    <ul className="cmcp-curriculum-browser-expectations">
                      {strand.expectations.map((exp) => {
                        const isSelected = selectionSet.has(exp.code);
                        const inputId = `${checkboxIdPrefix}-tree-${exp.code}`;
                        return (
                          <li
                            key={exp.code}
                            className={
                              'cmcp-curriculum-browser-expectation' +
                              (isSelected
                                ? ' cmcp-curriculum-browser-expectation-selected'
                                : '')
                            }
                          >
                            <input
                              id={inputId}
                              type="checkbox"
                              className="cmcp-curriculum-browser-expectation-checkbox"
                              checked={isSelected}
                              onChange={() => toggleCode(exp.code)}
                              aria-label={`Select expectation ${exp.code}`}
                            />
                            {/* <label htmlFor> handles click + keyboard
                                semantics natively — no JS event juggling
                                between the row and the input. */}
                            <label
                              htmlFor={inputId}
                              className="cmcp-curriculum-browser-expectation-code"
                            >
                              {exp.code}
                            </label>
                            <label
                              htmlFor={inputId}
                              className="cmcp-curriculum-browser-expectation-desc"
                            >
                              {exp.description}
                            </label>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </li>
              );
            })}
          </ul>
        )}

        {!detailLoading && !detailError && activeCourse && viewMode === 'table' && (
          <div className="cmcp-curriculum-browser-table-wrap">
            <table
              className="cmcp-curriculum-browser-table"
              aria-label={`${activeCourse.course_code} expectations (table view)`}
            >
              <thead>
                <tr>
                  <th
                    className="cmcp-curriculum-browser-table-checkbox-cell"
                    scope="col"
                  >
                    <span className="visually-hidden">Select</span>
                  </th>
                  <th scope="col">Strand</th>
                  <th scope="col">Code</th>
                  <th scope="col">Description</th>
                </tr>
              </thead>
              <tbody>
                {activeCourse.strands.flatMap((strand) =>
                  strand.expectations.map((exp) => {
                    const isSelected = selectionSet.has(exp.code);
                    return (
                      <tr
                        key={`${strand.name}-${exp.code}`}
                        className={
                          isSelected
                            ? 'cmcp-curriculum-browser-row-selected'
                            : undefined
                        }
                      >
                        <td className="cmcp-curriculum-browser-table-checkbox-cell">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => toggleCode(exp.code)}
                            aria-label={`Select expectation ${exp.code}`}
                          />
                        </td>
                        <td>{strand.name}</td>
                        <td className="cmcp-curriculum-browser-table-code-cell">
                          {exp.code}
                        </td>
                        <td>{exp.description}</td>
                      </tr>
                    );
                  }),
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Chip area — spans both columns */}
      <div
        className="cmcp-curriculum-browser-chips-wrap"
        style={{ gridColumn: '1 / -1' }}
      >
        <h3 className="cmcp-curriculum-browser-chips-heading">
          Selected ({selection.length})
        </h3>
        <ul
          className="cmcp-curriculum-browser-chips"
          role="list"
          aria-label="Selected expectations"
        >
          {selection.length === 0 && (
            <li className="cmcp-curriculum-browser-chips-empty">
              No expectations selected.
            </li>
          )}
          {selection.map((code) => (
            <li key={code} className="cmcp-curriculum-browser-chip">
              <span className="cmcp-curriculum-browser-chip-code">{code}</span>
              <button
                type="button"
                className="cmcp-curriculum-browser-chip-remove"
                onClick={() => removeCode(code)}
                aria-label={`Remove SE code ${code}`}
              >
                <span aria-hidden="true">×</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
