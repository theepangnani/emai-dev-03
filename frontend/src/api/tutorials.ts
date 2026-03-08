import { api } from './client';

export interface TutorialProgress {
  completed: Record<string, boolean>;
}

export const tutorialsApi = {
  getProgress: () => api.get<TutorialProgress>('/api/tutorials/progress').then(r => r.data),
  completeStep: (step: string) => api.post<TutorialProgress>('/api/tutorials/complete', { step }).then(r => r.data),
  reset: () => api.post<TutorialProgress>('/api/tutorials/reset').then(r => r.data),
};
