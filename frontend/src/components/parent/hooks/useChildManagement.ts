import { useState, useEffect } from 'react';
import { parentApi, googleApi } from '../../../api/client';
import { isValidEmail } from '../../../utils/validation';
import type { ChildSummary, DiscoveredChild } from '../../../api/client';

export type LinkTab = 'create' | 'email' | 'google';
export type DiscoveryState = 'idle' | 'discovering' | 'results' | 'no_results';

interface UseChildManagementParams {
  children: ChildSummary[];
  googleConnected: boolean;
  setGoogleConnected: (v: boolean) => void;
  loadDashboard: () => Promise<void>;
}

export function useChildManagement({
  children,
  googleConnected,
  setGoogleConnected,
  loadDashboard,
}: UseChildManagementParams) {
  // Link child modal state
  const [showLinkModal, setShowLinkModal] = useState(false);
  const [linkTab, setLinkTab] = useState<LinkTab>('create');
  const [linkEmail, setLinkEmail] = useState('');
  const [linkName, setLinkName] = useState('');
  const [linkRelationship, setLinkRelationship] = useState('guardian');
  const [linkError, setLinkError] = useState('');
  const [linkLoading, setLinkLoading] = useState(false);
  const [linkInviteLink, setLinkInviteLink] = useState('');

  // Google discovery state
  const [discoveryState, setDiscoveryState] = useState<DiscoveryState>('idle');
  const [discoveredChildren, setDiscoveredChildren] = useState<DiscoveredChild[]>([]);
  const [selectedDiscovered, setSelectedDiscovered] = useState<Set<number>>(new Set());
  const [coursesSearched, setCoursesSearched] = useState(0);
  const [bulkLinking, setBulkLinking] = useState(false);
  const [bulkLinkSuccess, setBulkLinkSuccess] = useState(0);

  // Create child (name-only) state
  const [createChildName, setCreateChildName] = useState('');
  const [createChildEmail, setCreateChildEmail] = useState('');
  const [createChildRelationship, setCreateChildRelationship] = useState('guardian');
  const [createChildLoading, setCreateChildLoading] = useState(false);
  const [createChildError, setCreateChildError] = useState('');
  const [createChildInviteLink, setCreateChildInviteLink] = useState('');

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

  const handleChildTabClick = (studentId: number, selectedChild: number | null, setSelectedChild: (v: number | null) => void, setChildOverview: (v: null) => void) => {
    if (selectedChild === studentId) {
      setSelectedChild(null);
      setChildOverview(null);
      sessionStorage.removeItem('selectedChildId');
      try { localStorage.removeItem('last_selected_child'); } catch { /* ignore */ }
    } else {
      setSelectedChild(studentId);
      const child = children.find(c => c.student_id === studentId);
      if (child) {
        sessionStorage.setItem('selectedChildId', String(child.user_id));
        try { localStorage.setItem('last_selected_child', String(child.user_id)); } catch { /* ignore */ }
      }
    }
  };

  return {
    // Link Child Modal
    showLinkModal, setShowLinkModal, linkTab, setLinkTab,
    linkEmail, setLinkEmail, linkName, setLinkName,
    linkRelationship, setLinkRelationship, linkError, setLinkError,
    linkLoading, linkInviteLink,
    createChildName, setCreateChildName, createChildEmail, setCreateChildEmail,
    createChildRelationship, setCreateChildRelationship, createChildLoading,
    createChildError, setCreateChildError, createChildInviteLink,
    handleCreateChild, handleLinkChild, closeLinkModal,
    discoveryState, discoveredChildren, selectedDiscovered,
    coursesSearched, bulkLinking, bulkLinkSuccess,
    handleConnectGoogle, triggerDiscovery, handleBulkLink, toggleDiscovered,
    setDiscoveryState, setDiscoveredChildren, setBulkLinkSuccess,
    handleChildTabClick,
  };
}
