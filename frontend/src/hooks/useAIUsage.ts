import { useQuery, useQueryClient } from '@tanstack/react-query';
import { aiUsageApi } from '../api/aiUsage';
import type { AIUsageResponse } from '../api/aiUsage';

const AI_USAGE_QUERY_KEY = ['ai-usage'] as const;

/**
 * Hook to fetch and cache AI usage data.
 * Auto-refetches on window focus and every 30 seconds.
 */
export function useAIUsage() {
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery<AIUsageResponse>({
    queryKey: AI_USAGE_QUERY_KEY,
    queryFn: aiUsageApi.getUsage,
    staleTime: 15_000,
    refetchInterval: 30_000,
    refetchOnWindowFocus: true,
    retry: 1,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: AI_USAGE_QUERY_KEY });
  };

  return {
    count: data?.count ?? 0,
    limit: data?.limit ?? 0,
    remaining: data?.remaining ?? 0,
    atLimit: data?.at_limit ?? false,
    warningThreshold: data?.warning_threshold ?? 0,
    period: data?.period ?? '',
    resetDate: data?.reset_date ?? '',
    isLoading,
    error,
    /** Call after AI generation to refresh usage data */
    invalidate,
  };
}
