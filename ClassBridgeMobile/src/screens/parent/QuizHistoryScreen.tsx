import React, { useCallback, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
} from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { parentApi } from '../../api/parent';
import { quizResultsApi } from '../../api/quizResults';
import { LoadingSpinner } from '../../components/LoadingSpinner';
import { EmptyState } from '../../components/EmptyState';
import { colors, spacing, fontSize, borderRadius } from '../../theme';
import type { QuizResultSummary, QuizHistoryStats } from '../../api/quizResults';

export function QuizHistoryScreen() {
  const queryClient = useQueryClient();
  const [selectedChildId, setSelectedChildId] = useState<number | null>(null);

  const { data: dashboard } = useQuery({
    queryKey: ['parentDashboard'],
    queryFn: parentApi.getDashboard,
  });

  const children = dashboard?.child_highlights || [];
  const selectedChild = selectedChildId
    ? children.find((c) => c.student_id === selectedChildId)
    : null;

  const studentUserId = selectedChild?.user_id;

  const { data: results, isLoading: loadingResults } = useQuery({
    queryKey: ['quizResults', studentUserId],
    queryFn: () =>
      quizResultsApi.list(
        studentUserId ? { student_user_id: studentUserId, limit: 50 } : { limit: 50 }
      ),
  });

  const { data: stats } = useQuery({
    queryKey: ['quizStats', studentUserId],
    queryFn: () =>
      quizResultsApi.stats(
        studentUserId ? { student_user_id: studentUserId } : undefined
      ),
  });

  const [refreshing, setRefreshing] = useState(false);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['quizResults'] }),
      queryClient.invalidateQueries({ queryKey: ['quizStats'] }),
    ]);
    setRefreshing(false);
  }, [queryClient]);

  if (loadingResults) {
    return <LoadingSpinner fullScreen message="Loading quiz history..." />;
  }

  const trendIcon = (trend?: string): keyof typeof MaterialIcons.glyphMap => {
    if (trend === 'improving') return 'trending-up';
    if (trend === 'declining') return 'trending-down';
    return 'trending-flat';
  };

  const trendColor = (trend?: string): string => {
    if (trend === 'improving') return colors.secondary;
    if (trend === 'declining') return colors.error;
    return colors.textMuted;
  };

  return (
    <View style={styles.container}>
      {/* Child Filter */}
      {children.length > 1 && (
        <View style={styles.filterRow}>
          <TouchableOpacity
            style={[
              styles.filterChip,
              !selectedChildId && styles.filterChipActive,
            ]}
            onPress={() => setSelectedChildId(null)}
          >
            <Text
              style={[
                styles.filterChipText,
                !selectedChildId && styles.filterChipTextActive,
              ]}
            >
              All
            </Text>
          </TouchableOpacity>
          {children.map((child) => (
            <TouchableOpacity
              key={child.student_id}
              style={[
                styles.filterChip,
                selectedChildId === child.student_id && styles.filterChipActive,
              ]}
              onPress={() => setSelectedChildId(child.student_id)}
            >
              <Text
                style={[
                  styles.filterChipText,
                  selectedChildId === child.student_id &&
                    styles.filterChipTextActive,
                ]}
              >
                {child.full_name.split(' ')[0]}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      )}

      <FlatList
        data={results || []}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            colors={[colors.primary]}
            tintColor={colors.primary}
          />
        }
        ListHeaderComponent={
          stats ? (
            <View style={styles.statsRow}>
              <StatCard
                icon="school"
                value={stats.total_attempts}
                label="Attempts"
                color={colors.primary}
              />
              <StatCard
                icon="quiz"
                value={stats.unique_quizzes}
                label="Quizzes"
                color="#4285F4"
              />
              <StatCard
                icon="bar-chart"
                value={`${Math.round(stats.average_score)}%`}
                label="Average"
                color={colors.secondary}
              />
              <StatCard
                icon={trendIcon(stats.recent_trend)}
                value={`${Math.round(stats.best_score)}%`}
                label="Best"
                color={trendColor(stats.recent_trend)}
              />
            </View>
          ) : null
        }
        ListEmptyComponent={
          <EmptyState
            icon="quiz"
            title="No quiz results yet"
            subtitle="Quiz results will appear here after quizzes are taken"
          />
        }
        renderItem={({ item }) => <QuizResultRow result={item} />}
      />
    </View>
  );
}

function StatCard({
  icon,
  value,
  label,
  color,
}: {
  icon: keyof typeof MaterialIcons.glyphMap;
  value: number | string;
  label: string;
  color: string;
}) {
  return (
    <View style={styles.statCard}>
      <MaterialIcons name={icon} size={18} color={color} />
      <Text style={[styles.statValue, { color }]}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

function QuizResultRow({ result }: { result: QuizResultSummary }) {
  const percentage = Math.round(result.percentage);
  const scoreColor =
    percentage >= 80
      ? colors.secondary
      : percentage >= 60
      ? colors.warning
      : colors.error;

  return (
    <View style={styles.resultCard}>
      <View style={styles.resultInfo}>
        <Text style={styles.resultTitle} numberOfLines={1}>
          {result.quiz_title || `Quiz #${result.study_guide_id}`}
        </Text>
        <View style={styles.resultMeta}>
          <Text style={styles.resultDate}>
            {new Date(result.completed_at).toLocaleDateString(undefined, {
              month: 'short',
              day: 'numeric',
            })}
          </Text>
          <Text style={styles.resultAttempt}>
            Attempt #{result.attempt_number}
          </Text>
        </View>
      </View>

      <View style={styles.scoreContainer}>
        <Text style={[styles.scoreText, { color: scoreColor }]}>
          {percentage}%
        </Text>
        <Text style={styles.scoreDetail}>
          {result.score}/{result.total_questions}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  filterRow: {
    flexDirection: 'row',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    gap: spacing.sm,
  },
  filterChip: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.full,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  filterChipActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  filterChipText: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    fontWeight: '500',
  },
  filterChipTextActive: {
    color: '#FFFFFF',
  },
  listContent: {
    padding: spacing.lg,
    paddingTop: spacing.sm,
  },
  statsRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginBottom: spacing.lg,
  },
  statCard: {
    flex: 1,
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1,
  },
  statValue: {
    fontSize: fontSize.lg,
    fontWeight: 'bold',
    marginTop: spacing.xs,
  },
  statLabel: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    marginTop: 2,
  },
  resultCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    padding: spacing.lg,
    marginBottom: spacing.sm,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1,
  },
  resultInfo: {
    flex: 1,
  },
  resultTitle: {
    fontSize: fontSize.md,
    fontWeight: '500',
    color: colors.text,
    marginBottom: spacing.xs,
  },
  resultMeta: {
    flexDirection: 'row',
    gap: spacing.md,
  },
  resultDate: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
  },
  resultAttempt: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
  },
  scoreContainer: {
    alignItems: 'center',
    minWidth: 50,
  },
  scoreText: {
    fontSize: fontSize.lg,
    fontWeight: 'bold',
  },
  scoreDetail: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    marginTop: 2,
  },
});
