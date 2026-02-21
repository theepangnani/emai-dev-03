import React, { useCallback, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  Modal,
  TextInput,
  Alert,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
} from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { tasksApi } from '../../api/tasks';
import { LoadingSpinner } from '../../components/LoadingSpinner';
import { EmptyState } from '../../components/EmptyState';
import { colors, spacing, fontSize, borderRadius } from '../../theme';
import type { TaskItem, AssignableUser, CreateTaskData } from '../../api/tasks';

type StatusFilter = 'all' | 'pending' | 'completed';
type PriorityFilter = 'all' | 'high' | 'medium' | 'low';

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

const PRIORITY_COLORS: Record<string, string> = {
  high: colors.error,
  medium: colors.warning,
  low: colors.primary,
};

export function TasksScreen() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [priorityFilter, setPriorityFilter] = useState<PriorityFilter>('all');
  const [showCreate, setShowCreate] = useState(false);

  const { data: tasks, isLoading } = useQuery({
    queryKey: ['parentTasks'],
    queryFn: () => tasksApi.list(),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ taskId, isCompleted }: { taskId: number; isCompleted: boolean }) =>
      tasksApi.toggleComplete(taskId, isCompleted),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['parentTasks'] });
      queryClient.invalidateQueries({ queryKey: ['parentDashboard'] });
    },
  });

  const [refreshing, setRefreshing] = useState(false);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await queryClient.invalidateQueries({ queryKey: ['parentTasks'] });
    setRefreshing(false);
  }, [queryClient]);

  if (isLoading) {
    return <LoadingSpinner fullScreen message="Loading tasks..." />;
  }

  const activeTasks = (tasks || []).filter((t) => !t.archived_at);

  const filteredTasks = activeTasks.filter((task) => {
    if (statusFilter === 'pending' && task.is_completed) return false;
    if (statusFilter === 'completed' && !task.is_completed) return false;
    if (priorityFilter !== 'all' && task.priority !== priorityFilter) return false;
    return true;
  });

  // Sort: pending first, then by due date
  const sortedTasks = [...filteredTasks].sort((a, b) => {
    if (a.is_completed !== b.is_completed) return a.is_completed ? 1 : -1;
    if (!a.due_date && !b.due_date) return 0;
    if (!a.due_date) return 1;
    if (!b.due_date) return -1;
    return new Date(a.due_date).getTime() - new Date(b.due_date).getTime();
  });

  return (
    <View style={styles.container}>
      {/* Filter Row */}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.filterScroll}
        contentContainerStyle={styles.filterRow}
      >
        {(['all', 'pending', 'completed'] as StatusFilter[]).map((status) => (
          <TouchableOpacity
            key={status}
            style={[
              styles.filterChip,
              statusFilter === status && styles.filterChipActive,
            ]}
            onPress={() => setStatusFilter(status)}
          >
            <Text
              style={[
                styles.filterChipText,
                statusFilter === status && styles.filterChipTextActive,
              ]}
            >
              {status.charAt(0).toUpperCase() + status.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}

        <View style={styles.filterDivider} />

        {(['all', 'high', 'medium', 'low'] as PriorityFilter[]).map((priority) => (
          <TouchableOpacity
            key={priority}
            style={[
              styles.filterChip,
              priorityFilter === priority && styles.filterChipActive,
            ]}
            onPress={() => setPriorityFilter(priority)}
          >
            <Text
              style={[
                styles.filterChipText,
                priorityFilter === priority && styles.filterChipTextActive,
              ]}
            >
              {priority === 'all'
                ? 'Any Priority'
                : priority.charAt(0).toUpperCase() + priority.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {/* Task count */}
      <View style={styles.countRow}>
        <Text style={styles.countText}>
          {sortedTasks.length} task{sortedTasks.length !== 1 ? 's' : ''}
        </Text>
      </View>

      {/* Task List */}
      <FlatList
        data={sortedTasks}
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
        ListEmptyComponent={
          <EmptyState
            icon="check-circle"
            title="No tasks"
            subtitle="Tap + to create a new task"
          />
        }
        renderItem={({ item }) => (
          <TaskRow
            task={item}
            onToggle={() =>
              toggleMutation.mutate({
                taskId: item.id,
                isCompleted: !item.is_completed,
              })
            }
          />
        )}
      />

      {/* FAB */}
      <TouchableOpacity
        style={styles.fab}
        onPress={() => setShowCreate(true)}
        activeOpacity={0.8}
      >
        <MaterialIcons name="add" size={28} color="#FFFFFF" />
      </TouchableOpacity>

      {/* Create Task Modal */}
      <CreateTaskModal
        visible={showCreate}
        onClose={() => setShowCreate(false)}
      />
    </View>
  );
}

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
          numberOfLines={1}
        >
          {task.title}
        </Text>
        <View style={styles.taskMeta}>
          {task.due_date && !task.is_completed && (
            <Text
              style={[styles.taskDue, { color: getDueDateColor(task.due_date) }]}
            >
              {formatDueDate(task.due_date)}
            </Text>
          )}
          {task.assignee_name && (
            <Text style={styles.taskAssignee} numberOfLines={1}>
              {task.assignee_name}
            </Text>
          )}
        </View>
      </View>
      {task.priority && !task.is_completed && (
        <View
          style={[
            styles.priorityDot,
            { backgroundColor: PRIORITY_COLORS[task.priority] || colors.textMuted },
          ]}
        />
      )}
    </TouchableOpacity>
  );
}

function CreateTaskModal({
  visible,
  onClose,
}: {
  visible: boolean;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState<string>('medium');
  const [assigneeId, setAssigneeId] = useState<number | undefined>();

  const { data: assignableUsers } = useQuery({
    queryKey: ['assignableUsers'],
    queryFn: tasksApi.getAssignableUsers,
    enabled: visible,
  });

  const createMutation = useMutation({
    mutationFn: (data: CreateTaskData) => tasksApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['parentTasks'] });
      queryClient.invalidateQueries({ queryKey: ['parentDashboard'] });
      setTitle('');
      setDescription('');
      setPriority('medium');
      setAssigneeId(undefined);
      onClose();
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.detail || 'Failed to create task.';
      Alert.alert('Error', msg);
    },
  });

  const handleCreate = () => {
    if (!title.trim()) {
      Alert.alert('Required', 'Please enter a task title.');
      return;
    }
    createMutation.mutate({
      title: title.trim(),
      description: description.trim() || undefined,
      priority,
      assigned_to_user_id: assigneeId,
    });
  };

  return (
    <Modal visible={visible} animationType="slide" transparent>
      <KeyboardAvoidingView
        style={styles.modalOverlay}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <View style={styles.modalContent}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>New Task</Text>
            <TouchableOpacity onPress={onClose}>
              <MaterialIcons name="close" size={24} color={colors.textMuted} />
            </TouchableOpacity>
          </View>

          <ScrollView keyboardShouldPersistTaps="handled">
            <Text style={styles.inputLabel}>Title</Text>
            <TextInput
              style={styles.input}
              placeholder="Task title"
              placeholderTextColor={colors.textMuted}
              value={title}
              onChangeText={setTitle}
              autoFocus
            />

            <Text style={styles.inputLabel}>Description (optional)</Text>
            <TextInput
              style={[styles.input, styles.inputMultiline]}
              placeholder="Add details..."
              placeholderTextColor={colors.textMuted}
              value={description}
              onChangeText={setDescription}
              multiline
              numberOfLines={3}
            />

            <Text style={styles.inputLabel}>Priority</Text>
            <View style={styles.priorityRow}>
              {['low', 'medium', 'high'].map((p) => (
                <TouchableOpacity
                  key={p}
                  style={[
                    styles.priorityOption,
                    priority === p && {
                      backgroundColor: PRIORITY_COLORS[p] + '20',
                      borderColor: PRIORITY_COLORS[p],
                    },
                  ]}
                  onPress={() => setPriority(p)}
                >
                  <Text
                    style={[
                      styles.priorityOptionText,
                      priority === p && { color: PRIORITY_COLORS[p] },
                    ]}
                  >
                    {p.charAt(0).toUpperCase() + p.slice(1)}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            {assignableUsers && assignableUsers.length > 0 && (
              <>
                <Text style={styles.inputLabel}>Assign To</Text>
                <ScrollView
                  horizontal
                  showsHorizontalScrollIndicator={false}
                  style={styles.assigneeScroll}
                >
                  <TouchableOpacity
                    style={[
                      styles.assigneeChip,
                      !assigneeId && styles.assigneeChipActive,
                    ]}
                    onPress={() => setAssigneeId(undefined)}
                  >
                    <Text
                      style={[
                        styles.assigneeChipText,
                        !assigneeId && styles.assigneeChipTextActive,
                      ]}
                    >
                      Myself
                    </Text>
                  </TouchableOpacity>
                  {assignableUsers.map((user) => (
                    <TouchableOpacity
                      key={user.user_id}
                      style={[
                        styles.assigneeChip,
                        assigneeId === user.user_id && styles.assigneeChipActive,
                      ]}
                      onPress={() => setAssigneeId(user.user_id)}
                    >
                      <Text
                        style={[
                          styles.assigneeChipText,
                          assigneeId === user.user_id &&
                            styles.assigneeChipTextActive,
                        ]}
                      >
                        {user.name}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </ScrollView>
              </>
            )}

            <TouchableOpacity
              style={[
                styles.createButton,
                createMutation.isPending && styles.createButtonDisabled,
              ]}
              onPress={handleCreate}
              disabled={createMutation.isPending}
              activeOpacity={0.7}
            >
              <MaterialIcons name="add" size={20} color="#FFFFFF" />
              <Text style={styles.createButtonText}>
                {createMutation.isPending ? 'Creating...' : 'Create Task'}
              </Text>
            </TouchableOpacity>
          </ScrollView>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  filterScroll: {
    maxHeight: 48,
  },
  filterRow: {
    flexDirection: 'row',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    gap: spacing.sm,
    alignItems: 'center',
  },
  filterChip: {
    paddingHorizontal: spacing.md,
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
  filterDivider: {
    width: 1,
    height: 20,
    backgroundColor: colors.border,
  },
  countRow: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.xs,
  },
  countText: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
  },
  listContent: {
    padding: spacing.lg,
    paddingTop: spacing.xs,
    paddingBottom: 80,
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
  taskMeta: {
    flexDirection: 'row',
    gap: spacing.md,
    marginTop: 2,
  },
  taskDue: {
    fontSize: fontSize.xs,
  },
  taskAssignee: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
  },
  priorityDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },

  // FAB
  fab: {
    position: 'absolute',
    right: spacing.xl,
    bottom: spacing.xl,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.2,
    shadowRadius: 5,
    elevation: 5,
  },

  // Modal
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.4)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: borderRadius.xl,
    borderTopRightRadius: borderRadius.xl,
    padding: spacing.xl,
    maxHeight: '80%',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.xl,
  },
  modalTitle: {
    fontSize: fontSize.xl,
    fontWeight: 'bold',
    color: colors.text,
  },
  inputLabel: {
    fontSize: fontSize.sm,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.sm,
  },
  input: {
    backgroundColor: colors.background,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    fontSize: fontSize.md,
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing.lg,
  },
  inputMultiline: {
    minHeight: 80,
    textAlignVertical: 'top',
  },
  priorityRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginBottom: spacing.lg,
  },
  priorityOption: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: spacing.md,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.background,
  },
  priorityOptionText: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    fontWeight: '500',
  },
  assigneeScroll: {
    marginBottom: spacing.lg,
  },
  assigneeChip: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.full,
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
    marginRight: spacing.sm,
  },
  assigneeChipActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  assigneeChipText: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    fontWeight: '500',
  },
  assigneeChipTextActive: {
    color: '#FFFFFF',
  },
  createButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    backgroundColor: colors.primary,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.lg,
    marginTop: spacing.sm,
  },
  createButtonDisabled: {
    opacity: 0.6,
  },
  createButtonText: {
    color: '#FFFFFF',
    fontSize: fontSize.md,
    fontWeight: '600',
  },
});
