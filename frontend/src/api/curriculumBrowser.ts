/**
 * CB-CMCP-001 M3-F 3F-1 (#4656) — Curriculum browser API client.
 *
 * Typed Axios wrapper for the M0-B curriculum REST endpoints used by
 * <CurriculumBrowser /> to render a subject → strand → topic tree and
 * let teachers / curriculum admins multi-pick SE codes.
 *
 *   GET /api/curriculum/courses          — list seeded subject codes
 *   GET /api/curriculum/{course_code}    — expectations grouped by strand
 *
 * No new backend work — these endpoints already shipped in M0-B
 * (`app/api/routes/curriculum.py`). The browser does not call the
 * `/search` endpoint (free-text search is out of scope for this
 * stripe — the existing SE-tag editor already exposes it).
 *
 * Note: the existing `frontend/src/api/curriculum.ts` only exposes the
 * `/search` route; we deliberately add a separate, scoped client here
 * rather than extending that file so the browser owns its own typed
 * surface and can be deleted/replaced independently.
 */
import { api } from './client';

export interface CurriculumExpectation {
  code: string;
  description: string;
  type: string; // 'overall' | 'specific'
}

export interface CurriculumStrand {
  name: string;
  expectations: CurriculumExpectation[];
}

export interface CurriculumCourse {
  course_code: string;
  grade_level: number;
  strands: CurriculumStrand[];
}

export interface CourseListItem {
  course_code: string;
  grade_level: number;
  expectation_count: number;
}

export const curriculumBrowserApi = {
  /** List all seeded subject codes (one row per CEGSubject with at least one accepted expectation). */
  async listCourses(): Promise<CourseListItem[]> {
    const { data } = await api.get<CourseListItem[]>('/api/curriculum/courses');
    return data;
  },

  /** Fetch all accepted expectations for a subject, grouped by strand. */
  async getCourse(courseCode: string): Promise<CurriculumCourse> {
    const { data } = await api.get<CurriculumCourse>(
      `/api/curriculum/${encodeURIComponent(courseCode)}`,
    );
    return data;
  },
};
