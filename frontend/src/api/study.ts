import { api, AI_TIMEOUT } from './client';

// Study Guide Types
export interface AutoCreatedTask {
  id: number;
  title: string;
  due_date: string;
  priority: string;
}

export interface StudyGuide {
  id: number;
  user_id: number;
  assignment_id: number | null;
  course_id: number | null;
  course_content_id: number | null;
  title: string;
  content: string;
  guide_type: string;
  version: number;
  parent_guide_id: number | null;
  relationship_type?: string | null;
  generation_context?: string | null;
  focus_prompt: string | null;
  is_truncated?: boolean;
  parent_summary?: string | null;
  created_at: string;
  archived_at: string | null;
  auto_created_tasks?: AutoCreatedTask[];
  // Sharing fields
  shared_with_user_id?: number | null;
  shared_at?: string | null;
  viewed_at?: string | null;
  viewed_count?: number;
  shared_with_name?: string | null;
  // §6.106: Strategy context
  document_type?: string | null;
  study_goal?: string | null;
  study_goal_text?: string | null;
  suggestion_topics?: string | null;
}

// Sharing types
export interface SharedGuideStatus {
  id: number;
  title: string;
  guide_type: string;
  shared_with_user_id: number | null;
  shared_with_name: string | null;
  shared_at: string | null;
  viewed_at: string | null;
  viewed_count: number;
  status: 'not_shared' | 'shared' | 'viewed';
  created_at: string;
}

export interface SharedWithMeGuide {
  id: number;
  title: string;
  content: string;
  guide_type: string;
  shared_by_name: string;
  shared_at: string;
  viewed_at: string | null;
  viewed_count: number;
  created_at: string;
  course_content_id: number | null;
}

export interface StudyGuideTreeNode {
  id: number;
  title: string;
  guide_type: string;
  created_at: string;
  children: StudyGuideTreeNode[];
}

export interface StudyGuideTreeResponse {
  root: StudyGuideTreeNode;
  current_path: number[];
}

export interface DuplicateCheckResponse {
  exists: boolean;
  existing_guide: StudyGuide | null;
  message: string | null;
}

export interface QuizQuestion {
  question: string;
  options: { A: string; B: string; C: string; D: string };
  correct_answer: string;
  explanation: string;
}

export interface Quiz {
  id: number;
  title: string;
  questions: QuizQuestion[];
  guide_type: string;
  course_content_id: number | null;
  version: number;
  parent_guide_id: number | null;
  created_at: string;
  auto_created_tasks?: AutoCreatedTask[];
}

export interface Flashcard {
  front: string;
  back: string;
}

export interface FlashcardSet {
  id: number;
  title: string;
  cards: Flashcard[];
  guide_type: string;
  course_content_id: number | null;
  version: number;
  parent_guide_id: number | null;
  created_at: string;
  auto_created_tasks?: AutoCreatedTask[];
}

export interface MindMapBranch {
  label: string;
  detail: string;
}

export interface MindMapBranchGroup {
  label: string;
  children: MindMapBranch[];
}

export interface MindMapData {
  central_topic: string;
  branches: MindMapBranchGroup[];
}

export interface MindMap {
  id: number;
  title: string;
  mind_map: MindMapData;
  guide_type: string;
  version: number;
  parent_guide_id: number | null;
  created_at: string;
  auto_created_tasks?: AutoCreatedTask[];
}

export interface SupportedFormats {
  documents: string[];
  spreadsheets: string[];
  presentations: string[];
  images: string[];
  archives: string[];
  max_file_size_mb: number;
  ocr_available: boolean;
}

export interface ExtractedText {
  filename: string;
  text: string;
  character_count: number;
  word_count: number;
}

// Quiz Result Types
export interface QuizResultCreate {
  study_guide_id: number;
  score: number;
  total_questions: number;
  answers: Record<number, string>;
  time_taken_seconds?: number;
  student_user_id?: number;
}

export interface QuizResultResponse {
  id: number;
  user_id: number;
  study_guide_id: number;
  score: number;
  total_questions: number;
  percentage: number;
  answers_json: string;
  attempt_number: number;
  time_taken_seconds: number | null;
  completed_at: string;
  quiz_title: string | null;
}

export interface QuizResultSummary {
  id: number;
  study_guide_id: number;
  quiz_title: string | null;
  score: number;
  total_questions: number;
  percentage: number;
  attempt_number: number;
  completed_at: string;
}

export interface QuizHistoryStats {
  total_attempts: number;
  unique_quizzes: number;
  average_score: number;
  best_score: number;
  recent_trend: 'improving' | 'declining' | 'stable';
}

