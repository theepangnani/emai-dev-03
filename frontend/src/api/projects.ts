import { api } from './client';

export interface MilestoneItem {
  id: number;
  project_id: number;
  title: string;
  due_date: string | null;
  is_completed: boolean;
  completed_at: string | null;
  order_index: number;
}

export interface ProjectItem {
  id: number;
  user_id: number;
  student_id: number | null;
  course_id: number | null;
  course_name: string | null;
  title: string;
  description: string | null;
  due_date: string | null;
  status: string;
  color: string;
  milestones: MilestoneItem[];
  milestone_total: number;
  milestone_completed: number;
  created_at: string;
  updated_at: string | null;
}

export interface ProjectCreate {
  title: string;
  description?: string;
  course_id?: number | null;
  student_id?: number | null;
  due_date?: string | null;
  status?: string;
  color?: string;
}

export interface ProjectUpdate {
  title?: string;
  description?: string | null;
  course_id?: number | null;
  student_id?: number | null;
  due_date?: string | null;
  status?: string;
  color?: string;
}

export interface MilestoneCreate {
  title: string;
  due_date?: string | null;
  order_index?: number;
}

export interface MilestoneUpdate {
  title?: string;
  due_date?: string | null;
  is_completed?: boolean;
  order_index?: number;
}

export const projectsApi = {
  list: async (params?: { student_id?: number; status?: string }) => {
    const response = await api.get('/api/projects/', { params });
    return response.data as ProjectItem[];
  },

  create: async (data: ProjectCreate) => {
    const response = await api.post('/api/projects/', data);
    return response.data as ProjectItem;
  },

  update: async (projectId: number, data: ProjectUpdate) => {
    const response = await api.patch(`/api/projects/${projectId}`, data);
    return response.data as ProjectItem;
  },

  archive: async (projectId: number) => {
    await api.delete(`/api/projects/${projectId}`);
  },

  addMilestone: async (projectId: number, data: MilestoneCreate) => {
    const response = await api.post(`/api/projects/${projectId}/milestones`, data);
    return response.data as MilestoneItem;
  },

  updateMilestone: async (projectId: number, milestoneId: number, data: MilestoneUpdate) => {
    const response = await api.patch(`/api/projects/${projectId}/milestones/${milestoneId}`, data);
    return response.data as MilestoneItem;
  },

  deleteMilestone: async (projectId: number, milestoneId: number) => {
    await api.delete(`/api/projects/${projectId}/milestones/${milestoneId}`);
  },
};
