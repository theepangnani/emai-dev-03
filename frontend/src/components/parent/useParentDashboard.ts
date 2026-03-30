import { useState, useEffect, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { parentApi, invitesApi } from '../../api/client';
import { courseContentsApi } from '../../api/courses';
import type { ChildSummary, ChildOverview, ParentDashboardData, TaskItem, InviteResponse } from '../../api/client';

import type { CalendarAssignment } from '../calendar/types';
import { getCourseColor, TASK_PRIORITY_COLORS } from '../calendar/types';
import { useConfirm } from '../ConfirmModal';
import type { CourseMaterial } from './StudentDetailPanel';

import { useChildManagement } from './hooks/useChildManagement';
import { useChildEditor } from './hooks/useChildEditor';
import { useParentTasks } from './hooks/useParentTasks';
import { useParentStudyTools } from './hooks/useParentStudyTools';
import { useParentInvites } from './hooks/useParentInvites';

export type { LinkTab, DiscoveryState } from './hooks/useChildManagement';

export const CHILD_COLORS = [
  '#8b5cf6', '#ec4899', '#14b8a6', '#f59e0b',
  '#3b82f6', '#ef4444', '#10b981', '#6366f1',
];

export function useParentDashboard() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { confirm, confirmModal } = useConfirm();

  // ============================================
  // Core shared state
  // ============================================
  const [children, setChildren] = useState<ChildSummary[]>([]);
  const [selectedChild, setSelectedChild] = useState<number | null>(null);
  const [childOverview, setChildOverview] = useState<ChildOverview | null>(null);
  const [allOverviews, setAllOverviews] = useState<ChildOverview[]>([]);
  const [loading, setLoading] = useState(true);
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [dashboardError, setDashboardError] = useState(false);
  const [dashboardData, setDashboardData] = useState<ParentDashboardData | null>(null);
  const [wizardChildId, setWizardChildId] = useState<number | null>(null);
  const [googleConnected, setGoogleConnected] = useState(false);
  const [allTasks, setAllTasks] = useState<TaskItem[]>([]);
  const [pendingInvites, setPendingInvites] = useState<InviteResponse[]>([]);

  // Collapsible calendar with first-visit onboarding
  const calendarVisitedKey = 'calendar-visited';
  const [calendarCollapsed, setCalendarCollapsed] = useState(() => {
    try {
      if (!localStorage.getItem(calendarVisitedKey)) return false;
      const saved = localStorage.getItem('calendar_collapsed');
      return saved !== '0';
    } catch { return false; }
  });
  const [showCalendarTooltip, setShowCalendarTooltip] = useState(() => {
    try { return !localStorage.getItem(calendarVisitedKey); } catch { return false; }
  });
  const dismissCalendarTooltip = () => {
    setShowCalendarTooltip(false);
    try { localStorage.setItem(calendarVisitedKey, '1'); } catch { /* ignore */ }
  };
  const toggleCalendar = () => {
    setCalendarCollapsed(prev => {
      const next = !prev;
      try {
        localStorage.setItem('calendar_collapsed', next ? '1' : '0');
        localStorage.setItem(calendarVisitedKey, '1');
      } catch { /* ignore */ }
      return next;
    });
    setShowCalendarTooltip(false);
  };

  // Student detail panel collapse state
  const [detailPanelCollapsed, setDetailPanelCollapsed] = useState(false);

  // Today's Focus dismiss state
  const [focusCollapsed, setFocusCollapsed] = useState(false);

  // Class materials for StudentDetailPanel
  const [courseMaterials, setCourseMaterials] = useState<CourseMaterial[]>([]);

  // ============================================
  // Data Loading
  // ============================================

  const loadDashboard = async () => {
    let childEmails: Set<string> = new Set();
    try {
      const data = await parentApi.getDashboard();
      setDashboardData(data);
      setChildren(data.children);
      setGoogleConnected(data.google_connected);
      setAllTasks(data.all_tasks as unknown as TaskItem[]);
      if (data.children.length === 1) {
        setSelectedChild(data.children[0].student_id);
      } else {
        // Restore persisted child selection from sessionStorage
        const storedUserId = sessionStorage.getItem('selectedChildId');
        const storedMatch = storedUserId ? data.children.find(c => c.user_id === Number(storedUserId)) : null;
        setSelectedChild(storedMatch ? storedMatch.student_id : null);
      }
      childEmails = new Set(data.children.map(c => c.email?.toLowerCase()).filter(Boolean) as string[]);
    } catch {
      setDashboardError(true);
    } finally {
      setLoading(false);
      setOverviewLoading(false);
    }
    try {
      const invites = await invitesApi.listSent();
      setPendingInvites(invites.filter(i => !i.accepted_at && new Date(i.expires_at) > new Date() && !childEmails.has(i.email.toLowerCase())));
    } catch { /* ignore */ }
  };

  // ============================================
  // Sub-hooks
  // ============================================

  const childMgmt = useChildManagement({
    children,
    googleConnected,
    setGoogleConnected,
    loadDashboard,
  });

  const childEditor = useChildEditor({
    loadDashboard,
  });

  const selectedChildUserId = useMemo(() => {
    if (!selectedChild) return null;
    return children.find(c => c.student_id === selectedChild)?.user_id ?? null;
  }, [selectedChild, children]);

  const tasks = useParentTasks({
    allTasks,
    setAllTasks,
    selectedChild,
    children,
    confirm,
  });

  const studyTools = useParentStudyTools({
    selectedChildUserId,
    navigate,
  });

  const invites = useParentInvites({
    pendingInvites,
    setPendingInvites,
  });

  // ============================================
  // Startup effects
  // ============================================

  useEffect(() => {
    const connected = searchParams.get('google_connected');
    const pendingAction = localStorage.getItem('pendingAction');

    if (connected === 'true' && pendingAction === 'discover_children') {
      localStorage.removeItem('pendingAction');
      setSearchParams({});
      childMgmt.setShowLinkModal(true);
      childMgmt.setLinkTab('google');
      setGoogleConnected(true);
      setTimeout(() => childMgmt.triggerDiscovery(), 100);
    } else if (connected === 'true') {
      setSearchParams({});
      setGoogleConnected(true);
    }

    loadDashboard();
  }, []);

  useEffect(() => {
    if (selectedChild) {
      loadChildOverview(selectedChild);
    } else if (children.length > 0 && dashboardData) {
      const overviews = dashboardData.child_highlights.map(h => ({
        student_id: h.student_id,
        user_id: h.user_id,
        full_name: h.full_name,
        grade_level: h.grade_level,
        google_connected: false,
        courses: h.courses,
        assignments: dashboardData.all_assignments.filter(a =>
          h.courses.some(c => c.id === a.course_id)
        ),
        study_guides_count: 0,
      }));
      setAllOverviews(overviews);
    }
  }, [selectedChild, children, dashboardData]);

  const loadChildOverview = async (studentId: number) => {
    setOverviewLoading(true);
    try {
      const data = await parentApi.getChildOverview(studentId);
      setChildOverview(data);
    } catch {
      setChildOverview(null);
    } finally {
      setOverviewLoading(false);
    }
  };

  // ============================================
  // Child tab click handler (wraps childMgmt)
  // ============================================

  const handleChildTabClick = (studentId: number) => {
    const isDeselecting = selectedChild === studentId;
    childMgmt.handleChildTabClick(studentId, selectedChild, setSelectedChild, setChildOverview);
    // Auto-expand detail panel when selecting a child, collapse when deselecting (#740)
    if (isDeselecting) {
      setDetailPanelCollapsed(true);
    } else {
      setDetailPanelCollapsed(false);
    }
  };

  // Non-toggling child selection for wizard (#1923, #1994)
  const selectChildForWizard = (studentId: number) => {
    setWizardChildId(studentId);
  };

  const resetWizardChild = () => {
    setWizardChildId(null);
  };

  // Explicit "All" tab click (#830)
  const handleAllChildrenClick = () => {
    setSelectedChild(null);
    setChildOverview(null);
    sessionStorage.removeItem('selectedChildId');
    setDetailPanelCollapsed(true);
  };

  // ============================================
  // Course materials loading
  // ============================================

  useEffect(() => {
    if (loading) return;
    let ignore = false;
    const params: { student_user_id?: number } = {};
    if (selectedChildUserId) params.student_user_id = selectedChildUserId;
    courseContentsApi.listAll(params)
      .then(items => {
        if (ignore) return;
        setCourseMaterials(
          items
            .filter(item => !item.archived_at)
            .map(item => ({
              id: item.id,
              title: item.title,
              content_type: item.content_type,
              course_name: item.course_name,
              created_at: item.created_at,
            }))
        );
      })
      .catch(() => {});
    return () => { ignore = true; };
  }, [loading, selectedChildUserId]);

  // ============================================
  // Derived data computations
  // ============================================

  const filteredTasks = useMemo(() => {
    if (!selectedChildUserId) return allTasks;
    return allTasks.filter(t =>
      t.assigned_to_user_id === selectedChildUserId ||
      t.created_by_user_id === selectedChildUserId
    );
  }, [allTasks, selectedChildUserId]);

  const taskCounts = useMemo(() => {
    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const todayEnd = new Date(todayStart);
    todayEnd.setDate(todayEnd.getDate() + 1);
    const threeDaysEnd = new Date(todayStart);
    threeDaysEnd.setDate(threeDaysEnd.getDate() + 4);

    let overdue = 0;
    let dueToday = 0;
    let upcoming = 0;

    for (const t of filteredTasks) {
      if (t.is_completed || t.archived_at || !t.due_date) continue;
      // Parse date strings as local time — handle both "2026-03-07" and "2026-03-07 00:00:00+00:00"
      const dateStr = t.due_date.length === 10 ? t.due_date + 'T00:00:00' : t.due_date;
      const due = new Date(dateStr);
      if (due < todayStart) overdue++;
      else if (due >= todayStart && due < todayEnd) dueToday++;
      else if (due >= todayEnd && due < threeDaysEnd) upcoming++;
    }
    return { overdue, dueToday, upcoming };
  }, [filteredTasks]);

  const activeOverviews = useMemo(() => {
    if (selectedChild && childOverview) return [childOverview];
    if (!selectedChild && allOverviews.length > 0) return allOverviews;
    return [];
  }, [selectedChild, childOverview, allOverviews]);

  const courseIds = useMemo(() => {
    return activeOverviews.flatMap(o => o.courses.map(c => c.id));
  }, [activeOverviews]);

  const calendarAssignments: CalendarAssignment[] = useMemo(() => {
    const assignments = activeOverviews.flatMap(overview =>
      overview.assignments
        .filter(a => a.due_date)
        .map(a => ({
          id: a.id,
          title: a.title,
          description: a.description,
          courseId: a.course_id,
          courseName: overview.courses.find(c => c.id === a.course_id)?.name || 'Unknown',
          courseColor: getCourseColor(a.course_id, courseIds),
          dueDate: new Date(a.due_date!),
          childName: children.length > 1 ? overview.full_name : '',
          maxPoints: a.max_points,
          itemType: 'assignment' as const,
        }))
    );

    const taskItems: CalendarAssignment[] = filteredTasks
      .filter(t => t.due_date)
      .map(t => ({
        id: t.id + 1_000_000,
        taskId: t.id,
        title: t.title,
        description: t.description,
        courseId: 0,
        courseName: '',
        courseColor: TASK_PRIORITY_COLORS[t.priority || 'medium'],
        dueDate: new Date(t.due_date!),
        childName: t.assignee_name || '',
        maxPoints: null,
        itemType: 'task' as const,
        priority: (t.priority || 'medium') as 'low' | 'medium' | 'high',
        isCompleted: t.is_completed,
      }));

    return [...assignments, ...taskItems];
  }, [activeOverviews, courseIds, children.length, filteredTasks]);

  const undatedAssignments: CalendarAssignment[] = useMemo(() => {
    return activeOverviews.flatMap(overview =>
      overview.assignments
        .filter(a => !a.due_date)
        .map(a => ({
          id: a.id,
          title: a.title,
          description: a.description,
          courseId: a.course_id,
          courseName: overview.courses.find(c => c.id === a.course_id)?.name || 'Unknown',
          courseColor: getCourseColor(a.course_id, courseIds),
          dueDate: new Date(),
          childName: children.length > 1 ? overview.full_name : '',
          maxPoints: a.max_points,
        }))
    );
  }, [activeOverviews, courseIds, children.length]);

  // Compute child courses for the upload wizard (uses wizardChildId, not selectedChild)
  const childCoursesForWizard = useMemo(() => {
    if (!wizardChildId) return undefined;
    const overview = allOverviews.find(o => o.student_id === wizardChildId);
    if (!overview) return undefined;
    return overview.courses.map(c => ({ id: c.id, name: c.name }));
  }, [wizardChildId, allOverviews]);

  const handleGoToCourse = (courseId: number) => {
    navigate(`/courses?highlight=${courseId}`);
  };

  // ============================================
  // Today's Focus computed values
  // ============================================

  const selectedChildFirstName = useMemo(() => {
    if (!selectedChild) return null;
    const name = children.find(c => c.student_id === selectedChild)?.full_name;
    return name?.split(' ')[0] ?? null;
  }, [selectedChild, children]);

  const wizardChildFirstName = useMemo(() => {
    if (!wizardChildId) return null;
    const name = children.find(c => c.student_id === wizardChildId)?.full_name;
    return name?.split(' ')[0] ?? null;
  }, [wizardChildId, children]);

  const perChildOverdue = useMemo(() => {
    if (selectedChild || children.length <= 1) return [];
    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    return children.map(child => {
      const childUserId = child.user_id;
      const childTasks = allTasks.filter(t =>
        t.assigned_to_user_id === childUserId || t.created_by_user_id === childUserId
      );
      let overdue = 0;
      for (const t of childTasks) {
        if (t.is_completed || t.archived_at || !t.due_date) continue;
        if (new Date(t.due_date) < todayStart) overdue++;
      }
      return { name: child.full_name.split(' ')[0], overdue };
    }).filter(c => c.overdue > 0);
  }, [selectedChild, children, allTasks]);

  // Per-child overdue counts for pill badges (always available)
  const childOverdueCounts = useMemo(() => {
    const map = new Map<number, number>();
    if (children.length === 0) return map;
    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    for (const child of children) {
      let overdue = 0;
      for (const t of allTasks) {
        if (t.assigned_to_user_id !== child.user_id && t.created_by_user_id !== child.user_id) continue;
        if (t.is_completed || t.archived_at || !t.due_date) continue;
        if (new Date(t.due_date) < todayStart) overdue++;
      }
      if (overdue > 0) map.set(child.student_id, overdue);
    }
    return map;
  }, [children, allTasks]);

  // ============================================
  // Return the EXACT same API surface
  // ============================================

  return {
    // Core
    loading, dashboardError, children, navigate, confirmModal,

    // Child selection
    selectedChild, handleChildTabClick, handleAllChildrenClick, selectChildForWizard, selectedChildUserId, selectedChildFirstName, wizardChildId, wizardChildFirstName, resetWizardChild,

    // Overview
    overviewLoading,

    // Dashboard data
    childCoursesForWizard, filteredTasks, taskCounts, courseMaterials, pendingInvites: invites.pendingInvites, resendingId: invites.resendingId, handleResendInvite: invites.handleResendInvite,

    // Calendar
    calendarCollapsed, toggleCalendar, showCalendarTooltip, dismissCalendarTooltip,
    calendarAssignments, undatedAssignments,
    handleGoToCourse, handleViewStudyGuides: studyTools.handleViewStudyGuides, handleTaskDrop: tasks.handleTaskDrop,

    // Today's Focus
    focusCollapsed, setFocusCollapsed, perChildOverdue, childOverdueCounts,

    // Detail panel
    detailPanelCollapsed, setDetailPanelCollapsed,

    // Link Child Modal
    showLinkModal: childMgmt.showLinkModal, setShowLinkModal: childMgmt.setShowLinkModal, linkTab: childMgmt.linkTab, setLinkTab: childMgmt.setLinkTab,
    linkEmail: childMgmt.linkEmail, setLinkEmail: childMgmt.setLinkEmail, linkName: childMgmt.linkName, setLinkName: childMgmt.setLinkName,
    linkRelationship: childMgmt.linkRelationship, setLinkRelationship: childMgmt.setLinkRelationship, linkError: childMgmt.linkError, setLinkError: childMgmt.setLinkError,
    linkLoading: childMgmt.linkLoading, linkInviteLink: childMgmt.linkInviteLink,
    createChildName: childMgmt.createChildName, setCreateChildName: childMgmt.setCreateChildName, createChildEmail: childMgmt.createChildEmail, setCreateChildEmail: childMgmt.setCreateChildEmail,
    createChildRelationship: childMgmt.createChildRelationship, setCreateChildRelationship: childMgmt.setCreateChildRelationship, createChildLoading: childMgmt.createChildLoading,
    createChildError: childMgmt.createChildError, setCreateChildError: childMgmt.setCreateChildError, createChildInviteLink: childMgmt.createChildInviteLink,
    handleCreateChild: childMgmt.handleCreateChild, handleLinkChild: childMgmt.handleLinkChild, closeLinkModal: childMgmt.closeLinkModal,
    googleConnected, discoveryState: childMgmt.discoveryState, discoveredChildren: childMgmt.discoveredChildren, selectedDiscovered: childMgmt.selectedDiscovered,
    coursesSearched: childMgmt.coursesSearched, bulkLinking: childMgmt.bulkLinking, bulkLinkSuccess: childMgmt.bulkLinkSuccess,
    handleConnectGoogle: childMgmt.handleConnectGoogle, triggerDiscovery: childMgmt.triggerDiscovery, handleBulkLink: childMgmt.handleBulkLink, toggleDiscovered: childMgmt.toggleDiscovered,
    setGoogleConnected, setDiscoveryState: childMgmt.setDiscoveryState, setDiscoveredChildren: childMgmt.setDiscoveredChildren, setBulkLinkSuccess: childMgmt.setBulkLinkSuccess,

    // Invite Student Modal
    showInviteModal: invites.showInviteModal, setShowInviteModal: invites.setShowInviteModal,
    inviteEmail: invites.inviteEmail, setInviteEmail: invites.setInviteEmail, inviteRelationship: invites.inviteRelationship, setInviteRelationship: invites.setInviteRelationship,
    inviteError: invites.inviteError, setInviteError: invites.setInviteError, inviteLoading: invites.inviteLoading, inviteSuccess: invites.inviteSuccess, setInviteSuccess: invites.setInviteSuccess,
    handleInviteStudent: invites.handleInviteStudent, closeInviteModal: invites.closeInviteModal,

    // Edit Child Modal
    showEditChildModal: childEditor.showEditChildModal, setShowEditChildModal: childEditor.setShowEditChildModal, editChild: childEditor.editChild, setEditChild: childEditor.setEditChild,
    editChildName: childEditor.editChildName, setEditChildName: childEditor.setEditChildName, editChildEmail: childEditor.editChildEmail, setEditChildEmail: childEditor.setEditChildEmail,
    editChildGrade: childEditor.editChildGrade, setEditChildGrade: childEditor.setEditChildGrade, editChildSchool: childEditor.editChildSchool, setEditChildSchool: childEditor.setEditChildSchool,
    editChildDob: childEditor.editChildDob, setEditChildDob: childEditor.setEditChildDob, editChildPhone: childEditor.editChildPhone, setEditChildPhone: childEditor.setEditChildPhone,
    editChildAddress: childEditor.editChildAddress, setEditChildAddress: childEditor.setEditChildAddress, editChildCity: childEditor.editChildCity, setEditChildCity: childEditor.setEditChildCity,
    editChildProvince: childEditor.editChildProvince, setEditChildProvince: childEditor.setEditChildProvince, editChildPostal: childEditor.editChildPostal, setEditChildPostal: childEditor.setEditChildPostal,
    editChildNotes: childEditor.editChildNotes, setEditChildNotes: childEditor.setEditChildNotes,
    editChildInterests: childEditor.editChildInterests, setEditChildInterests: childEditor.setEditChildInterests,
    editChildInterestInput: childEditor.editChildInterestInput, setEditChildInterestInput: childEditor.setEditChildInterestInput,
    editChildLoading: childEditor.editChildLoading, editChildError: childEditor.editChildError,
    editChildOptionalOpen: childEditor.editChildOptionalOpen, setEditChildOptionalOpen: childEditor.setEditChildOptionalOpen,
    handleEditChild: childEditor.handleEditChild, closeEditChildModal: childEditor.closeEditChildModal,

    // Day Detail Modal
    dayModalDate: tasks.dayModalDate, dayTasks: tasks.dayTasks, newTaskTitle: tasks.newTaskTitle, setNewTaskTitle: tasks.setNewTaskTitle,
    newTaskCreating: tasks.newTaskCreating, expandedTaskId: tasks.expandedTaskId, setExpandedTaskId: tasks.setExpandedTaskId,
    openDayModal: tasks.openDayModal, closeDayModal: tasks.closeDayModal, handleCreateDayTask: tasks.handleCreateDayTask,
    handleToggleTask: tasks.handleToggleTask, handleDeleteTask: tasks.handleDeleteTask,

    // Task Detail Modal
    taskDetailModal: tasks.taskDetailModal, setTaskDetailModal: tasks.setTaskDetailModal,

    // Study Tools
    showStudyModal: studyTools.showStudyModal, setShowStudyModal: studyTools.setShowStudyModal, isGenerating: studyTools.isGenerating,
    studyModalInitialTitle: studyTools.studyModalInitialTitle, studyModalInitialContent: studyTools.studyModalInitialContent,
    resetStudyModal: studyTools.resetStudyModal, handleGenerateFromModal: studyTools.handleGenerateFromModal,
    backgroundGeneration: studyTools.backgroundGeneration, dismissBackgroundGeneration: studyTools.dismissBackgroundGeneration, getBackgroundGenerationRoute: studyTools.getBackgroundGenerationRoute,

    // Create Task Modal
    showCreateTaskModal: tasks.showCreateTaskModal, setShowCreateTaskModal: tasks.setShowCreateTaskModal, loadDashboard,
  };
}
