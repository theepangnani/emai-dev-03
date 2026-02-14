import { useState, useEffect, useRef, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { parentApi, googleApi, invitesApi, studyApi, tasksApi } from '../api/client';
import { queueStudyGeneration } from './StudyGuidesPage';
import type { ChildSummary, ChildOverview, ParentDashboardData, DiscoveredChild, SupportedFormats, DuplicateCheckResponse, TaskItem, InviteResponse } from '../api/client';
import { DashboardLayout } from '../components/DashboardLayout';
import { PageSkeleton } from '../components/Skeleton';
import { CalendarView } from '../components/calendar/CalendarView';
import type { CalendarAssignment } from '../components/calendar/types';
import { getCourseColor, dateKey, TASK_PRIORITY_COLORS } from '../components/calendar/types';
import { useConfirm } from '../components/ConfirmModal';
import './ParentDashboard.css';

const MAX_FILE_SIZE_MB = 100;

type LinkTab = 'create' | 'email' | 'google';
type DiscoveryState = 'idle' | 'discovering' | 'results' | 'no_results';

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

  // Dashboard summary data (from single API call)
  const [dashboardData, setDashboardData] = useState<ParentDashboardData | null>(null);

  // Collapsible calendar (default expanded; user can collapse and preference is saved)
  const [calendarCollapsed, setCalendarCollapsed] = useState(() => {
    try {
      const saved = localStorage.getItem('calendar_collapsed');
      return saved === '1';
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

  // Study tools modal state
  const [showStudyModal, setShowStudyModal] = useState(false);
  const [studyTitle, setStudyTitle] = useState('');
  const [studyContent, setStudyContent] = useState('');
  const [studyType, setStudyType] = useState<'study_guide' | 'quiz' | 'flashcards'>('study_guide');
  const [studyMode, setStudyMode] = useState<'text' | 'file'>('text');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isGenerating] = useState(false);
  const [studyError, setStudyError] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [supportedFormats, setSupportedFormats] = useState<SupportedFormats | null>(null);
  const [duplicateCheck, setDuplicateCheck] = useState<DuplicateCheckResponse | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

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
      // Failed to load dashboard
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
    setBulkLinking(true);
    setLinkError('');
    try {
      await parentApi.linkChildrenBulk(Array.from(selectedDiscovered));
      closeLinkModal();
      await loadDashboard();
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
    setCreateChildName('');
    setCreateChildEmail('');
    setCreateChildRelationship('guardian');
    setCreateChildError('');
    setCreateChildInviteLink('');
  };

  // ============================================
  // Edit Child Handlers
  // ============================================

  const openEditChild = (child: ChildSummary) => {
    setEditChild(child);
    setEditChildName(child.full_name);
    setEditChildEmail(child.email || '');
    setEditChildGrade(child.grade_level != null ? String(child.grade_level) : '');
    setEditChildSchool(child.school_name || '');
    setEditChildDob(child.date_of_birth || '');
    setEditChildPhone(child.phone || '');
    setEditChildAddress(child.address || '');
    setEditChildCity(child.city || '');
    setEditChildProvince(child.province || '');
    setEditChildPostal(child.postal_code || '');
    setEditChildNotes(child.notes || '');
    setEditChildError('');
    // Auto-expand optional section if any optional field has data
    const hasOptionalData = !!(child.date_of_birth || child.phone || child.address || child.city || child.province || child.postal_code || child.notes);
    setEditChildOptionalOpen(hasOptionalData);
    setShowEditChildModal(true);
  };

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

  useEffect(() => {
    if (showStudyModal && !supportedFormats) {
      studyApi.getSupportedFormats().then(setSupportedFormats).catch(() => {});
    }
  }, [showStudyModal, supportedFormats]);

  const handleFileSelect = (file: File) => {
    if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      setStudyError(`File size exceeds ${MAX_FILE_SIZE_MB} MB limit`);
      return;
    }
    setSelectedFile(file);
    setStudyMode('file');
    if (!studyTitle) {
      setStudyTitle(file.name.replace(/\.[^/.]+$/, ''));
    }
  };

  const handleDragOver = (e: React.DragEvent) => { e.preventDefault(); setIsDragging(true); };
  const handleDragLeave = (e: React.DragEvent) => { e.preventDefault(); setIsDragging(false); };
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileSelect(file);
  };
  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFileSelect(file);
  };
  const clearFileSelection = () => {
    setSelectedFile(null);
    setStudyMode('text');
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const resetStudyModal = () => {
    setShowStudyModal(false);
    setStudyTitle('');
    setStudyContent('');
    setStudyType('study_guide');
    setStudyMode('text');
    setSelectedFile(null);
    setStudyError('');
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleGenerateStudy = async () => {
    if (studyMode === 'file' && !selectedFile) { setStudyError('Please select a file'); return; }
    if (studyMode === 'text' && !studyContent.trim()) { setStudyError('Please enter content'); return; }

    if (!duplicateCheck && !await confirm({ title: 'Generate Study Material', message: `Generate ${studyType.replace('_', ' ')}? This will use AI credits.`, confirmLabel: 'Generate' })) return;

    if (studyMode === 'text' && !duplicateCheck) {
      try {
        const dupResult = await studyApi.checkDuplicate({ title: studyTitle || undefined, guide_type: studyType });
        if (dupResult.exists) { setDuplicateCheck(dupResult); return; }
      } catch { /* Continue */ }
    }
    // Queue generation and navigate to study guides page (non-blocking)
    queueStudyGeneration({
      title: studyTitle || `New ${studyType.replace('_', ' ')}`,
      content: studyContent,
      type: studyType,
      mode: studyMode,
      file: selectedFile ?? undefined,
      regenerateId: duplicateCheck?.existing_guide?.id,
    });
    setDuplicateCheck(null);
    resetStudyModal();
    navigate('/course-materials');
  };

  // ============================================
  // Tasks & Day Detail Modal
  // ============================================

  const selectedChildUserId = useMemo(() => {
    if (!selectedChild) return null;
    return children.find(c => c.student_id === selectedChild)?.user_id ?? null;
  }, [selectedChild, children]);

  // Tasks are loaded from the dashboard API call.
  // When a specific child is selected, filter tasks client-side.
  const filteredTasks = useMemo(() => {
    if (!selectedChildUserId) return allTasks;
    return allTasks.filter(t =>
      t.assigned_to_user_id === selectedChildUserId ||
      t.created_by_user_id === selectedChildUserId
    );
  }, [allTasks, selectedChildUserId]);

  // Compute overdue/due-today counts from filtered tasks (respects child filter)
  // Uses local time to match TasksPage filter logic
  const { taskOverdueCount, taskDueTodayCount } = useMemo(() => {
    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const todayEnd = new Date(todayStart);
    todayEnd.setDate(todayEnd.getDate() + 1);
    let overdue = 0;
    let dueToday = 0;
    for (const t of filteredTasks) {
      if (t.is_completed || t.archived_at || !t.due_date) continue;
      const due = new Date(t.due_date);
      if (due < todayStart) overdue++;
      else if (due >= todayStart && due < todayEnd) dueToday++;
    }
    return { taskOverdueCount: overdue, taskDueTodayCount: dueToday };
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
        setStudyTitle(assignment.title);
        setStudyContent('');
        setShowStudyModal(true);
        return;
      }
      queueStudyGeneration({
        title: assignment.title,
        content: assignment.description,
        type: 'study_guide',
        mode: 'text',
      });
      navigate('/course-materials');
    } catch {
      // On error, fall back to the modal
      setStudyTitle(assignment.title);
      setStudyContent(assignment.description || '');
      setShowStudyModal(true);
    } finally {
      setGeneratingStudyId(null);
    }
  };

  const handleGoToCourse = (courseId: number) => {
    navigate(`/courses?highlight=${courseId}`);
  };

  const handleViewStudyGuides = () => {
    navigate('/course-materials');
  };

  // ============================================
  // Render
  // ============================================

  if (loading) {
    return (
      <DashboardLayout welcomeSubtitle="Monitor your child's progress">
        <PageSkeleton />
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout
      welcomeSubtitle="Monitor your child's progress"
      sidebarActions={[
        { label: '+ Add Child', onClick: () => setShowLinkModal(true) },
        { label: '+ Create Course Material', onClick: () => setShowStudyModal(true) },
      ]}
    >
      {children.length === 0 ? (
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
            {children.map((child) => (
              <div key={child.student_id} className="child-tab-wrapper">
                <button
                  className={`child-tab ${selectedChild === child.student_id ? 'active' : ''}`}
                  onClick={() => handleChildTabClick(child.student_id)}
                >
                  {child.full_name}
                  {child.grade_level != null && <span className="grade-badge">Grade {child.grade_level}</span>}
                </button>
                <button
                  className="child-edit-btn"
                  onClick={(e) => { e.stopPropagation(); openEditChild(child); }}
                  title="Edit child info"
                >
                  &#9998;
                </button>
              </div>
            ))}
          </div>

          {/* Status Summary Cards */}
          {dashboardData && (
            <div className="status-summary">
              <div
                className={`status-card${taskOverdueCount > 0 ? ' urgent' : ''}`}
                onClick={() => navigate('/tasks?due=overdue')}
              >
                <span className="status-card-count">{taskOverdueCount}</span>
                <span className="status-card-label">Overdue</span>
              </div>
              <div
                className={`status-card${taskDueTodayCount > 0 ? ' active' : ''}`}
                onClick={() => navigate('/tasks?due=today')}
              >
                <span className="status-card-count">{taskDueTodayCount}</span>
                <span className="status-card-label">Due Today</span>
              </div>
              <div
                className={`status-card${dashboardData.unread_messages > 0 ? ' notify' : ''}`}
                onClick={() => navigate('/messages')}
              >
                <span className="status-card-count">{dashboardData.unread_messages}</span>
                <span className="status-card-label">Messages</span>
              </div>
              <div className="status-card" onClick={() => navigate('/tasks')}>
                <span className="status-card-count">{dashboardData.total_tasks}</span>
                <span className="status-card-label">Total Tasks</span>
              </div>
            </div>
          )}

          {/* Per-Child Highlights */}
          {dashboardData && dashboardData.child_highlights.length > 1 && (
            <div className="child-highlights">
              {dashboardData.child_highlights.map(h => (
                <div
                  key={h.student_id}
                  className="child-highlight-card"
                  onClick={() => {
                    setSelectedChild(prev => prev === h.student_id ? null : h.student_id);
                  }}
                >
                  <div className="child-highlight-header">
                    <span className="child-highlight-name">{h.full_name}</span>
                    {h.grade_level != null && <span className="grade-badge">Grade {h.grade_level}</span>}
                  </div>
                  <div className="child-highlight-stats">
                    {h.overdue_count > 0 && (
                      <span className="child-stat overdue">{h.overdue_count} overdue</span>
                    )}
                    {h.due_today_count > 0 && (
                      <span className="child-stat due-today">{h.due_today_count} due today</span>
                    )}
                    {h.overdue_count === 0 && h.due_today_count === 0 && (
                      <span className="child-stat all-clear">All caught up</span>
                    )}
                    <span className="child-stat courses">{h.courses.length} course{h.courses.length !== 1 ? 's' : ''}</span>
                  </div>
                  {h.overdue_items.length > 0 && (
                    <div className="child-highlight-items">
                      {h.overdue_items.slice(0, 3).map((item, i) => (
                        <div key={i} className="child-highlight-item overdue">
                          <span className="child-highlight-item-title">{item.title}</span>
                          <span className="child-highlight-item-course">{item.course_name}</span>
                        </div>
                      ))}
                      {h.overdue_items.length > 3 && (
                        <span className="child-highlight-more">+{h.overdue_items.length - 3} more</span>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Pending Invites */}
          {pendingInvites.length > 0 && (
            <div className="pending-invites-section">
              <h3>Pending Invites</h3>
              {pendingInvites.map(inv => (
                <div key={inv.id} className="pending-invite-row">
                  <span className="pending-invite-email">{inv.email}</span>
                  <span className="pending-invite-type">{inv.invite_type}</span>
                  <button
                    className="btn-sm"
                    disabled={resendingId === inv.id}
                    onClick={() => handleResendInvite(inv.id)}
                  >
                    {resendingId === inv.id ? 'Sending...' : 'Resend'}
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Quick Actions Above Calendar */}
          <div className="calendar-actions-bar">
            <button className="btn-accent-outline" onClick={() => setShowStudyModal(true)}>
              + Create Course Material
            </button>
            <button className="btn-accent-outline" onClick={() => navigate('/course-materials')}>
              View Course Materials
            </button>
          </div>

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
                  <div className="google-connect-prompt">
                    <div className="google-icon">✓</div>
                    <h3>Google Account Connected</h3>
                    <p>Search your Google Classroom courses to find your children's student accounts.</p>
                    <button className="google-connect-btn" onClick={triggerDiscovery}>Search Google Classroom</button>
                    <button className="cancel-btn" style={{ marginTop: '8px', fontSize: '13px' }} onClick={async () => { try { await googleApi.disconnect(); setGoogleConnected(false); } catch { setLinkError('Failed to disconnect Google account'); } }}>
                      Disconnect Google
                    </button>
                    {linkError && <p className="link-error">{linkError}</p>}
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
                    <p className="modal-desc">
                      Found {discoveredChildren.length} student{discoveredChildren.length !== 1 ? 's' : ''} across {coursesSearched} course{coursesSearched !== 1 ? 's' : ''}. Select the children you want to link:
                    </p>
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
                    <div className="modal-actions">
                      <button className="cancel-btn" onClick={closeLinkModal} disabled={bulkLinking}>Cancel</button>
                      <button className="generate-btn" onClick={handleBulkLink} disabled={bulkLinking || selectedDiscovered.size === 0}>
                        {bulkLinking ? 'Linking...' : `Link ${selectedDiscovered.size} Selected`}
                      </button>
                    </div>
                  </div>
                )}
                {discoveryState === 'no_results' && (
                  <div className="google-connect-prompt">
                    <div className="google-icon">📭</div>
                    <h3>No Matching Students Found</h3>
                    <p>We searched {coursesSearched} Google Classroom course{coursesSearched !== 1 ? 's' : ''} but didn't find any matching student accounts.</p>
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
                          {a.courseId > 0 && <button className="day-modal-action-btn" onClick={() => { closeDayModal(); handleGoToCourse(a.courseId); }}>Course</button>}
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
                            <span className={`task-priority-badge ${priorityClass}`}>{priorityClass}</span>
                            {task.assignee_name && <span className="task-sticky-assignee">&rarr; {task.assignee_name}</span>}
                          </span>
                        </div>
                        <button className="task-delete-btn" onClick={(e) => { e.stopPropagation(); handleDeleteTask(task.id); }} title="Archive task">&times;</button>
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

      {/* Study Tools Modal */}
      {showStudyModal && (
        <div className="modal-overlay" onClick={resetStudyModal}>
          <div className="modal modal-lg" onClick={(e) => e.stopPropagation()}>
            <h2>Create Study Material</h2>
            <p className="modal-desc">Upload a document or photo, or paste text to generate AI-powered study materials.</p>
            <div className="modal-form">
              <label>
                What to create
                <select value={studyType} onChange={(e) => setStudyType(e.target.value as any)} disabled={isGenerating}>
                  <option value="study_guide">Study Guide</option>
                  <option value="quiz">Practice Quiz</option>
                  <option value="flashcards">Flashcards</option>
                </select>
              </label>
              <label>
                Title (optional)
                <input type="text" value={studyTitle} onChange={(e) => setStudyTitle(e.target.value)} placeholder="e.g., Chapter 5 Review" disabled={isGenerating} />
              </label>
              <div className="mode-toggle">
                <button className={`mode-btn ${studyMode === 'text' ? 'active' : ''}`} onClick={() => setStudyMode('text')} disabled={isGenerating}>Paste Text</button>
                <button className={`mode-btn ${studyMode === 'file' ? 'active' : ''}`} onClick={() => setStudyMode('file')} disabled={isGenerating}>Upload File</button>
              </div>
              {studyMode === 'text' ? (
                <label>
                  Content to study
                  <textarea value={studyContent} onChange={(e) => setStudyContent(e.target.value)} placeholder="Paste notes, textbook content, or any study material..." rows={8} disabled={isGenerating} />
                </label>
              ) : (
                <div className="file-upload-section">
                  <input ref={fileInputRef} type="file" onChange={handleFileInputChange} accept=".pdf,.docx,.doc,.txt,.md,.xlsx,.xls,.csv,.pptx,.ppt,.png,.jpg,.jpeg,.gif,.bmp,.tiff,.webp,.zip" style={{ display: 'none' }} disabled={isGenerating} />
                  <div className={`drop-zone ${isDragging ? 'dragging' : ''} ${selectedFile ? 'has-file' : ''}`} onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop} onClick={() => !isGenerating && fileInputRef.current?.click()}>
                    {selectedFile ? (
                      <div className="selected-file">
                        <span className="file-icon">📄</span>
                        <div className="file-info">
                          <span className="file-name">{selectedFile.name}</span>
                          <span className="file-size">{(selectedFile.size / 1024 / 1024).toFixed(2)} MB</span>
                        </div>
                        <button className="clear-file-btn" onClick={(e) => { e.stopPropagation(); clearFileSelection(); }} disabled={isGenerating}>✕</button>
                      </div>
                    ) : (
                      <div className="drop-zone-content">
                        <span className="upload-icon">📁</span>
                        <p>Drag & drop a file here, or click to browse</p>
                        <small>Supports: PDF, Word, Excel, PowerPoint, Images (photos), Text, ZIP</small>
                      </div>
                    )}
                  </div>
                </div>
              )}
              {studyError && <p className="link-error">{studyError}</p>}
            </div>
            {duplicateCheck && duplicateCheck.exists && (
              <div className="duplicate-warning">
                <p>{duplicateCheck.message}</p>
                <div className="duplicate-actions">
                  <button className="generate-btn" onClick={() => { const guide = duplicateCheck.existing_guide!; resetStudyModal(); setDuplicateCheck(null); navigate(guide.guide_type === 'quiz' ? `/study/quiz/${guide.id}` : guide.guide_type === 'flashcards' ? `/study/flashcards/${guide.id}` : `/study/guide/${guide.id}`); }}>View Existing</button>
                  <button className="generate-btn" onClick={handleGenerateStudy}>Regenerate (New Version)</button>
                  <button className="cancel-btn" onClick={() => setDuplicateCheck(null)}>Cancel</button>
                </div>
              </div>
            )}
            <div className="modal-actions">
              <button className="cancel-btn" onClick={() => { resetStudyModal(); setDuplicateCheck(null); }} disabled={isGenerating}>Cancel</button>
              <button className="generate-btn" onClick={handleGenerateStudy} disabled={isGenerating || (studyMode === 'file' ? !selectedFile : !studyContent.trim())}>
                {isGenerating ? 'Generating...' : 'Generate'}
              </button>
            </div>
          </div>
        </div>
      )}
      {confirmModal}
    </DashboardLayout>
  );
}
