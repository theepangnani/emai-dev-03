import apiClient from './client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type GoalStatus = 'active' | 'completed' | 'paused' | 'abandoned';
export type GoalCategory = 'academic' | 'personal' | 'extracurricular' | 'skill';

export interface GoalMilestone {
  id: number;
  goal_id: number;
  title: string;
  description: string | null;
  target_date: string | null;
  completed: boolean;
  completed_at: string | null;
  display_order: number;
  created_at: string;
  updated_at: string;
}

export interface StudentGoal {
  id: number;
  student_id: number;
  title: string;
  description: string | null;
  category: GoalCategory;
  target_date: string | null;
  status: GoalStatus;
  progress_pct: number;
  created_at: string;
  updated_at: string;
  milestones: GoalMilestone[];
}

export interface StudentGoalSummary {
  id: number;
  student_id: number;
  title: string;
  description: string | null;
  category: GoalCategory;
  target_date: string | null;
  status: GoalStatus;
  progress_pct: number;
  created_at: string;
  updated_at: string;
  milestone_count: number;
  completed_milestone_count: number;
}

export interface CreateGoalPayload {
  title: string;
  description?: string;
  category: GoalCategory;
  target_date?: string | null;
  status?: GoalStatus;
  progress_pct?: number;
}

export interface UpdateGoalPayload {
  title?: string;
  description?: string | null;
  category?: GoalCategory;
  target_date?: string | null;
  status?: GoalStatus;
  progress_pct?: number;
}

export interface CreateMilestonePayload {
  title: string;
  description?: string;
  target_date?: string | null;
  display_order?: number;
}

export interface UpdateMilestonePayload {
  title?: string;
  description?: string | null;
  target_date?: string | null;
  completed?: boolean;
  display_order?: number;
}

export interface GoalProgressUpdate {
  progress_pct: number;
  note?: string;
}

export interface AIMilestoneSuggestion {
  title: string;
  description: string;
  suggested_target_date: string | null;
}

export interface AIMilestonesResponse {
  suggestions: AIMilestoneSuggestion[];
  created_milestones: GoalMilestone[] | null;
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export const studentGoalsApi = {
  // Goal CRUD
  createGoal: async (payload: CreateGoalPayload): Promise<StudentGoal> => {
    const response = await apiClient.post<StudentGoal>('/api/goals/', payload);
    return response.data;
  },

  listGoals: async (params?: {
    status?: GoalStatus;
    category?: GoalCategory;
  }): Promise<StudentGoalSummary[]> => {
    const response = await apiClient.get<StudentGoalSummary[]>('/api/goals/', { params });
    return response.data;
  },

  getGoal: async (goalId: number): Promise<StudentGoal> => {
    const response = await apiClient.get<StudentGoal>(`/api/goals/${goalId}`);
    return response.data;
  },

  updateGoal: async (goalId: number, payload: UpdateGoalPayload): Promise<StudentGoal> => {
    const response = await apiClient.patch<StudentGoal>(`/api/goals/${goalId}`, payload);
    return response.data;
  },

  deleteGoal: async (goalId: number): Promise<void> => {
    await apiClient.delete(`/api/goals/${goalId}`);
  },

  // Progress
  updateProgress: async (goalId: number, payload: GoalProgressUpdate): Promise<StudentGoal> => {
    const response = await apiClient.post<StudentGoal>(`/api/goals/${goalId}/progress`, payload);
    return response.data;
  },

  // Milestones
  addMilestone: async (goalId: number, payload: CreateMilestonePayload): Promise<GoalMilestone> => {
    const response = await apiClient.post<GoalMilestone>(`/api/goals/${goalId}/milestones`, payload);
    return response.data;
  },

  updateMilestone: async (
    goalId: number,
    milestoneId: number,
    payload: UpdateMilestonePayload,
  ): Promise<GoalMilestone> => {
    const response = await apiClient.patch<GoalMilestone>(
      `/api/goals/${goalId}/milestones/${milestoneId}`,
      payload,
    );
    return response.data;
  },

  toggleMilestone: async (
    goalId: number,
    milestoneId: number,
    completed: boolean,
  ): Promise<GoalMilestone> => {
    return studentGoalsApi.updateMilestone(goalId, milestoneId, { completed });
  },

  // AI milestone generation
  generateAIMilestones: async (
    goalId: number,
    save: boolean = false,
  ): Promise<AIMilestonesResponse> => {
    const response = await apiClient.post<AIMilestonesResponse>(
      `/api/goals/${goalId}/ai-milestones`,
      null,
      { params: { save } },
    );
    return response.data;
  },

  // Parent: view child goals
  getChildGoals: async (
    studentId: number,
    params?: { status?: GoalStatus },
  ): Promise<StudentGoalSummary[]> => {
    const response = await apiClient.get<StudentGoalSummary[]>(
      `/api/goals/student/${studentId}`,
      { params },
    );
    return response.data;
  },
};

export default studentGoalsApi;
