/**
 * CB-CMCP-001 M3α 3A-3 — Ontario curriculum (CEG) search client (#4583).
 *
 * Typed Axios wrapper for the M0-B curriculum-search endpoint:
 *
 *     GET /api/curriculum/{course_code}/search?q=<keyword>
 *
 * Backed by `app/api/routes/curriculum.py::search_curriculum_expectations`,
 * shipped under the `cmcp.enabled` flag. Used by the SE-tag editor
 * (CB-CMCP-001 M3-A 3A-3) for the autocomplete dropdown.
 *
 * The backend response groups expectations under strands; the typed wrapper
 * preserves that shape so callers can decide whether to flatten for an
 * autocomplete list.
 */
import { api } from './client';

export interface CurriculumExpectationItem {
  code: string;
  description: string;
  type: string; // 'overall' | 'specific'
}

export interface CurriculumStrandGroup {
  name: string;
  expectations: CurriculumExpectationItem[];
}

export interface CurriculumCourseResponse {
  course_code: string;
  grade_level: number;
  strands: CurriculumStrandGroup[];
}

export const curriculumApi = {
  /**
   * Keyword-search expectations within a single course (subject).
   *
   * Returns the same shape as `GET /{course_code}` but filtered by the
   * keyword (case-insensitive substring match against ministry code OR
   * description). Empty `q` falls through to the unfiltered course view.
   */
  async searchExpectations(
    courseCode: string,
    q: string,
  ): Promise<CurriculumCourseResponse> {
    const { data } = await api.get<CurriculumCourseResponse>(
      `/api/curriculum/${encodeURIComponent(courseCode)}/search`,
      { params: { q } },
    );
    return data;
  },
};
