/**
 * Ontario Curriculum Management API (#571).
 */
import { api } from './client';

export interface CurriculumExpectationItem {
  code: string;
  description: string;
  type: 'overall' | 'specific' | string;
}

export interface CurriculumStrand {
  name: string;
  expectations: CurriculumExpectationItem[];
}

export interface CurriculumCourseResponse {
  course_code: string;
  grade_level: number;
  strands: CurriculumStrand[];
}

export interface CurriculumCourseListItem {
  course_code: string;
  grade_level: number;
  expectation_count: number;
}

export const curriculumApi = {
  /** List all course codes that have seeded curriculum expectations. */
  getCourses(): Promise<CurriculumCourseListItem[]> {
    return api.get<CurriculumCourseListItem[]>('/curriculum/courses').then((r) => r.data);
  },

  /** Get all expectations for a course, grouped by strand. */
  getCourse(courseCode: string): Promise<CurriculumCourseResponse> {
    return api
      .get<CurriculumCourseResponse>(`/curriculum/${encodeURIComponent(courseCode)}`)
      .then((r) => r.data);
  },

  /** Search expectations within a course by keyword. */
  searchExpectations(courseCode: string, q: string): Promise<CurriculumCourseResponse> {
    return api
      .get<CurriculumCourseResponse>(
        `/curriculum/${encodeURIComponent(courseCode)}/search`,
        { params: { q } },
      )
      .then((r) => r.data);
  },
};
