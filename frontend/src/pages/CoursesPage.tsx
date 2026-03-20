import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { parentApi, coursesApi, courseContentsApi, googleApi } from '../api/client';
import type { ChildSummary, ChildOverview, CourseContentItem } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { DashboardLayout } from '../components/DashboardLayout';
import { useConfirm } from '../components/ConfirmModal';
import { useToast } from '../components/Toast';
import { useFocusTrap } from '../hooks/useFocusTrap';
import { isValidEmail } from '../utils/validation';
import { SearchableSelect, MultiSearchableSelect } from '../components/SearchableSelect';
import type { SearchableOption } from '../components/SearchableSelect';
import CreateClassModal from '../components/CreateClassModal';
import { getCourseColor } from '../components/calendar/types';
import { PageSkeleton, CardSkeleton } from '../components/Skeleton';
import { PageNav } from '../components/PageNav';
import EmptyState from '../components/EmptyState';
import { GoogleClassroomPrompt } from '../components/GoogleClassroomPrompt';
import { AddActionButton } from '../components/AddActionButton';
import '../components/AddActionButton.css';
import './CoursesPage.css';

const CHILD_COLORS = [
  '#8b5cf6', '#ec4899', '#14b8a6', '#f59e0b',
  '#3b82f6', '#ef4444', '#10b981', '#6366f1',
];

interface CourseItem {
  id: number;
  name: string;
  description: string | null;
  subject: string | null;
  created_at: string;
  google_classroom_id?: string | null;
  classroom_type?: string | null;
  teacher_name?: string | null;
  teacher_id?: number | null;
  is_private?: boolean;
  require_approval?: boolean;
}

type SyncState = 'idle' | 'syncing' | 'done' | 'error';

function formatTimeAgo(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}

// Helper for keyboard accessibility
const handleKeyDown = (e: React.KeyboardEvent, callback: () => void) => {
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault();
    callback();
  }
};

