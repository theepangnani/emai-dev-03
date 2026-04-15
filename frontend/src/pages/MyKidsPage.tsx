import { useState, useEffect, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { parentApi, courseContentsApi, coursesApi, tasksApi, invitesApi } from '../api/client';
import type { ChildSummary, ChildOverview, CourseContentItem, TaskItem, LinkedTeacher } from '../api/client';
import { GoogleClassroomPrompt } from '../components/GoogleClassroomPrompt';
import { DashboardLayout } from '../components/DashboardLayout';
import { useConfirm } from '../components/ConfirmModal';
import { useFocusTrap } from '../hooks/useFocusTrap';
import { PageSkeleton } from '../components/Skeleton';
import { AddActionButton } from '../components/AddActionButton';
import { useToast } from '../components/Toast';
import { GradesSummaryCard } from '../components/GradesSummaryCard';
import { isValidEmail } from '../utils/validation';
import { PageNav } from '../components/PageNav';
import { ConversationStartersCard } from '../components/briefing/ConversationStartersCard';
import { SectionPanel } from '../components/SectionPanel';
import UploadMaterialWizard from '../components/UploadMaterialWizard';
import { useParentStudyTools } from '../components/parent/hooks/useParentStudyTools';
import { GenerationSpinner } from '../components/GenerationSpinner';
import './MyKidsPage.css';
import { ChildXpStats } from '../components/xp/ChildXpStats';
import { OnTrackBadge } from '../components/OnTrackBadge';
import { StudyRequestModal } from '../components/StudyRequestModal';
import { AwardXpModal } from '../components/AwardXpModal';
import { StudyTimeSuggestions } from '../components/StudyTimeSuggestions';
import { JourneyNudgeBanner } from '../components/JourneyNudgeBanner';
import { EmailDigestSetupWizard } from '../components/EmailDigestSetupWizard';
import './DashboardGrid.css';
import '../components/ChildSelectorTabs.css';

const CHILD_COLORS = [
  '#8b5cf6', '#ec4899', '#14b8a6', '#f59e0b',
  '#3b82f6', '#ef4444', '#10b981', '#6366f1',
];

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  return (parts[0]?.[0] || '?').toUpperCase();
}

// Helper for keyboard accessibility
const handleKeyDown = (e: React.KeyboardEvent, callback: () => void) => {
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault();
    callback();
  }
};

