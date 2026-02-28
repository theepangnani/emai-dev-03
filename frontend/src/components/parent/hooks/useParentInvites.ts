import { useState } from 'react';
import { invitesApi } from '../../../api/client';
import type { InviteResponse } from '../../../api/client';
import { isValidEmail } from '../../../utils/validation';

interface UseParentInvitesParams {
  pendingInvites: InviteResponse[];
  setPendingInvites: React.Dispatch<React.SetStateAction<InviteResponse[]>>;
}

export function useParentInvites({
  pendingInvites,
  setPendingInvites,
}: UseParentInvitesParams) {
  // Invite student modal state
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRelationship, setInviteRelationship] = useState('guardian');
  const [inviteError, setInviteError] = useState('');
  const [inviteLoading, setInviteLoading] = useState(false);
  const [inviteSuccess, setInviteSuccess] = useState('');

  // Resend state
  const [resendingId, setResendingId] = useState<number | null>(null);

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

  return {
    // Invite Student Modal
    showInviteModal, setShowInviteModal,
    inviteEmail, setInviteEmail, inviteRelationship, setInviteRelationship,
    inviteError, setInviteError, inviteLoading, inviteSuccess, setInviteSuccess,
    handleInviteStudent, closeInviteModal,
    // Resend
    pendingInvites, resendingId, handleResendInvite,
  };
}