export interface ResolvedStudent {
  student_user_id: number;
  student_name: string;
}

export async function classifyDocument(textContent: string, filename: string): Promise<{ document_type: string; confidence: number }> {
  const response = await api.post('/api/study/classify-document', {
    text_content: textContent,
    filename,
  });
  return response.data;
}

// Study Tools API
export const studyApi = {
  generateGuide: async (params: { assignment_id?: number; course_id?: number; course_content_id?: number; title?: string; content?: string; regenerate_from_id?: number; custom_prompt?: string; focus_prompt?: string; document_type?: string; study_goal?: string; study_goal_text?: string }) => {
    const response = await api.post('/api/study/generate', params, AI_TIMEOUT);
    return response.data as StudyGuide;
  },

  generateQuiz: async (params: { assignment_id?: number; course_id?: number; course_content_id?: number; topic?: string; content?: string; num_questions?: number; regenerate_from_id?: number; focus_prompt?: string; difficulty?: string; document_type?: string; study_goal?: string; study_goal_text?: string }) => {
    const response = await api.post('/api/study/quiz/generate', params, AI_TIMEOUT);
    return response.data as Quiz;
  },

  generateFlashcards: async (params: { assignment_id?: number; course_id?: number; course_content_id?: number; topic?: string; content?: string; num_cards?: number; regenerate_from_id?: number; focus_prompt?: string; document_type?: string; study_goal?: string; study_goal_text?: string }) => {
    const response = await api.post('/api/study/flashcards/generate', params, AI_TIMEOUT);
    return response.data as FlashcardSet;
  },

  generateMindMap: async (params: { assignment_id?: number; course_id?: number; course_content_id?: number; topic?: string; content?: string; regenerate_from_id?: number; focus_prompt?: string }) => {
    const response = await api.post('/api/study/mind-map/generate', params, AI_TIMEOUT);
    return response.data as MindMap;
  },

  checkDuplicate: async (params: { title?: string; guide_type: string; assignment_id?: number; course_id?: number }) => {
    const response = await api.post('/api/study/check-duplicate', params);
    return response.data as DuplicateCheckResponse;
  },

  listGuides: async (params?: { guide_type?: string; course_id?: number; course_content_id?: number; include_children?: boolean; include_archived?: boolean; student_user_id?: number }) => {
    const response = await api.get('/api/study/guides', { params: params || {} });
    return response.data as StudyGuide[];
  },

  listGuideVersions: async (guideId: number) => {
    const response = await api.get(`/api/study/guides/${guideId}/versions`);
    return response.data as StudyGuide[];
  },

  getGuide: async (id: number) => {
    const response = await api.get(`/api/study/guides/${id}`);
    return response.data as StudyGuide;
  },

  deleteGuide: async (id: number) => {
    await api.delete(`/api/study/guides/${id}`);
  },

  restoreGuide: async (id: number) => {
    const response = await api.patch(`/api/study/guides/${id}/restore`);
    return response.data as StudyGuide;
  },

  permanentDeleteGuide: async (id: number) => {
    await api.delete(`/api/study/guides/${id}/permanent`);
  },

  updateGuide: async (id: number, data: { title?: string; course_id?: number | null; course_content_id?: number | null }) => {
    const response = await api.patch(`/api/study/guides/${id}`, data);
    return response.data as StudyGuide;
  },

  continueGuide: async (guideId: number) => {
    const response = await api.post(`/api/study/${guideId}/continue`, null, AI_TIMEOUT);
    return response.data as StudyGuide;
  },

  /** Return the SSE endpoint URL for streaming continuation of a truncated guide. */
  continueGuideStreamUrl: (guideId: number) => `/api/study/${guideId}/continue-stream`,

  // File Upload Methods
  getSupportedFormats: async () => {
    const response = await api.get('/api/study/upload/formats');
    return response.data as SupportedFormats;
  },

  generateFromFile: async (params: {
    file: File;
    title?: string;
    guide_type: 'study_guide' | 'quiz' | 'flashcards';
    num_questions?: number;
    num_cards?: number;
    course_id?: number;
    course_content_id?: number;
    focus_prompt?: string;
    difficulty?: string;
    document_type?: string;
    study_goal?: string;
    study_goal_text?: string;
  }) => {
    const formData = new FormData();
    formData.append('file', params.file);
    if (params.title) formData.append('title', params.title);
    formData.append('guide_type', params.guide_type);
    if (params.num_questions) formData.append('num_questions', params.num_questions.toString());
    if (params.num_cards) formData.append('num_cards', params.num_cards.toString());
    if (params.course_id) formData.append('course_id', params.course_id.toString());
    if (params.course_content_id) formData.append('course_content_id', params.course_content_id.toString());
    if (params.focus_prompt) formData.append('focus_prompt', params.focus_prompt);
    if (params.difficulty) formData.append('difficulty', params.difficulty);
    if (params.document_type) formData.append('document_type', params.document_type);
    if (params.study_goal) formData.append('study_goal', params.study_goal);
    if (params.study_goal_text) formData.append('study_goal_text', params.study_goal_text);

    const response = await api.post('/api/study/upload/generate', formData, AI_TIMEOUT);
    return response.data as StudyGuide;
  },

  generateFromTextAndImages: async (params: {
    content: string;
    images: File[];
    title?: string;
    guide_type: 'study_guide' | 'quiz' | 'flashcards';
    num_questions?: number;
    num_cards?: number;
    course_id?: number;
    course_content_id?: number;
    focus_prompt?: string;
    difficulty?: string;
    document_type?: string;
    study_goal?: string;
    study_goal_text?: string;
  }) => {
    const formData = new FormData();
    formData.append('content', params.content);
    if (params.title) formData.append('title', params.title);
    formData.append('guide_type', params.guide_type);
    if (params.num_questions) formData.append('num_questions', params.num_questions.toString());
    if (params.num_cards) formData.append('num_cards', params.num_cards.toString());
    if (params.course_id) formData.append('course_id', params.course_id.toString());
    if (params.course_content_id) formData.append('course_content_id', params.course_content_id.toString());
    if (params.focus_prompt) formData.append('focus_prompt', params.focus_prompt);
    if (params.difficulty) formData.append('difficulty', params.difficulty);
    if (params.document_type) formData.append('document_type', params.document_type);
    if (params.study_goal) formData.append('study_goal', params.study_goal);
    if (params.study_goal_text) formData.append('study_goal_text', params.study_goal_text);
    params.images.forEach(img => formData.append('images', img));

    const response = await api.post('/api/study/generate-with-images', formData, AI_TIMEOUT);
    return response.data as StudyGuide;
  },

  extractTextFromFile: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await api.post('/api/study/upload/extract-text', formData, AI_TIMEOUT);
    return response.data as ExtractedText;
  },

  // Quiz Results Methods
  saveQuizResult: async (data: QuizResultCreate) => {
    const response = await api.post('/api/quiz-results/', data);
    return response.data as QuizResultResponse;
  },

  getQuizHistory: async (params?: { study_guide_id?: number; student_user_id?: number; limit?: number; offset?: number }) => {
    const response = await api.get('/api/quiz-results/', { params: params || {} });
    return response.data as QuizResultSummary[];
  },

  getQuizStats: async (params?: { student_user_id?: number }) => {
    const response = await api.get('/api/quiz-results/stats', { params: params || {} });
    return response.data as QuizHistoryStats;
  },

  getQuizResult: async (id: number) => {
    const response = await api.get(`/api/quiz-results/${id}`);
    return response.data as QuizResultResponse;
  },

  deleteQuizResult: async (id: number) => {
    await api.delete(`/api/quiz-results/${id}`);
  },

  generateChildGuide: async (guideId: number, params: { topic: string; guide_type: string; custom_prompt?: string; document_type?: string; study_goal?: string; max_tokens?: number }) => {
    const response = await api.post(`/api/study/guides/${guideId}/generate-child`, params, AI_TIMEOUT);
    return response.data as StudyGuide;
  },

  listChildGuides: async (guideId: number) => {
    const response = await api.get(`/api/study/guides/${guideId}/children`);
    return response.data as StudyGuide[];
  },

  getGuideTree: async (guideId: number) => {
    const response = await api.get(`/api/study/guides/${guideId}/tree`);
    return response.data as StudyGuideTreeResponse;
  },

  resolveStudent: async (params: { course_id?: number; study_guide_id?: number }) => {
    const response = await api.get('/api/quiz-results/resolve-student', { params });
    return response.data as ResolvedStudent | null;
  },

  // Study Sharing (Parent-Child Study Link #1414)
  shareGuide: async (guideId: number, studentId: number) => {
    const response = await api.post(`/api/study-guides/${guideId}/share`, { student_id: studentId });
    return response.data;
  },

  getSharedWithMe: async () => {
    const response = await api.get('/api/study-guides/shared-with-me');
    return response.data as SharedWithMeGuide[];
  },

  markViewed: async (guideId: number) => {
    const response = await api.post(`/api/study-guides/${guideId}/mark-viewed`);
    return response.data;
  },

  getSharedStatus: async () => {
    const response = await api.get('/api/study-guides/shared-status');
    return response.data as SharedGuideStatus[];
  },
};