export function MyKidsPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { confirm, confirmModal } = useConfirm();
  const { toast } = useToast();
  const [children, setChildren] = useState<ChildSummary[]>([]);
  const [selectedChild, setSelectedChild] = useState<number | null>(null);
  const selectedChildUserId = children.find(c => c.student_id === selectedChild)?.user_id ?? null;
  const studyTools = useParentStudyTools({ selectedChildUserId, navigate });
  const urlStudentId = searchParams.get('student_id');
  const [overview, setOverview] = useState<ChildOverview | null>(null);
  const [materials, setMaterials] = useState<CourseContentItem[]>([]);
  const recentMaterials = useMemo(() =>
    [...materials]
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      .slice(0, 5),
    [materials]
  );
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [linkedTeachers, setLinkedTeachers] = useState<LinkedTeacher[]>([]);
  const [loading, setLoading] = useState(true);
  const [sectionLoading, setSectionLoading] = useState(false);


  // Collapsible sections
  const [showCourses, setShowCourses] = useState(false);
  const [showGrades, setShowGrades] = useState(false);
  const [showMaterials, setShowMaterials] = useState(false);
  const [showTeachers, setShowTeachers] = useState(false);
  const [showConversation, setShowConversation] = useState(false);

  // Reassign class material to course
  const [reassignContent, setReassignContent] = useState<CourseContentItem | null>(null);
  const [courses, setCourses] = useState<{ id: number; name: string }[]>([]);
  const [categorizeCourseId, setCategorizeCourseId] = useState<number | string>('');
  const [categorizeSearch, setCategorizeSearch] = useState('');
  const [categorizeNewName, setCategorizeNewName] = useState('');
  const [categorizeCreating, setCategorizeCreating] = useState(false);

  // Add teacher modal
  const [showAddTeacher, setShowAddTeacher] = useState(false);
  const [teacherEmail, setTeacherEmail] = useState('');
  const [teacherName, setTeacherName] = useState('');
  const [addTeacherError, setAddTeacherError] = useState('');
  const [addTeacherLoading, setAddTeacherLoading] = useState(false);

  // Reset password modal
  const [showResetPassword, setShowResetPassword] = useState(false);
  const [resetPwMethod, setResetPwMethod] = useState<'email' | 'direct'>('direct');
  const [resetPwValue, setResetPwValue] = useState('');
  const [resetPwConfirm, setResetPwConfirm] = useState('');
  const [resetPwLoading, setResetPwLoading] = useState(false);
  const [resetPwError, setResetPwError] = useState('');
  const [resetPwSuccess, setResetPwSuccess] = useState('');

  // Study request modal
  const [showStudyRequest, setShowStudyRequest] = useState(false);

  // Award XP modal
  const [awardXpChild, setAwardXpChild] = useState<{ studentId: number; userId: number; name: string } | null>(null);

  // Email digest wizard
  const [showEmailDigestWizard, setShowEmailDigestWizard] = useState(false);

  // Wizard-local child selection (does not mutate page filter) (#1994)
  const [wizardChildId, setWizardChildId] = useState<number | null>(null);
  const [wizardCourses, setWizardCourses] = useState<{ id: number; name: string }[] | undefined>(undefined);
  useEffect(() => {
    if (!wizardChildId) { setWizardCourses(undefined); return; }
    // If we already have overview for this child, use it
    if (selectedChild === wizardChildId && overview) {
      setWizardCourses(overview.courses.map(c => ({ id: c.id, name: c.name })));
      return;
    }
    let ignore = false;
    parentApi.getChildOverview(wizardChildId).then(ov => {
      if (!ignore) setWizardCourses(ov.courses.map(c => ({ id: c.id, name: c.name })));
    }).catch(() => { if (!ignore) setWizardCourses(undefined); });
    return () => { ignore = true; };
  }, [wizardChildId, selectedChild, overview]);

  // All-children view: unassigned courses/materials
  const [unassignedCourses, setUnassignedCourses] = useState<Array<{ id: number; name: string; description?: string | null; subject?: string | null; teacher_name?: string | null }>>([]);
  const [unassignedMaterials, setUnassignedMaterials] = useState<CourseContentItem[]>([]);
  const [showUnassignedCourses, setShowUnassignedCourses] = useState(true);
  const [showUnassignedMaterials, setShowUnassignedMaterials] = useState(true);
  const [assignCourseModal, setAssignCourseModal] = useState<{ id: number; name: string } | null>(null);
  const [assignLoading, setAssignLoading] = useState(false);

  // Add Child modal state
  const [showAddChildModal, setShowAddChildModal] = useState(false);
  const [addChildTab, setAddChildTab] = useState<'create' | 'email'>('create');
  const [addChildName, setAddChildName] = useState('');
  const [addChildEmail, setAddChildEmail] = useState('');
  const [addChildRelationship, setAddChildRelationship] = useState('guardian');
  const [addChildLoading, setAddChildLoading] = useState(false);
  const [addChildError, setAddChildError] = useState('');
  const [addChildInviteLink, setAddChildInviteLink] = useState('');

  // Add Course modal state
  const [showAddCourseModal, setShowAddCourseModal] = useState(false);
  const [addCourseName, setAddCourseName] = useState('');
  const [addCourseDesc, setAddCourseDesc] = useState('');
  const [addCourseSubject, setAddCourseSubject] = useState('');
  const [addCourseLoading, setAddCourseLoading] = useState(false);
  const [addCourseError, setAddCourseError] = useState('');

  // Edit child state
  const [editingChild, setEditingChild] = useState<ChildSummary | null>(null);
  const [editName, setEditName] = useState('');
  const [editGrade, setEditGrade] = useState('');
  const [editSchool, setEditSchool] = useState('');
  const [editLoading, setEditLoading] = useState(false);
  const [editError, setEditError] = useState('');

  // Invite resend state
  const [resendingInviteId, setResendingInviteId] = useState<number | null>(null);
  const [resendSuccess, setResendSuccess] = useState<number | null>(null);
  const [copiedInviteId, setCopiedInviteId] = useState<number | null>(null);
  const [openChildMenuId, setOpenChildMenuId] = useState<number | null>(null);

  // Focus traps for modals
  const addChildModalRef = useFocusTrap<HTMLDivElement>(showAddChildModal);
  const addCourseModalRef = useFocusTrap<HTMLDivElement>(showAddCourseModal);
  const assignCourseModalRef = useFocusTrap<HTMLDivElement>(!!assignCourseModal, () => setAssignCourseModal(null));
  const reassignContentModalRef = useFocusTrap<HTMLDivElement>(!!reassignContent, () => setReassignContent(null));

  // Close child context menu on outside click
  useEffect(() => {
    if (!openChildMenuId) return;
    const close = () => setOpenChildMenuId(null);
    document.addEventListener('click', close);
    return () => document.removeEventListener('click', close);
  }, [openChildMenuId]);

  useEffect(() => {
    (async () => {
      try {
        const kids = await parentApi.getChildren();
        setChildren(kids);
        const urlSid = urlStudentId ? Number(urlStudentId) : null;
        const match = urlSid ? kids.find(k => k.student_id === urlSid) : null;
        if (match) {
          setSelectedChild(match.student_id);
        } else {
          // Restore persisted child selection from sessionStorage
          const storedUserId = sessionStorage.getItem('selectedChildId');
          const parsedUserId = storedUserId ? Number(storedUserId) : NaN;
          const storedMatch = !isNaN(parsedUserId) ? kids.find(k => k.user_id === parsedUserId) : null;
          if (storedMatch) {
            setSelectedChild(storedMatch.student_id);
          } else if (kids.length === 1) {
            setSelectedChild(kids[0].student_id);
          }
        }
      } catch { /* */ }
      finally { setLoading(false); }
    })();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Load child data when selection changes
  useEffect(() => {
    if (!selectedChild) {
      setOverview(null);
      setTasks([]);
      setLinkedTeachers([]);
      // Load unassigned courses/materials for "All Children" view
      if (children.length > 0) {
        setSectionLoading(true);
        Promise.all([
          coursesApi.list(),
          courseContentsApi.listAll(),
          ...children.map(c => parentApi.getChildOverview(c.student_id)),
        ]).then(([courseList, mats, ...overviews]) => {
          const typedOverviews = overviews as ChildOverview[];
          const enrolled = new Set<number>();
          typedOverviews.forEach(ov => {
            ov.courses.forEach(c => enrolled.add(c.id));
          });
          const unassigned = (courseList as Array<{ id: number; name: string }>).filter(c => !enrolled.has(c.id));
          setUnassignedCourses(unassigned);
          const unassignedIds = new Set(unassigned.map(c => c.id));
          setUnassignedMaterials((mats as CourseContentItem[]).filter(m => !m.archived_at && unassignedIds.has(m.course_id)));
          // Store ALL non-archived materials for the "all children" Class Materials panel
          setMaterials((mats as CourseContentItem[]).filter(m => !m.archived_at));
          setCourses(courseList);
        }).catch(() => {
          setUnassignedCourses([]);
          setUnassignedMaterials([]);
          setMaterials([]);
        }).finally(() => setSectionLoading(false));
      }
      return;
    }
    const child = children.find(c => c.student_id === selectedChild);
    if (!child) return;

    setSectionLoading(true);
    Promise.all([
      parentApi.getChildOverview(selectedChild),
      courseContentsApi.listAll({ student_user_id: child.user_id }),
      tasksApi.list({ assigned_to_user_id: child.user_id }),
      parentApi.getLinkedTeachers(selectedChild),
      coursesApi.list(),
    ]).then(([ov, mats, tks, teachers, courseList]) => {
      setOverview(ov);
      setMaterials(mats.filter(m => !m.archived_at));
      setTasks(tks.filter(t => !t.archived_at));
      setLinkedTeachers(teachers);
      setCourses(courseList);
    }).catch(() => {
      setOverview(null);
      setMaterials([]);
      setTasks([]);
      setLinkedTeachers([]);
    }).finally(() => setSectionLoading(false));
  }, [selectedChild, children]);

  // Per-child task stats for the selected child (must be before early returns to follow Rules of Hooks)
  const selectedTaskStats = useMemo(() => {
    if (!selectedChild || tasks.length === 0) return null;
    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const activeTasks = tasks.filter(t => !t.is_completed);
    const completedTasks = tasks.filter(t => t.is_completed);
    const totalTasks = tasks.length;
    const completed = completedTasks.length;
    const completionPct = totalTasks > 0 ? Math.round((completed / totalTasks) * 100) : 0;
    const pendingWithDue = activeTasks
      .filter(t => t.due_date)
      .sort((a, b) => new Date(a.due_date!).getTime() - new Date(b.due_date!).getTime());
    let nextDeadline: { title: string; label: string } | null = null;
    if (pendingWithDue.length > 0) {
      const next = pendingWithDue[0];
      const dueDate = new Date(next.due_date!);
      const diffDays = Math.floor((dueDate.getTime() - todayStart.getTime()) / 86400000);
      let label: string;
      if (diffDays < 0) label = `overdue by ${Math.abs(diffDays)}d`;
      else if (diffDays === 0) label = 'due today';
      else if (diffDays === 1) label = 'due tomorrow';
      else label = `due in ${diffDays} days`;
      nextDeadline = { title: next.title, label };
    }
    return { totalTasks, completed, completionPct, nextDeadline };
  }, [selectedChild, tasks]);


  const sidebarActions = [
    { label: '+ Course Material', icon: '\u{1F4C4}', onClick: () => navigate('/course-materials') },
    { label: '+ Task', icon: '\u2705', onClick: () => navigate('/tasks') },
    { label: '+ Add Child', icon: '\u{1F476}', onClick: () => setShowAddChildModal(true) },
    { label: 'Export Data', icon: '\u{1F4E5}', onClick: () => navigate('/settings/data-export') },
  ];

  if (loading) {
    return (
      <DashboardLayout welcomeSubtitle="Manage your children's education" showBackButton sidebarActions={sidebarActions}>
        <PageSkeleton />
      </DashboardLayout>
    );
  }

  // Empty state check moved after all const/function declarations to avoid
  // TDZ errors in minified builds (const handlers must be initialized first)

  const openReassignModal = (m: CourseContentItem) => {
    setReassignContent(m);
    setCategorizeCourseId('');
    setCategorizeSearch('');
    setCategorizeNewName('');
  };

  const handleReassignContent = async (courseId?: number) => {
    if (!reassignContent) return;
    const targetCourseId = courseId ?? (categorizeCourseId ? Number(categorizeCourseId) : null);
    if (!targetCourseId) return;
    try {
      await courseContentsApi.update(reassignContent.id, { course_id: targetCourseId });
      const targetCourseName = courses.find(c => c.id === targetCourseId)?.name ?? null;
      // Update child-view materials list
      setMaterials(prev => prev.map(m =>
        m.id === reassignContent.id
          ? { ...m, course_id: targetCourseId, course_name: targetCourseName }
          : m
      ));
      // Update unassigned materials: remove if moved to enrolled course, update if moved to another unassigned course
      const isTargetUnassigned = unassignedCourses.some(c => c.id === targetCourseId);
      if (isTargetUnassigned) {
        setUnassignedMaterials(prev => prev.map(m =>
          m.id === reassignContent.id
            ? { ...m, course_id: targetCourseId, course_name: targetCourseName }
            : m
        ));
      } else {
        setUnassignedMaterials(prev => prev.filter(m => m.id !== reassignContent.id));
      }
      setReassignContent(null);
    } catch { /* ignore */ }
  };

  const handleCreateAndReassign = async () => {
    if (!reassignContent || !categorizeNewName.trim()) return;
    setCategorizeCreating(true);
    try {
      const newCourse = await coursesApi.create({ name: categorizeNewName.trim() });
      setCourses(prev => [...prev, newCourse]);
      // New course has no child enrolled — add to unassigned so handleReassignContent keeps the material visible
      setUnassignedCourses(prev => [...prev, { id: newCourse.id, name: newCourse.name }]);
      await handleReassignContent(newCourse.id);
    } catch { /* ignore */ }
    setCategorizeCreating(false);
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
      // Refresh children list
      const kids = await parentApi.getChildren();
      setChildren(kids);
      if (kids.length === 1) setSelectedChild(kids[0].student_id);
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
      // Refresh children list
      const kids = await parentApi.getChildren();
      setChildren(kids);
      if (kids.length === 1) setSelectedChild(kids[0].student_id);
    } catch (err: any) {
      setAddChildError(err.response?.data?.detail || 'Failed to link child');
    } finally {
      setAddChildLoading(false);
    }
  };

  const closeAddCourseModal = () => {
    setShowAddCourseModal(false);
    setAddCourseName('');
    setAddCourseDesc('');
    setAddCourseSubject('');
    setAddCourseError('');
  };

  const handleAddCourse = async () => {
    if (!addCourseName.trim()) return;
    setAddCourseLoading(true);
    setAddCourseError('');
    try {
      const newCourse = await coursesApi.create({
        name: addCourseName.trim(),
        description: addCourseDesc.trim() || undefined,
        subject: addCourseSubject.trim() || undefined,
      });
      setCourses(prev => [...prev, newCourse]);
      // Auto-assign to the selected child if one is selected
      if (selectedChild) {
        await parentApi.assignCoursesToChild(selectedChild, [newCourse.id]);
        // Update overview courses locally
        setOverview(prev => prev ? {
          ...prev,
          courses: [...prev.courses, {
            id: newCourse.id, name: newCourse.name,
            description: newCourse.description || null,
            subject: newCourse.subject || null,
            google_classroom_id: null, teacher_id: null,
            created_at: new Date().toISOString(),
            teacher_name: null, teacher_email: null,
          }],
        } : prev);
        // Update child's course count locally
        setChildren(prev => prev.map(c =>
          c.student_id === selectedChild
            ? { ...c, course_count: c.course_count + 1 }
            : c
        ));
      } else {
        // No child selected — add to unassigned courses
        setUnassignedCourses(prev => [...prev, { id: newCourse.id, name: newCourse.name }]);
      }
      closeAddCourseModal();
    } catch (err: any) {
      setAddCourseError(err.response?.data?.detail || 'Failed to create class');
    } finally {
      setAddCourseLoading(false);
    }
  };

  function renderAddChildModal() { return (
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
  ); }

  // Empty state: no children linked yet (placed after all declarations to avoid TDZ)
  if (children.length === 0) {
    return (
      <DashboardLayout welcomeSubtitle="Manage your children's education" showBackButton sidebarActions={sidebarActions}>
        <div className="pd-empty-state">
          <div className="pd-empty-state-icon">&#128102;</div>
          <h3 className="pd-empty-state-title">No children linked yet</h3>
          <p className="pd-empty-state-text">Add your child to start managing their education.</p>
          <button className="pd-empty-state-cta" onClick={() => setShowAddChildModal(true)}>
            + Add Child
          </button>
        </div>
        {showAddChildModal && renderAddChildModal()}
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout welcomeSubtitle="Manage your children's education" showBackButton sidebarActions={sidebarActions}>
      <PageNav items={[
        { label: 'Home', to: '/dashboard' },
        { label: 'My Kids' },
      ]} />
      <JourneyNudgeBanner pageName="my-kids" />
      {/* Child Tabs */}
      <div className="pd-child-selector-wrapper">
        <div className="pd-child-selector">
        {/* "All" button — shown when there are multiple children */}
        {children.length > 1 && (
          <button
            className={`pd-child-tab pd-child-tab-all ${selectedChild === null ? 'active' : ''}`}
            onClick={() => { setSelectedChild(null); sessionStorage.removeItem('selectedChildId'); }}
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
          <div key={child.student_id} className="child-tab-wrapper">
            <button
              className={`pd-child-tab ${selectedChild === child.student_id ? 'active' : ''}`}
              onClick={() => {
                if (selectedChild === child.student_id) {
                  setSelectedChild(null);
                  sessionStorage.removeItem('selectedChildId');
                } else {
                  setSelectedChild(child.student_id);
                  sessionStorage.setItem('selectedChildId', String(child.user_id));
                }
              }}
            >
              <span className="pd-child-color-dot" style={{ backgroundColor: CHILD_COLORS[index % CHILD_COLORS.length] }} />
              {child.full_name}
              {child.grade_level != null && <span className="pd-grade-badge">Grade {child.grade_level}</span>}
              {child.invite_status && (
                <span className={`invite-status-badge invite-status-${child.invite_status}`}>
                  {child.invite_status === 'active' ? 'Active' : child.invite_status === 'pending' ? 'Pending' : 'Unverified'}
                </span>
              )}
              <span className="child-tab-detail">
                {child.school_name && <>{child.school_name} · </>}
                {child.course_count} {child.course_count === 1 ? 'class' : 'classes'} · {child.active_task_count} {child.active_task_count === 1 ? 'task' : 'tasks'}
              </span>
              <ChildXpStats studentId={child.student_id} />
              <OnTrackBadge studentId={child.student_id} />
            </button>
            <div className="invite-menu-wrapper">
              <button
                className="invite-menu-trigger"
                title="Child options"
                onClick={(e) => {
                  e.stopPropagation();
                  setOpenChildMenuId(openChildMenuId === child.student_id ? null : child.student_id);
                }}
              >
                ···
              </button>
              {openChildMenuId === child.student_id && (
                <div className="invite-menu-dropdown" onClick={(e) => e.stopPropagation()}>
                  <button
                    className="invite-menu-item"
                    onClick={() => {
                      setOpenChildMenuId(null);
                      setEditingChild(child);
                      setEditName(child.full_name);
                      setEditGrade(child.grade_level != null ? String(child.grade_level) : '');
                      setEditSchool(child.school_name || '');
                    }}
                  >
                    Edit Child
                  </button>
                  {child.invite_status === 'pending' && child.invite_id && (
                    <>
                      <button
                        className="invite-menu-item"
                        disabled={resendingInviteId === child.invite_id}
                        onClick={async () => {
                          setResendingInviteId(child.invite_id);
                          setResendSuccess(null);
                          try {
                            await invitesApi.resend(child.invite_id!);
                            setResendSuccess(child.invite_id);
                            setTimeout(() => setResendSuccess(null), 3000);
                          } catch {
                            /* rate limit or other error — silently handled */
                          } finally {
                            setResendingInviteId(null);
                          }
                        }}
                      >
                        {resendingInviteId === child.invite_id ? 'Sending...' : resendSuccess === child.invite_id ? '✓ Sent!' : 'Resend Invite'}
                      </button>
                      <button
                        className="invite-menu-item"
                        onClick={async () => {
                          const link = child.invite_link ?? `${window.location.origin}/accept-invite`;
                          await navigator.clipboard.writeText(link);
                          setCopiedInviteId(child.invite_id);
                          setOpenChildMenuId(null);
                          setTimeout(() => setCopiedInviteId(null), 2000);
                        }}
                      >
                        {copiedInviteId === child.invite_id ? '✓ Copied!' : 'Copy Invite Link'}
                      </button>
                    </>
                  )}
                  <button
                    className="invite-menu-item"
                    onClick={() => {
                      setOpenChildMenuId(null);
                      setAwardXpChild({ studentId: child.student_id, userId: child.user_id, name: child.full_name });
                    }}
                  >
                    Award XP
                  </button>
                  <button
                    className="invite-menu-item invite-menu-item--danger"
                    onClick={async () => {
                      setOpenChildMenuId(null);
                      const ok = await confirm({
                        title: 'Remove Child',
                        message: `Are you sure you want to remove ${child.full_name}? This will unlink them from your account but won't delete their account.`,
                        confirmLabel: 'Remove',
                        variant: 'danger',
                      });
                      if (!ok) return;
                      try {
                        await parentApi.removeChild(child.student_id);
                        toast(`${child.full_name} has been removed`, 'success');
                        setChildren(prev => prev.filter(c => c.student_id !== child.student_id));
                        if (selectedChild === child.student_id) setSelectedChild(null);
                      } catch {
                        toast('Failed to remove child', 'error');
                      }
                    }}
                  >
                    Remove Child
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
        <AddActionButton actions={[
          { icon: '\u{1F4C4}', label: 'Class Material', onClick: () => studyTools.setShowStudyModal(true), showPlus: true },
          { icon: '\u{1F4DA}', label: 'Add Class', onClick: () => setShowAddCourseModal(true), showPlus: true },
          { icon: '\u{1F4CA}', label: 'Quiz History', onClick: () => navigate('/quiz-history') },
          { icon: '\u{1F476}', label: 'Add Child', onClick: () => setShowAddChildModal(true), showPlus: true },
          { icon: '\u{1F4E5}', label: 'Export Data', onClick: () => navigate('/settings/data-export') },
          ...(selectedChild ? [{ icon: '\u{1F511}', label: 'Reset Password', onClick: () => {
            setShowResetPassword(true);
            const child = children.find(c => c.student_id === selectedChild);
            setResetPwMethod(child?.email ? 'email' : 'direct');
            setResetPwValue(''); setResetPwConfirm(''); setResetPwError(''); setResetPwSuccess('');
          }}] : []),
        ]} />
        </div>
      </div>

      {!selectedChild ? (
        /* All-children overview — two-column grid with materials, study times, and unassigned sections */
        <>
          {sectionLoading ? (
            <PageSkeleton />
          ) : (
            <div className="dashboard-redesign">
              {/* ── Class Materials (all children) ───────── */}
              <SectionPanel
                title="Class Materials"
                icon="&#128196;"
                count={materials.length}
                collapsed={!showMaterials}
                onToggle={() => setShowMaterials(p => !p)}
                headerRight={
                  materials.length > 0 ? (
                    <button
                      className="section-panel__view-all"
                      onClick={(e) => { e.stopPropagation(); navigate('/course-materials'); }}
                    >
                      View All
                    </button>
                  ) : undefined
                }
              >
                <div className="mykids-list">
                  {materials.length === 0 ? (
                    <p className="dash-empty-hint">No class materials yet.</p>
                  ) : recentMaterials.map(m => (
                    <div key={m.id} className="mykids-list-row" onClick={() => navigate(`/course-materials/${m.id}`)} onKeyDown={(e) => handleKeyDown(e, () => navigate(`/course-materials/${m.id}`))} role="button" tabIndex={0}>
                      <div className="mykids-list-body">
                        <span className="mykids-list-title">{m.title}</span>
                        <span className="mykids-list-meta">
                          <span className="mykids-badge">{m.content_type}</span>
                          {m.course_name && <span> &middot; {m.course_name}</span>}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </SectionPanel>

              {/* ── Best Study Times (per child) ───────── */}
              {children.map(child => (
                <StudyTimeSuggestions key={child.student_id} studentId={child.student_id} />
              ))}

              {/* ── Unassigned Classes ─────────────────── */}
              {unassignedCourses.length > 0 && (
                <SectionPanel title="Unassigned Classes" icon="&#128218;" count={unassignedCourses.length} collapsed={!showUnassignedCourses} onToggle={() => setShowUnassignedCourses(p => !p)}>
                  <div className="mykids-list">
                    {unassignedCourses.map(c => (
                      <div key={c.id} className="mykids-list-row" onClick={() => navigate(`/courses/${c.id}`)} onKeyDown={(e) => handleKeyDown(e, () => navigate(`/courses/${c.id}`))} role="button" tabIndex={0}>
                        <div className="mykids-list-body">
                          <span className="mykids-list-title">{c.name}</span>
                          <span className="mykids-list-meta">
                            {c.subject && <span>{c.subject}</span>}
                            {c.teacher_name && <span>{c.subject ? ' \u00B7 ' : ''}{c.teacher_name}</span>}
                            {!c.subject && !c.teacher_name && <span>No child assigned</span>}
                          </span>
                        </div>
                        <button className="mykids-list-action-btn" title="Assign to child" onClick={(e) => { e.stopPropagation(); setAssignCourseModal(c); }}>&#43;</button>
                      </div>
                    ))}
                  </div>
                </SectionPanel>
              )}

              {/* ── Unassigned Materials ───────────────── */}
              {unassignedMaterials.length > 0 && (
                <SectionPanel title="Unassigned Materials" icon="&#128196;" count={unassignedMaterials.length} collapsed={!showUnassignedMaterials} onToggle={() => setShowUnassignedMaterials(p => !p)}>
                  <div className="mykids-list">
                    {unassignedMaterials.map(m => (
                      <div key={m.id} className="mykids-list-row" onClick={() => navigate(`/course-materials/${m.id}`)} onKeyDown={(e) => handleKeyDown(e, () => navigate(`/course-materials/${m.id}`))} role="button" tabIndex={0}>
                        <div className="mykids-list-body">
                          <span className="mykids-list-title">{m.title}</span>
                          <span className="mykids-list-meta">
                            <span className="mykids-badge">{m.content_type}</span>
                            {m.course_name && <span> &middot; {m.course_name}</span>}
                          </span>
                        </div>
                        <button className="mykids-list-action-btn" title="Move to class" onClick={(e) => { e.stopPropagation(); openReassignModal(m); }}>&#128194;</button>
                      </div>
                    ))}
                  </div>
                </SectionPanel>
              )}
            </div>
          )}
        </>
      ) : sectionLoading ? (
        <PageSkeleton />
      ) : (
        <>
          {/* ── Progress Summary ──────────────────── */}
          {selectedTaskStats && selectedTaskStats.totalTasks > 0 && (() => {
            const childIndex = children.findIndex(c => c.student_id === selectedChild);
            const color = CHILD_COLORS[childIndex >= 0 ? childIndex % CHILD_COLORS.length : 0];
            return (
              <div className="mykids-progress-summary">
                <div className="mykids-progress-info">
                  <span className="mykids-progress-text">
                    {selectedTaskStats.completed}/{selectedTaskStats.totalTasks} tasks complete
                  </span>
                  {selectedTaskStats.nextDeadline && (
                    <span className="mykids-next-deadline">
                      Next: <strong>{selectedTaskStats.nextDeadline.title}</strong> — {selectedTaskStats.nextDeadline.label}
                    </span>
                  )}
                </div>
                <div className="mykids-progress-bar-wrap">
                  <div className="mykids-progress-bar">
                    <div className="mykids-progress-fill" style={{ width: `${selectedTaskStats.completionPct}%`, backgroundColor: color }} />
                  </div>
                  <span className="mykids-progress-pct">{selectedTaskStats.completionPct}%</span>
                </div>
              </div>
            );
          })()}

          {/* ── Quick Actions ──────────────────────── */}
          <div className="dash-quick-actions" style={{ marginBottom: 16 }}>
            <button className="dash-quick-action" onClick={() => navigate('/study')}>
              <span className="dash-quick-action-icon" aria-hidden="true">&#128214;</span>
              <span>Study</span>
            </button>
            <button className="dash-quick-action" onClick={() => navigate(selectedChild ? `/tasks?student_id=${selectedChild}` : '/tasks')}>
              <span className="dash-quick-action-icon" aria-hidden="true">&#9989;</span>
              <span>View Tasks</span>
            </button>
            <button className="dash-quick-action" onClick={() => navigate('/courses')}>
              <span className="dash-quick-action-icon" aria-hidden="true">&#128218;</span>
              <span>View Classes</span>
            </button>
            <button className="dash-quick-action" onClick={() => navigate('/course-materials')}>
              <span className="dash-quick-action-icon" aria-hidden="true">&#128196;</span>
              <span>View Class Material</span>
            </button>
            <button className="dash-quick-action" onClick={() => navigate('/ai-tools')}>
              <span className="dash-quick-action-icon" aria-hidden="true">&#128161;</span>
              <span>Help My Kid</span>
            </button>
            <button className="dash-quick-action" onClick={() => setShowStudyRequest(true)}>
              <span className="dash-quick-action-icon" aria-hidden="true">&#128172;</span>
              <span>Request Study</span>
            </button>
            <button className="dash-quick-action" onClick={() => navigate('/school-report-cards')}>
              <span className="dash-quick-action-icon" aria-hidden="true">&#x1F4CB;</span>
              <span>Report Cards</span>
            </button>
            <button className="dash-quick-action" onClick={() => setShowEmailDigestWizard(true)}>
              <span className="dash-quick-action-icon" aria-hidden="true">&#x1F4E7;</span>
              <span>Email Digest</span>
            </button>
          </div>

          <div className="dashboard-redesign">
          {/* ── Class Materials ───────────────────── */}
          <SectionPanel title="Class Materials" icon="&#128196;" count={materials.length} collapsed={!showMaterials} onToggle={() => setShowMaterials(p => !p)} headerRight={
            materials.length > 0 ? (
              <button
                className="section-panel__view-all"
                onClick={(e) => { e.stopPropagation(); navigate('/course-materials'); }}
              >
                View All
              </button>
            ) : undefined
          }>
              <div className="mykids-list">
                {materials.length === 0 ? (
                  <p className="dash-empty-hint">No class materials yet.</p>
                ) : recentMaterials.map(m => (
                  <div key={m.id} className="mykids-list-row" onClick={() => navigate(`/course-materials/${m.id}`)} onKeyDown={(e) => handleKeyDown(e, () => navigate(`/course-materials/${m.id}`))} role="button" tabIndex={0}>
                    <div className="mykids-list-body">
                      <span className="mykids-list-title">{m.title}</span>
                      <span className="mykids-list-meta">
                        <span className="mykids-badge">{m.content_type}</span>
                        {m.course_name && <span> &middot; {m.course_name}</span>}
                      </span>
                    </div>
                    <button
                            className="mykids-list-action-btn"
                      title="Move to class"
                      onClick={(e) => { e.stopPropagation(); openReassignModal(m); }}
                    >&#128194;</button>
                  </div>
                ))}
              </div>
          </SectionPanel>

          {/* ── Best Study Times ──────────────────── */}
          {selectedChild && <StudyTimeSuggestions studentId={selectedChild} />}

          {/* ── Courses ───────────────────────────── */}
          <SectionPanel title="Classes" icon="&#128218;" count={overview?.courses.length ?? 0} collapsed={!showCourses} onToggle={() => setShowCourses(p => !p)}>
            {overview && (
              <div className="mykids-list">
                {overview.courses.length === 0 ? (
                  <GoogleClassroomPrompt
                    childName={children.find(c => c.student_id === selectedChild)?.full_name ?? 'your child'}
                    childStudentId={selectedChild}
                    onAddManually={() => setShowAddCourseModal(true)}
                  />
                ) : overview.courses.map(c => (
                  <div key={c.id} className="mykids-list-row" onClick={() => navigate(`/courses/${c.id}`)} onKeyDown={(e) => handleKeyDown(e, () => navigate(`/courses/${c.id}`))} role="button" tabIndex={0}>
                    <div className="mykids-list-body">
                      <span className="mykids-list-title">{c.name}</span>
                      <span className="mykids-list-meta">
                        {c.subject && <span>{c.subject}</span>}
                        {c.teacher_name && <span>{c.subject ? ' \u00B7 ' : ''}{c.teacher_name}</span>}
                      </span>
                    </div>
                    <span className="mykids-list-chevron">&#8250;</span>
                  </div>
                ))}
              </div>
            )}
          </SectionPanel>

          {/* ── Dinner Table Talk ──────────────────── */}
          <SectionPanel title="Dinner Table Talk" icon="&#128172;" collapsed={!showConversation} onToggle={() => setShowConversation(p => !p)}>
                <ConversationStartersCard studentId={selectedChild} />
          </SectionPanel>

          {/* ── Grades ────────────────────────────── */}
          <SectionPanel title="Grades" icon="&#128202;" collapsed={!showGrades} onToggle={() => setShowGrades(p => !p)}>
              <GradesSummaryCard
                selectedChildId={selectedChild ?? undefined}
                onViewDetails={() => navigate('/grades')}
              />
          </SectionPanel>

          {/* ── Linked Teachers ────────────────────── */}
          <SectionPanel title="Teachers" icon="&#128105;&#8205;&#127979;" count={(overview?.courses.filter(c => c.teacher_name).length ?? 0) + linkedTeachers.length} collapsed={!showTeachers} onToggle={() => setShowTeachers(p => !p)} className="dash-section--full" headerRight={<button className="mykids-add-teacher-btn btn-primary btn-sm" onClick={(e) => { e.stopPropagation(); setShowAddTeacher(true); setTeacherEmail(''); setTeacherName(''); setAddTeacherError(''); }}>+ Add Teacher</button>}>
              <div className="mykids-list">
                {/* Teachers from courses */}
                {overview?.courses.filter(c => c.teacher_name).map(c => (
                  <div key={`course-${c.id}`} className="mykids-teacher-row">
                    <div className="mykids-teacher-info">
                      <span className="mykids-teacher-name">{c.teacher_name}</span>
                      <span className="mykids-teacher-email">{c.teacher_email || c.name} (via class)</span>
                    </div>
                    {c.teacher_id && (
                      <button
                        className="mykids-message-btn btn-secondary btn-sm"
                        onClick={() => navigate(`/messages?recipient_id=${c.teacher_id}`)}
                      >
                        Message
                      </button>
                    )}
                  </div>
                ))}
                {/* Directly linked teachers */}
                {linkedTeachers.map(t => (
                  <div key={`link-${t.id}`} className="mykids-teacher-row">
                    <div className="mykids-teacher-info">
                      <span className="mykids-teacher-name">{t.teacher_name || 'Unknown'}</span>
                      <span className="mykids-teacher-email">{t.teacher_email}</span>
                    </div>
                    {t.teacher_user_id && (
                      <button
                        className="mykids-message-btn btn-secondary btn-sm"
                        onClick={() => navigate(`/messages?recipient_id=${t.teacher_user_id}`)}
                      >
                        Message
                      </button>
                    )}
                    <button
                      className="mykids-remove-btn btn-danger btn-sm"
                      onClick={async () => {
                        if (!selectedChild) return;
                        const ok = await confirm({ title: 'Remove Teacher', message: `Remove ${t.teacher_name || t.teacher_email} as a linked teacher?`, confirmLabel: 'Remove', variant: 'danger' });
                        if (!ok) return;
                        await parentApi.unlinkTeacher(selectedChild, t.id);
                        setLinkedTeachers(prev => prev.filter(lt => lt.id !== t.id));
                      }}
                    >
                      Remove
                    </button>
                  </div>
                ))}
                {(overview?.courses.filter(c => c.teacher_name).length ?? 0) === 0 && linkedTeachers.length === 0 && (
                  <p className="dash-empty-hint">No teachers linked yet. Add a teacher by email to start messaging.</p>
                )}
              </div>
          </SectionPanel>
        </div>
        </>
      )}
      {/* Add Teacher Modal */}
      {showAddTeacher && selectedChild && (
        <div className="mykids-modal-overlay" onClick={() => setShowAddTeacher(false)}>
          <div className="mykids-modal" onClick={e => e.stopPropagation()}>
            <h3>Add Teacher</h3>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 16 }}>
              Link a teacher by email so you can send them messages directly.
            </p>
            {addTeacherError && <div className="mykids-modal-error">{addTeacherError}</div>}
            <label>Teacher Email *</label>
            <input
              type="email"
              placeholder="teacher@school.edu"
              value={teacherEmail}
              onChange={e => setTeacherEmail(e.target.value)}
            />
            <label>Teacher Name (optional)</label>
            <input
              type="text"
              placeholder="Ms. Smith"
              value={teacherName}
              onChange={e => setTeacherName(e.target.value)}
            />
            <div className="mykids-modal-actions">
              <button onClick={() => setShowAddTeacher(false)}>Cancel</button>
              <button
                className="mykids-modal-submit generate-btn"
                disabled={addTeacherLoading || !teacherEmail.trim()}
                onClick={async () => {
                  if (!isValidEmail(teacherEmail.trim())) {
                    setAddTeacherError('Please enter a valid email address');
                    return;
                  }
                  setAddTeacherLoading(true);
                  setAddTeacherError('');
                  try {
                    const linked = await parentApi.linkTeacher(
                      selectedChild,
                      teacherEmail.trim(),
                      teacherName.trim() || undefined,
                    );
                    setLinkedTeachers(prev => [...prev, linked]);
                    setShowAddTeacher(false);
                  } catch (err: any) {
                    setAddTeacherError(err?.response?.data?.detail || 'Failed to link teacher');
                  } finally {
                    setAddTeacherLoading(false);
                  }
                }}
              >
                {addTeacherLoading ? 'Adding...' : 'Add Teacher'}
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Reset Password Modal */}
      {showResetPassword && selectedChild && (
        <div className="mykids-modal-overlay" onClick={() => setShowResetPassword(false)}>
          <div className="mykids-modal" onClick={e => e.stopPropagation()}>
            <h3>Reset Password</h3>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 16 }}>
              {children.find(c => c.student_id === selectedChild)?.full_name}
            </p>
            {resetPwSuccess ? (
              <div style={{ padding: '12px 16px', background: 'var(--success-bg, #ecfdf5)', color: 'var(--success, #059669)', borderRadius: 8, fontSize: 14 }}>
                {resetPwSuccess}
              </div>
            ) : (
              <>
                {children.find(c => c.student_id === selectedChild)?.email && (
                  <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
                    <button
                      className={`mykids-tab-btn${resetPwMethod === 'email' ? ' active' : ''}`}
                      onClick={() => setResetPwMethod('email')}
                      style={{ flex: 1, padding: '8px 12px', borderRadius: 6, border: '1px solid var(--border)', background: resetPwMethod === 'email' ? 'var(--accent)' : 'transparent', color: resetPwMethod === 'email' ? 'white' : 'var(--text-primary)', cursor: 'pointer', fontSize: 13 }}
                    >
                      Send Reset Email
                    </button>
                    <button
                      className={`mykids-tab-btn${resetPwMethod === 'direct' ? ' active' : ''}`}
                      onClick={() => setResetPwMethod('direct')}
                      style={{ flex: 1, padding: '8px 12px', borderRadius: 6, border: '1px solid var(--border)', background: resetPwMethod === 'direct' ? 'var(--accent)' : 'transparent', color: resetPwMethod === 'direct' ? 'white' : 'var(--text-primary)', cursor: 'pointer', fontSize: 13 }}
                    >
                      Set Directly
                    </button>
                  </div>
                )}
                {resetPwError && <div className="mykids-modal-error">{resetPwError}</div>}
                {resetPwMethod === 'direct' ? (
                  <>
                    <label>New Password</label>
                    <input
                      type="password"
                      placeholder="Min 8 chars, upper, lower, digit, special"
                      value={resetPwValue}
                      onChange={e => setResetPwValue(e.target.value)}
                    />
                    <label style={{ marginTop: 8 }}>Confirm Password</label>
                    <input
                      type="password"
                      placeholder="Confirm password"
                      value={resetPwConfirm}
                      onChange={e => setResetPwConfirm(e.target.value)}
                    />
                  </>
                ) : (
                  <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                    A password reset link will be sent to <strong>{children.find(c => c.student_id === selectedChild)?.email}</strong>.
                  </p>
                )}
              </>
            )}
            <div className="mykids-modal-actions">
              <button onClick={() => setShowResetPassword(false)}>
                {resetPwSuccess ? 'Close' : 'Cancel'}
              </button>
              {!resetPwSuccess && (
                <button
                  className="mykids-modal-submit generate-btn"
                  disabled={resetPwLoading || (resetPwMethod === 'direct' && !resetPwValue.trim())}
                  onClick={async () => {
                    if (resetPwMethod === 'direct') {
                      if (resetPwValue !== resetPwConfirm) {
                        setResetPwError('Passwords do not match');
                        return;
                      }
                    }
                    setResetPwLoading(true);
                    setResetPwError('');
                    try {
                      const result = await parentApi.resetChildPassword(
                        selectedChild,
                        resetPwMethod === 'direct' ? resetPwValue : undefined,
                      );
                      setResetPwSuccess(result.message);
                    } catch (err: any) {
                      setResetPwError(err?.response?.data?.detail || 'Failed to reset password');
                    } finally {
                      setResetPwLoading(false);
                    }
                  }}
                >
                  {resetPwLoading ? 'Processing...' : resetPwMethod === 'email' ? 'Send Reset Email' : 'Set Password'}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
      {/* Reassign class material to course modal */}
      {reassignContent && (
        <div className="modal-overlay" onClick={() => setReassignContent(null)}>
          <div className="modal" role="dialog" aria-modal="true" aria-label="Move to Class" ref={reassignContentModalRef} onClick={(e) => e.stopPropagation()}>
            <h2>Move to Class</h2>
            <p className="modal-desc">Assign &ldquo;{reassignContent.title}&rdquo; to a class.</p>
            <div className="modal-form">
              <input
                type="text"
                placeholder="Search classes or type a new name..."
                value={categorizeSearch}
                onChange={(e) => { setCategorizeSearch(e.target.value); setCategorizeCourseId(''); setCategorizeNewName(''); }}
                autoFocus
              />
              <div className="categorize-list">
                {courses
                  .filter(c => !categorizeSearch || c.name.toLowerCase().includes(categorizeSearch.toLowerCase()))
                  .map(c => (
                    <div
                      key={c.id}
                      className={`categorize-item${categorizeCourseId === c.id ? ' selected' : ''}${c.id === reassignContent.course_id ? ' current' : ''}`}
                      onClick={() => { setCategorizeCourseId(c.id); setCategorizeNewName(''); }}
                    >
                      &#127891; {c.name}{c.id === reassignContent.course_id ? ' (current)' : ''}
                    </div>
                  ))
                }
                {categorizeSearch.trim() && !courses.some(c => c.name.toLowerCase() === categorizeSearch.trim().toLowerCase()) && (
                  <div
                    className={`categorize-item create-new${categorizeNewName ? ' selected' : ''}`}
                    onClick={() => { setCategorizeNewName(categorizeSearch.trim()); setCategorizeCourseId(''); }}
                  >
                    &#10133; Create &ldquo;{categorizeSearch.trim()}&rdquo;
                  </div>
                )}
              </div>
            </div>
            <div className="modal-actions">
              <button className="cancel-btn" onClick={() => setReassignContent(null)}>Cancel</button>
              {categorizeNewName ? (
                <button className="generate-btn" disabled={categorizeCreating} onClick={handleCreateAndReassign}>
                  {categorizeCreating ? 'Creating...' : 'Create & Move'}
                </button>
              ) : (
                <button className="generate-btn" disabled={!categorizeCourseId || categorizeCourseId === reassignContent.course_id} onClick={() => handleReassignContent()}>Move</button>
              )}
            </div>
          </div>
        </div>
      )}
      {/* Assign Course to Child Modal */}
      {assignCourseModal && (
        <div className="mykids-modal-overlay" onClick={() => setAssignCourseModal(null)}>
          <div className="mykids-modal" role="dialog" aria-modal="true" aria-label="Assign Class to Child" ref={assignCourseModalRef} onClick={e => e.stopPropagation()}>
            <h3>Assign Class to Child</h3>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 16 }}>
              Select a child to assign &ldquo;{assignCourseModal.name}&rdquo; to.
            </p>
            <div className="mykids-assign-child-list">
              {children.map((child, index) => (
                <button
                  key={child.student_id}
                  className="mykids-assign-child-btn"
                  disabled={assignLoading}
                  onClick={async () => {
                    setAssignLoading(true);
                    try {
                      await parentApi.assignCoursesToChild(child.student_id, [assignCourseModal.id]);
                      // Remove from unassigned lists
                      setUnassignedCourses(prev => prev.filter(c => c.id !== assignCourseModal.id));
                      setUnassignedMaterials(prev => prev.filter(m => m.course_id !== assignCourseModal.id));
                      // Update child's course count locally
                      setChildren(prev => prev.map(c =>
                        c.student_id === child.student_id
                          ? { ...c, course_count: c.course_count + 1 }
                          : c
                      ));
                      setAssignCourseModal(null);
                    } catch { /* ignore */ }
                    finally { setAssignLoading(false); }
                  }}
                >
                  <span className="mykids-child-avatar" style={{ backgroundColor: CHILD_COLORS[index % CHILD_COLORS.length], width: 32, height: 32, fontSize: 13 }}>
                    {getInitials(child.full_name)}
                  </span>
                  <span>{child.full_name}</span>
                  {child.grade_level != null && <span className="grade-badge">Grade {child.grade_level}</span>}
                </button>
              ))}
            </div>
            <div className="mykids-modal-actions">
              <button onClick={() => setAssignCourseModal(null)}>Cancel</button>
            </div>
          </div>
        </div>
      )}
      {/* Add Course Modal */}
      {showAddCourseModal && (
        <div className="modal-overlay" onClick={closeAddCourseModal}>
          <div className="modal" role="dialog" aria-modal="true" aria-label="Add Class" ref={addCourseModalRef} onClick={(e) => e.stopPropagation()}>
            <h2>Add Class</h2>
            {selectedChild && (
              <p className="modal-desc">
                This class will be automatically assigned to <strong>{children.find(c => c.student_id === selectedChild)?.full_name}</strong>.
              </p>
            )}
            <div className="modal-form">
              <label>
                Class Name *
                <input
                  type="text"
                  value={addCourseName}
                  onChange={(e) => setAddCourseName(e.target.value)}
                  placeholder="e.g. Math 101"
                  disabled={addCourseLoading}
                  onKeyDown={(e) => e.key === 'Enter' && handleAddCourse()}
                  autoFocus
                />
              </label>
              <label>
                Subject (optional)
                <input
                  type="text"
                  value={addCourseSubject}
                  onChange={(e) => setAddCourseSubject(e.target.value)}
                  placeholder="e.g. Mathematics"
                  disabled={addCourseLoading}
                />
              </label>
              <label>
                Description (optional)
                <input
                  type="text"
                  value={addCourseDesc}
                  onChange={(e) => setAddCourseDesc(e.target.value)}
                  placeholder="Brief description"
                  disabled={addCourseLoading}
                />
              </label>
              {addCourseError && <p className="link-error">{addCourseError}</p>}
            </div>
            <div className="modal-actions">
              <button className="cancel-btn" onClick={closeAddCourseModal} disabled={addCourseLoading}>Cancel</button>
              <button className="generate-btn" onClick={handleAddCourse} disabled={addCourseLoading || !addCourseName.trim()}>
                {addCourseLoading ? 'Creating...' : selectedChild ? 'Create & Assign' : 'Create Class'}
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Add Child Modal */}
      {showAddChildModal && renderAddChildModal()}
      {/* Edit Child Modal */}
      {editingChild && (
        <div className="modal-overlay" onClick={() => { setEditingChild(null); setEditError(''); }}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 420 }}>
            <h2>Edit Child</h2>
            <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '16px 24px' }}>
              <label style={{ fontSize: 13, fontWeight: 600 }}>Name
                <input type="text" value={editName} onChange={e => setEditName(e.target.value)} style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid var(--color-border)', marginTop: 4, fontSize: 14, fontFamily: 'inherit' }} />
              </label>
              <label style={{ fontSize: 13, fontWeight: 600 }}>Grade
                <input type="number" value={editGrade} onChange={e => setEditGrade(e.target.value)} placeholder="e.g. 10" style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid var(--color-border)', marginTop: 4, fontSize: 14, fontFamily: 'inherit' }} />
              </label>
              <label style={{ fontSize: 13, fontWeight: 600 }}>School
                <input type="text" value={editSchool} onChange={e => setEditSchool(e.target.value)} style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid var(--color-border)', marginTop: 4, fontSize: 14, fontFamily: 'inherit' }} />
              </label>
              {editError && <p style={{ color: 'var(--color-danger)', fontSize: 13, margin: 0 }}>{editError}</p>}
            </div>
            <div className="modal-actions">
              <button className="cancel-btn" onClick={() => { setEditingChild(null); setEditError(''); }}>Cancel</button>
              <button className="generate-btn" disabled={editLoading || !editName.trim()} onClick={async () => {
                setEditLoading(true);
                setEditError('');
                try {
                  const payload: Record<string, unknown> = {};
                  if (editName.trim() !== editingChild.full_name) payload.full_name = editName.trim();
                  const newGrade = editGrade ? parseInt(editGrade, 10) : null;
                  if (newGrade !== editingChild.grade_level) payload.grade_level = newGrade ?? undefined;
                  if (editSchool.trim() !== (editingChild.school_name || '')) payload.school_name = editSchool.trim() || undefined;
                  if (Object.keys(payload).length > 0) {
                    await parentApi.updateChild(editingChild.student_id, payload as any);
                  }
                  setEditingChild(null);
                  // Refresh children
                  const kids = await parentApi.getChildren();
                  setChildren(kids);
                  toast('Child updated', 'success');
                } catch (err: any) {
                  setEditError(err.response?.data?.detail || 'Failed to update');
                } finally {
                  setEditLoading(false);
                }
              }}>{editLoading ? 'Saving...' : 'Save'}</button>
            </div>
          </div>
        </div>
      )}
      {/* ── Upload Class Material Modal ── */}
      <UploadMaterialWizard
        open={studyTools.showStudyModal}
        onClose={() => { studyTools.resetStudyModal(); setWizardChildId(null); }}
        onGenerate={studyTools.handleGenerateFromModal}
        isGenerating={studyTools.isGenerating}
        courses={wizardChildId ? (wizardCourses ?? (selectedChild === wizardChildId && overview ? overview.courses.map(c => ({ id: c.id, name: c.name })) : undefined)) : (selectedChild && overview ? overview.courses.map(c => ({ id: c.id, name: c.name })) : undefined)}
        selectedCourseId={(() => { const wc = wizardChildId ? (wizardCourses ?? (selectedChild === wizardChildId && overview ? overview.courses.map(c => ({ id: c.id, name: c.name })) : undefined)) : (selectedChild && overview ? overview.courses.map(c => ({ id: c.id, name: c.name })) : undefined); return wc?.length === 1 ? wc[0].id : ''; })()}
        showParentNote={true}
        childName={(wizardChildId ? children.find(c => c.student_id === wizardChildId)?.full_name : children.find(c => c.student_id === selectedChild)?.full_name)}
        children={children.map(c => ({ id: c.student_id, name: c.full_name }))}
        onChildChange={(studentId: number) => setWizardChildId(studentId)}
      />
      {studyTools.backgroundGeneration && (
        <div className={`sd-generation-banner ${studyTools.backgroundGeneration.status}`}>
          {studyTools.backgroundGeneration.status === 'generating' && (
            <span><GenerationSpinner size="sm" /> Uploading {studyTools.backgroundGeneration.type}...</span>
          )}
          {studyTools.backgroundGeneration.status === 'success' && (
            <>
              <span>{studyTools.backgroundGeneration.type} ready!</span>
              <button className="sd-gen-view-btn" onClick={() => { navigate(studyTools.getBackgroundGenerationRoute()); studyTools.dismissBackgroundGeneration(); }}>View</button>
              <button className="sd-gen-dismiss-btn" onClick={studyTools.dismissBackgroundGeneration}>&times;</button>
            </>
          )}
          {studyTools.backgroundGeneration.status === 'error' && (
            <>
              <span>Failed to generate {studyTools.backgroundGeneration.type}{studyTools.backgroundGeneration.error ? `: ${studyTools.backgroundGeneration.error}` : ''}</span>
              <button className="sd-gen-dismiss-btn" onClick={studyTools.dismissBackgroundGeneration}>&times;</button>
            </>
          )}
        </div>
      )}
      {confirmModal}
      <StudyRequestModal
        open={showStudyRequest}
        onClose={() => setShowStudyRequest(false)}
        children={children.map(c => ({ student_id: c.student_id, user_id: c.user_id, full_name: c.full_name }))}
        preselectedChildUserId={selectedChildUserId}
        onSuccess={() => toast('Study request sent!', 'success')}
      />
      {awardXpChild && (
        <AwardXpModal
          open={!!awardXpChild}
          onClose={() => setAwardXpChild(null)}
          studentName={awardXpChild.name}
          studentUserId={awardXpChild.userId}
          onSuccess={() => toast(`XP awarded to ${awardXpChild.name}!`, 'success')}
        />
      )}
      <EmailDigestSetupWizard
        open={showEmailDigestWizard}
        onClose={() => setShowEmailDigestWizard(false)}
        childName={children.find(c => c.student_id === selectedChild)?.full_name}
        onComplete={() => toast('Email digest set up!', 'success')}
      />
    </DashboardLayout>
  );
}
