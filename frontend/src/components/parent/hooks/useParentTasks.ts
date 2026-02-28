import { useState } from 'react';
import { tasksApi } from '../../../api/client';
import type { TaskItem } from '../../../api/client';
import { dateKey } from '../../calendar/types';

interface UseParentTasksParams {
  allTasks: TaskItem[];
  setAllTasks: React.Dispatch<React.SetStateAction<TaskItem[]>>;
  selectedChild: number | null;
  children: { student_id: number; user_id: number }[];
  confirm: (options: { title: string; message: string; confirmLabel: string }) => Promise<boolean>;
}

export function useParentTasks({
  allTasks,
  setAllTasks,
  selectedChild,
  children,
  confirm,
}: UseParentTasksParams) {
  // Day detail modal state
  const [dayModalDate, setDayModalDate] = useState<Date | null>(null);
  const [dayTasks, setDayTasks] = useState<TaskItem[]>([]);
  const [newTaskTitle, setNewTaskTitle] = useState('');
  const [newTaskCreating, setNewTaskCreating] = useState(false);
  const [expandedTaskId, setExpandedTaskId] = useState<number | null>(null);

  // Create task modal state (from quick actions)
  const [showCreateTaskModal, setShowCreateTaskModal] = useState(false);

  // Task detail modal state
  const [taskDetailModal, setTaskDetailModal] = useState<TaskItem | null>(null);

  const openDayModal = (date: Date) => {
    setDayModalDate(date);
    setNewTaskTitle('');
    const dk = dateKey(date);
    const filtered = allTasks.filter(t => {
      if (!t.due_date) return false;
      return dateKey(new Date(t.due_date)) === dk;
    });
    setDayTasks(filtered);
  };

  const closeDayModal = () => {
    setDayModalDate(null);
    setDayTasks([]);
    setNewTaskTitle('');
  };

  const handleCreateDayTask = async () => {
    if (!newTaskTitle.trim() || !dayModalDate) return;
    setNewTaskCreating(true);
    try {
      const childUserId = selectedChild
        ? children.find(c => c.student_id === selectedChild)?.user_id
        : undefined;
      const task = await tasksApi.create({
        title: newTaskTitle.trim(),
        due_date: dayModalDate.toISOString(),
        assigned_to_user_id: childUserId,
      });
      setDayTasks(prev => [...prev, task]);
      setAllTasks(prev => [...prev, task]);
      setNewTaskTitle('');
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to create task');
    } finally {
      setNewTaskCreating(false);
    }
  };

  const handleToggleTask = async (task: TaskItem) => {
    try {
      const updated = await tasksApi.update(task.id, { is_completed: !task.is_completed });
      setDayTasks(prev => prev.map(t => t.id === task.id ? updated : t));
      setAllTasks(prev => prev.map(t => t.id === task.id ? updated : t));
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to update task');
    }
  };

  const handleDeleteTask = async (taskId: number) => {
    const ok = await confirm({ title: 'Archive Task', message: 'Archive this task? You can restore it later.', confirmLabel: 'Archive' });
    if (!ok) return;
    try {
      await tasksApi.delete(taskId);
      setDayTasks(prev => prev.filter(t => t.id !== taskId));
      setAllTasks(prev => prev.filter(t => t.id !== taskId));
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to delete task');
    }
  };

  const handleTaskDrop = async (calendarId: number, newDate: Date) => {
    const taskId = calendarId - 1_000_000;
    const task = allTasks.find(t => t.id === taskId);
    if (!task) return;

    const prevTasks = allTasks;
    const newDueDate = newDate.toISOString();

    setAllTasks(prev => prev.map(t => t.id === taskId ? { ...t, due_date: newDueDate } : t));

    try {
      const updated = await tasksApi.update(taskId, { due_date: newDueDate });
      setAllTasks(prev => prev.map(t => t.id === taskId ? updated : t));
    } catch {
      setAllTasks(prevTasks);
      alert('Failed to reschedule task. You may not have permission to edit this task.');
    }
  };

  return {
    // Day Detail Modal
    dayModalDate, dayTasks, newTaskTitle, setNewTaskTitle,
    newTaskCreating, expandedTaskId, setExpandedTaskId,
    openDayModal, closeDayModal, handleCreateDayTask,
    handleToggleTask, handleDeleteTask, handleTaskDrop,

    // Task Detail Modal
    taskDetailModal, setTaskDetailModal,

    // Create Task Modal
    showCreateTaskModal, setShowCreateTaskModal,
  };
}
