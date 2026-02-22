import { useState } from 'react';
import { parentApi } from '../../../api/client';
import { isValidEmail } from '../../../utils/validation';
import type { ChildSummary } from '../../../api/client';

interface UseChildEditorParams {
  loadDashboard: () => Promise<void>;
}

export function useChildEditor({ loadDashboard }: UseChildEditorParams) {
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

  return {
    showEditChildModal, setShowEditChildModal, editChild, setEditChild,
    editChildName, setEditChildName, editChildEmail, setEditChildEmail,
    editChildGrade, setEditChildGrade, editChildSchool, setEditChildSchool,
    editChildDob, setEditChildDob, editChildPhone, setEditChildPhone,
    editChildAddress, setEditChildAddress, editChildCity, setEditChildCity,
    editChildProvince, setEditChildProvince, editChildPostal, setEditChildPostal,
    editChildNotes, setEditChildNotes, editChildLoading, editChildError,
    editChildOptionalOpen, setEditChildOptionalOpen,
    handleEditChild, closeEditChildModal,
  };
}
