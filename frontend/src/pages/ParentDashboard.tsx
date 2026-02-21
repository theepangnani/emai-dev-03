import { useState, useEffect, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { parentApi, googleApi, invitesApi, studyApi, tasksApi } from '../api/client';
import { courseContentsApi, coursesApi } from '../api/courses';
import { queueStudyGeneration } from './StudyGuidesPage';
import { isValidEmail } from '../utils/validation';
import type { ChildSummary, ChildOverview, ParentDashboardData, DiscoveredChild, DuplicateCheckResponse, TaskItem, InviteResponse } from '../api/client';
import { DashboardLayout } from '../components/DashboardLayout';
import type { InspirationData } from '../components/DashboardLayout';
import { PageSkeleton } from '../components/Skeleton';
import { CalendarView } from '../components/calendar/CalendarView';
import type { CalendarAssignment } from '../components/calendar/types';
import { getCourseColor, dateKey, TASK_PRIORITY_COLORS } from '../components/calendar/types';
import { useConfirm } from '../components/ConfirmModal';
import CreateStudyMaterialModal from '../components/CreateStudyMaterialModal';
import type { StudyMaterialGenerateParams } from '../components/CreateStudyMaterialModal';
import { AlertBanner } from '../components/parent/AlertBanner';
import { StudentDetailPanel } from '../components/parent/StudentDetailPanel';
import type { CourseMaterial } from '../components/parent/StudentDetailPanel';
import { QuickActionsBar } from '../components/parent/QuickActionsBar';
import { CreateTaskModal } from '../components/CreateTaskModal';
import './ParentDashboard.css';



type LinkTab = 'create' | 'email' | 'google';
type DiscoveryState = 'idle' | 'discovering' | 'results' | 'no_results';

const CHILD_COLORS = [
  '#8b5cf6', '#ec4899', '#14b8a6', '#f59e0b',
  '#3b82f6', '#ef4444', '#10b981', '#6366f1',
];

export function ParentDashboard() {
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

  // Dashboard summary data (from single API call)
  const [dashboardData, setDashboardData] = useState<ParentDashboardData | null>(null);

  // Collapsible calendar (default expanded; user can collapse and preference is saved)
  const [calendarCollapsed, setCalendarCollapsed] = useState(() => {
    try {
      const saved = localStorage.getItem('calendar_collapsed');
      return saved !== '0';
    } catch { return false; }
  });
  const toggleCalendar = () => {
    setCalendarCollapsed(prev => {
      const next = !prev;
      try { localStorage.setItem('calendar_collapsed', next ? '1' : '0'); } catch { /* ignore */ }
      return next;
    });
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

  // Load dashboard data in a single API call
  const loadDashboard = async () => {
    let childEmails: Set<string> = new Set();
    try {
      const data = await parentApi.getDashboard();
      setDashboardData(data);
      setChildren(data.children);
      setGoogleConnected(data.google_connected);
      // Build task items from dashboard data
      setAllTasks(data.all_tasks as unknown as TaskItem[]);
      if (data.children.length === 1) {
        setSelectedChild(data.children[0].student_id);
      } else {
        setSelectedChild(null);
      }
      childEmails = new Set(data.children.map(c => c.email?.toLowerCase()).filter(Boolean) as string[]);
    } catch {
      setDashboardError(true);
    } finally {
      setLoading(false);
      setOverviewLoading(false);
    }
    // Load pending invites in background — exclude invites for already-linked children
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

  // When child selection changes, load individual overview for filtering
  useEffect(() => {
    if (selectedChild) {
      loadChildOverview(selectedChild);
    } else if (children.length > 0 && dashboardData) {
      // Build all overviews from dashboard data
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
      // Refresh dashboard in background, then re-discover to show updated "Already linked" badges
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

  // Auto-trigger discovery when switching to Google tab while already connected
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
      // Only send fields that actually changed to prevent accidental overwrites
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
    } else {
      setSelectedChild(studentId);
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
      // Upload-only mode: no AI types selected → create course content directly
      if (modalParams.types.length === 0) {
        try {
          const defaultCourse = await coursesApi.getDefault();
          if (modalParams.mode === 'file' && modalParams.file) {
            // File upload: save original file + extract text on backend
            await courseContentsApi.uploadFile(
              modalParams.file,
              defaultCourse.id,
              modalParams.title || undefined,
              'notes',
            );
          } else {
            // Text/paste mode: create content with text only
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

      // Check for duplicates only when single type selected
      if (modalParams.types.length === 1 && modalParams.mode === 'text' && !modalParams.pastedImages?.length) {
        try {
          const dupResult = await studyApi.checkDuplicate({ title: modalParams.title || undefined, guide_type: modalParams.types[0] });
          if (dupResult.exists) { setDuplicateCheck(dupResult); return; }
        } catch { /* Continue */ }
      }
      // Queue one generation per selected type, then navigate
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
  // Tasks & Day Detail Modal
  // ============================================

  const selectedChildUserId = useMemo(() => {
    if (!selectedChild) return null;
    return children.find(c => c.student_id === selectedChild)?.user_id ?? null;
  }, [selectedChild, children]);

  // Load class materials for StudentDetailPanel
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

  // Tasks are loaded from the dashboard API call.
  // When a specific child is selected, filter tasks client-side.
  const filteredTasks = useMemo(() => {
    if (!selectedChildUserId) return allTasks;
    return allTasks.filter(t =>
      t.assigned_to_user_id === selectedChildUserId ||
      t.created_by_user_id === selectedChildUserId
    );
  }, [allTasks, selectedChildUserId]);

  // Compute task urgency counts from filtered tasks (for AlertBanner + Today's Focus)
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
    // Filter tasks for this day
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
      // Find the child's user_id for assignment (if a child is selected)
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
    // Calendar uses id + 1_000_000 offset for tasks
    const taskId = calendarId - 1_000_000;
    const task = allTasks.find(t => t.id === taskId);
    if (!task) return;

    const prevTasks = allTasks;
    const newDueDate = newDate.toISOString();

    // Optimistic update
    setAllTasks(prev => prev.map(t => t.id === taskId ? { ...t, due_date: newDueDate } : t));

    try {
      const updated = await tasksApi.update(taskId, { due_date: newDueDate });
      setAllTasks(prev => prev.map(t => t.id === taskId ? updated : t));
    } catch {
      // Revert on failure
      setAllTasks(prevTasks);
      alert('Failed to reschedule task. You may not have permission to edit this task.');
    }
  };

  // ============================================
  // Calendar Data Derivation
  // ============================================

  // Use selected child overview or merge all overviews
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

    // Merge tasks with due dates into calendar
    const taskItems: CalendarAssignment[] = filteredTasks
      .filter(t => t.due_date)
      .map(t => ({
        id: t.id + 1_000_000, // offset to avoid ID collisions with assignments
        taskId: t.id,  // real task ID for navigation
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
    if (generatingStudyId) return; // already generating
    setGeneratingStudyId(assignment.id);
    try {
      // Check if study material already exists for this assignment
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
      // No existing material — generate with smart defaults (no modal)
      if (!assignment.description?.trim()) {
        // No content to generate from — fall back to modal
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
      // On error, fall back to the modal
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
  // Today's Focus header builder
  // ============================================

  const selectedChildFirstName = useMemo(() => {
    if (!selectedChild) return null;
    const name = children.find(c => c.student_id === selectedChild)?.full_name;
    return name?.split(' ')[0] ?? null;
  }, [selectedChild, children]);

  const renderHeaderSlot = (inspiration: InspirationData | null) => {
    if (focusDismissed) {
      return null;
    }

    const { overdue, dueToday, upcoming } = taskCounts;
    const inviteCount = pendingInvites.length;
    const allClear = overdue === 0 && dueToday === 0 && upcoming === 0 && inviteCount === 0;
    const childLabel = selectedChildFirstName ?? (children.length === 1 ? children[0]?.full_name?.split(' ')[0] : null);

    return (
      <div className="today-focus-header">
        <div className="today-focus-main">
          {allClear ? (
            <div className="today-focus-status all-clear">
              <span className="today-focus-icon">{'\u2705'}</span>
              <div>
                <div className="today-focus-title">All caught up!</div>
                <div className="today-focus-subtitle">
                  {childLabel ? `${childLabel} has no urgent tasks.` : 'No urgent tasks right now.'}
                  {' '}Great time to create study materials.
                </div>
              </div>
            </div>
          ) : (
            <div className="today-focus-status">
              <span className="today-focus-icon">{overdue > 0 ? '\u{1F525}' : '\u{1F4CB}'}</span>
              <div>
                <div className="today-focus-title">
                  {childLabel ? `${childLabel}'s Focus` : "Today's Focus"}
                </div>
                <div className="today-focus-items">
                  {overdue > 0 && (
                    <button type="button" className="focus-tag overdue" onClick={() => navigate('/tasks?due=overdue')}>{overdue} overdue</button>
                  )}
                  {dueToday > 0 && (
                    <button type="button" className="focus-tag today" onClick={() => navigate('/tasks?due=today')}>{dueToday} due today</button>
                  )}
                  {upcoming > 0 && (
                    <button type="button" className="focus-tag upcoming" onClick={() => navigate('/tasks?due=week')}>{upcoming} next 3 days</button>
                  )}
                  {inviteCount > 0 && (
                    <button type="button" className="focus-tag invites" onClick={() => navigate('/my-kids')}>{inviteCount} pending invite{inviteCount !== 1 ? 's' : ''}</button>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
        {inspiration && (
          <div className="today-focus-inspiration">
            <span className="today-focus-quote">"{inspiration.text}"</span>
            {inspiration.author && (
              <span className="today-focus-author"> — {inspiration.author}</span>
            )}
          </div>
        )}
        <button
          className="today-focus-close"
          onClick={() => setFocusDismissed(true)}
          aria-label="Close Today's Focus"
        >
          {'\u00D7'}
        </button>
      </div>
    );
  };

  // ============================================
  // Render
  // ============================================

  if (loading) {
    return (
      <DashboardLayout welcomeSubtitle="At-a-glance monitoring, calendar, and quick actions">
        <PageSkeleton />
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout
      welcomeSubtitle="At-a-glance monitoring, calendar, and quick actions"
      headerSlot={children.length > 0 ? renderHeaderSlot : undefined}
    >
      {dashboardError ? (
        <div className="no-children-state">
          <h3>Unable to Load Dashboard</h3>
          <p>Something went wrong while loading your dashboard. Please try refreshing the page.</p>
          <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', marginTop: '20px' }}>
            <button className="link-child-btn" onClick={() => window.location.reload()}>
              Refresh Page
            </button>
          </div>
        </div>
      ) : children.length === 0 ? (
        <div className="no-children-state">
          <h3>Get Started</h3>
          <p>Add your child to start managing their education. No school account required!</p>
          <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', marginTop: '20px' }}>
            <button className="link-child-btn" onClick={() => setShowLinkModal(true)}>
              + Add Child
            </button>
          </div>
        </div>
      ) : (
        <>
          {/* Child Filter */}
          <div className="child-selector">
            {children.length > 1 && (
              <button
                className={`child-tab ${selectedChild === null ? 'active' : ''}`}
                onClick={() => { setSelectedChild(null); setChildOverview(null); }}
              >
                All Children
              </button>
            )}
            {children.map((child, index) => (
              <button
                key={child.student_id}
                className={`child-tab ${selectedChild === child.student_id ? 'active' : ''}`}
                onClick={() => handleChildTabClick(child.student_id)}
              >
                <span className="child-color-dot" style={{ backgroundColor: CHILD_COLORS[index % CHILD_COLORS.length] }} />
                {child.full_name}
                {child.grade_level != null && <span className="grade-badge">Grade {child.grade_level}</span>}
              </button>
            ))}
          </div>

          {/* Alert Banner (pending invites only) */}
          <AlertBanner
            pendingInvites={pendingInvites.map(i => ({ id: i.id, email: i.email }))}
            onResendInvite={handleResendInvite}
            resendingId={resendingId}
          />

          {/* Quick Actions */}
          <QuickActionsBar
            onCreateMaterial={() => setShowStudyModal(true)}
            onCreateTask={() => setShowCreateTaskModal(true)}
          />

          {/* Student Detail Panel (always shown — aggregated for All Children, specific for selected child) */}
          <StudentDetailPanel
            selectedChildName={selectedChild ? (children.find(c => c.student_id === selectedChild)?.full_name ?? null) : null}
            courseMaterials={courseMaterials}
            tasks={filteredTasks}
            collapsed={detailPanelCollapsed}
            onToggleCollapsed={() => setDetailPanelCollapsed(v => !v)}
            onViewMaterial={(mat) => {
              navigate(`/course-materials/${mat.id}`);
            }}
            onToggleTask={handleToggleTask}
            onTaskClick={(task) => setTaskDetailModal(task)}
            onViewAllTasks={() => navigate('/tasks', { state: { selectedChild: selectedChildUserId } })}
            onViewAllMaterials={() => navigate('/course-materials', { state: { selectedChild: selectedChildUserId } })}
          />

          {/* Collapsible Calendar Section */}
          <div className="calendar-collapse-section">
            <button className="calendar-collapse-toggle" onClick={toggleCalendar}>
              <span className={`calendar-collapse-chevron${calendarCollapsed ? '' : ' expanded'}`}>&#9654;</span>
              <span className="calendar-collapse-label">
                {calendarCollapsed
                  ? `Calendar (${calendarAssignments.length} items)`
                  : 'Calendar'}
              </span>
            </button>
          </div>

          {!calendarCollapsed && (
            <>
              {overviewLoading ? (
                <PageSkeleton />
              ) : (
                <>
                  <CalendarView
                    assignments={calendarAssignments}
                    onCreateStudyGuide={handleOneClickStudy}
                    onDayClick={openDayModal}
                    onTaskDrop={handleTaskDrop}
                    onGoToCourse={handleGoToCourse}
                    onViewStudyGuides={handleViewStudyGuides}
                    generatingStudyId={generatingStudyId}
                  />

                  {/* Undated Assignments */}
                  {undatedAssignments.length > 0 && (
                    <div className="undated-section">
                      <h4>Undated Assignments ({undatedAssignments.length})</h4>
                      <div className="undated-list">
                        {undatedAssignments.map(a => (
                          <div
                            key={a.id}
                            className="undated-item"
                            onClick={() => handleOneClickStudy(a)}
                          >
                            <span className="cal-entry-dot" style={{ background: a.courseColor }} />
                            <span className="undated-title">{a.title}</span>
                            <span className="undated-course">{a.courseName}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}
            </>
          )}
        </>
      )}

      {/* ============================================
          Modals
          ============================================ */}

      {/* Link Child Modal */}
      {showLinkModal && (
        <div className="modal-overlay" onClick={closeLinkModal}>
          <div className="modal modal-lg" onClick={(e) => e.stopPropagation()}>
            <h2>Add Child</h2>

            <div className="link-tabs">
              <button className={`link-tab ${linkTab === 'create' ? 'active' : ''}`} onClick={() => { setLinkTab('create'); setLinkError(''); }}>
                Create New
              </button>
              <button className={`link-tab ${linkTab === 'email' ? 'active' : ''}`} onClick={() => { setLinkTab('email'); setLinkError(''); }}>
                Link by Email
              </button>
              <button className={`link-tab ${linkTab === 'google' ? 'active' : ''}`} onClick={() => { setLinkTab('google'); setLinkError(''); }}>
                Google Classroom
              </button>
            </div>

            {linkTab === 'create' && (
              <>
                {createChildInviteLink ? (
                  <div className="modal-form">
                    <div className="invite-success-box">
                      <p style={{ margin: '0 0 8px', fontWeight: 600 }}>Child added successfully!</p>
                      <p style={{ margin: '0 0 8px', fontSize: 14 }}>
                        Share this link with your child so they can set their password and log in:
                      </p>
                      <div className="invite-link-container">
                        <span className="invite-link">{createChildInviteLink}</span>
                        <button className="copy-link-btn" onClick={() => navigator.clipboard.writeText(createChildInviteLink)}>Copy</button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <>
                    <p className="modal-desc">Add your child with just their name. Email is optional.</p>
                    <div className="modal-form">
                      <label>
                        Child's Name *
                        <input type="text" value={createChildName} onChange={(e) => setCreateChildName(e.target.value)} placeholder="e.g. Alex Smith" disabled={createChildLoading} onKeyDown={(e) => e.key === 'Enter' && handleCreateChild()} />
                      </label>
                      <label>
                        Email (optional)
                        <input type="email" value={createChildEmail} onChange={(e) => { setCreateChildEmail(e.target.value); setCreateChildError(''); }} placeholder="child@example.com" disabled={createChildLoading} />
                      </label>
                      <label>
                        Relationship
                        <select value={createChildRelationship} onChange={(e) => setCreateChildRelationship(e.target.value)} disabled={createChildLoading}>
                          <option value="mother">Mother</option>
                          <option value="father">Father</option>
                          <option value="guardian">Guardian</option>
                          <option value="other">Other</option>
                        </select>
                      </label>
                      {createChildError && <p className="link-error">{createChildError}</p>}
                    </div>
                  </>
                )}
                <div className="modal-actions">
                  <button className="cancel-btn" onClick={closeLinkModal} disabled={createChildLoading}>{createChildInviteLink ? 'Close' : 'Cancel'}</button>
                  {!createChildInviteLink && (
                    <button className="generate-btn" onClick={handleCreateChild} disabled={createChildLoading || !createChildName.trim()}>
                      {createChildLoading ? 'Creating...' : 'Add Child'}
                    </button>
                  )}
                </div>
              </>
            )}

            {linkTab === 'email' && (
              <>
                {linkInviteLink ? (
                  <div className="modal-form">
                    <div className="invite-success-box">
                      <p style={{ margin: '0 0 8px', fontWeight: 600 }}>Child linked successfully!</p>
                      <p style={{ margin: '0 0 8px', fontSize: 14 }}>
                        A new student account was created. Share this link with your child so they can set their password and log in:
                      </p>
                      <div className="invite-link-container">
                        <span className="invite-link">{linkInviteLink}</span>
                        <button className="copy-link-btn" onClick={() => navigator.clipboard.writeText(linkInviteLink)}>Copy</button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <>
                    <p className="modal-desc">Enter your child's email to link or create their account.</p>
                    <div className="modal-form">
                      <label>
                        Child's Name
                        <input type="text" value={linkName} onChange={(e) => setLinkName(e.target.value)} placeholder="e.g. Alex Smith" disabled={linkLoading} />
                      </label>
                      <label>
                        Student Email
                        <input type="email" value={linkEmail} onChange={(e) => { setLinkEmail(e.target.value); setLinkError(''); }} placeholder="child@school.edu" disabled={linkLoading} onKeyDown={(e) => e.key === 'Enter' && handleLinkChild()} />
                      </label>
                      <label>
                        Relationship
                        <select value={linkRelationship} onChange={(e) => setLinkRelationship(e.target.value)} disabled={linkLoading}>
                          <option value="mother">Mother</option>
                          <option value="father">Father</option>
                          <option value="guardian">Guardian</option>
                          <option value="other">Other</option>
                        </select>
                      </label>
                      {linkError && <p className="link-error">{linkError}</p>}
                    </div>
                  </>
                )}
                <div className="modal-actions">
                  <button className="cancel-btn" onClick={closeLinkModal} disabled={linkLoading}>{linkInviteLink ? 'Close' : 'Cancel'}</button>
                  {!linkInviteLink && (
                    <button className="generate-btn" onClick={handleLinkChild} disabled={linkLoading || !linkEmail.trim()}>
                      {linkLoading ? 'Linking...' : 'Link Child'}
                    </button>
                  )}
                </div>
              </>
            )}

            {linkTab === 'google' && (
              <>
                {!googleConnected && discoveryState === 'idle' && (
                  <div className="google-connect-prompt">
                    <div className="google-icon">🔗</div>
                    <h3>Connect Google Account</h3>
                    <p>Sign in with your Google account to automatically discover your children's student accounts from Google Classroom.</p>
                    <button className="google-connect-btn" onClick={handleConnectGoogle}>Connect Google Account</button>
                    {linkError && <p className="link-error">{linkError}</p>}
                  </div>
                )}
                {googleConnected && discoveryState === 'idle' && (
                  <div className="discovery-loading">
                    <div className="loading-spinner-large" />
                    <p>Searching Google Classroom courses for student accounts...</p>
                  </div>
                )}
                {discoveryState === 'discovering' && (
                  <div className="discovery-loading">
                    <div className="loading-spinner-large" />
                    <p>Searching Google Classroom courses for student accounts...</p>
                  </div>
                )}
                {discoveryState === 'results' && (
                  <div className="discovery-results">
                    {bulkLinkSuccess > 0 && (
                      <div className="invite-success-box" style={{ marginBottom: 12 }}>
                        <p style={{ margin: 0, fontWeight: 600 }}>
                          Successfully linked {bulkLinkSuccess} child{bulkLinkSuccess !== 1 ? 'ren' : ''}!
                        </p>
                      </div>
                    )}
                    {discoveredChildren.every(c => c.already_linked) ? (
                      <p className="modal-desc">
                        All {discoveredChildren.length} discovered student{discoveredChildren.length !== 1 ? 's' : ''} are linked to your account.
                      </p>
                    ) : (
                      <p className="modal-desc">
                        Found {discoveredChildren.length} student{discoveredChildren.length !== 1 ? 's' : ''} across {coursesSearched} class{coursesSearched !== 1 ? 'es' : ''}. Select the children you want to link:
                      </p>
                    )}
                    <div className="discovered-list">
                      {discoveredChildren.map((child) => (
                        <label key={child.user_id} className={`discovered-item ${child.already_linked ? 'disabled' : ''}`}>
                          <input type="checkbox" checked={selectedDiscovered.has(child.user_id)} onChange={() => toggleDiscovered(child.user_id)} disabled={child.already_linked} />
                          <div className="discovered-info">
                            <span className="discovered-name">{child.full_name}</span>
                            <span className="discovered-email">{child.email}</span>
                            <span className="discovered-courses">{child.google_courses.join(', ')}</span>
                            {child.already_linked && <span className="discovered-linked-badge">Already linked</span>}
                          </div>
                        </label>
                      ))}
                    </div>
                    {linkError && <p className="link-error">{linkError}</p>}
                    <div className="modal-actions" style={{ justifyContent: 'space-between' }}>
                      <button className="cancel-btn" style={{ fontSize: '13px' }} onClick={async () => { try { await googleApi.disconnect(); setGoogleConnected(false); setDiscoveryState('idle'); setDiscoveredChildren([]); setBulkLinkSuccess(0); } catch { setLinkError('Failed to disconnect Google account'); } }}>
                        Disconnect Google
                      </button>
                      <div style={{ display: 'flex', gap: 8 }}>
                        <button className="cancel-btn" onClick={closeLinkModal} disabled={bulkLinking}>Done</button>
                        {!discoveredChildren.every(c => c.already_linked) && (
                          <button className="generate-btn" onClick={handleBulkLink} disabled={bulkLinking || selectedDiscovered.size === 0}>
                            {bulkLinking ? 'Linking...' : `Link ${selectedDiscovered.size} Selected`}
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                )}
                {discoveryState === 'no_results' && (
                  <div className="google-connect-prompt">
                    <div className="google-icon">📭</div>
                    <h3>No Matching Students Found</h3>
                    <p>We searched {coursesSearched} Google Classroom class{coursesSearched !== 1 ? 'es' : ''} but didn't find any matching student accounts.</p>
                    <button className="link-tab-switch" onClick={() => { setLinkTab('email'); setDiscoveryState('idle'); }}>Try linking by email instead</button>
                    <div className="modal-actions">
                      <button className="cancel-btn" onClick={closeLinkModal}>Close</button>
                      <button className="generate-btn" onClick={triggerDiscovery}>Search Again</button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* Invite Student Modal */}
      {showInviteModal && (
        <div className="modal-overlay" onClick={closeInviteModal}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Invite Student</h2>
            <p className="modal-desc">Send an email invite to create a new student account linked to yours.</p>
            <div className="modal-form">
              <label>
                Student Email
                <input type="email" value={inviteEmail} onChange={(e) => { setInviteEmail(e.target.value); setInviteError(''); setInviteSuccess(''); }} placeholder="child@example.com" disabled={inviteLoading} onKeyDown={(e) => e.key === 'Enter' && handleInviteStudent()} />
              </label>
              <label>
                Relationship
                <select value={inviteRelationship} onChange={(e) => setInviteRelationship(e.target.value)} disabled={inviteLoading}>
                  <option value="mother">Mother</option>
                  <option value="father">Father</option>
                  <option value="guardian">Guardian</option>
                  <option value="other">Other</option>
                </select>
              </label>
              {inviteError && <p className="link-error">{inviteError}</p>}
              {inviteSuccess && (
                <div className="invite-success-box">
                  <p className="link-success">Invite created!</p>
                  <p className="invite-link-label">Share this link with your child:</p>
                  <div className="invite-link-container">
                    <code className="invite-link">{inviteSuccess.split('\n')[1]}</code>
                    <button className="copy-link-btn" onClick={() => { navigator.clipboard.writeText(inviteSuccess.split('\n')[1]); alert('Link copied!'); }}>Copy</button>
                  </div>
                </div>
              )}
            </div>
            <div className="modal-actions">
              <button className="cancel-btn" onClick={closeInviteModal} disabled={inviteLoading}>Close</button>
              <button className="generate-btn" onClick={handleInviteStudent} disabled={inviteLoading || !inviteEmail.trim() || !!inviteSuccess}>
                {inviteLoading ? 'Creating...' : 'Create Invite'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Child Modal */}
      {showEditChildModal && editChild && (
        <div className="modal-overlay" onClick={closeEditChildModal}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Edit Child</h2>
            <p className="modal-desc">Update {editChild.full_name}'s profile information.</p>
            <div className="modal-form">
              <label>
                Name
                <input type="text" value={editChildName} onChange={(e) => setEditChildName(e.target.value)} placeholder="Child's name" disabled={editChildLoading} onKeyDown={(e) => e.key === 'Enter' && handleEditChild()} />
              </label>
              <label>
                Email
                <input type="email" value={editChildEmail} onChange={(e) => setEditChildEmail(e.target.value)} placeholder="child@example.com" disabled={editChildLoading} onKeyDown={(e) => e.key === 'Enter' && handleEditChild()} />
              </label>
              <label>
                Grade Level
                <select value={editChildGrade} onChange={(e) => setEditChildGrade(e.target.value)} disabled={editChildLoading}>
                  <option value="">Not set</option>
                  {Array.from({ length: 13 }, (_, i) => (
                    <option key={i} value={String(i)}>{i === 0 ? 'Kindergarten' : `Grade ${i}`}</option>
                  ))}
                </select>
              </label>
              <label>
                School
                <input type="text" value={editChildSchool} onChange={(e) => setEditChildSchool(e.target.value)} placeholder="e.g., Lincoln Elementary" disabled={editChildLoading} />
              </label>

              {/* Collapsible optional fields */}
              <div className="collapsible-section">
                <button type="button" className="collapsible-toggle" onClick={() => setEditChildOptionalOpen(!editChildOptionalOpen)}>
                  <span className={`collapsible-arrow ${editChildOptionalOpen ? 'open' : ''}`}>&#9656;</span>
                  Additional Details
                </button>
                {editChildOptionalOpen && (
                  <div className="collapsible-content">
                    <label>
                      Date of Birth
                      <input type="date" value={editChildDob} onChange={(e) => setEditChildDob(e.target.value)} disabled={editChildLoading} />
                    </label>
                    <label>
                      Phone
                      <input type="tel" value={editChildPhone} onChange={(e) => setEditChildPhone(e.target.value)} placeholder="e.g., 555-123-4567" disabled={editChildLoading} />
                    </label>
                    <label>
                      Address
                      <input type="text" value={editChildAddress} onChange={(e) => setEditChildAddress(e.target.value)} placeholder="Street address" disabled={editChildLoading} />
                    </label>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                      <label>
                        City
                        <input type="text" value={editChildCity} onChange={(e) => setEditChildCity(e.target.value)} placeholder="City" disabled={editChildLoading} />
                      </label>
                      <label>
                        Province
                        <input type="text" value={editChildProvince} onChange={(e) => setEditChildProvince(e.target.value)} placeholder="Province" disabled={editChildLoading} />
                      </label>
                    </div>
                    <label>
                      Postal Code
                      <input type="text" value={editChildPostal} onChange={(e) => setEditChildPostal(e.target.value)} placeholder="e.g., A1B 2C3" disabled={editChildLoading} />
                    </label>
                    <label>
                      Notes
                      <textarea value={editChildNotes} onChange={(e) => setEditChildNotes(e.target.value)} placeholder="Any additional notes about your child..." disabled={editChildLoading} rows={3} />
                    </label>
                  </div>
                )}
              </div>
              {editChildError && <p className="link-error">{editChildError}</p>}
            </div>
            <div className="modal-actions">
              <button className="cancel-btn" onClick={closeEditChildModal} disabled={editChildLoading}>Cancel</button>
              <button className="generate-btn" onClick={handleEditChild} disabled={editChildLoading || !editChildName.trim()}>
                {editChildLoading ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Day Detail Modal */}
      {dayModalDate && (
        <div className="modal-overlay" onClick={closeDayModal}>
          <div className="modal modal-lg" onClick={(e) => e.stopPropagation()}>
            <h2>{dayModalDate.toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}</h2>

            {/* Assignments for this day */}
            {(() => {
              const dk = dateKey(dayModalDate);
              const dayAssigns = calendarAssignments.filter(a => dateKey(a.dueDate) === dk && a.itemType !== 'task');
              return dayAssigns.length > 0 ? (
                <div className="day-modal-section">
                  <div className="day-modal-section-title">Assignments</div>
                  <div className="day-modal-list">
                    {dayAssigns.map(a => (
                      <div key={a.id} className="day-modal-item">
                        <span className="cal-entry-dot" style={{ background: a.courseColor }} />
                        <div className="day-modal-item-info">
                          <span className="day-modal-item-title">{a.title}</span>
                          <span className="day-modal-item-meta">{a.courseName}{a.childName ? ` \u2022 ${a.childName}` : ''}</span>
                        </div>
                        <div className="day-modal-item-actions">
                          {a.courseId > 0 && <button className="day-modal-action-btn" onClick={() => { closeDayModal(); handleGoToCourse(a.courseId); }}>Class</button>}
                          <button className="day-modal-study-btn" disabled={generatingStudyId === a.id} onClick={() => { closeDayModal(); handleOneClickStudy(a); }}>{generatingStudyId === a.id ? 'Checking...' : 'Study'}</button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null;
            })()}

            {/* Tasks for this day */}
            <div className="day-modal-section">
              <div className="day-modal-section-title">Tasks</div>
              <div className="day-modal-list">
                {dayTasks.length === 0 && (
                  <div className="day-modal-empty">No tasks for this day</div>
                )}
                {dayTasks.map(task => {
                  const isExpanded = expandedTaskId === task.id;
                  const priorityClass = task.priority || 'medium';
                  return (
                    <div
                      key={task.id}
                      className={`task-sticky-note ${priorityClass}${task.is_completed ? ' completed' : ''}`}
                      onClick={() => setExpandedTaskId(prev => prev === task.id ? null : task.id)}
                    >
                      <div className="task-sticky-header">
                        <input
                          type="checkbox"
                          checked={task.is_completed}
                          onChange={(e) => { e.stopPropagation(); handleToggleTask(task); }}
                          className="task-checkbox"
                        />
                        <div className="task-sticky-body">
                          <span className={`task-sticky-title${task.is_completed ? ' completed' : ''}`}>{task.title}</span>
                          <span className="task-sticky-meta">
                            <span className={`task-priority-badge ${priorityClass}`} aria-label={`Priority: ${priorityClass}`}>{priorityClass === 'high' ? '\u25B2 ' : priorityClass === 'low' ? '\u25BC ' : '\u25CF '}{priorityClass}</span>
                            {task.assignee_name && <span className="task-sticky-assignee">&rarr; {task.assignee_name}</span>}
                          </span>
                        </div>
                        <button className="task-delete-btn" onClick={(e) => { e.stopPropagation(); handleDeleteTask(task.id); }} title="Archive task" aria-label="Delete this task">&times;</button>
                      </div>
                      {isExpanded && (
                        <div className="task-sticky-detail">
                          {task.description && <p className="task-sticky-desc">{task.description}</p>}
                          <div className="task-sticky-detail-row">
                            {task.due_date && <span>Due: {new Date(task.due_date).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</span>}
                            {task.creator_name && <span>Created by: {task.creator_name}</span>}
                            {task.category && <span>Category: {task.category}</span>}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
              <div className="day-modal-add-task">
                <input
                  type="text"
                  value={newTaskTitle}
                  onChange={(e) => setNewTaskTitle(e.target.value)}
                  placeholder="Add a task..."
                  onKeyDown={(e) => e.key === 'Enter' && handleCreateDayTask()}
                  disabled={newTaskCreating}
                />
                <button onClick={handleCreateDayTask} disabled={newTaskCreating || !newTaskTitle.trim()} className="generate-btn">
                  {newTaskCreating ? '...' : 'Add'}
                </button>
              </div>
            </div>

            <div className="modal-actions">
              <button className="cancel-btn" onClick={closeDayModal}>Close</button>
            </div>
          </div>
        </div>
      )}

      {/* Task Detail Modal */}
      {taskDetailModal && (
        <div className="modal-overlay" onClick={() => setTaskDetailModal(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>{taskDetailModal.title}</h2>
            <div className="task-detail-modal-body">
              {taskDetailModal.description && (
                <p className="task-detail-desc">{taskDetailModal.description}</p>
              )}
              <div className="task-detail-fields">
                <div className="task-detail-row">
                  <span className="task-detail-label">Status</span>
                  <span className={`sdp-task-badge ${taskDetailModal.is_completed ? 'completed' : 'pending'}`}>
                    {taskDetailModal.is_completed ? 'Completed' : 'Pending'}
                  </span>
                </div>
                {taskDetailModal.due_date && (
                  <div className="task-detail-row">
                    <span className="task-detail-label">Due Date</span>
                    <span>{new Date(taskDetailModal.due_date).toLocaleDateString(undefined, { weekday: 'short', month: 'long', day: 'numeric', year: 'numeric' })}</span>
                  </div>
                )}
                {taskDetailModal.priority && (
                  <div className="task-detail-row">
                    <span className="task-detail-label">Priority</span>
                    <span className={`task-priority-badge ${taskDetailModal.priority}`}>{taskDetailModal.priority}</span>
                  </div>
                )}
                {taskDetailModal.assignee_name && (
                  <div className="task-detail-row">
                    <span className="task-detail-label">Assigned To</span>
                    <span>{taskDetailModal.assignee_name}</span>
                  </div>
                )}
                {taskDetailModal.creator_name && (
                  <div className="task-detail-row">
                    <span className="task-detail-label">Created By</span>
                    <span>{taskDetailModal.creator_name}</span>
                  </div>
                )}
                {taskDetailModal.course_name && (
                  <div className="task-detail-row">
                    <span className="task-detail-label">Class</span>
                    <span>{taskDetailModal.course_name}</span>
                  </div>
                )}
                {taskDetailModal.category && (
                  <div className="task-detail-row">
                    <span className="task-detail-label">Category</span>
                    <span>{taskDetailModal.category}</span>
                  </div>
                )}
              </div>
            </div>
            <div className="modal-actions">
              <button className="cancel-btn" onClick={() => setTaskDetailModal(null)}>Close</button>
              <button
                className="generate-btn view-details-btn"
                onClick={() => {
                  setTaskDetailModal(null);
                  navigate(`/tasks/${taskDetailModal.id}`);
                }}
              >
                View Details
              </button>
              <button
                className="generate-btn"
                onClick={() => {
                  handleToggleTask(taskDetailModal);
                  setTaskDetailModal({ ...taskDetailModal, is_completed: !taskDetailModal.is_completed });
                }}
              >
                {taskDetailModal.is_completed ? 'Mark Incomplete' : 'Mark Complete'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Study Tools Modal */}
      <CreateStudyMaterialModal
        open={showStudyModal}
        onClose={resetStudyModal}
        onGenerate={handleGenerateFromModal}
        isGenerating={isGenerating}
        initialTitle={studyModalInitialTitle}
        initialContent={studyModalInitialContent}
        duplicateCheck={duplicateCheck}
        onViewExisting={() => {
          const guide = duplicateCheck?.existing_guide;
          if (guide) {
            resetStudyModal();
            navigate(guide.guide_type === 'quiz' ? `/study/quiz/${guide.id}` : guide.guide_type === 'flashcards' ? `/study/flashcards/${guide.id}` : `/study/guide/${guide.id}`);
          }
        }}
        onRegenerate={() => handleGenerateFromModal({
          title: studyModalInitialTitle,
          content: studyModalInitialContent,
          types: ['study_guide'],
          mode: 'text',
        })}
        onDismissDuplicate={() => setDuplicateCheck(null)}
      />
      {/* Create Task Modal (quick action) */}
      <CreateTaskModal
        open={showCreateTaskModal}
        onClose={() => setShowCreateTaskModal(false)}
        onCreated={() => { setShowCreateTaskModal(false); loadDashboard(); }}
      />
      {confirmModal}
    </DashboardLayout>
  );
}