export function CoursesPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { user } = useAuth();
  const { confirm, confirmModal } = useConfirm();
  const { toast } = useToast();
  const isParent = user?.role === 'parent';
  const isStudent = user?.role === 'student';
  const urlStudentId = searchParams.get('student_id');

  // Student self-enrollment state
  const [enrolledCourses, setEnrolledCourses] = useState<CourseItem[]>([]);
  const [availableCourses, setAvailableCourses] = useState<CourseItem[]>([]);
  const [studentTab, setStudentTab] = useState<'enrolled' | 'browse'>(() => {
    const tab = searchParams.get('tab');
    return tab === 'browse' ? 'browse' : 'enrolled';
  });
  const [enrollingId, setEnrollingId] = useState<number | null>(null);
  const [pendingCourseIds, setPendingCourseIds] = useState<Set<number>>(new Set());
    const [classroomTypeFilter, setClassroomTypeFilter] = useState("");

  // Browse search filters (server-side)
  const [browseSearch, setBrowseSearch] = useState('');
  const [browseSubject, setBrowseSubject] = useState('');
  const [browseTeacher, setBrowseTeacher] = useState('');
  const [browseLoading, setBrowseLoading] = useState(false);

  // Parent-specific state
  const [children, setChildren] = useState<ChildSummary[]>([]);
  const [selectedChild, setSelectedChild] = useState<number | null>(null);
  const [childOverview, setChildOverview] = useState<ChildOverview | null>(null);
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [googleConnected, setGoogleConnected] = useState(false);
  const [syncState, setSyncState] = useState<SyncState>('idle');
  const [syncMessage, setSyncMessage] = useState('');
  const [lastSynced, setLastSynced] = useState<Date | null>(null);

  // Shared state
  const [myCourses, setMyCourses] = useState<CourseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [actionError, setActionError] = useState('');

  // Inline course content expansion
  const [expandedCourseId, setExpandedCourseId] = useState<number | null>(null);
  const [expandedContents, setExpandedContents] = useState<CourseContentItem[]>([]);
  const [expandedLoading, setExpandedLoading] = useState(false);

  // Create course modal
  const [showCreateModal, setShowCreateModal] = useState(() => searchParams.get('create') === '1');
  const [courseName, setCourseName] = useState('');
  const [courseSubject, setCourseSubject] = useState('');
  const [courseDescription, setCourseDescription] = useState('');
  const [courseRequireApproval, setCourseRequireApproval] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState('');
  const [selectedTeacher, setSelectedTeacher] = useState<SearchableOption | null>(null);
  const [selectedStudents, setSelectedStudents] = useState<SearchableOption[]>([]);
  const [showCreateTeacher, setShowCreateTeacher] = useState(false);
  const [newTeacherName, setNewTeacherName] = useState('');
  const [newTeacherEmail, setNewTeacherEmail] = useState('');
  const [wizardStep, setWizardStep] = useState(1);
  const [showAddChildModal, setShowAddChildModal] = useState(false);
  const [addChildTab, setAddChildTab] = useState<'create' | 'email'>('create');
  const [addChildName, setAddChildName] = useState('');
  const [addChildEmail, setAddChildEmail] = useState('');
  const [addChildRelationship, setAddChildRelationship] = useState('guardian');
  const [addChildLoading, setAddChildLoading] = useState(false);
  const [addChildError, setAddChildError] = useState('');
  const [addChildInviteLink, setAddChildInviteLink] = useState('');

  // Assign course modal (parent only)
  const [showAssignModal, setShowAssignModal] = useState(false);
  const [selectedCoursesForAssign, setSelectedCoursesForAssign] = useState<Set<number>>(new Set());
  const [assignLoading, setAssignLoading] = useState(false);

  // Collapsible sections
  const [childCoursesExpanded, setChildCoursesExpanded] = useState(true);
  const [myCoursesExpanded, setMyCoursesExpanded] = useState(true);

  // Edit course modal
  const [editCourse, setEditCourse] = useState<CourseItem | null>(null);
  const [editCourseName, setEditCourseName] = useState('');
  const [editCourseSubject, setEditCourseSubject] = useState('');
  const [editCourseDescription, setEditCourseDescription] = useState('');
  const [editCourseRequireApproval, setEditCourseRequireApproval] = useState(false);
  const [editCourseTeacher, setEditCourseTeacher] = useState<SearchableOption | null>(null);
  const [editCourseStudents, setEditCourseStudents] = useState<SearchableOption[]>([]);
  const [editCourseOriginalStudents, setEditCourseOriginalStudents] = useState<SearchableOption[]>([]);
  const [editStudentIdMap, setEditStudentIdMap] = useState<Record<number, number>>({});
  const [editCourseLoading, setEditCourseLoading] = useState(false);
  const [editCourseError, setEditCourseError] = useState('');

  // Edit content modal
  const [editContent, setEditContent] = useState<CourseContentItem | null>(null);
  const [editContentTitle, setEditContentTitle] = useState('');
  const [editContentDescription, setEditContentDescription] = useState('');
  const [editContentType, setEditContentType] = useState('');
  const [editContentLoading, setEditContentLoading] = useState(false);
  const [editContentError, setEditContentError] = useState('');
  const createModalRef = useFocusTrap<HTMLDivElement>(showCreateModal);
  const assignModalRef = useFocusTrap<HTMLDivElement>(showAssignModal, () => setShowAssignModal(false));
  const editCourseModalRef = useFocusTrap<HTMLDivElement>(!!editCourse);
  const editContentModalRef = useFocusTrap<HTMLDivElement>(!!editContent);
  const addChildModalRef = useFocusTrap<HTMLDivElement>(showAddChildModal);

  useEffect(() => {
    loadData();
    const timeout = setTimeout(() => {
      setLoading(prev => {
        if (prev) setLoadError(true);
        return false;
      });
    }, 15000);
    return () => clearTimeout(timeout);
  }, []);

  useEffect(() => {
    if (selectedChild) {
      loadChildOverview(selectedChild);
    } else if (children.length > 0) {
      loadAllChildrenCourses();
    }
  }, [selectedChild]);

  // Persist selected child to sessionStorage for cross-page consistency
  useEffect(() => {
    if (selectedChild && children.length > 0) {
      const child = children.find(c => c.student_id === selectedChild);
      if (child) sessionStorage.setItem('selectedChildId', String(child.user_id));
    }
  }, [selectedChild, children]);

  // Debounced server-side browse search
  useEffect(() => {
    if (!isStudent || studentTab !== 'browse') return;
    setBrowseLoading(true);
    const timer = setTimeout(async () => {
      try {
        const params: Record<string, string> = {};
        if (browseSearch.trim()) params.search = browseSearch.trim();
        if (browseSubject.trim()) params.subject = browseSubject.trim();
        if (browseTeacher.trim()) params.teacher_name = browseTeacher.trim();
        const results = await coursesApi.browse(params);
        setAvailableCourses(results);
        // Check pending status for require_approval courses
        const approvalCourses = results.filter((c: CourseItem) => c.require_approval);
        if (approvalCourses.length > 0) {
          const courseIds = approvalCourses.map((c: CourseItem) => c.id);
          const statusMap = await coursesApi.enrollmentStatusBatch(courseIds);
          const pending = new Set<number>(
            courseIds.filter((id: number) => statusMap[String(id)]?.status === 'pending')
          );
          setPendingCourseIds(pending);
        }
      } catch {
        // Fall back silently; user can retry
      } finally {
        setBrowseLoading(false);
      }
    }, 350);
    return () => clearTimeout(timer);
  }, [browseSearch, browseSubject, browseTeacher, studentTab, isStudent]);

  const loadData = async () => {
    setLoadError(false);
    try {
      if (isParent) {
        const [childrenData, courses] = await Promise.all([
          parentApi.getChildren(),
          coursesApi.createdByMe(),
        ]);
        setChildren(childrenData);
        setMyCourses(courses);
        if (childrenData.length > 0) {
          const urlSid = urlStudentId ? Number(urlStudentId) : null;
          const match = urlSid ? childrenData.find(c => c.student_id === urlSid) : null;
          if (match) {
            setSelectedChild(match.student_id);
          } else {
            const storedUserId = sessionStorage.getItem('selectedChildId');
            const storedMatch = storedUserId ? childrenData.find(c => c.user_id === Number(storedUserId)) : null;
            setSelectedChild(storedMatch ? storedMatch.student_id : childrenData[0].student_id);
          }
        }
        try {
          const status = await googleApi.getStatus();
          setGoogleConnected(status.connected);
        } catch { /* ignore */ }
      } else if (isStudent) {
        // Student: load enrolled courses + created courses; browse courses loaded by browse effect
        const [enrolled, created] = await Promise.all([
          coursesApi.enrolledByMe(),
          coursesApi.createdByMe(),
        ]);
        setEnrolledCourses(enrolled);
        setMyCourses(created);
      } else {
        // Teacher/Admin: show all visible courses
        const courses = await coursesApi.list();
        setMyCourses(courses);
      }
    } catch {
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  };

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

  const loadAllChildrenCourses = async () => {
    setOverviewLoading(true);
    try {
      const overviews = await Promise.all(
        children.map(c => parentApi.getChildOverview(c.student_id))
      );
      const seen = new Set<number>();
      const allCourses = overviews.flatMap(o => o.courses).filter(c => {
        if (seen.has(c.id)) return false;
        seen.add(c.id);
        return true;
      });
      setChildOverview({
        student_id: 0,
        user_id: 0,
        full_name: '',
        grade_level: null,
        google_connected: false,
        courses: allCourses,
        assignments: [],
        study_guides_count: 0,
      });
    } catch {
      setChildOverview(null);
    } finally {
      setOverviewLoading(false);
    }
  };

  const CONTENT_TYPE_LABELS: Record<string, string> = {
    notes: 'Notes', syllabus: 'Syllabus', labs: 'Labs',
    assignments: 'Assignments', readings: 'Readings', resources: 'Resources', other: 'Other',
  };

  const toggleCourseExpand = async (courseId: number) => {
    if (expandedCourseId === courseId) {
      setExpandedCourseId(null);
      return;
    }
    setExpandedCourseId(courseId);
    setExpandedLoading(true);
    try {
      const contents = await courseContentsApi.list(courseId);
      setExpandedContents(contents);
    } catch {
      setExpandedContents([]);
    } finally {
      setExpandedLoading(false);
    }
  };

  const handleSearchTeachers = async (q: string): Promise<SearchableOption[]> => {
    const results = await coursesApi.searchTeachers(q);
    return results.map(t => ({
      id: t.id,
      label: t.name,
      sublabel: t.email || (t.is_shadow ? 'Shadow teacher' : undefined),
    }));
  };

  const handleSearchStudents = async (q: string): Promise<SearchableOption[]> => {
    const results = await coursesApi.searchStudents(q);
    return results.map(s => ({
      id: s.id,
      label: s.name,
      sublabel: s.email,
    }));
  };

  const handleCreateCourse = async () => {
    if (!courseName.trim()) return;
    if (!selectedTeacher && !showCreateTeacher) {
      setCreateError('A teacher is required');
      return;
    }
    if (showCreateTeacher && !newTeacherName.trim()) {
      setCreateError('Teacher name is required');
      return;
    }
    if (newTeacherEmail && !isValidEmail(newTeacherEmail.trim())) {
      setCreateError('Please enter a valid teacher email');
      return;
    }
    setCreateError('');
    setCreateLoading(true);
    try {
      const data: Parameters<typeof coursesApi.create>[0] = {
        name: courseName.trim(),
        subject: courseSubject.trim() || undefined,
        description: courseDescription.trim() || undefined,
        student_ids: selectedStudents.map(s => s.id),
        require_approval: courseRequireApproval,
      };
      if (selectedTeacher) {
        data.teacher_id = selectedTeacher.id;
      } else if (showCreateTeacher) {
        data.new_teacher_name = newTeacherName.trim();
        data.new_teacher_email = newTeacherEmail.trim() || undefined;
      }
      const newCourse = await coursesApi.create(data);
      closeCreateModal();
      if (isParent) {
        const courses = await coursesApi.createdByMe();
        setMyCourses(courses);
        if (selectedChild) loadChildOverview(selectedChild);
      } else if (isStudent) {
        const [enrolled, created] = await Promise.all([
          coursesApi.enrolledByMe(),
          coursesApi.createdByMe(),
        ]);
        setEnrolledCourses(enrolled);
        setMyCourses(created);
      } else {
        const courses = await coursesApi.list();
        setMyCourses(courses);
      }
      // Navigate to the new course detail page
      navigate(`/courses/${newCourse.id}`);
    } catch (err: any) {
      setCreateError(err.response?.data?.detail || 'Failed to create class');
    } finally {
      setCreateLoading(false);
    }
  };

  const closeCreateModal = () => {
    setShowCreateModal(false);
    setCourseName('');
    setCourseSubject('');
    setCourseDescription('');
    setCourseRequireApproval(false);
    setCreateError('');
    setSelectedTeacher(null);
    setSelectedStudents([]);
    setShowCreateTeacher(false);
    setNewTeacherName('');
    setNewTeacherEmail('');
    setWizardStep(1);
    setAddChildName('');
    setAddChildEmail('');
    setAddChildError('');
  };

  const closeAddChildModal = () => {
    setShowAddChildModal(false);
    setAddChildTab('create');
    setAddChildName('');
    setAddChildEmail('');
    setAddChildRelationship('guardian');
    setAddChildError('');
    setAddChildInviteLink('');
  };

  const handleCreateChild = async () => {
    if (!addChildName.trim()) return;
    if (addChildEmail.trim() && !isValidEmail(addChildEmail.trim())) {
      setAddChildError('Please enter a valid email address');
      return;
    }
    setAddChildLoading(true);
    setAddChildError('');
    try {
      const result = await parentApi.createChild(
        addChildName.trim(),
        addChildRelationship,
        addChildEmail.trim() || undefined,
      );
      if (result.invite_link) {
        setAddChildInviteLink(result.invite_link);
      } else {
        closeAddChildModal();
        toast(`${addChildName.trim()} added successfully`, 'success');
      }
      // Refresh children list and auto-select new child
      const kids = await parentApi.getChildren();
      setChildren(kids);
      const newKid = kids.find(k => !selectedStudents.some(s => s.id === k.student_id));
      if (newKid) {
        setSelectedStudents(prev => [...prev, { id: newKid.student_id, label: newKid.full_name, sublabel: newKid.email || undefined }]);
      }
    } catch (err: any) {
      setAddChildError(err.response?.data?.detail || 'Failed to create child');
    } finally {
      setAddChildLoading(false);
    }
  };

  const handleLinkChild = async () => {
    if (!addChildEmail.trim()) return;
    if (!isValidEmail(addChildEmail.trim())) {
      setAddChildError('Please enter a valid email address');
      return;
    }
    setAddChildLoading(true);
    setAddChildError('');
    try {
      const result = await parentApi.linkChild(
        addChildEmail.trim(),
        addChildRelationship,
        addChildName.trim() || undefined,
      );
      if (result.invite_link) {
        setAddChildInviteLink(result.invite_link);
      } else if (result.link_request_pending) {
        closeAddChildModal();
        toast(`A link request has been sent to ${result.full_name}. They need to approve it before you can manage their account.`, 'info');
      } else {
        closeAddChildModal();
        toast(`${result.full_name} linked successfully`, 'success');
      }
      // Refresh children list and auto-select new child
      const kids = await parentApi.getChildren();
      setChildren(kids);
      const newKid = kids.find(k => !selectedStudents.some(s => s.id === k.student_id));
      if (newKid) {
        setSelectedStudents(prev => [...prev, { id: newKid.student_id, label: newKid.full_name, sublabel: newKid.email || undefined }]);
      }
    } catch (err: any) {
      setAddChildError(err.response?.data?.detail || 'Failed to link child');
    } finally {
      setAddChildLoading(false);
    }
  };

  const handleAssignCourses = async () => {
    if (!selectedChild || selectedCoursesForAssign.size === 0) return;
    setAssignLoading(true);
    try {
      await parentApi.assignCoursesToChild(selectedChild, Array.from(selectedCoursesForAssign));
      setShowAssignModal(false);
      setSelectedCoursesForAssign(new Set());
      loadChildOverview(selectedChild);
    } catch (err: any) {
      setActionError(err.response?.data?.detail || 'Failed to assign classes');
    } finally {
      setAssignLoading(false);
    }
  };

  const handleSyncCourses = async () => {
    if (!selectedChild) return;
    setSyncState('syncing');
    setSyncMessage('');
    try {
      const result = await parentApi.syncChildCourses(selectedChild);
      setSyncMessage(result.message);
      setSyncState('done');
      setLastSynced(new Date());
      loadChildOverview(selectedChild);
      setTimeout(() => { setSyncState('idle'); setSyncMessage(''); }, 4000);
    } catch (err: any) {
      setSyncMessage(err.response?.data?.detail || 'Failed to sync classes');
      setSyncState('error');
    }
  };

  const handleUnassignCourse = async (courseId: number, courseName: string) => {
    if (!selectedChild) return;
    const ok = await confirm({
      title: 'Unassign Class',
      message: `Remove "${courseName}" from ${childName}?`,
      confirmLabel: 'Unassign',
    });
    if (!ok) return;
    try {
      await parentApi.unassignCourseFromChild(selectedChild, courseId);
      loadChildOverview(selectedChild);
    } catch (err: any) {
      setActionError(err.response?.data?.detail || 'Failed to unassign class');
    }
  };

  const handleQuickAssign = async (courseId: number) => {
    if (!selectedChild) return;
    try {
      await parentApi.assignCoursesToChild(selectedChild, [courseId]);
      loadChildOverview(selectedChild);
    } catch (err: any) {
      setActionError(err.response?.data?.detail || 'Failed to assign class');
    }
  };

  const handleEnroll = async (courseId: number) => {
    setEnrollingId(courseId);
    try {
      const result = await coursesApi.enroll(courseId);
      if (result.status === 'pending') {
        // Approval required — mark as pending
        setPendingCourseIds(prev => new Set([...prev, courseId]));
      } else {
        // Direct enrollment
        const course = availableCourses.find(c => c.id === courseId);
        if (course) {
          setEnrolledCourses(prev => [...prev, course]);
          setAvailableCourses(prev => prev.filter(c => c.id !== courseId));
        }
      }
    } catch (err: any) {
      setActionError(err.response?.data?.detail || 'Failed to enroll');
    } finally {
      setEnrollingId(null);
    }
  };

  const handleUnenroll = async (courseId: number, courseName: string) => {
    const ok = await confirm({
      title: 'Unenroll from Class',
      message: `Are you sure you want to unenroll from "${courseName}"?`,
      confirmLabel: 'Unenroll',
    });
    if (!ok) return;
    setEnrollingId(courseId);
    try {
      await coursesApi.unenroll(courseId);
      // Move course from enrolled to available
      const course = enrolledCourses.find(c => c.id === courseId);
      if (course) {
        setAvailableCourses(prev => [...prev, course]);
        setEnrolledCourses(prev => prev.filter(c => c.id !== courseId));
      }
    } catch (err: any) {
      setActionError(err.response?.data?.detail || 'Failed to unenroll');
    } finally {
      setEnrollingId(null);
    }
  };

  // ── Edit Course modal handlers ────────────────────────────────
  const openEditCourse = (course: CourseItem) => {
    setEditCourse(course);
    setEditCourseName(course.name);
    setEditCourseSubject(course.subject || '');
    setEditCourseDescription(course.description || '');
    setEditCourseRequireApproval(course.require_approval || false);
    setEditCourseTeacher(course.teacher_id ? { id: course.teacher_id, label: course.teacher_name || 'Unknown' } : null);
    coursesApi.listStudents(course.id).then(students => {
      const opts = students.map(s => ({ id: s.user_id, label: s.full_name, sublabel: s.email }));
      const idMap: Record<number, number> = {};
      students.forEach(s => { idMap[s.user_id] = s.student_id; });
      setEditCourseStudents(opts);
      setEditCourseOriginalStudents(opts);
      setEditStudentIdMap(idMap);
    }).catch(() => {});
    setEditCourseError('');
  };

  const closeEditCourse = () => {
    setEditCourse(null);
    setEditCourseError('');
    setEditCourseTeacher(null);
    setEditCourseStudents([]);
    setEditCourseOriginalStudents([]);
    setEditStudentIdMap({});
  };

  const handleSaveEditCourse = async () => {
    if (!editCourse || !editCourseName.trim()) return;
    setEditCourseLoading(true);
    setEditCourseError('');
    try {
      await coursesApi.update(editCourse.id, {
        name: editCourseName.trim(),
        subject: editCourseSubject.trim() || undefined,
        description: editCourseDescription.trim() || undefined,
        teacher_id: editCourseTeacher?.id ?? null,
        require_approval: editCourseRequireApproval,
      });
      // Handle student changes
      const originalIds = new Set(editCourseOriginalStudents.map(s => s.id));
      const currentIds = new Set(editCourseStudents.map(s => s.id));
      for (const student of editCourseStudents) {
        if (!originalIds.has(student.id) && student.sublabel) {
          await coursesApi.addStudent(editCourse.id, student.sublabel);
        }
      }
      for (const student of editCourseOriginalStudents) {
        if (!currentIds.has(student.id) && editStudentIdMap[student.id]) {
          await coursesApi.removeStudent(editCourse.id, editStudentIdMap[student.id]);
        }
      }
      closeEditCourse();
      loadData();
    } catch (err: any) {
      setEditCourseError(err.response?.data?.detail || 'Failed to update class');
    } finally {
      setEditCourseLoading(false);
    }
  };

  const handleDeleteCourseFromModal = async () => {
    if (!editCourse) return;
    const ok = await confirm({
      title: 'Delete Class',
      message: `Are you sure you want to delete "${editCourse.name}"? This cannot be undone.`,
      confirmLabel: 'Delete',
    });
    if (!ok) return;
    setEditCourseLoading(true);
    try {
      await coursesApi.delete(editCourse.id);
      closeEditCourse();
      loadData();
    } catch (err: any) {
      setEditCourseError(err.response?.data?.detail || 'Failed to delete class');
      setEditCourseLoading(false);
    }
  };

  // ── Edit Content modal handlers ──────────────────────────────
  const openEditContent = (item: CourseContentItem) => {
    setEditContent(item);
    setEditContentTitle(item.title);
    setEditContentDescription(item.description || '');
    setEditContentType(item.content_type);
    setEditContentError('');
  };

  const closeEditContent = () => {
    setEditContent(null);
    setEditContentError('');
  };

  const handleSaveEditContent = async () => {
    if (!editContent || !editContentTitle.trim()) return;
    setEditContentLoading(true);
    setEditContentError('');
    try {
      await courseContentsApi.update(editContent.id, {
        title: editContentTitle.trim(),
        description: editContentDescription.trim() || undefined,
        content_type: editContentType,
      });
      closeEditContent();
      if (expandedCourseId) {
        const contents = await courseContentsApi.list(expandedCourseId);
        setExpandedContents(contents);
      }
    } catch (err: any) {
      setEditContentError(err.response?.data?.detail || 'Failed to update material');
    } finally {
      setEditContentLoading(false);
    }
  };

  const handleDeleteContentFromModal = async () => {
    if (!editContent) return;
    const ok = await confirm({
      title: 'Delete Material',
      message: `Are you sure you want to delete "${editContent.title}"?`,
      confirmLabel: 'Delete',
    });
    if (!ok) return;
    setEditContentLoading(true);
    try {
      await courseContentsApi.delete(editContent.id);
      closeEditContent();
      if (expandedCourseId) {
        const contents = await courseContentsApi.list(expandedCourseId);
        setExpandedContents(contents);
      }
    } catch (err: any) {
      setEditContentError(err.response?.data?.detail || 'Failed to delete material');
      setEditContentLoading(false);
    }
  };

  // Apply classroom type filter
  const filterByType = (courses: CourseItem[]) => {
    if (!classroomTypeFilter) return courses;
    return courses.filter(c => c.classroom_type === classroomTypeFilter);
  };


  const filteredAvailable = filterByType(availableCourses);

  const childName = childOverview?.full_name || children.find(c => c.student_id === selectedChild)?.full_name || '';
  const courseIds = (childOverview?.courses || []).map(c => c.id);

  if (loading || loadError) {
    return (
      <DashboardLayout welcomeSubtitle="Manage classes">
        {loadError ? (
          <div className="no-children-state">
            <h3>Unable to Load Classes</h3>
            <p>Something went wrong while loading your classes. Please try again.</p>
            <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', marginTop: '20px' }}>
              <button className="link-child-btn" onClick={() => { setLoading(true); setLoadError(false); loadData(); }}>
                Retry
              </button>
              <button className="cancel-btn" onClick={() => window.location.reload()}>
                Refresh Page
              </button>
            </div>
          </div>
        ) : (
          <PageSkeleton />
        )}
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout
      welcomeSubtitle="Manage classes"
      sidebarActions={[
        { label: '+ Add Class', onClick: () => setShowCreateModal(true) },
      ]}
    >
      <div className="courses-page">
        <PageNav items={[
          { label: 'Home', to: '/dashboard' },
          { label: 'Classes' },
        ]} />
        {actionError && (
          <div className="error-banner" style={{ background: '#fef2f2', color: '#991b1b', padding: '8px 16px', borderRadius: '8px', marginBottom: 12 }}>
            {actionError}
            <button onClick={() => setActionError('')} style={{ marginLeft: 8, background: 'none', border: 'none', cursor: 'pointer', color: '#991b1b' }}>&times;</button>
          </div>
        )}
        {/* Classroom type filter */}
        <div className="courses-type-filter">
          <label htmlFor="classroom-type-filter">Filter by type:</label>
          <select
            id="classroom-type-filter"
            value={classroomTypeFilter}
            onChange={(e) => {
              setClassroomTypeFilter(e.target.value);
              if (e.target.value) {
                searchParams.set("type", e.target.value);
              } else {
                searchParams.delete("type");
              }
              setSearchParams(searchParams, { replace: true });
            }}
          >
            <option value="">All Types</option>
            <option value="school">School</option>
            <option value="private">Private / Tutor</option>
            <option value="manual">Manual</option>
          </select>
        </div>

        {/* Parent: Child selector */}
        {isParent && children.length > 0 && (
          <div className="cp-child-selector">
            {children.length > 1 && (
              <button
                className={`cp-child-tab cp-child-tab-all ${selectedChild === null ? 'active' : ''}`}
                onClick={() => setSelectedChild(null)}
                title="All children"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                  <circle cx="9" cy="7" r="4" />
                  <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                  <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                </svg>
              </button>
            )}
            {children.map((child, index) => (
              <button
                key={child.student_id}
                className={`cp-child-tab ${selectedChild === child.student_id ? 'active' : ''}`}
                onClick={() => setSelectedChild(selectedChild === child.student_id ? null : child.student_id)}
              >
                <span className="cp-child-color-dot" style={{ backgroundColor: CHILD_COLORS[index % CHILD_COLORS.length] }} />
                {child.full_name}
              </button>
            ))}
            <AddActionButton actions={[
              { icon: '\u{1F4DA}', label: 'Add Class', onClick: () => setShowCreateModal(true), showPlus: true },
              { icon: '\u{1F4C4}', label: 'Assign Class', onClick: () => setShowAssignModal(true), showPlus: true },
            ]} />
          </div>
        )}

        {/* Parent: Child's courses */}
        {isParent && (
          <div className="cp-section">
            <div className="cp-section-header">
              <button className="collapse-toggle" onClick={() => setChildCoursesExpanded(v => !v)}>
                <span className={`section-chevron${childCoursesExpanded ? ' expanded' : ''}`}>&#9654;</span>
                <h3 className="cp-section-title">{childName ? `${childName}'s Classes` : 'Classes'} ({childOverview?.courses.length ?? 0})</h3>
              </button>
              <div className="cp-section-header-right">
                <button className="courses-btn secondary btn-secondary btn-sm" onClick={() => setShowCreateModal(true)}>
                  + Create Class
                </button>
                {myCourses.length > 0 && selectedChild && (
                  <button className="courses-btn secondary btn-secondary btn-sm" onClick={() => { setSelectedCoursesForAssign(new Set()); setShowAssignModal(true); }}>
                    Assign Class
                  </button>
                )}
                {googleConnected && childOverview?.google_connected && (
                  <>
                    <button className="courses-btn secondary btn-secondary btn-sm" onClick={handleSyncCourses} disabled={syncState === 'syncing'}>
                      {syncState === 'syncing' ? (<><span className="btn-spinner" /> Syncing...</>) : 'Sync Google'}
                    </button>
                    {lastSynced && syncState !== 'error' && (
                      <span className="last-synced">Last synced: {formatTimeAgo(lastSynced)}</span>
                    )}
                  </>
                )}
              </div>
            </div>
            {childCoursesExpanded && (
            <>
            {syncState === 'error' ? (
              <div className="cp-sync-banner error">
                <span>{syncMessage || 'Sync failed'}</span>
                <button onClick={handleSyncCourses} className="retry-btn">Retry</button>
              </div>
            ) : syncMessage ? (
              <div className="cp-sync-banner info">{syncMessage}</div>
            ) : null}
            {overviewLoading ? (
              <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                <CardSkeleton />
                <CardSkeleton />
                <CardSkeleton />
              </div>
            ) : childOverview && childOverview.courses.length > 0 ? (
              <div className="courses-list">
                {filterByType(childOverview.courses).map((course) => (
                  <div key={course.id} className="course-list-item-wrapper">
                    <div
                      className={`course-list-row${expandedCourseId === course.id ? ' expanded' : ''}`}
                      onClick={() => toggleCourseExpand(course.id)}
                      onKeyDown={(e) => handleKeyDown(e, () => toggleCourseExpand(course.id))}
                      role="button"
                      tabIndex={0}
                    >
                      <div className="course-list-color" style={{ background: getCourseColor(course.id, courseIds) }} />
                      <div className="course-list-body">
                        <span className="course-list-title">{course.name}</span>
                        <div className="course-list-meta">
                          {course.subject && <span className="course-card-subject">{course.subject}</span>}
                          {course.teacher_name && <span>{course.teacher_name}</span>}
                          {course.google_classroom_id && <span className="course-card-badge google">Google</span>}
                          {course.classroom_type === 'school' && <span className="course-card-badge school">School</span>}
                          {course.classroom_type === 'private' && course.google_classroom_id && <span className="course-card-badge private-gc">Private</span>}
                        </div>
                      </div>
                      <span className="course-list-expand">{expandedCourseId === course.id ? '▲' : '▼'}</span>
                      <div className="course-list-actions" onClick={(e) => e.stopPropagation()}>
                        <button className="course-list-btn" title="Edit" onClick={() => openEditCourse(course)}>&#9998;</button>
                        <button className="course-list-btn danger" title={`Unassign from ${childName}`} onClick={() => handleUnassignCourse(course.id, course.name)}>&#10005;</button>
                      </div>
                    </div>
                    {expandedCourseId === course.id && (
                      <div className="course-content-panel">
                        <div className="course-content-header">
                          <h5>Class Materials</h5>
                          <button className="courses-btn secondary btn-secondary btn-sm" onClick={() => navigate(`/courses/${course.id}`)}>
                            View Details &rarr;
                          </button>
                        </div>
                        {expandedLoading ? (
                          <div className="course-content-empty"><p>Loading...</p></div>
                        ) : expandedContents.length === 0 ? (
                          <div className="course-content-empty">
                            <p>No materials yet. <span style={{ cursor: 'pointer', color: 'var(--color-accent)' }} onClick={() => navigate(`/courses/${course.id}`)}>Add content &rarr;</span></p>
                          </div>
                        ) : (
                          <div className="course-content-list">
                            {expandedContents.map((item) => (
                              <div key={item.id} className="content-item">
                                <div className="content-item-info">
                                  <span className={`content-type-badge ${item.content_type}`}>
                                    {CONTENT_TYPE_LABELS[item.content_type] || item.content_type}
                                  </span>
                                  <Link to={`/course-materials/${item.id}`} className="content-item-title content-item-link">{item.title}</Link>
                                  {item.description && <p className="content-item-desc">{item.description}</p>}
                                </div>
                                <div className="content-item-actions">
                                  {item.reference_url && (
                                    <a href={item.reference_url} target="_blank" rel="noopener noreferrer" className="content-link">Link</a>
                                  )}
                                  {item.google_classroom_url && (
                                    <a href={item.google_classroom_url} target="_blank" rel="noopener noreferrer" className="content-link google">Google</a>
                                  )}
                                  <button className="course-list-btn" title="Edit" onClick={(e) => { e.stopPropagation(); openEditContent(item); }}>&#9998;</button>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <GoogleClassroomPrompt
                childName={childName || 'your child'}
                childStudentId={selectedChild ?? 0}
                onAddManually={() => setShowCreateModal(true)}
              />
            )}
            </>
            )}
          </div>
        )}

        {/* Student: Enrollment tabs */}
        {isStudent && (
          <>
            <div className="courses-tabs">
              <button
                className={`courses-tab ${studentTab === 'enrolled' ? 'active' : ''}`}
                onClick={() => { setStudentTab('enrolled'); searchParams.delete('tab'); setSearchParams(searchParams, { replace: true }); }}
              >
                My Classes ({enrolledCourses.length})
              </button>
              <button className="title-add-btn" onClick={() => setShowCreateModal(true)} title="Create Class" aria-label="Create Class" style={{ marginLeft: 'auto' }}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
                  <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
                </svg>
              </button>
              <button
                className={`courses-tab ${studentTab === 'browse' ? 'active' : ''}`}
                onClick={() => { setStudentTab('browse'); searchParams.set('tab', 'browse'); setSearchParams(searchParams, { replace: true }); }}
              >
                Browse Classes ({availableCourses.length})
              </button>
            </div>

            {studentTab === 'enrolled' && (
              <div className="cp-section">
                {enrolledCourses.length > 0 ? (
                  <div className="courses-list">
                    {filterByType(enrolledCourses).map((course) => (
                      <div key={course.id} className="course-list-item-wrapper">
                        <div
                          className={`course-list-row${expandedCourseId === course.id ? ' expanded' : ''}`}
                          onClick={() => toggleCourseExpand(course.id)}
                          onKeyDown={(e) => handleKeyDown(e, () => toggleCourseExpand(course.id))}
                          role="button"
                          tabIndex={0}
                        >
                          <div className="course-list-color" style={{ background: getCourseColor(course.id, enrolledCourses.map(c => c.id)) }} />
                          <div className="course-list-body">
                            <span className="course-list-title">{course.name}</span>
                            <div className="course-list-meta">
                              {course.subject && <span className="course-card-subject">{course.subject}</span>}
                              {course.teacher_name && <span>{course.teacher_name}</span>}
                              {course.google_classroom_id && <span className="course-card-badge google">Google</span>}
                              {course.classroom_type === "school" && <span className="course-card-badge school">School</span>}
                              {course.classroom_type === "private" && course.google_classroom_id && <span className="course-card-badge private-gc">Private</span>}
                            </div>
                          </div>
                          <span className="course-list-expand">{expandedCourseId === course.id ? '▲' : '▼'}</span>
                          <div className="course-list-actions" onClick={(e) => e.stopPropagation()}>
                            <button className="course-list-btn" title="Edit" onClick={() => openEditCourse(course)}>&#9998;</button>
                            <button
                              className="course-list-btn danger"
                              title="Unenroll"
                              onClick={() => handleUnenroll(course.id, course.name)}
                              disabled={enrollingId === course.id}
                            >&#10005;</button>
                          </div>
                        </div>
                        {expandedCourseId === course.id && (
                          <div className="course-content-panel">
                            <div className="course-content-header">
                              <h5>Class Materials</h5>
                              <button className="courses-btn secondary btn-secondary btn-sm" onClick={() => navigate(`/courses/${course.id}`)}>
                                View Details &rarr;
                              </button>
                            </div>
                            {expandedLoading ? (
                              <div className="course-content-empty"><p>Loading...</p></div>
                            ) : expandedContents.length === 0 ? (
                              <div className="course-content-empty">
                                <p>No materials yet.</p>
                              </div>
                            ) : (
                              <div className="course-content-list">
                                {expandedContents.map((item) => (
                                  <div key={item.id} className="content-item">
                                    <div className="content-item-info">
                                      <span className={`content-type-badge ${item.content_type}`}>
                                        {CONTENT_TYPE_LABELS[item.content_type] || item.content_type}
                                      </span>
                                      <Link to={`/course-materials/${item.id}`} className="content-item-title content-item-link">{item.title}</Link>
                                      {item.description && <p className="content-item-desc">{item.description}</p>}
                                    </div>
                                    <div className="content-item-actions">
                                      {item.reference_url && (
                                        <a href={item.reference_url} target="_blank" rel="noopener noreferrer" className="content-link">Link</a>
                                      )}
                                      {item.google_classroom_url && (
                                        <a href={item.google_classroom_url} target="_blank" rel="noopener noreferrer" className="content-link google">Google</a>
                                      )}
                                      <button className="course-list-btn" title="Edit" onClick={(e) => { e.stopPropagation(); openEditContent(item); }}>&#9998;</button>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState
                    title="Not enrolled in any classes yet"
                    action={{ label: 'Browse Classes', onClick: () => setStudentTab('browse') }}
                    variant="compact"
                  />
                )}
              </div>
            )}

            {studentTab === 'browse' && (
              <div className="cp-section">
                <div className="courses-search" style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  <input
                    type="text"
                    placeholder="Search by name or description..."
                    value={browseSearch}
                    onChange={(e) => setBrowseSearch(e.target.value)}
                    className="courses-search-input"
                    style={{ flex: '2 1 200px' }}
                  />
                  <input
                    type="text"
                    placeholder="Subject..."
                    value={browseSubject}
                    onChange={(e) => setBrowseSubject(e.target.value)}
                    className="courses-search-input"
                    style={{ flex: '1 1 120px' }}
                  />
                  <input
                    type="text"
                    placeholder="Teacher..."
                    value={browseTeacher}
                    onChange={(e) => setBrowseTeacher(e.target.value)}
                    className="courses-search-input"
                    style={{ flex: '1 1 120px' }}
                  />
                </div>
                {browseLoading ? (
                  <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}><CardSkeleton /><CardSkeleton /><CardSkeleton /></div>
                ) : filteredAvailable.length > 0 ? (
                  <div className="courses-list">
                    {filteredAvailable.map((course) => (
                      <div key={course.id} className="course-list-row browse">
                        <div className="course-list-color" style={{ background: 'var(--color-accent)' }} />
                        <div className="course-list-body">
                          <span className="course-list-title">{course.name}</span>
                          <div className="course-list-meta">
                            {course.subject && <span className="course-card-subject">{course.subject}</span>}
                            {course.teacher_name && <span>{course.teacher_name}</span>}
                            {course.google_classroom_id && <span className="course-card-badge google">Google</span>}
                            {course.classroom_type === "school" && <span className="course-card-badge school">School</span>}
                            {course.classroom_type === "private" && course.google_classroom_id && <span className="course-card-badge private-gc">Private</span>}
                            {course.description && <span className="course-list-desc">{course.description}</span>}
                          </div>
                        </div>
                        <button
                          className={`courses-btn primary btn-primary btn-sm${pendingCourseIds.has(course.id) ? ' btn-pending' : ''}`}
                          onClick={() => handleEnroll(course.id)}
                          disabled={enrollingId === course.id || pendingCourseIds.has(course.id)}
                        >
                          {pendingCourseIds.has(course.id) ? 'Pending Approval' : enrollingId === course.id ? (<><span className="btn-spinner" /> Enrolling...</>) : course.require_approval ? 'Request to Join' : 'Enroll'}
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState
                    title={(browseSearch || browseSubject || browseTeacher) ? 'No classes match your search.' : 'No available classes to browse.'}
                    variant="compact"
                  />
                )}
              </div>
            )}
          </>
        )}

        {/* Created courses section (parents, teachers, admins always; students only when they have created classes) */}
        {(!isStudent || myCourses.length > 0) && (
        <div className="cp-section">
          <div className="cp-section-header">
            <button className="collapse-toggle" onClick={() => setMyCoursesExpanded(v => !v)}>
              <span className={`section-chevron${myCoursesExpanded ? ' expanded' : ''}`}>&#9654;</span>
              <h3 className="cp-section-title">{isParent || isStudent ? 'My Created Classes' : 'Classes'} ({myCourses.length})</h3>
            </button>
            {!isParent && !isStudent && (
              <button className="title-add-btn" onClick={() => setShowCreateModal(true)} title="Create Class" aria-label="Create Class">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
                  <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
                </svg>
              </button>
            )}
          </div>
          {myCoursesExpanded && myCourses.length > 0 ? (
            <div className="courses-list">
              {filterByType(myCourses).map((course) => (
                <div
                  key={course.id}
                  className="course-list-row"
                  onClick={() => navigate(`/courses/${course.id}`)}
                  onKeyDown={(e) => handleKeyDown(e, () => navigate(`/courses/${course.id}`))}
                  role="button"
                  tabIndex={0}
                >
                  <div className="course-list-color" style={{ background: 'var(--color-accent)' }} />
                  <div className="course-list-body">
                    <span className="course-list-title">{course.name}</span>
                    <div className="course-list-meta">
                      {course.subject && <span className="course-card-subject">{course.subject}</span>}
                      {course.google_classroom_id && <span className="course-card-badge google">Google</span>}
                      {course.classroom_type === "school" && <span className="course-card-badge school">School</span>}
                      {course.classroom_type === "private" && course.google_classroom_id && <span className="course-card-badge private-gc">Private</span>}
                      {course.description && <span className="course-list-desc">{course.description}</span>}
                    </div>
                  </div>
                  <div className="course-list-actions" onClick={(e) => e.stopPropagation()}>
                    {isParent && selectedChild && (() => {
                      const alreadyAssigned = childOverview?.courses.some(c => c.id === course.id) ?? false;
                      return !alreadyAssigned ? (
                        <button className="course-list-btn assign" title={`Assign to ${childName}`} onClick={() => handleQuickAssign(course.id)}>&#10003;</button>
                      ) : (
                        <span className="course-card-assigned-badge" title={`Assigned to ${childName}`}>&#10003;</span>
                      );
                    })()}
                    <button className="course-list-btn" title="Edit" onClick={() => openEditCourse(course)}>&#9998;</button>
                  </div>
                </div>
              ))}
            </div>
          ) : myCoursesExpanded ? (
            <EmptyState
              title={isParent ? 'No classes created yet.' : 'No classes available. Create one to get started.'}
              variant="compact"
            />
          ) : null}
        </div>
        )}
      </div>

      {/* Create Course Modal (teacher/admin — single form) */}
      <CreateClassModal
        open={showCreateModal && !isParent && !isStudent}
        onClose={closeCreateModal}
        onCreated={async (newCourse) => {
          closeCreateModal();
          if (isParent) {
            const courses = await coursesApi.createdByMe();
            setMyCourses(courses);
            if (selectedChild) loadChildOverview(selectedChild);
          } else if (isStudent) {
            const [enrolled, created] = await Promise.all([
              coursesApi.enrolledByMe(),
              coursesApi.createdByMe(),
            ]);
            setEnrolledCourses(enrolled);
            setMyCourses(created);
          } else {
            const courses = await coursesApi.list();
            setMyCourses(courses);
          }
          navigate(`/courses/${newCourse.id}`);
        }}
      />

      {/* Parent Create Class Wizard */}
      {showCreateModal && isParent && (
        <div className="modal-overlay" onClick={closeCreateModal}>
          <div className="modal modal-lg" role="dialog" aria-modal="true" aria-label="Create Class" ref={createModalRef} onClick={(e) => e.stopPropagation()}>
            <h2>Create Class</h2>
            <div style={{ display: 'flex', justifyContent: 'center', gap: '8px', margin: '0 0 16px' }}>
              {[1, 2, 3].map((s) => (
                <div key={s} style={{
                  display: 'flex', alignItems: 'center', gap: '6px',
                  color: wizardStep >= s ? '#6366f1' : '#9ca3af',
                  fontWeight: wizardStep === s ? 600 : 400,
                  fontSize: '0.85rem',
                }}>
                  <span style={{
                    width: '24px', height: '24px', borderRadius: '50%',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    background: wizardStep >= s ? '#6366f1' : '#e5e7eb',
                    color: wizardStep >= s ? '#fff' : '#6b7280',
                    fontSize: '0.75rem', fontWeight: 600,
                  }}>{s}</span>
                  {s === 1 ? 'Details' : s === 2 ? 'Teacher' : 'Students'}
                  {s < 3 && <span style={{ color: '#d1d5db', margin: '0 2px' }}>—</span>}
                </div>
              ))}
            </div>

            <div className="modal-form" style={{ overflow: 'visible' }}>
              {/* Step 1: Class Details */}
              {wizardStep === 1 && (
                <>
                  <label>
                    Class Name *
                    <input
                      type="text"
                      value={courseName}
                      onChange={(e) => { setCourseName(e.target.value); setCreateError(''); }}
                      placeholder="e.g. Algebra I"
                      disabled={createLoading}
                    />
                  </label>
                  <label>
                    Subject
                    <input
                      type="text"
                      value={courseSubject}
                      onChange={(e) => setCourseSubject(e.target.value)}
                      placeholder="e.g. Mathematics"
                      disabled={createLoading}
                    />
                  </label>
                  <label>
                    Description
                    <textarea
                      value={courseDescription}
                      onChange={(e) => setCourseDescription(e.target.value)}
                      placeholder="Brief description of the class..."
                      rows={2}
                      disabled={createLoading}
                    />
                  </label>
                </>
              )}

              {/* Step 2: Teacher */}
              {wizardStep === 2 && (
                <div style={{ minHeight: '200px' }}>
                  <label>
                    Teacher *
                  </label>
                  {!showCreateTeacher ? (
                    <SearchableSelect
                      placeholder="Search for a teacher by name or email..."
                      onSearch={handleSearchTeachers}
                      onSelect={(opt) => { setSelectedTeacher(opt); setCreateError(''); }}
                      selected={selectedTeacher}
                      onClear={() => setSelectedTeacher(null)}
                      disabled={createLoading}
                      createAction={{ label: '+ Create New Teacher', onClick: () => { setSelectedTeacher(null); setShowCreateTeacher(true); } }}
                    />
                  ) : (
                    <div className="create-teacher-inline">
                      <div className="create-teacher-inline__header">
                        <h4>New Teacher</h4>
                        <button type="button" className="create-teacher-inline__cancel" onClick={() => { setShowCreateTeacher(false); setNewTeacherName(''); setNewTeacherEmail(''); }}>
                          Back to search
                        </button>
                      </div>
                      <label>
                        Name *
                        <input
                          type="text"
                          value={newTeacherName}
                          onChange={(e) => { setNewTeacherName(e.target.value); setCreateError(''); }}
                          placeholder="e.g. Ms. Johnson"
                          disabled={createLoading}
                        />
                      </label>
                      <label>
                        Email (optional)
                        <input
                          type="email"
                          value={newTeacherEmail}
                          onChange={(e) => setNewTeacherEmail(e.target.value)}
                          placeholder="teacher@school.com"
                          disabled={createLoading}
                        />
                      </label>
                      <p className="shadow-note">
                        {newTeacherEmail ? 'An invitation will be sent to join ClassBridge as a teacher.' : 'No email = shadow teacher (can be invited later).'}
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* Step 3: Students */}
              {wizardStep === 3 && (
                <>
                  <label>Select children to enroll</label>
                  <MultiSearchableSelect
                    placeholder="Search your children..."
                    onSearch={async (q) => {
                      const query = q.toLowerCase();
                      return children
                        .filter(c => c.full_name.toLowerCase().includes(query) || (c.email && c.email.toLowerCase().includes(query)))
                        .map(c => ({ id: c.student_id, label: c.full_name, sublabel: c.email || undefined }));
                    }}
                    selected={selectedStudents}
                    onAdd={(opt) => setSelectedStudents(prev => [...prev, opt])}
                    onRemove={(id) => setSelectedStudents(prev => prev.filter(s => s.id !== id))}
                    disabled={createLoading}
                    createAction={{ label: '+ Add Child', onClick: () => { setShowAddChildModal(true); } }}
                  />

                  <label className="toggle-label" style={{ marginTop: '8px' }}>
                    <input type="checkbox" checked={courseRequireApproval} onChange={(e) => setCourseRequireApproval(e.target.checked)} disabled={createLoading} />
                    Require approval to join
                  </label>
                </>
              )}

              {createError && <p className="link-error">{createError}</p>}
            </div>

            <div className="modal-actions">
              {wizardStep === 1 && (
                <>
                  <button className="cancel-btn" onClick={closeCreateModal}>Cancel</button>
                  <button
                    className="generate-btn"
                    onClick={() => setWizardStep(2)}
                    disabled={!courseName.trim()}
                  >
                    Next
                  </button>
                </>
              )}
              {wizardStep === 2 && (
                <>
                  <button className="cancel-btn" onClick={() => setWizardStep(1)}>Back</button>
                  <button
                    className="generate-btn"
                    onClick={() => {
                      // Auto-select all children if none selected yet
                      if (selectedStudents.length === 0 && children.length > 0) {
                        setSelectedStudents(children.map(c => ({ id: c.student_id, label: c.full_name, sublabel: c.email || undefined })));
                      }
                      setWizardStep(3);
                    }}
                    disabled={!selectedTeacher && !(showCreateTeacher && newTeacherName.trim())}
                  >
                    Next
                  </button>
                </>
              )}
              {wizardStep === 3 && (
                <>
                  <button className="cancel-btn" onClick={() => setWizardStep(2)} disabled={createLoading}>Back</button>
                  <button
                    className="generate-btn"
                    onClick={handleCreateCourse}
                    disabled={createLoading}
                  >
                    {createLoading ? 'Creating...' : 'Create Class'}
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Student Create Class Wizard (2-step) */}
      {showCreateModal && isStudent && (
        <div className="modal-overlay" onClick={closeCreateModal}>
          <div className="modal modal-lg" role="dialog" aria-modal="true" aria-label="Create Class" ref={createModalRef} onClick={(e) => e.stopPropagation()}>
            <h2>Create Class</h2>
            <div style={{ display: 'flex', justifyContent: 'center', gap: '8px', margin: '0 0 16px' }}>
              {[1, 2].map((s) => (
                <div key={s} style={{
                  display: 'flex', alignItems: 'center', gap: '6px',
                  color: wizardStep >= s ? '#6366f1' : '#9ca3af',
                  fontWeight: wizardStep === s ? 600 : 400,
                  fontSize: '0.85rem',
                }}>
                  <span style={{
                    width: '24px', height: '24px', borderRadius: '50%',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    background: wizardStep >= s ? '#6366f1' : '#e5e7eb',
                    color: wizardStep >= s ? '#fff' : '#6b7280',
                    fontSize: '0.75rem', fontWeight: 600,
                  }}>{s}</span>
                  {s === 1 ? 'Details' : 'Teacher'}
                  {s < 2 && <span style={{ color: '#d1d5db', margin: '0 2px' }}>—</span>}
                </div>
              ))}
            </div>

            <div className="modal-form" style={{ overflow: 'visible' }}>
              {/* Step 1: Class Details */}
              {wizardStep === 1 && (
                <>
                  <label>
                    Class Name *
                    <input
                      type="text"
                      value={courseName}
                      onChange={(e) => { setCourseName(e.target.value); setCreateError(''); }}
                      placeholder="e.g. Algebra I"
                      disabled={createLoading}
                    />
                  </label>
                  <label>
                    Subject
                    <input
                      type="text"
                      value={courseSubject}
                      onChange={(e) => setCourseSubject(e.target.value)}
                      placeholder="e.g. Mathematics"
                      disabled={createLoading}
                    />
                  </label>
                  <label>
                    Description
                    <textarea
                      value={courseDescription}
                      onChange={(e) => setCourseDescription(e.target.value)}
                      placeholder="Brief description of the class..."
                      rows={2}
                      disabled={createLoading}
                    />
                  </label>
                </>
              )}

              {/* Step 2: Teacher + Create */}
              {wizardStep === 2 && (
                <>
                  <label>
                    Teacher *
                  </label>
                  {!showCreateTeacher ? (
                    <SearchableSelect
                      placeholder="Search for a teacher by name or email..."
                      onSearch={handleSearchTeachers}
                      onSelect={(opt) => { setSelectedTeacher(opt); setCreateError(''); }}
                      selected={selectedTeacher}
                      onClear={() => setSelectedTeacher(null)}
                      disabled={createLoading}
                      createAction={{ label: '+ Create New Teacher', onClick: () => { setSelectedTeacher(null); setShowCreateTeacher(true); } }}
                    />
                  ) : (
                    <div className="create-teacher-inline">
                      <div className="create-teacher-inline__header">
                        <h4>New Teacher</h4>
                        <button type="button" className="create-teacher-inline__cancel" onClick={() => { setShowCreateTeacher(false); setNewTeacherName(''); setNewTeacherEmail(''); }}>
                          Back to search
                        </button>
                      </div>
                      <label>
                        Name *
                        <input
                          type="text"
                          value={newTeacherName}
                          onChange={(e) => { setNewTeacherName(e.target.value); setCreateError(''); }}
                          placeholder="e.g. Ms. Johnson"
                          disabled={createLoading}
                        />
                      </label>
                      <label>
                        Email (optional)
                        <input
                          type="email"
                          value={newTeacherEmail}
                          onChange={(e) => setNewTeacherEmail(e.target.value)}
                          placeholder="teacher@school.com"
                          disabled={createLoading}
                        />
                      </label>
                      <p className="shadow-note">
                        {newTeacherEmail ? 'An invitation will be sent to join ClassBridge as a teacher.' : 'No email = shadow teacher (can be invited later).'}
                      </p>
                    </div>
                  )}
                  <p style={{ color: '#6b7280', fontSize: '0.85rem', marginTop: '8px' }}>You will be automatically enrolled as a student in this class.</p>
                </>
              )}

              {createError && <p className="link-error">{createError}</p>}
            </div>

            <div className="modal-actions">
              {wizardStep === 1 && (
                <>
                  <button className="cancel-btn" onClick={closeCreateModal}>Cancel</button>
                  <button
                    className="generate-btn"
                    onClick={() => setWizardStep(2)}
                    disabled={!courseName.trim()}
                  >
                    Next
                  </button>
                </>
              )}
              {wizardStep === 2 && (
                <>
                  <button className="cancel-btn" onClick={() => setWizardStep(1)} disabled={createLoading}>Back</button>
                  <button
                    className="generate-btn"
                    onClick={handleCreateCourse}
                    disabled={createLoading || (!selectedTeacher && !(showCreateTeacher && newTeacherName.trim()))}
                  >
                    {createLoading ? 'Creating...' : 'Create Class'}
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Assign Course to Child Modal (parent only) */}
      {showAssignModal && selectedChild && (
        <div className="modal-overlay" onClick={() => setShowAssignModal(false)}>
          <div className="modal" role="dialog" aria-modal="true" aria-label={`Assign Class to ${childName}`} ref={assignModalRef} onClick={(e) => e.stopPropagation()}>
            <h2>Assign Class to {childName}</h2>
            <p className="modal-desc">Select classes to assign to your child.</p>
            <div className="modal-form">
              {myCourses.length === 0 ? (
                <EmptyState
                  title="No classes created yet"
                  action={{ label: '+ Create Class', onClick: () => { setShowAssignModal(false); setShowCreateModal(true); } }}
                  variant="compact"
                />
              ) : (
                <div className="discovered-list">
                  {myCourses.map((course) => {
                    const alreadyAssigned = childOverview?.courses.some(c => c.id === course.id) ?? false;
                    return (
                      <label key={course.id} className={`discovered-item ${alreadyAssigned ? 'disabled' : ''}`}>
                        <input type="checkbox" checked={selectedCoursesForAssign.has(course.id)} onChange={() => { setSelectedCoursesForAssign(prev => { const next = new Set(prev); if (next.has(course.id)) next.delete(course.id); else next.add(course.id); return next; }); }} disabled={alreadyAssigned} />
                        <div className="discovered-info">
                          <span className="discovered-name">{course.name}</span>
                          {course.subject && <span className="discovered-email">{course.subject}</span>}
                          {alreadyAssigned && <span className="discovered-linked-badge">Already assigned</span>}
                        </div>
                      </label>
                    );
                  })}
                </div>
              )}
            </div>
            <div className="modal-actions">
              <button className="cancel-btn" onClick={() => setShowAssignModal(false)} disabled={assignLoading}>Cancel</button>
              <button className="generate-btn" onClick={handleAssignCourses} disabled={assignLoading || selectedCoursesForAssign.size === 0}>
                {assignLoading ? 'Assigning...' : `Assign ${selectedCoursesForAssign.size} Class${selectedCoursesForAssign.size !== 1 ? 'es' : ''}`}
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Edit Course Modal */}
      {editCourse && (
        <div className="modal-overlay" onClick={closeEditCourse}>
          <div className="modal" role="dialog" aria-modal="true" aria-label="Edit Class" ref={editCourseModalRef} onClick={(e) => e.stopPropagation()}>
            <h2>Edit Class</h2>
            <div className="modal-form">
              <label>
                Class Name *
                <input type="text" value={editCourseName} onChange={(e) => setEditCourseName(e.target.value)} placeholder="e.g. Math Grade 5" disabled={editCourseLoading} onKeyDown={(e) => e.key === 'Enter' && handleSaveEditCourse()} />
              </label>
              <label>
                Subject
                <input type="text" value={editCourseSubject} onChange={(e) => setEditCourseSubject(e.target.value)} placeholder="e.g. Mathematics" disabled={editCourseLoading} />
              </label>
              <label>
                Description
                <textarea value={editCourseDescription} onChange={(e) => setEditCourseDescription(e.target.value)} placeholder="Class details..." rows={3} disabled={editCourseLoading} />
              </label>
              <label>
                Teacher
              </label>
              <SearchableSelect
                placeholder="Search for a teacher..."
                onSearch={handleSearchTeachers}
                onSelect={(opt) => setEditCourseTeacher(opt)}
                selected={editCourseTeacher}
                onClear={() => setEditCourseTeacher(null)}
                disabled={editCourseLoading}
              />
              <label>
                Students
              </label>
              <MultiSearchableSelect
                placeholder="Search students by name or email..."
                onSearch={handleSearchStudents}
                selected={editCourseStudents}
                onAdd={(opt) => setEditCourseStudents(prev => [...prev, opt])}
                onRemove={(id) => setEditCourseStudents(prev => prev.filter(s => s.id !== id))}
                disabled={editCourseLoading}
              />
              <label className="toggle-label">
                <input type="checkbox" checked={editCourseRequireApproval} onChange={(e) => setEditCourseRequireApproval(e.target.checked)} disabled={editCourseLoading} />
                Require approval to join
              </label>
              {editCourseError && <p className="link-error">{editCourseError}</p>}
            </div>
            <div className="modal-actions">
              {!editCourse.google_classroom_id && (
                <button className="cancel-btn danger-text" onClick={handleDeleteCourseFromModal} disabled={editCourseLoading}>Delete Class</button>
              )}
              <button className="cancel-btn" onClick={closeEditCourse} disabled={editCourseLoading}>Cancel</button>
              <button className="generate-btn" onClick={handleSaveEditCourse} disabled={editCourseLoading || !editCourseName.trim()}>
                {editCourseLoading ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Content Modal */}
      {editContent && (
        <div className="modal-overlay" onClick={closeEditContent}>
          <div className="modal" role="dialog" aria-modal="true" aria-label="Edit Material" ref={editContentModalRef} onClick={(e) => e.stopPropagation()}>
            <h2>Edit Material</h2>
            <div className="modal-form">
              <label>
                Title *
                <input type="text" value={editContentTitle} onChange={(e) => setEditContentTitle(e.target.value)} placeholder="Material title" disabled={editContentLoading} onKeyDown={(e) => e.key === 'Enter' && handleSaveEditContent()} />
              </label>
              <label>
                Description
                <textarea value={editContentDescription} onChange={(e) => setEditContentDescription(e.target.value)} placeholder="Material description..." rows={3} disabled={editContentLoading} />
              </label>
              <label>
                Type
                <select value={editContentType} onChange={(e) => setEditContentType(e.target.value)} disabled={editContentLoading}>
                  {Object.entries(CONTENT_TYPE_LABELS).map(([val, label]) => (
                    <option key={val} value={val}>{label}</option>
                  ))}
                </select>
              </label>
              {editContentError && <p className="link-error">{editContentError}</p>}
            </div>
            <div className="modal-actions">
              <button className="cancel-btn danger-text" onClick={handleDeleteContentFromModal} disabled={editContentLoading}>Delete Material</button>
              <button className="cancel-btn" onClick={closeEditContent} disabled={editContentLoading}>Cancel</button>
              <button className="generate-btn" onClick={handleSaveEditContent} disabled={editContentLoading || !editContentTitle.trim()}>
                {editContentLoading ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {showAddChildModal && (
        <div className="modal-overlay" onClick={closeAddChildModal}>
          <div className="modal" role="dialog" aria-modal="true" aria-label="Add Child" ref={addChildModalRef} onClick={(e) => e.stopPropagation()}>
            <h2>Add Child</h2>

            <div className="link-tabs">
              <button className={`link-tab ${addChildTab === 'create' ? 'active' : ''}`} onClick={() => { setAddChildTab('create'); setAddChildError(''); }}>
                Create New
              </button>
              <button className={`link-tab ${addChildTab === 'email' ? 'active' : ''}`} onClick={() => { setAddChildTab('email'); setAddChildError(''); }}>
                Link by Email
              </button>
            </div>

            {addChildTab === 'create' && (
              <>
                {addChildInviteLink ? (
                  <div className="modal-form">
                    <div className="invite-success-box">
                      <p style={{ margin: '0 0 8px', fontWeight: 600 }}>Child added successfully!</p>
                      {addChildEmail.trim() && (
                        <p style={{ margin: '0 0 8px', fontSize: 14 }}>
                          An invitation email has been sent to <strong>{addChildEmail.trim()}</strong>. Your child needs to check their email and click the link to set up their account.
                        </p>
                      )}
                      <p style={{ margin: '0 0 8px', fontSize: 14, color: '#64748b' }}>
                        You can also share this link directly:
                      </p>
                      <div className="invite-link-container">
                        <span className="invite-link">{addChildInviteLink}</span>
                        <button className="copy-link-btn" onClick={() => navigator.clipboard.writeText(addChildInviteLink)}>Copy</button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <>
                    <p className="modal-desc">Add your child with just their name. Email is optional.</p>
                    <div className="modal-form">
                      <label>
                        Child's Name *
                        <input type="text" value={addChildName} onChange={(e) => setAddChildName(e.target.value)} placeholder="e.g. Alex Smith" disabled={addChildLoading} onKeyDown={(e) => e.key === 'Enter' && handleCreateChild()} />
                      </label>
                      <label>
                        Email (optional)
                        <input type="email" value={addChildEmail} onChange={(e) => { setAddChildEmail(e.target.value); setAddChildError(''); }} placeholder="child@example.com" disabled={addChildLoading} />
                      </label>
                      <label>
                        Relationship
                        <select value={addChildRelationship} onChange={(e) => setAddChildRelationship(e.target.value)} disabled={addChildLoading}>
                          <option value="mother">Mother</option>
                          <option value="father">Father</option>
                          <option value="guardian">Guardian</option>
                          <option value="other">Other</option>
                        </select>
                      </label>
                      {addChildError && (
                        <div className="modal-error">
                          <span className="error-icon">!</span>
                          <span className="error-message">{addChildError}</span>
                          <button onClick={handleCreateChild} className="retry-btn" disabled={addChildLoading}>Try Again</button>
                        </div>
                      )}
                    </div>
                  </>
                )}
                <div className="modal-actions">
                  <button className="cancel-btn" onClick={closeAddChildModal} disabled={addChildLoading}>{addChildInviteLink ? 'Close' : 'Cancel'}</button>
                  {!addChildInviteLink && (
                    <button className="generate-btn" onClick={handleCreateChild} disabled={addChildLoading || !addChildName.trim()}>
                      {addChildLoading ? <><span className="btn-spinner" /> Creating...</> : 'Add Child'}
                    </button>
                  )}
                </div>
              </>
            )}

            {addChildTab === 'email' && (
              <>
                {addChildInviteLink ? (
                  <div className="modal-form">
                    <div className="invite-success-box">
                      <p style={{ margin: '0 0 8px', fontWeight: 600 }}>Child linked successfully!</p>
                      <p style={{ margin: '0 0 8px', fontSize: 14 }}>
                        An invitation email has been sent to <strong>{addChildEmail.trim()}</strong>. Your child needs to check their email and click the link to set up their account.
                      </p>
                      <p style={{ margin: '0 0 8px', fontSize: 14, color: '#64748b' }}>
                        You can also share this link directly:
                      </p>
                      <div className="invite-link-container">
                        <span className="invite-link">{addChildInviteLink}</span>
                        <button className="copy-link-btn" onClick={() => navigator.clipboard.writeText(addChildInviteLink)}>Copy</button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <>
                    <p className="modal-desc">Enter your child's email to link or create their account.</p>
                    <div className="modal-form">
                      <label>
                        Child's Name
                        <input type="text" value={addChildName} onChange={(e) => setAddChildName(e.target.value)} placeholder="e.g. Alex Smith" disabled={addChildLoading} />
                      </label>
                      <label>
                        Student Email *
                        <input type="email" value={addChildEmail} onChange={(e) => { setAddChildEmail(e.target.value); setAddChildError(''); }} placeholder="child@school.edu" disabled={addChildLoading} onKeyDown={(e) => e.key === 'Enter' && handleLinkChild()} />
                      </label>
                      <label>
                        Relationship
                        <select value={addChildRelationship} onChange={(e) => setAddChildRelationship(e.target.value)} disabled={addChildLoading}>
                          <option value="mother">Mother</option>
                          <option value="father">Father</option>
                          <option value="guardian">Guardian</option>
                          <option value="other">Other</option>
                        </select>
                      </label>
                      {addChildError && (
                        <div className="modal-error">
                          <span className="error-icon">!</span>
                          <span className="error-message">{addChildError}</span>
                          <button onClick={handleLinkChild} className="retry-btn" disabled={addChildLoading}>Try Again</button>
                        </div>
                      )}
                    </div>
                  </>
                )}
                <div className="modal-actions">
                  <button className="cancel-btn" onClick={closeAddChildModal} disabled={addChildLoading}>{addChildInviteLink ? 'Close' : 'Cancel'}</button>
                  {!addChildInviteLink && (
                    <button className="generate-btn" onClick={handleLinkChild} disabled={addChildLoading || !addChildEmail.trim()}>
                      {addChildLoading ? <><span className="btn-spinner" /> Linking...</> : 'Link Child'}
                    </button>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {confirmModal}
    </DashboardLayout>
  );
}
