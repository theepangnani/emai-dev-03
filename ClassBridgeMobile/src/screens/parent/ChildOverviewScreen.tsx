import React, { useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
} from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import { parentApi } from '../../api/parent';
import { tasksApi } from '../../api/tasks';
import { LoadingSpinner } from '../../components/LoadingSpinner';
import { EmptyState } from '../../components/EmptyState';
import { colors, spacing, fontSize, borderRadius } from '../../theme';
import type { TaskItem } from '../../api/tasks';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { HomeStackParamList } from '../../navigation/AppNavigator';

type Props = NativeStackScreenProps<HomeStackParamList, 'ChildOverview'>;

function formatDueDate(dateStr: string | null): string {
  if (!dateStr) return 'No due date';
  const date = new Date(dateStr);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);
  const dueDay = new Date(date.getFullYear(), date.getMonth(), date.getDate());

  if (dueDay < today) return 'Overdue';
  if (dueDay.getTime() === today.getTime()) return 'Due today';
  if (dueDay.getTime() === tomorrow.getTime()) return 'Due tomorrow';
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function getDueDateColor(dateStr: string | null): string {
  if (!dateStr) return colors.textMuted;
  const date = new Date(dateStr);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const dueDay = new Date(date.getFullYear(), date.getMonth(), date.getDate());

  if (dueDay < today) return colors.error;
  if (dueDay.getTime() === today.getTime()) return '#E65100';
  return colors.textSecondary;
}

