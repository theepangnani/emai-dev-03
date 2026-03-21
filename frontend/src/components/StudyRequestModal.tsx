import { useState } from 'react';
import { studyRequestsApi } from '../api/studyRequests';
import { useFocusTrap } from '../hooks/useFocusTrap';

interface ChildOption {
  student_id: number;
  user_id: number;
  full_name: string;
}

interface StudyRequestModalProps {
  open: boolean;
  onClose: () => void;
  children: ChildOption[];
  preselectedChildUserId?: number | null;
  onSuccess?: () => void;
}

export function StudyRequestModal({
  open,
  onClose,
  children: childOptions,
  preselectedChildUserId,
  onSuccess,
}: StudyRequestModalProps) {
  const [selectedChildUserId, setSelectedChildUserId] = useState<number | null>(
    preselectedChildUserId ?? (childOptions.length === 1 ? childOptions[0].user_id : null)
  );
  const [subject, setSubject] = useState('');
  const [topic, setTopic] = useState('');
  const [urgency, setUrgency] = useState<'low' | 'normal' | 'high'>('normal');
  const [message, setMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const modalRef = useFocusTrap<HTMLDivElement>(open, onClose);

  if (!open) return null;

  const handleSubmit = async () => {
    if (!selectedChildUserId || !subject.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await studyRequestsApi.create({
        student_id: selectedChildUserId,
        subject: subject.trim(),
        topic: topic.trim() || undefined,
        urgency,
        message: message.trim() || undefined,
      });
      setSuccess(true);
      onSuccess?.();
      setTimeout(() => {
        setSuccess(false);
        setSubject('');
        setTopic('');
        setUrgency('normal');
        setMessage('');
        onClose();
      }, 1500);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to send study request');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label="Request Study Session"
        ref={modalRef}
        onClick={(e) => e.stopPropagation()}
      >
        <h2>Request Study Session</h2>
        <p className="modal-desc">
          Suggest a topic for your child to review. They will be notified and can respond.
        </p>

        {success ? (
          <div className="link-success" style={{ padding: '20px 0', textAlign: 'center' }}>
            Study request sent! Your child will be notified.
          </div>
        ) : (
          <div className="modal-form">
            {childOptions.length > 1 && (
              <label>
                Child *
                <select
                  value={selectedChildUserId ?? ''}
                  onChange={(e) => setSelectedChildUserId(e.target.value ? Number(e.target.value) : null)}
                  disabled={submitting}
                >
                  <option value="">Select a child...</option>
                  {childOptions.map((c) => (
                    <option key={c.user_id} value={c.user_id}>
                      {c.full_name}
                    </option>
                  ))}
                </select>
              </label>
            )}

            <label>
              Subject *
              <input
                type="text"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="e.g., Math, Science, English"
                disabled={submitting}
                maxLength={100}
              />
            </label>

            <label>
              Topic (optional)
              <input
                type="text"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="e.g., Fractions, Photosynthesis"
                disabled={submitting}
                maxLength={200}
              />
            </label>

            <label>
              Urgency
              <select
                value={urgency}
                onChange={(e) => setUrgency(e.target.value as 'low' | 'normal' | 'high')}
                disabled={submitting}
              >
                <option value="low">Low — when they have time</option>
                <option value="normal">Normal — this week</option>
                <option value="high">High — before the next class</option>
              </select>
            </label>

            <label>
              Message (optional)
              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Add a note for your child..."
                disabled={submitting}
                maxLength={500}
                rows={3}
              />
            </label>

            {error && <p className="link-error">{error}</p>}
          </div>
        )}

        {!success && (
          <div className="modal-actions">
            <button className="cancel-btn" onClick={onClose} disabled={submitting}>
              Cancel
            </button>
            <button
              className="generate-btn"
              onClick={handleSubmit}
              disabled={submitting || !selectedChildUserId || !subject.trim()}
            >
              {submitting ? 'Sending...' : 'Send Request'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
