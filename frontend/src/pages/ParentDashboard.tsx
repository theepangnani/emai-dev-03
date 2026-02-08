import { useState, useEffect, useRef, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { parentApi, googleApi, invitesApi, studyApi, coursesApi } from '../api/client';
import type { ChildSummary, ChildOverview, DiscoveredChild, SupportedFormats, StudyGuide, DuplicateCheckResponse } from '../api/client';
import { DashboardLayout } from '../components/DashboardLayout';
import { CalendarView } from '../components/calendar/CalendarView';
import { ParentActionBar } from '../components/parent/ParentActionBar';
import { ParentSidebar } from '../components/parent/ParentSidebar';
import type { CalendarAssignment } from '../components/calendar/types';
import { getCourseColor } from '../components/calendar/types';
import './ParentDashboard.css';

const MAX_FILE_SIZE_MB = 100;

type LinkTab = 'create' | 'email' | 'google';
type DiscoveryState = 'idle' | 'discovering' | 'results' | 'no_results';
type SyncState = 'idle' | 'syncing' | 'done' | 'error';

interface ParentCourse {
  id: number;
  name: string;
  description: string | null;
  subject: string | null;
  created_at: string;
}

export function ParentDashboard() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [children, setChildren] = useState<ChildSummary[]>([]);
  const [selectedChild, setSelectedChild] = useState<number | null>(null);
  const [childOverview, setChildOverview] = useState<ChildOverview | null>(null);
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

  // Child sync state
  const [syncState, setSyncState] = useState<SyncState>('idle');
  const [syncMessage, setSyncMessage] = useState('');

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
  const [myStudyGuides, setMyStudyGuides] = useState<StudyGuide[]>([]);
  const [childStudyGuides, setChildStudyGuides] = useState<StudyGuide[]>([]);
  const [duplicateCheck, setDuplicateCheck] = useState<DuplicateCheckResponse | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Create child (name-only) state
  const [createChildName, setCreateChildName] = useState('');
  const [createChildEmail, setCreateChildEmail] = useState('');
  const [createChildRelationship, setCreateChildRelationship] = useState('guardian');
  const [createChildLoading, setCreateChildLoading] = useState(false);
  const [createChildError, setCreateChildError] = useState('');
  const [createChildInviteLink, setCreateChildInviteLink] = useState('');

  // Course management state
  const [showCreateCourseModal, setShowCreateCourseModal] = useState(false);
  const [courseName, setCourseName] = useState('');
  const [courseSubject, setCourseSubject] = useState('');
  const [courseDescription, setCourseDescription] = useState('');
  const [createCourseLoading, setCreateCourseLoading] = useState(false);
  const [createCourseError, setCreateCourseError] = useState('');
  const [parentCourses, setParentCourses] = useState<ParentCourse[]>([]);
  const [showAssignCourseModal, setShowAssignCourseModal] = useState(false);
  const [selectedCoursesForAssign, setSelectedCoursesForAssign] = useState<Set<number>>(new Set());
  const [assignLoading, setAssignLoading] = useState(false);

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
    loadMyStudyGuides();
    loadParentCourses();
  }, []);

  const loadMyStudyGuides = async () => {
    try {
      const data = await studyApi.listGuides();
      setMyStudyGuides(data);
    } catch {
      // Failed to load study guides
    }
  };

  useEffect(() => {
    if (selectedChild) {
      loadChildOverview(selectedChild);
    }
  }, [selectedChild]);

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
      if (data.length > 0) {
        setSelectedChild(data[0].student_id);
      }
    } catch {
      // Failed to load children
    } finally {
      setLoading(false);
    }
  };

  const loadParentCourses = async () => {
    try {
      const data = await coursesApi.createdByMe();
      setParentCourses(data);
    } catch {
      // Failed to load courses
    }
  };

  const loadChildOverview = async (studentId: number) => {
    setOverviewLoading(true);
    try {
      const data = await parentApi.getChildOverview(studentId);
      setChildOverview(data);
      const childGuides = await studyApi.listGuides({ include_children: true, student_user_id: data.user_id });
      setChildStudyGuides(childGuides.filter(g => g.user_id !== data.user_id ? false : true));
    } catch {
      setChildOverview(null);
      setChildStudyGuides([]);
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
  // Course Management Handlers
  // ============================================

  const handleCreateCourse = async () => {
    if (!courseName.trim()) return;
    setCreateCourseError('');
    setCreateCourseLoading(true);
    try {
      await coursesApi.create({
        name: courseName.trim(),
        subject: courseSubject.trim() || undefined,
        description: courseDescription.trim() || undefined,
      });
      closeCreateCourseModal();
      await loadParentCourses();
      if (selectedChild) loadChildOverview(selectedChild);
    } catch (err: any) {
      setCreateCourseError(err.response?.data?.detail || 'Failed to create course');
    } finally {
      setCreateCourseLoading(false);
    }
  };

  const closeCreateCourseModal = () => {
    setShowCreateCourseModal(false);
    setCourseName('');
    setCourseSubject('');
    setCourseDescription('');
    setCreateCourseError('');
  };

  const handleAssignCourses = async () => {
    if (!selectedChild || selectedCoursesForAssign.size === 0) return;
    setAssignLoading(true);
    try {
      await parentApi.assignCoursesToChild(selectedChild, Array.from(selectedCoursesForAssign));
      setShowAssignCourseModal(false);
      setSelectedCoursesForAssign(new Set());
      loadChildOverview(selectedChild);
    } catch {
      // silently fail
    } finally {
      setAssignLoading(false);
    }
  };

  const handleUnassignCourse = async (courseId: number) => {
    if (!selectedChild) return;
    try {
      await parentApi.unassignCourseFromChild(selectedChild, courseId);
      loadChildOverview(selectedChild);
    } catch {
      // silently fail
    }
  };

  const handleSyncChildCourses = async () => {
    if (!selectedChild) return;
    setSyncState('syncing');
    setSyncMessage('');
    try {
      const result = await parentApi.syncChildCourses(selectedChild);
      setSyncMessage(result.message);
      setSyncState('done');
      loadChildOverview(selectedChild);
      setTimeout(() => { setSyncState('idle'); setSyncMessage(''); }, 4000);
    } catch (err: any) {
      setSyncMessage(err.response?.data?.detail || 'Failed to sync courses');
      setSyncState('error');
      setTimeout(() => { setSyncState('idle'); setSyncMessage(''); }, 4000);
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
      loadMyStudyGuides();
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
  // Calendar Data Derivation
  // ============================================

  const courseIds = useMemo(() => {
    return (childOverview?.courses || []).map(c => c.id);
  }, [childOverview]);

  const calendarAssignments: CalendarAssignment[] = useMemo(() => {
    if (!childOverview) return [];
    return childOverview.assignments
      .filter(a => a.due_date)
      .map(a => ({
        id: a.id,
        title: a.title,
        description: a.description,
        courseId: a.course_id,
        courseName: childOverview.courses.find(c => c.id === a.course_id)?.name || 'Unknown',
        courseColor: getCourseColor(a.course_id, courseIds),
        dueDate: new Date(a.due_date!),
        childName: children.length > 1 ? childOverview.full_name : '',
        maxPoints: a.max_points,
      }));
  }, [childOverview, courseIds, children.length]);

  const undatedAssignments: CalendarAssignment[] = useMemo(() => {
    if (!childOverview) return [];
    return childOverview.assignments
      .filter(a => !a.due_date)
      .map(a => ({
        id: a.id,
        title: a.title,
        description: a.description,
        courseId: a.course_id,
        courseName: childOverview.courses.find(c => c.id === a.course_id)?.name || 'Unknown',
        courseColor: getCourseColor(a.course_id, courseIds),
        dueDate: new Date(),
        childName: '',
        maxPoints: a.max_points,
      }));
  }, [childOverview, courseIds]);

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
    <DashboardLayout welcomeSubtitle="Monitor your child's progress">
      {children.length === 0 ? (
        <div className="no-children-state">
          <h3>Get Started</h3>
          <p>Add your child to start managing their education. No school account required!</p>
          <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', marginTop: '20px' }}>
            <button className="link-child-btn" onClick={() => setShowLinkModal(true)}>
              + Add Child
            </button>
            <button className="link-child-btn" onClick={() => setShowCreateCourseModal(true)}>
              + Create Course
            </button>
          </div>
        </div>
      ) : (
        <div className="parent-layout">
          {/* Action Bar */}
          <div className="parent-action-bar-area">
            <ParentActionBar
              onAddChild={() => setShowLinkModal(true)}
              onAddCourse={() => setShowCreateCourseModal(true)}
              onCreateStudyGuide={() => setShowStudyModal(true)}
            />
          </div>

          {/* Child Filter */}
          {children.length > 1 && (
            <div className="parent-child-filter">
              <div className="child-selector">
                {children.map((child) => (
                  <button
                    key={child.student_id}
                    className={`child-tab ${selectedChild === child.student_id ? 'active' : ''}`}
                    onClick={() => setSelectedChild(child.student_id)}
                  >
                    {child.full_name}
                    {child.relationship_type && (
                      <span className="relationship-badge">{child.relationship_type}</span>
                    )}
                    {child.grade_level && <span className="grade-badge">Grade {child.grade_level}</span>}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Main Content: Calendar + Sidebar */}
          {overviewLoading ? (
            <div className="parent-calendar-area">
              <div className="loading-state">Loading child data...</div>
            </div>
          ) : (
            <>
              <div className="parent-calendar-area">
                <CalendarView
                  assignments={calendarAssignments}
                  onCreateStudyGuide={handleCalendarCreateStudyGuide}
                />
              </div>

              <div className="parent-sidebar-area">
                <ParentSidebar
                  childCourses={childOverview?.courses || []}
                  parentCourses={parentCourses}
                  myStudyGuides={myStudyGuides}
                  childStudyGuides={childStudyGuides}
                  childName={childOverview?.full_name || ''}
                  undatedAssignments={undatedAssignments}
                  onAssignCourse={() => { setSelectedCoursesForAssign(new Set()); setShowAssignCourseModal(true); }}
                  onCreateCourse={() => setShowCreateCourseModal(true)}
                  onSyncCourses={handleSyncChildCourses}
                  onDeleteGuide={(id) => setMyStudyGuides(prev => prev.filter(g => g.id !== id))}
                  onUpdateGuides={setMyStudyGuides}
                  onAssignmentClick={handleCalendarCreateStudyGuide}
                  syncState={syncState}
                  syncMessage={syncMessage}
                  googleConnected={childOverview?.google_connected || false}
                  hasParentCourses={parentCourses.length > 0}
                  hasChild={!!childOverview}
                />
              </div>
            </>
          )}
        </div>
      )}

      {/* ============================================
          Modals (unchanged)
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

      {/* Create Course Modal */}
      {showCreateCourseModal && (
        <div className="modal-overlay" onClick={closeCreateCourseModal}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Create Course</h2>
            <p className="modal-desc">Create a course for your child. No teacher or school required.</p>
            <div className="modal-form">
              <label>
                Course Name *
                <input type="text" value={courseName} onChange={(e) => setCourseName(e.target.value)} placeholder="e.g. Math Grade 5" disabled={createCourseLoading} onKeyDown={(e) => e.key === 'Enter' && handleCreateCourse()} />
              </label>
              <label>
                Subject (optional)
                <input type="text" value={courseSubject} onChange={(e) => setCourseSubject(e.target.value)} placeholder="e.g. Mathematics" disabled={createCourseLoading} />
              </label>
              <label>
                Description (optional)
                <textarea value={courseDescription} onChange={(e) => setCourseDescription(e.target.value)} placeholder="Course details..." rows={3} disabled={createCourseLoading} />
              </label>
              {createCourseError && <p className="link-error">{createCourseError}</p>}
            </div>
            <div className="modal-actions">
              <button className="cancel-btn" onClick={closeCreateCourseModal} disabled={createCourseLoading}>Cancel</button>
              <button className="generate-btn" onClick={handleCreateCourse} disabled={createCourseLoading || !courseName.trim()}>
                {createCourseLoading ? 'Creating...' : 'Create Course'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Assign Course to Child Modal */}
      {showAssignCourseModal && selectedChild && (
        <div className="modal-overlay" onClick={() => setShowAssignCourseModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Assign Course to {childOverview?.full_name}</h2>
            <p className="modal-desc">Select courses to assign to your child.</p>
            <div className="modal-form">
              {parentCourses.length === 0 ? (
                <div className="empty-state">
                  <p>No courses created yet</p>
                  <button className="link-child-btn-small" onClick={() => { setShowAssignCourseModal(false); setShowCreateCourseModal(true); }}>+ Create Course</button>
                </div>
              ) : (
                <div className="discovered-list">
                  {parentCourses.map((course) => {
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
              <button className="cancel-btn" onClick={() => setShowAssignCourseModal(false)} disabled={assignLoading}>Cancel</button>
              <button className="generate-btn" onClick={handleAssignCourses} disabled={assignLoading || selectedCoursesForAssign.size === 0}>
                {assignLoading ? 'Assigning...' : `Assign ${selectedCoursesForAssign.size} Course${selectedCoursesForAssign.size !== 1 ? 's' : ''}`}
              </button>
            </div>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
