import { api } from './client';

// ---------------------------------------------------------------------------
// TypeScript types
// ---------------------------------------------------------------------------

export interface RubricCriterion {
  criterion: string;
  max_points: number;
  description: string;
}

export interface PeerReviewAssignment {
  id: number;
  teacher_id: number;
  course_id: number | null;
  title: string;
  instructions: string | null;
  due_date: string | null;
  is_anonymous: boolean;
  rubric: RubricCriterion[];
  max_reviewers_per_student: number;
  reviews_released: boolean;
  created_at: string;
  updated_at: string | null;
}

export interface PeerReviewAssignmentCreate {
  title: string;
  instructions?: string;
  due_date?: string;
  is_anonymous?: boolean;
  rubric?: RubricCriterion[];
  max_reviewers_per_student?: number;
  course_id?: number;
}

export interface PeerReviewSubmission {
  id: number;
  assignment_id: number;
  author_id: number;
  title: string;
  content: string;
  file_key: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface PeerReviewSubmissionCreate {
  title: string;
  content: string;
}

export interface PeerReview {
  id: number;
  submission_id: number;
  reviewer_id: number;
  scores: Record<string, number> | null;
  overall_score: number | null;
  written_feedback: string | null;
  status: 'draft' | 'submitted' | 'completed';
  is_anonymous: boolean;
  submitted_at: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface PeerReviewCreate {
  allocation_id: number;
  scores: Record<string, number>;
  written_feedback?: string;
}

export interface ReviewTodoItem {
  allocation_id: number;
  submission_id: number;
  submission_title: string;
  submission_content: string;
  review_status: string;
  review_id: number | null;
  author_id?: number;
}

export interface PeerReviewSummary {
  submission_id: number;
  author_id: number;
  author_name: string;
  avg_score: number | null;
  review_count: number;
  criteria_averages: Record<string, number>;
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

/** Teacher: create a peer review assignment */
export async function createPeerReviewAssignment(
  data: PeerReviewAssignmentCreate,
): Promise<PeerReviewAssignment> {
  const res = await api.post<PeerReviewAssignment>('/api/peer-review/assignments', data);
  return res.data;
}

/** List assignments — teacher sees own, student sees all */
export async function listPeerReviewAssignments(): Promise<PeerReviewAssignment[]> {
  const res = await api.get<PeerReviewAssignment[]>('/api/peer-review/assignments');
  return res.data;
}

/** Get a single assignment with rubric */
export async function getPeerReviewAssignment(id: number): Promise<PeerReviewAssignment> {
  const res = await api.get<PeerReviewAssignment>(`/api/peer-review/assignments/${id}`);
  return res.data;
}

/** Student: submit work for an assignment */
export async function submitWork(
  assignmentId: number,
  data: PeerReviewSubmissionCreate,
): Promise<PeerReviewSubmission> {
  const res = await api.post<PeerReviewSubmission>(
    `/api/peer-review/assignments/${assignmentId}/submit`,
    data,
  );
  return res.data;
}

/** Teacher: allocate reviewers for an assignment */
export async function allocateReviewers(
  assignmentId: number,
): Promise<{ allocated: number; message: string }> {
  const res = await api.post<{ allocated: number; message: string }>(
    `/api/peer-review/assignments/${assignmentId}/allocate`,
  );
  return res.data;
}

/** Student: get the list of submissions to review */
export async function getMyReviewsToDo(assignmentId: number): Promise<ReviewTodoItem[]> {
  const res = await api.get<ReviewTodoItem[]>(
    `/api/peer-review/assignments/${assignmentId}/my-reviews`,
  );
  return res.data;
}

/** Student: submit a peer review */
export async function submitPeerReview(data: PeerReviewCreate): Promise<PeerReview> {
  const res = await api.post<PeerReview>('/api/peer-review/reviews', data);
  return res.data;
}

/** Teacher / author: get reviews for a submission */
export async function getSubmissionReviews(submissionId: number): Promise<PeerReview[]> {
  const res = await api.get<PeerReview[]>(`/api/peer-review/submissions/${submissionId}/reviews`);
  return res.data;
}

/** Teacher: release reviews to students */
export async function releaseReviews(assignmentId: number): Promise<PeerReviewAssignment> {
  const res = await api.post<PeerReviewAssignment>(
    `/api/peer-review/assignments/${assignmentId}/release`,
  );
  return res.data;
}

/** Teacher: get assignment score summary */
export async function getAssignmentSummary(assignmentId: number): Promise<PeerReviewSummary[]> {
  const res = await api.get<PeerReviewSummary[]>(
    `/api/peer-review/assignments/${assignmentId}/summary`,
  );
  return res.data;
}