export function ChildOverviewScreen({ route }: Props) {
  const { studentId } = route.params;
  const queryClient = useQueryClient();

  const {
    data: overview,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ['childOverview', studentId],
    queryFn: () => parentApi.getChildOverview(studentId),
  });

  const {
    data: tasks,
    refetch: refetchTasks,
  } = useQuery({
    queryKey: ['childTasks', studentId],
    queryFn: async () => {
      // Get child's user_id from overview, then fetch tasks
      if (!overview) return [];
      return tasksApi.list({ assigned_to_user_id: overview.user_id });
    },
    enabled: !!overview,
  });

  const toggleMutation = useMutation({
    mutationFn: ({ taskId, isCompleted }: { taskId: number; isCompleted: boolean }) =>
      tasksApi.toggleComplete(taskId, isCompleted),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['childTasks', studentId] });
      queryClient.invalidateQueries({ queryKey: ['parentDashboard'] });
    },
  });

  const [refreshing, setRefreshing] = React.useState(false);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await Promise.all([
      refetch(),
      refetchTasks(),
    ]);
    setRefreshing(false);
  }, [refetch, refetchTasks]);

  if (isLoading) {
    return <LoadingSpinner fullScreen message="Loading..." />;
  }

  if (isError || !overview) {
    return (
      <View style={styles.errorContainer}>
        <EmptyState
          icon="error-outline"
          title="Failed to load"
          subtitle="Pull down to try again"
        />
      </View>
    );
  }

  // Sort assignments by due date (overdue first, then soonest)
  const sortedAssignments = [...overview.assignments].sort((a, b) => {
    if (!a.due_date && !b.due_date) return 0;
    if (!a.due_date) return 1;
    if (!b.due_date) return -1;
    return new Date(a.due_date).getTime() - new Date(b.due_date).getTime();
  });

  const activeTasks = (tasks || []).filter(t => !t.archived_at);
  const pendingTasks = activeTasks.filter(t => !t.is_completed);
  const completedTasks = activeTasks.filter(t => t.is_completed);

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={onRefresh}
          colors={[colors.primary]}
          tintColor={colors.primary}
        />
      }
    >
      {/* Quick Stats */}
      <View style={styles.statsRow}>
        <View style={styles.statItem}>
          <MaterialIcons name="menu-book" size={20} color={colors.primary} />
          <Text style={styles.statValue}>{overview.courses.length}</Text>
          <Text style={styles.statLabel}>Courses</Text>
        </View>
        <View style={styles.statItem}>
          <MaterialIcons name="assignment" size={20} color={colors.secondary} />
          <Text style={styles.statValue}>{overview.assignments.length}</Text>
          <Text style={styles.statLabel}>Assignments</Text>
        </View>
        <View style={styles.statItem}>
          <MaterialIcons name="check-circle" size={20} color={colors.warning} />
          <Text style={styles.statValue}>{pendingTasks.length}</Text>
          <Text style={styles.statLabel}>Tasks</Text>
        </View>
      </View>

      {/* Courses Section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Courses</Text>
        {overview.courses.length === 0 ? (
          <View style={styles.emptyCard}>
            <Text style={styles.emptyText}>No courses yet</Text>
          </View>
        ) : (
          overview.courses.map(course => (
            <View key={course.id} style={styles.courseCard}>
              <View style={styles.courseInfo}>
                <Text style={styles.courseName}>{course.name}</Text>
                {course.subject && (
                  <Text style={styles.courseSubject}>{course.subject}</Text>
                )}
                {course.teacher_name && (
                  <Text style={styles.courseTeacher}>
                    {course.teacher_name}
                  </Text>
                )}
              </View>
              {course.google_classroom_id && (
                <MaterialIcons
                  name="cloud-done"
                  size={18}
                  color={colors.secondary}
                />
              )}
            </View>
          ))
        )}
      </View>

      {/* Assignments Section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Assignments</Text>
        {sortedAssignments.length === 0 ? (
          <View style={styles.emptyCard}>
            <Text style={styles.emptyText}>No assignments</Text>
          </View>
        ) : (
          sortedAssignments.map(assignment => (
            <View key={assignment.id} style={styles.assignmentCard}>
              <View style={styles.assignmentInfo}>
                <Text style={styles.assignmentTitle}>{assignment.title}</Text>
                {assignment.description && (
                  <Text style={styles.assignmentDesc} numberOfLines={2}>
                    {assignment.description}
                  </Text>
                )}
                <View style={styles.assignmentMeta}>
                  <Text
                    style={[
                      styles.dueDate,
                      { color: getDueDateColor(assignment.due_date) },
                    ]}
                  >
                    {formatDueDate(assignment.due_date)}
                  </Text>
                  {assignment.max_points != null && (
                    <Text style={styles.points}>
                      {assignment.max_points} pts
                    </Text>
                  )}
                </View>
              </View>
            </View>
          ))
        )}
      </View>

      {/* Tasks Section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>
          Tasks{' '}
          {activeTasks.length > 0 && (
            <Text style={styles.taskCount}>
              ({completedTasks.length}/{activeTasks.length} done)
            </Text>
          )}
        </Text>
        {activeTasks.length === 0 ? (
          <View style={styles.emptyCard}>
            <Text style={styles.emptyText}>No tasks</Text>
          </View>
        ) : (
          <>
            {pendingTasks.map(task => (
              <TaskRow
                key={task.id}
                task={task}
                onToggle={() =>
                  toggleMutation.mutate({
                    taskId: task.id,
                    isCompleted: true,
                  })
                }
              />
            ))}
            {completedTasks.length > 0 && pendingTasks.length > 0 && (
              <View style={styles.completedDivider}>
                <View style={styles.dividerLine} />
                <Text style={styles.dividerText}>Completed</Text>
                <View style={styles.dividerLine} />
              </View>
            )}
            {completedTasks.map(task => (
              <TaskRow
                key={task.id}
                task={task}
                onToggle={() =>
                  toggleMutation.mutate({
                    taskId: task.id,
                    isCompleted: false,
                  })
                }
              />
            ))}
          </>
        )}
      </View>
    </ScrollView>
  );
}

// --- Sub-components ---

function TaskRow({
  task,
  onToggle,
}: {
  task: TaskItem;
  onToggle: () => void;
}) {
  return (
    <TouchableOpacity
      style={styles.taskCard}
      onPress={onToggle}
      activeOpacity={0.7}
    >
      <MaterialIcons
        name={task.is_completed ? 'check-circle' : 'radio-button-unchecked'}
        size={24}
        color={task.is_completed ? colors.secondary : colors.textMuted}
      />
      <View style={styles.taskInfo}>
        <Text
          style={[
            styles.taskTitle,
            task.is_completed && styles.taskTitleCompleted,
          ]}
        >
          {task.title}
        </Text>
        {task.due_date && !task.is_completed && (
          <Text
            style={[
              styles.taskDue,
              { color: getDueDateColor(task.due_date) },
            ]}
          >
            {formatDueDate(task.due_date)}
          </Text>
        )}
      </View>
      {task.priority === 'high' && !task.is_completed && (
        <MaterialIcons name="priority-high" size={18} color={colors.error} />
      )}
    </TouchableOpacity>
  );
}

// --- Styles ---

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.lg,
    paddingBottom: spacing.xxxl,
  },
  errorContainer: {
    flex: 1,
    backgroundColor: colors.background,
    justifyContent: 'center',
  },

  // Stats row
  statsRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginBottom: spacing.xl,
  },
  statItem: {
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
    fontSize: fontSize.xl,
    fontWeight: 'bold',
    color: colors.text,
    marginTop: spacing.xs,
  },
  statLabel: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    marginTop: 2,
  },

  // Section
  section: {
    marginBottom: spacing.xl,
  },
  sectionTitle: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.md,
  },
  taskCount: {
    fontSize: fontSize.sm,
    fontWeight: '400',
    color: colors.textMuted,
  },

  // Empty card
  emptyCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    padding: spacing.xl,
    alignItems: 'center',
  },
  emptyText: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
  },

  // Course card
  courseCard: {
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
  courseInfo: {
    flex: 1,
  },
  courseName: {
    fontSize: fontSize.md,
    fontWeight: '600',
    color: colors.text,
  },
  courseSubject: {
    fontSize: fontSize.sm,
    color: colors.primary,
    marginTop: 2,
  },
  courseTeacher: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: 2,
  },

  // Assignment card
  assignmentCard: {
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
  assignmentInfo: {
    flex: 1,
  },
  assignmentTitle: {
    fontSize: fontSize.md,
    fontWeight: '500',
    color: colors.text,
  },
  assignmentDesc: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: 2,
  },
  assignmentMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    marginTop: spacing.xs,
  },
  dueDate: {
    fontSize: fontSize.sm,
    fontWeight: '500',
  },
  points: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    backgroundColor: colors.divider,
    borderRadius: borderRadius.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 1,
  },

  // Task card
  taskCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
    gap: spacing.md,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1,
  },
  taskInfo: {
    flex: 1,
  },
  taskTitle: {
    fontSize: fontSize.md,
    color: colors.text,
  },
  taskTitleCompleted: {
    textDecorationLine: 'line-through',
    color: colors.textMuted,
  },
  taskDue: {
    fontSize: fontSize.xs,
    marginTop: 2,
  },

  // Completed divider
  completedDivider: {
    flexDirection: 'row',
    alignItems: 'center',
    marginVertical: spacing.sm,
    gap: spacing.sm,
  },
  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: colors.divider,
  },
  dividerText: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
  },
});
