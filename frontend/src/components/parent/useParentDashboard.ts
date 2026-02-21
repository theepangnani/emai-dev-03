import { useState, useEffect, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { parentApi, googleApi, invitesApi, studyApi, tasksApi } from '../../api/client';
import { courseContentsApi, coursesApi } from '../../api/courses';
import { queueStudyGeneration } from '../../pages/StudyGuidesPage';
import { isValidEmail } from '../../utils/validation';
import type { ChildSummary, ChildOverview, ParentDashboardData, DiscoveredChild, DuplicateCheckResponse, TaskItem, InviteResponse } from '../../api/client';

import type { CalendarAssignment } from '../calendar/types';
import { getCourseColor, dateKey, TASK_PRIORITY_COLORS } from '../calendar/types';
import { useConfirm } from '../ConfirmModal';
import type { StudyMaterialGenerateParams } from '../CreateStudyMaterialModal';
import type { CourseMaterial } from './StudentDetailPanel';

export type LinkTab = 'create' | 'email' | 'google';
export type DiscoveryState = 'idle' | 'discovering' | 'results' | 'no_results';

export const CHILD_COLORS = [
  '#8b5cf6', '#ec4899', '#14b8a6', '#f59e0b',
  '#3b82f6', '#ef4444', '#10b981', '#6366f1',
];

export function useParentDashboard() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { confirm, confirmModal } = useConfirm();
  const [children, setChildren] = useState<ChildSummary[]>([]);
  const [selectedChild, setSelectedChild] = useState<number | null>(null);
  const [childOverview, setChildOverview] = useState<ChildOverview | null>(null);
  const [allOverviews, setAllOverviews] = useState<ChildOverview[]>([]);
  const [loading, setLoading] = useState(true);
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [dashboardError, setDashboardError] = useState(false);

  const [dashboardData, setDashboardData] = useState<ParentDashboardData | null>(null);

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

  // Link child modal state
  const [showLinkModal, setShowLinkModal] = useState(false);
  const [linkTab, setLinkTab] = useState<LinkTab>('create');
  const [linkEmail, setLinkEmail] = useState('');
  const [linkName, setLinkName] = useState('');
  const [linkRelationship, setLinkRelationship] = useState('guardian');
  const [linkError, setLinkError] = useState('');
  const [linkLoading, setLinkLoading] = useState(false);
  const [linkInviteLink, setLinkInviteLink] = useState('');

  // Invite student modal state
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRelationship, setInviteRelationship] = useState('guardian');
  const [inviteError, setInviteError] = useState('');
  const [inviteLoading, setInviteLoading] = useState(false);
  const [inviteSuccess, setInviteSuccess] = useState('');

  // Google discovery state
  const [discoveryState, setDiscoveryState] = useState<DiscoveryState>('idle');
  const [discoveredChildren, setDiscoveredChildren] = useState<DiscoveredChild[]>([]);
  const [selectedDiscovered, setSelectedDiscovered] = useState<Set<number>>(new Set());
  const [googleConnected, setGoogleConnected] = useState(false);
  const [coursesSearched, setCoursesSearched] = useState(0);
  const [bulkLinking, setBulkLinking] = useState(false);
  const [bulkLinkSuccess, setBulkLinkSuccess] = useState(0);

  // Study tools modal state
  const [showStudyModal, setShowStudyModal] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [duplicateCheck, setDuplicateCheck] = useState<DuplicateCheckResponse | null>(null);
  const [studyModalInitialTitle, setStudyModalInitialTitle] = useState('');
  const [studyModalInitialContent, setStudyModalInitialContent] = useState('');

  // One-click study generation state
  const [generatingStudyId, setGeneratingStudyId] = useState<number | null>(null);

  // Edit child modal state
  const [showEditChildModal, setShowEditChildModal] = useState(false);
  const [editChild, setEditChild] = useState<ChildSummary | null>(null);
  const [editChildName, setEditChildName] = useState('');
  const [editChildEmail, setEditChildEmail] = useState('');
  const [editChildGrade, setEditChildGrade] = useState('');
  const [editChildSchool, setEditChildSchool] = useState('');
  const [editChildDob, setEditChildDob] = useState('');
  const [editChildPhone, setEditChildPhone] = useState('');
  const [editChildAddress, setEditChildAddress] = useState('');
  const [editChildCity, setEditChildCity] = useState('');
  const [editChildProvince, setEditChildProvince] = useState('');
  const [editChildPostal, setEditChildPostal] = useState('');
  const [editChildNotes, setEditChildNotes] = useState('');
  const [editChildLoading, setEditChildLoading] = useState(false);
  const [editChildError, setEditChildError] = useState('');
  const [editChildOptionalOpen, setEditChildOptionalOpen] = useState(false);

  // Day detail modal state
  const [dayModalDate, setDayModalDate] = useState<Date | null>(null);
  const [dayTasks, setDayTasks] = useState<TaskItem[]>([]);
  const [allTasks, setAllTasks] = useState<TaskItem[]>([]);
  const [newTaskTitle, setNewTaskTitle] = useState('');
  const [newTaskCreating, setNewTaskCreating] = useState(false);
  const [expandedTaskId, setExpandedTaskId] = useState<number | null>(null);

  // Create child (name-only) state
  const [createChildName, setCreateChildName] = useState('');
  const [createChildEmail, setCreateChildEmail] = useState('');
  const [createChildRelationship, setCreateChildRelationship] = useState('guardian');
  const [createChildLoading, setCreateChildLoading] = useState(false);
  const [createChildError, setCreateChildError] = useState('');
  const [createChildInviteLink, setCreateChildInviteLink] = useState('');

  // Pending invites state
  const [pendingInvites, setPendingInvites] = useState<InviteResponse[]>([]);
  const [resendingId, setResendingId] = useState<number | null>(null);

  // Create task modal state (from quick actions)
  const [showCreateTaskModal, setShowCreateTaskModal] = useState(false);

  // Task detail modal state
  const [taskDetailModal, setTaskDetailModal] = useState<TaskItem | null>(null);

  // Student detail panel collapse state
  const [detailPanelCollapsed, setDetailPanelCollapsed] = useState(false);

  // Today's Focus dismiss state
  const [focusDismissed, setFocusDismissed] = useState(false);

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

  useEffect(() => {
    const connected = searchParams.get('google_connected');
    const pendingAction = localStorage.getItem('pendingAction');

    if (connected === 'true' && pendingAction === 'discover_children') {
      localStorage.removeItem('pendingAction');
      setSearchParams({});
      setShowLinkModal(true);
      setLinkTab('google');
      setGoogleConnected(true);
      setTimeout(() => triggerDiscovery(), 100);
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
  // Child Management Handlers
  // ============================================

  const handleCreateChild = async () => {
    if (!createChildName.trim()) return;
    setCreateChildError('');
    setCreateChildInviteLink('');
    if (createChildEmail.trim() && !isValidEmail(createChildEmail.trim())) {
      setCreateChildError('Please enter a valid email address');
      return;
    }
    setCreateChildLoading(true);
    try {
      const result = await parentApi.createChild(
        createChildName.trim(),
        createChildRelationship,
        createChildEmail.trim() || undefined,
      );
      if (result.invite_link) {
        setCreateChildInviteLink(result.invite_link);
      } else {
        closeLinkModal();
      }
      await loadDashboard();
    } catch (err: any) {
      setCreateChildError(err.response?.data?.detail || 'Failed to create child');
    } finally {
      setCreateChildLoading(false);
    }
  };

  const handleLinkChild = async () => {
    if (!linkEmail.trim()) return;
    setLinkError('');
    setLinkInviteLink('');
    if (!isValidEmail(linkEmail.trim())) {
      setLinkError('Please enter a valid email address');
      return;
    }
    setLinkLoading(true);
    try {
      const result = await parentApi.linkChild(linkEmail.trim(), linkRelationship, linkName.trim() || undefined);
      if (result.invite_link) {
        setLinkInviteLink(result.invite_link);
      } else {
        closeLinkModal();
      }
      await loadDashboard();
    } catch (err: any) {
      setLinkError(err.response?.data?.detail || 'Failed to link child');
    } finally {
      setLinkLoading(false);
    }
  };

  const handleInviteStudent = async () => {
    if (!inviteEmail.trim()) return;
    if (!isValidEmail(inviteEmail.trim())) {
      setInviteError('Please enter a valid email address');
      return;
    }
    setInviteError('');
    setInviteSuccess('');
    setInviteLoading(true);
    try {
      const result = await invitesApi.create({
        email: inviteEmail.trim(),
        invite_type: 'student',
        metadata: { relationship_type: inviteRelationship },
      });
      const inviteLink = `${window.location.origin}/accept-invite?token=${result.token}`;
      setInviteSuccess(`Invite created! Share this link with your child:\n${inviteLink}`);
      setInviteEmail('');
    } catch (err: any) {
      setInviteError(err.response?.data?.detail || 'Failed to send invite');
    } finally {
      setInviteLoading(false);
    }
  };

  const closeInviteModal = () => {
    setShowInviteModal(false);
    setInviteEmail('');
    setInviteRelationship('guardian');
    setInviteError('');
    setInviteSuccess('');
  };

  const handleResendInvite = async (inviteId: number) => {
    setResendingId(inviteId);
    try {
      const updated = await invitesApi.resend(inviteId);
      setPendingInvites(prev => prev.map(i => i.id === inviteId ? updated : i));
    } catch { /* ignore */ }
    setResendingId(null);
  };

  const handleConnectGoogle = async () => {
    try {
      localStorage.setItem('pendingAction', 'discover_children');
      const { authorization_url } = await googleApi.getConnectUrl();
      window.location.href = authorization_url;
    } catch {
      setLinkError('Failed to initiate Google connection');
      localStorage.removeItem('pendingAction');
    }
  };

  const triggerDiscovery = async () => {
    setDiscoveryState('discovering');
    setDiscoveredChildren([]);
    setSelectedDiscovered(new Set());
    setLinkError('');
    try {
      const data = await parentApi.discoverViaGoogle();
      setGoogleConnected(data.google_connected);
      setCoursesSearched(data.courses_searched);
      if (data.discovered.length > 0) {
        setDiscoveredChildren(data.discovered);
        const preSelected = new Set(
          data.discovered.filter(c => !c.already_linked).map(c => c.user_id)
        );
        setSelectedDiscovered(preSelected);
        setDiscoveryState('results');
      } else {
        setDiscoveryState('no_results');
      }
    } catch (err: any) {
      setLinkError(err.response?.data?.detail || 'Failed to search Google Classroom');
      setDiscoveryState('idle');
    }
  };

  const handleBulkLink = async () => {
    if (selectedDiscovered.size === 0) return;
    const linkedCount = selectedDiscovered.size;
    setBulkLinking(true);
    setLinkError('');
    try {
      await parentApi.linkChildrenBulk(Array.from(selectedDiscovered));
      setBulkLinkSuccess(linkedCount);
      loadDashboard();
      await triggerDiscovery();
    } catch (err: any) {
      setLinkError(err.response?.data?.detail || 'Failed to link selected children');
    } finally {
      setBulkLinking(false);
    }
  };

  const toggleDiscovered = (userId: number) => {
    setSelectedDiscovered(prev => {
      const next = new Set(prev);
      if (next.has(userId)) next.delete(userId);
      else next.add(userId);
      return next;
    });
  };

  const closeLinkModal = () => {
    setShowLinkModal(false);
    setLinkTab('create');
    setLinkEmail('');
    setLinkName('');
    setLinkRelationship('guardian');
    setLinkError('');
    setLinkInviteLink('');
    setDiscoveryState('idle');
    setDiscoveredChildren([]);
    setSelectedDiscovered(new Set());
    setBulkLinkSuccess(0);
    setCreateChildName('');
    setCreateChildEmail('');
    setCreateChildRelationship('guardian');
    setCreateChildError('');
    setCreateChildInviteLink('');
  };

  useEffect(() => {
    if (showLinkModal && linkTab === 'google' && googleConnected && discoveryState === 'idle') {
      triggerDiscovery();
    }
  }, [linkTab, showLinkModal]);

  // ============================================
  // Edit Child Handlers
  // ============================================

  const closeEditChildModal = () => {
    setShowEditChildModal(false);
    setEditChild(null);
    setEditChildName('');
    setEditChildEmail('');
    setEditChildGrade('');
    setEditChildSchool('');
    setEditChildDob('');
    setEditChildPhone('');
    setEditChildAddress('');
    setEditChildCity('');
    setEditChildProvince('');
    setEditChildPostal('');
    setEditChildNotes('');
    setEditChildError('');
    setEditChildOptionalOpen(false);
  };

  const handleEditChild = async () => {
    if (!editChild || !editChildName.trim()) return;
    if (editChildEmail.trim() && !isValidEmail(editChildEmail.trim())) {
      setEditChildError('Please enter a valid email address');
      return;
    }
    setEditChildLoading(true);
    setEditChildError('');
    try {
      const payload: Record<string, unknown> = {};
      if (editChildName.trim() !== editChild.full_name) payload.full_name = editChildName.trim();
      if (editChildEmail.trim() !== (editChild.email || '')) payload.email = editChildEmail.trim();
      const newGrade = editChildGrade ? parseInt(editChildGrade, 10) : null;
      if (newGrade !== editChild.grade_level) payload.grade_level = newGrade ?? undefined;
      if (editChildSchool.trim() !== (editChild.school_name || '')) payload.school_name = editChildSchool.trim() || undefined;
      if (editChildDob !== (editChild.date_of_birth || '')) payload.date_of_birth = editChildDob || undefined;
      if (editChildPhone.trim() !== (editChild.phone || '')) payload.phone = editChildPhone.trim() || undefined;
      if (editChildAddress.trim() !== (editChild.address || '')) payload.address = editChildAddress.trim() || undefined;
      if (editChildCity.trim() !== (editChild.city || '')) payload.city = editChildCity.trim() || undefined;
      if (editChildProvince.trim() !== (editChild.province || '')) payload.province = editChildProvince.trim() || undefined;
      if (editChildPostal.trim() !== (editChild.postal_code || '')) payload.postal_code = editChildPostal.trim() || undefined;
      if (editChildNotes.trim() !== (editChild.notes || '')) payload.notes = editChildNotes.trim() || undefined;

      if (Object.keys(payload).length === 0) {
        closeEditChildModal();
        return;
      }
      await parentApi.updateChild(editChild.student_id, payload as any);
      closeEditChildModal();
      await loadDashboard();
    } catch (err: any) {
      setEditChildError(err.response?.data?.detail || 'Failed to update child');
    } finally {
      setEditChildLoading(false);
    }
  };

  const handleChildTabClick = (studentId: number) => {
    if (selectedChild === studentId) {
      setSelectedChild(null);
      setChildOverview(null);
      sessionStorage.removeItem('selectedChildId');
    } else {
      setSelectedChild(studentId);
      const child = children.find(c => c.student_id === studentId);
      if (child) sessionStorage.setItem('selectedChildId', String(child.user_id));
    }
  };

  // ============================================
  // Study Tools Handlers
  // ============================================

  const resetStudyModal = () => {
    setShowStudyModal(false);
    setDuplicateCheck(null);
    setStudyModalInitialTitle('');
    setStudyModalInitialContent('');
  };

  const handleGenerateFromModal = async (modalParams: StudyMaterialGenerateParams) => {
    setIsGenerating(true);
    try {
      if (modalParams.types.length === 0) {
        try {
          const defaultCourse = await coursesApi.getDefault();
          if (modalParams.mode === 'file' && modalParams.file) {
            await courseContentsApi.uploadFile(
              modalParams.file,
              defaultCourse.id,
              modalParams.title || undefined,
              'notes',
            );
          } else {
            await courseContentsApi.create({
              course_id: defaultCourse.id,
              title: modalParams.title || 'Uploaded material',
              text_content: modalParams.content || undefined,
              content_type: 'notes',
            });
          }
        } catch { /* continue */ }
        setDuplicateCheck(null);
        resetStudyModal();
        navigate('/course-materials', { state: { selectedChild: selectedChildUserId } });
        return;
      }

      if (modalParams.types.length === 1 && modalParams.mode === 'text' && !modalParams.pastedImages?.length) {
        try {
          const dupResult = await studyApi.checkDuplicate({ title: modalParams.title || undefined, guide_type: modalParams.types[0] });
          if (dupResult.exists) { setDuplicateCheck(dupResult); return; }
        } catch { /* Continue */ }
      }
      for (const type of modalParams.types) {
        queueStudyGeneration({
          title: modalParams.title,
          content: modalParams.content,
          type,
          focusPrompt: modalParams.focusPrompt,
          mode: modalParams.mode,
          file: modalParams.file,
          pastedImages: modalParams.pastedImages,
          regenerateId: duplicateCheck?.existing_guide?.id,
        });
      }
      setDuplicateCheck(null);
      resetStudyModal();
      navigate('/course-materials', { state: { selectedChild: selectedChildUserId } });
    } finally {
      setIsGenerating(false);
    }
  };

  // ============================================
  // Tasks & Day Detail
  // ============================================

  const selectedChildUserId = useMemo(() => {
    if (!selectedChild) return null;
    return children.find(c => c.student_id === selectedChild)?.user_id ?? null;
  }, [selectedChild, children]);

  useEffect(() => {
    if (loading) return;
    const params: { student_user_id?: number } = {};
    if (selectedChildUserId) params.student_user_id = selectedChildUserId;
    courseContentsApi.listAll(params)
      .then(items => {
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
  }, [loading, selectedChildUserId]);

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
      const due = new Date(t.due_date);
      if (due < todayStart) overdue++;
      else if (due >= todayStart && due < todayEnd) dueToday++;
      else if (due >= todayEnd && due < threeDaysEnd) upcoming++;
    }
    return { overdue, dueToday, upcoming };
  }, [filteredTasks]);

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

  // ============================================
  // Calendar Data Derivation
  // ============================================

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

  const handleOneClickStudy = async (assignment: CalendarAssignment) => {
    if (generatingStudyId) return;
    setGeneratingStudyId(assignment.id);
    try {
      const dupResult = await studyApi.checkDuplicate({
        title: assignment.title,
        guide_type: 'study_guide',
      });
      if (dupResult.exists && dupResult.existing_guide) {
        const guide = dupResult.existing_guide;
        const path = guide.guide_type === 'quiz' ? `/study/quiz/${guide.id}`
          : guide.guide_type === 'flashcards' ? `/study/flashcards/${guide.id}`
          : `/study/guide/${guide.id}`;
        navigate(path);
        return;
      }
      if (!assignment.description?.trim()) {
        setStudyModalInitialTitle(assignment.title);
        setStudyModalInitialContent('');
        setShowStudyModal(true);
        return;
      }
      queueStudyGeneration({
        title: assignment.title,
        content: assignment.description,
        type: 'study_guide',
        mode: 'text',
      });
      navigate('/course-materials', { state: { selectedChild: selectedChildUserId } });
    } catch {
      setStudyModalInitialTitle(assignment.title);
      setStudyModalInitialContent(assignment.description || '');
      setShowStudyModal(true);
    } finally {
      setGeneratingStudyId(null);
    }
  };

  const handleGoToCourse = (courseId: number) => {
    navigate(`/courses?highlight=${courseId}`);
  };

  const handleViewStudyGuides = () => {
    navigate('/course-materials', { state: { selectedChild: selectedChildUserId } });
  };

  // ============================================
  // Today's Focus computed values
  // ============================================

  const selectedChildFirstName = useMemo(() => {
    if (!selectedChild) return null;
    const name = children.find(c => c.student_id === selectedChild)?.full_name;
    return name?.split(' ')[0] ?? null;
  }, [selectedChild, children]);

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

  return {
    // Core
    loading, dashboardError, children, navigate, confirmModal,

    // Child selection
    selectedChild, handleChildTabClick, selectedChildUserId, selectedChildFirstName,

    // Overview
    overviewLoading,

    // Dashboard data
    filteredTasks, taskCounts, courseMaterials, pendingInvites, resendingId, handleResendInvite,

    // Calendar
    calendarCollapsed, toggleCalendar, showCalendarTooltip, dismissCalendarTooltip,
    calendarAssignments, undatedAssignments, generatingStudyId,
    handleOneClickStudy, handleGoToCourse, handleViewStudyGuides, handleTaskDrop,

    // Today's Focus
    focusDismissed, setFocusDismissed, perChildOverdue,

    // Detail panel
    detailPanelCollapsed, setDetailPanelCollapsed,

    // Link Child Modal
    showLinkModal, setShowLinkModal, linkTab, setLinkTab,
    linkEmail, setLinkEmail, linkName, setLinkName,
    linkRelationship, setLinkRelationship, linkError, setLinkError,
    linkLoading, linkInviteLink,
    createChildName, setCreateChildName, createChildEmail, setCreateChildEmail,
    createChildRelationship, setCreateChildRelationship, createChildLoading,
    createChildError, setCreateChildError, createChildInviteLink,
    handleCreateChild, handleLinkChild, closeLinkModal,
    googleConnected, discoveryState, discoveredChildren, selectedDiscovered,
    coursesSearched, bulkLinking, bulkLinkSuccess,
    handleConnectGoogle, triggerDiscovery, handleBulkLink, toggleDiscovered,
    setGoogleConnected, setDiscoveryState, setDiscoveredChildren, setBulkLinkSuccess,

    // Invite Student Modal
    showInviteModal, setShowInviteModal,
    inviteEmail, setInviteEmail, inviteRelationship, setInviteRelationship,
    inviteError, setInviteError, inviteLoading, inviteSuccess, setInviteSuccess,
    handleInviteStudent, closeInviteModal,

    // Edit Child Modal
    showEditChildModal, setShowEditChildModal, editChild, setEditChild,
    editChildName, setEditChildName, editChildEmail, setEditChildEmail,
    editChildGrade, setEditChildGrade, editChildSchool, setEditChildSchool,
    editChildDob, setEditChildDob, editChildPhone, setEditChildPhone,
    editChildAddress, setEditChildAddress, editChildCity, setEditChildCity,
    editChildProvince, setEditChildProvince, editChildPostal, setEditChildPostal,
    editChildNotes, setEditChildNotes, editChildLoading, editChildError,
    editChildOptionalOpen, setEditChildOptionalOpen,
    handleEditChild, closeEditChildModal,

    // Day Detail Modal
    dayModalDate, dayTasks, newTaskTitle, setNewTaskTitle,
    newTaskCreating, expandedTaskId, setExpandedTaskId,
    openDayModal, closeDayModal, handleCreateDayTask,
    handleToggleTask, handleDeleteTask,

    // Task Detail Modal
    taskDetailModal, setTaskDetailModal,

    // Study Tools
    showStudyModal, setShowStudyModal, isGenerating,
    studyModalInitialTitle, studyModalInitialContent,
    duplicateCheck, setDuplicateCheck,
    resetStudyModal, handleGenerateFromModal,

    // Create Task Modal
    showCreateTaskModal, setShowCreateTaskModal, loadDashboard,
  };
}
