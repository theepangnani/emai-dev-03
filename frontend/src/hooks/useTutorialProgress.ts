import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { tutorialsApi } from '../api/tutorials';

export function useTutorialProgress() {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ['tutorial-progress'],
    queryFn: tutorialsApi.getProgress,
    staleTime: 5 * 60 * 1000,
  });

  const completeMutation = useMutation({
    mutationFn: (step: string) => tutorialsApi.completeStep(step),
    onSuccess: (result) => {
      queryClient.setQueryData(['tutorial-progress'], result);
    },
  });

  const resetMutation = useMutation({
    mutationFn: () => tutorialsApi.reset(),
    onSuccess: (result) => {
      queryClient.setQueryData(['tutorial-progress'], result);
    },
  });

  const completed = data?.completed ?? {};

  const isStepCompleted = (step: string) => !!completed[step];

  const hasAnyCompleted = Object.values(completed).some(Boolean);

  const completeStep = (step: string) => completeMutation.mutateAsync(step);

  const resetAll = () => resetMutation.mutateAsync();

  return {
    completed,
    isLoading,
    isStepCompleted,
    hasAnyCompleted,
    completeStep,
    resetAll,
  };
}
