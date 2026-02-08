import { useState, useEffect, useRef, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { parentApi, googleApi, invitesApi, studyApi, tasksApi } from '../api/client';
import type { ChildSummary, ChildOverview, DiscoveredChild, SupportedFormats, DuplicateCheckResponse, TaskItem } from '../api/client';
import { DashboardLayout } from '../components/DashboardLayout';
import { CalendarView } from '../components/calendar/CalendarView';
import type { CalendarAssignment } from '../components/calendar/types';
import { getCourseColor, dateKey } from '../components/calendar/types';
import './ParentDashboard.css';

const MAX_FILE_SIZE_MB = 100;

type LinkTab = 'create' | 'email' | 'google';
type DiscoveryState = 'idle' | 'discovering' | 'results' | 'no_results';

export function ParentDashboard() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [children, setChildren] = useState<ChildSummary[]>([]);
  const [selectedChild, setSelectedChild] = useState<number | null>(null);
  const [childOverview, setChildOverview] = useState<ChildOverview | null>(null);
  const [allOverviews, setAllOverviews] = useState<ChildOverview[]>([]);
  const [loading, setLoading] = useState(true);
  const [overviewLoading, setOverviewLoading] = useState(false);

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
  const [isGenerating, setIsGenerating] = useState(false);
  const [studyError, setStudyError] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [supportedFormats, setSupportedFormats] = useState<SupportedFormats | null>(null);
  const [duplicateCheck, setDuplicateCheck] = useState<DuplicateCheckResponse | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Edit child modal state
  const [showEditChildModal, setShowEditChildModal] = useState(false);
  const [editChild, setEditChild] = useState<ChildSummary | null>(null);
  const [editChildName, setEditChildName] = useState('');
  const [editChildGrade, setEditChildGrade] = useState('');
  const [editChildSchool, setEditChildSchool] = useState('');
  const [editChildLoading, setEditChildLoading] = useState(false);
  const [editChildError, setEditChildError] = useState('');

  // Day detail modal state
  const [dayModalDate, setDayModalDate] = useState<Date | null>(null);
  const [dayTasks, setDayTasks] = useState<TaskItem[]>([]);
  const [allTasks, setAllTasks] = useState<TaskItem[]>([]);
  const [newTaskTitle, setNewTaskTitle] = useState('');
  const [newTaskCreating, setNewTaskCreating] = useState(false);

  // Create child (name-only) state
  const [createChildName, setCreateChildName] = useState('');
  const [createChildEmail, setCreateChildEmail] = useState('');
  const [createChildRelationship, setCreateChildRelationship] = useState('guardian');
  const [createChildLoading, setCreateChildLoading] = useState(false);
  const [createChildError, setCreateChildError] = useState('');
  const [createChildInviteLink, setCreateChildInviteLink] = useState('');

  // ============================================
  // Data Loading
  // ============================================

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

    loadChildren();
    checkGoogleStatus();
  }, []);

  useEffect(() => {
    if (selectedChild) {
      loadChildOverview(selectedChild);
    } else if (children.length > 0) {
      loadAllOverviews();
    }
  }, [selectedChild, children]);

  const checkGoogleStatus = async () => {
    try {
      const status = await googleApi.getStatus();
      setGoogleConnected(status.connected);
    } catch {
      // ignore
    }
  };

  const loadChildren = async () => {
    try {
      const data = await parentApi.getChildren();
      setChildren(data);
      if (data.length > 0 && data.length === 1) {
        setSelectedChild(data[0].student_id);
      } else if (data.length > 1) {
        // Show all children by default
        setSelectedChild(null);
      }
    } catch {
      // Failed to load children
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

  const loadAllOverviews = async () => {
    setOverviewLoading(true);
    try {
      const overviews = await Promise.all(
        children.map(c => parentApi.getChildOverview(c.student_id))
      );
      setAllOverviews(overviews);
    } catch {
      setAllOverviews([]);
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
      await loadChildren();
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
      await loadChildren();
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
      await loadChildren();
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
    setEditChildGrade(child.grade_level != null ? String(child.grade_level) : '');
    setEditChildSchool(child.school_name || '');
    setEditChildError('');
    setShowEditChildModal(true);
  };

  const closeEditChildModal = () => {
    setShowEditChildModal(false);
    setEditChild(null);
    setEditChildName('');
    setEditChildGrade('');
    setEditChildSchool('');
    setEditChildError('');
  };

  const handleEditChild = async () => {
    if (!editChild || !editChildName.trim()) return;
    setEditChildLoading(true);
    setEditChildError('');
    try {
      await parentApi.updateChild(editChild.student_id, {
        full_name: editChildName.trim(),
        grade_level: editChildGrade ? parseInt(editChildGrade, 10) : undefined,
        school_name: editChildSchool.trim() || undefined,
      });
      closeEditChildModal();
      await loadChildren();
      if (selectedChild === editChild.student_id) {
        await loadChildOverview(editChild.student_id);
      }
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

    if (studyMode === 'text' && !duplicateCheck) {
      try {
        const dupResult = await studyApi.checkDuplicate({ title: studyTitle || undefined, guide_type: studyType });
        if (dupResult.exists) { setDuplicateCheck(dupResult); return; }
      } catch { /* Continue */ }
    }
    setDuplicateCheck(null);
    setIsGenerating(true);
    setStudyError('');

    try {
      let result;
      const regenerateId = duplicateCheck?.existing_guide?.id;
      if (studyMode === 'file' && selectedFile) {
        result = await studyApi.generateFromFile({
          file: selectedFile,
          title: studyTitle || undefined,
          guide_type: studyType,
          num_questions: studyType === 'quiz' ? 10 : undefined,
          num_cards: studyType === 'flashcards' ? 15 : undefined,
        });
      } else {
        if (studyType === 'study_guide') {
          result = await studyApi.generateGuide({ title: studyTitle, content: studyContent, regenerate_from_id: regenerateId });
        } else if (studyType === 'quiz') {
          result = await studyApi.generateQuiz({ topic: studyTitle, content: studyContent, num_questions: 10, regenerate_from_id: regenerateId });
        } else {
          result = await studyApi.generateFlashcards({ topic: studyTitle, content: studyContent, num_cards: 15, regenerate_from_id: regenerateId });
        }
      }
      resetStudyModal();
      if (studyType === 'study_guide') navigate(`/study/guide/${result.id}`);
      else if (studyType === 'quiz') navigate(`/study/quiz/${result.id}`);
      else navigate(`/study/flashcards/${result.id}`);
    } catch (err: any) {
      setStudyError(err.response?.data?.detail || 'Failed to generate study material');
    } finally {
      setIsGenerating(false);
    }
  };

  // ============================================
  // Tasks & Day Detail Modal
  // ============================================

  useEffect(() => {
    loadTasks();
  }, []);

  const loadTasks = async () => {
    try {
      const data = await tasksApi.list();
      setAllTasks(data);
    } catch {
      // silently fail
    }
  };

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
      const task = await tasksApi.create({
        title: newTaskTitle.trim(),
        due_date: dayModalDate.toISOString(),
        student_id: selectedChild || undefined,
      });
      setDayTasks(prev => [...prev, task]);
      setAllTasks(prev => [...prev, task]);
      setNewTaskTitle('');
    } catch {
      // silently fail
    } finally {
      setNewTaskCreating(false);
    }
  };

  const handleToggleTask = async (task: TaskItem) => {
    try {
      const updated = await tasksApi.update(task.id, { is_completed: !task.is_completed });
      setDayTasks(prev => prev.map(t => t.id === task.id ? updated : t));
      setAllTasks(prev => prev.map(t => t.id === task.id ? updated : t));
    } catch {
      // silently fail
    }
  };

  const handleDeleteTask = async (taskId: number) => {
    try {
      await tasksApi.delete(taskId);
      setDayTasks(prev => prev.filter(t => t.id !== taskId));
      setAllTasks(prev => prev.filter(t => t.id !== taskId));
    } catch {
      // silently fail
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
    return activeOverviews.flatMap(overview =>
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
        }))
    );
  }, [activeOverviews, courseIds, children.length]);

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

  const handleCalendarCreateStudyGuide = (assignment: CalendarAssignment) => {
    setStudyTitle(assignment.title);
    setStudyContent(assignment.description || '');
    setShowStudyModal(true);
  };

  // ============================================
  // Render
  // ============================================

  if (loading) {
    return (
      <DashboardLayout welcomeSubtitle="Monitor your child's progress">
        <div className="loading-state">Loading...</div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout
      welcomeSubtitle="Monitor your child's progress"
      sidebarActions={[
        { label: '+ Add Child', onClick: () => setShowLinkModal(true) },
        { label: '+ Create Study Guide', onClick: () => setShowStudyModal(true) },
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

          {/* Calendar */}
          {overviewLoading ? (
            <div className="loading-state">Loading child data...</div>
          ) : (
            <>
              <CalendarView
                assignments={calendarAssignments}
                onCreateStudyGuide={handleCalendarCreateStudyGuide}
                onDayClick={openDayModal}
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
                        onClick={() => handleCalendarCreateStudyGuide(a)}
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
              const dayAssigns = calendarAssignments.filter(a => dateKey(a.dueDate) === dk);
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
                        <button className="day-modal-study-btn" onClick={() => { closeDayModal(); handleCalendarCreateStudyGuide(a); }}>Study</button>
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
                {dayTasks.map(task => (
                  <div key={task.id} className={`day-modal-item task-item${task.is_completed ? ' completed' : ''}`}>
                    <input
                      type="checkbox"
                      checked={task.is_completed}
                      onChange={() => handleToggleTask(task)}
                      className="task-checkbox"
                    />
                    <span className={`day-modal-item-title${task.is_completed ? ' completed' : ''}`}>{task.title}</span>
                    <button className="task-delete-btn" onClick={() => handleDeleteTask(task.id)} title="Delete task">&times;</button>
                  </div>
                ))}
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
    </DashboardLayout>
  );
}
