/**
 * Meeting Scheduler Page
 *
 * Teacher view:
 *   - Availability grid: weekdays x time slots (toggle on/off), slot duration selector
 *   - Upcoming/past bookings with confirm/cancel/complete actions + video link input
 *   - Week schedule view
 *
 * Parent view:
 *   - Teacher selector (manually type teacher ID for now; TODO: link to parent-teacher connections)
 *   - Calendar showing available slots
 *   - "Book a Meeting" modal form
 *   - My upcoming/past bookings with cancel option
 *   - Video link display on confirmed meetings
 */
import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { DashboardLayout } from '../components/DashboardLayout';
import {
  getMyAvailability,
  setMyAvailability,
  getAvailableSlots,
  bookMeeting,
  listMyMeetings,
  confirmMeeting,
  cancelMeeting,
  completeMeeting,
  getTeacherSchedule,
  type TeacherAvailability,
  type AvailableSlot,
  type MeetingBooking,
  type AvailabilityCreate,
} from '../api/meetingScheduler';
import './MeetingSchedulerPage.css';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const MEETING_TYPES = [
  { value: 'video_call', label: 'Video Call' },
  { value: 'in_person', label: 'In Person' },
  { value: 'phone', label: 'Phone' },
];
const SLOT_DURATIONS = [15, 20, 30, 45, 60];

// ---------------------------------------------------------------------------
// Helper functions
// ---------------------------------------------------------------------------

function formatDateTime(isoStr: string): string {
  const d = new Date(isoStr);
  return d.toLocaleString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatTime(isoStr: string): string {
  const d = new Date(isoStr);
  return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
}

function statusBadgeClass(status: string): string {
  switch (status) {
    case 'confirmed': return 'badge badge--green';
    case 'pending': return 'badge badge--yellow';
    case 'cancelled': return 'badge badge--red';
    case 'completed': return 'badge badge--grey';
    default: return 'badge';
  }
}

function getMondayOfWeek(d: Date): Date {
  const day = d.getDay(); // 0=Sun
  const diff = (day === 0 ? -6 : 1 - day);
  const mon = new Date(d);
  mon.setDate(d.getDate() + diff);
  mon.setHours(0, 0, 0, 0);
  return mon;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

// ---- Booking Card ----

interface BookingCardProps {
  booking: MeetingBooking;
  role: string;
  onConfirm?: (id: number, videoLink: string) => void;
  onCancel?: (id: number, reason: string) => void;
  onComplete?: (id: number, notes: string) => void;
}

function BookingCard({ booking, role, onConfirm, onCancel, onComplete }: BookingCardProps) {
  const [videoLink, setVideoLink] = useState(booking.video_link || '');
  const [cancelReason, setCancelReason] = useState('');
  const [completeNotes, setCompleteNotes] = useState('');
  const [expanded, setExpanded] = useState(false);

  const isTeacher = role === 'teacher';
  const isPast = new Date(booking.proposed_at) < new Date();

  return (
    <div className={`booking-card booking-card--${booking.status}`}>
      <div className="booking-card__header" onClick={() => setExpanded(!expanded)}>
        <div className="booking-card__info">
          <span className={statusBadgeClass(booking.status)}>{booking.status}</span>
          <strong>{booking.topic}</strong>
          <span className="booking-card__when">{formatDateTime(booking.proposed_at)}</span>
          <span className="booking-card__duration">{booking.duration_minutes} min</span>
          <span className="booking-card__type">{booking.meeting_type.replace('_', ' ')}</span>
        </div>
        <span className="booking-card__chevron">{expanded ? '▲' : '▼'}</span>
      </div>

      {expanded && (
        <div className="booking-card__body">
          <p><strong>{isTeacher ? 'Parent' : 'Teacher'}:</strong> {isTeacher ? booking.parent_name : booking.teacher_name}</p>
          {booking.student_name && <p><strong>Student:</strong> {booking.student_name}</p>}
          {booking.notes && <p><strong>Notes:</strong> {booking.notes}</p>}

          {booking.video_link && (
            <p>
              <strong>Video Link:</strong>{' '}
              <a href={booking.video_link} target="_blank" rel="noopener noreferrer">
                Join Meeting
              </a>
            </p>
          )}

          {booking.teacher_notes && (
            <p><strong>Teacher Notes:</strong> {booking.teacher_notes}</p>
          )}

          {booking.cancellation_reason && (
            <p><strong>Cancellation Reason:</strong> {booking.cancellation_reason}</p>
          )}

          {/* Teacher actions */}
          {isTeacher && booking.status === 'pending' && onConfirm && (
            <div className="booking-card__actions">
              <input
                type="url"
                placeholder="Video link (Zoom/Meet/Teams)"
                value={videoLink}
                onChange={e => setVideoLink(e.target.value)}
                className="input-field"
              />
              <button
                className="btn btn--primary"
                onClick={() => onConfirm(booking.id, videoLink)}
              >
                Confirm Meeting
              </button>
            </div>
          )}

          {isTeacher && booking.status === 'confirmed' && !isPast && onCancel && (
            <div className="booking-card__actions">
              <input
                type="text"
                placeholder="Reason for cancellation (optional)"
                value={cancelReason}
                onChange={e => setCancelReason(e.target.value)}
                className="input-field"
              />
              <button className="btn btn--danger" onClick={() => onCancel(booking.id, cancelReason)}>
                Cancel Meeting
              </button>
            </div>
          )}

          {isTeacher && booking.status === 'confirmed' && isPast && onComplete && (
            <div className="booking-card__actions">
              <textarea
                placeholder="Post-meeting notes (optional)"
                value={completeNotes}
                onChange={e => setCompleteNotes(e.target.value)}
                className="input-field"
                rows={3}
              />
              <button className="btn btn--primary" onClick={() => onComplete(booking.id, completeNotes)}>
                Mark as Completed
              </button>
            </div>
          )}

          {/* Parent cancel action */}
          {!isTeacher && (booking.status === 'pending' || booking.status === 'confirmed') && onCancel && (
            <div className="booking-card__actions">
              <input
                type="text"
                placeholder="Reason for cancellation (optional)"
                value={cancelReason}
                onChange={e => setCancelReason(e.target.value)}
                className="input-field"
              />
              <button className="btn btn--danger" onClick={() => onCancel(booking.id, cancelReason)}>
                Cancel Meeting
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---- Teacher Availability Grid ----

interface AvailabilityGridProps {
  availability: TeacherAvailability[];
  onSave: (slots: AvailabilityCreate[]) => void;
  saving: boolean;
}

function AvailabilityGrid({ availability, onSave, saving }: AvailabilityGridProps) {
  // Local state: array of editable slot rows
  const [rows, setRows] = useState<AvailabilityCreate[]>(() => {
    if (availability.length > 0) {
      return availability.map(a => ({
        weekday: a.weekday,
        start_time: a.start_time,
        end_time: a.end_time,
        slot_duration_minutes: a.slot_duration_minutes,
        is_active: a.is_active,
      }));
    }
    return [];
  });

  const addRow = () => {
    setRows(prev => [
      ...prev,
      { weekday: 0, start_time: '09:00:00', end_time: '17:00:00', slot_duration_minutes: 30, is_active: true },
    ]);
  };

  const removeRow = (idx: number) => {
    setRows(prev => prev.filter((_, i) => i !== idx));
  };

  const updateRow = (idx: number, field: keyof AvailabilityCreate, value: unknown) => {
    setRows(prev => prev.map((r, i) => i === idx ? { ...r, [field]: value } : r));
  };

  const handleSave = () => {
    onSave(rows.filter(r => r.is_active));
  };

  return (
    <div className="availability-grid">
      <div className="availability-grid__header">
        <h3>Weekly Availability</h3>
        <button className="btn btn--secondary btn--sm" onClick={addRow}>+ Add Window</button>
      </div>

      {rows.length === 0 && (
        <p className="empty-state">No availability set. Add a window to get started.</p>
      )}

      <div className="availability-grid__rows">
        {rows.map((row, idx) => (
          <div key={idx} className="availability-row">
            <label className="availability-row__field">
              <span>Day</span>
              <select
                value={row.weekday}
                onChange={e => updateRow(idx, 'weekday', Number(e.target.value))}
                className="input-select"
              >
                {WEEKDAYS.map((d, i) => (
                  <option key={i} value={i}>{d}</option>
                ))}
              </select>
            </label>

            <label className="availability-row__field">
              <span>Start</span>
              <input
                type="time"
                value={row.start_time.slice(0, 5)}
                onChange={e => updateRow(idx, 'start_time', e.target.value + ':00')}
                className="input-field"
              />
            </label>

            <label className="availability-row__field">
              <span>End</span>
              <input
                type="time"
                value={row.end_time.slice(0, 5)}
                onChange={e => updateRow(idx, 'end_time', e.target.value + ':00')}
                className="input-field"
              />
            </label>

            <label className="availability-row__field">
              <span>Slot (min)</span>
              <select
                value={row.slot_duration_minutes}
                onChange={e => updateRow(idx, 'slot_duration_minutes', Number(e.target.value))}
                className="input-select"
              >
                {SLOT_DURATIONS.map(d => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </label>

            <button
              className="btn btn--icon btn--danger"
              onClick={() => removeRow(idx)}
              title="Remove"
            >
              &times;
            </button>
          </div>
        ))}
      </div>

      {rows.length > 0 && (
        <button className="btn btn--primary" onClick={handleSave} disabled={saving}>
          {saving ? 'Saving…' : 'Save Availability'}
        </button>
      )}
    </div>
  );
}

// ---- Slot Picker (parent booking) ----

interface SlotPickerProps {
  teacherId: number;
  onSelect: (slot: AvailableSlot) => void;
}

function SlotPicker({ teacherId, onSelect }: SlotPickerProps) {
  const [slots, setSlots] = useState<AvailableSlot[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [weekOffset, setWeekOffset] = useState(0);

  const loadSlots = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const now = new Date();
      const monday = getMondayOfWeek(now);
      monday.setDate(monday.getDate() + weekOffset * 7);
      const sunday = new Date(monday);
      sunday.setDate(monday.getDate() + 7);

      const res = await getAvailableSlots(teacherId, monday, sunday);
      setSlots(res.slots);
    } catch {
      setError('Failed to load available slots.');
    } finally {
      setLoading(false);
    }
  }, [teacherId, weekOffset]);

  useEffect(() => {
    loadSlots();
  }, [loadSlots]);

  if (loading) return <p className="loading-text">Loading available slots…</p>;
  if (error) return <p className="error-text">{error}</p>;

  // Group slots by date
  const grouped: Record<string, AvailableSlot[]> = {};
  slots.forEach(s => {
    const dateKey = new Date(s.slot_start).toDateString();
    if (!grouped[dateKey]) grouped[dateKey] = [];
    grouped[dateKey].push(s);
  });

  return (
    <div className="slot-picker">
      <div className="slot-picker__nav">
        <button className="btn btn--icon" onClick={() => setWeekOffset(w => w - 1)} title="Previous week">
          &#8592;
        </button>
        <span className="slot-picker__week-label">
          Week of {(() => {
            const mon = getMondayOfWeek(new Date());
            mon.setDate(mon.getDate() + weekOffset * 7);
            return mon.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
          })()}
        </span>
        <button className="btn btn--icon" onClick={() => setWeekOffset(w => w + 1)} title="Next week">
          &#8594;
        </button>
      </div>

      {slots.length === 0 ? (
        <p className="empty-state">No available slots this week.</p>
      ) : (
        <div className="slot-picker__grid">
          {Object.entries(grouped).map(([dateStr, daySlots]) => (
            <div key={dateStr} className="slot-picker__day">
              <div className="slot-picker__day-label">{dateStr}</div>
              <div className="slot-picker__slots">
                {daySlots.map((slot, i) => (
                  <button
                    key={i}
                    className="slot-btn slot-btn--available"
                    onClick={() => onSelect(slot)}
                    title={`${formatTime(slot.slot_start)} – ${formatTime(slot.slot_end)}`}
                  >
                    {formatTime(slot.slot_start)}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---- Book Meeting Modal ----

interface BookMeetingModalProps {
  teacherId: number;
  selectedSlot: AvailableSlot | null;
  onClose: () => void;
  onBooked: () => void;
}

function BookMeetingModal({ teacherId, selectedSlot, onClose, onBooked }: BookMeetingModalProps) {
  const [topic, setTopic] = useState('');
  const [notes, setNotes] = useState('');
  const [meetingType, setMeetingType] = useState<'video_call' | 'in_person' | 'phone'>('video_call');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async () => {
    if (!selectedSlot) return;
    if (!topic.trim()) { setError('Please enter a topic.'); return; }
    setSubmitting(true);
    setError('');
    try {
      await bookMeeting({
        teacher_id: teacherId,
        proposed_at: selectedSlot.slot_start,
        duration_minutes: selectedSlot.duration_minutes,
        meeting_type: meetingType,
        topic,
        notes: notes || undefined,
      });
      onBooked();
      onClose();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setError(axiosErr?.response?.data?.detail || 'Failed to book meeting.');
    } finally {
      setSubmitting(false);
    }
  };

  if (!selectedSlot) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal__header">
          <h3>Book a Meeting</h3>
          <button className="modal__close" onClick={onClose}>&times;</button>
        </div>
        <div className="modal__body">
          <p className="modal__slot-info">
            <strong>Time:</strong> {formatDateTime(selectedSlot.slot_start)} ({selectedSlot.duration_minutes} min)
          </p>

          <label className="form-label">
            Meeting Type
            <select
              className="input-select"
              value={meetingType}
              onChange={e => setMeetingType(e.target.value as 'video_call' | 'in_person' | 'phone')}
            >
              {MEETING_TYPES.map(mt => (
                <option key={mt.value} value={mt.value}>{mt.label}</option>
              ))}
            </select>
          </label>

          <label className="form-label">
            Topic <span className="required">*</span>
            <input
              type="text"
              className="input-field"
              value={topic}
              onChange={e => setTopic(e.target.value)}
              placeholder="e.g. Mid-term progress discussion"
            />
          </label>

          <label className="form-label">
            Additional Notes
            <textarea
              className="input-field"
              value={notes}
              onChange={e => setNotes(e.target.value)}
              rows={3}
              placeholder="Any specific concerns or topics you'd like to discuss"
            />
          </label>

          {error && <p className="error-text">{error}</p>}
        </div>
        <div className="modal__footer">
          <button className="btn btn--secondary" onClick={onClose}>Cancel</button>
          <button className="btn btn--primary" onClick={handleSubmit} disabled={submitting}>
            {submitting ? 'Booking…' : 'Confirm Booking'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export function MeetingSchedulerPage() {
  const { user } = useAuth();
  const role = user?.role ?? '';

  const [meetings, setMeetings] = useState<MeetingBooking[]>([]);
  const [availability, setAvailability] = useState<TeacherAvailability[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [savingAvail, setSavingAvail] = useState(false);
  const [activeTab, setActiveTab] = useState<'upcoming' | 'past' | 'availability' | 'schedule'>('upcoming');
  const [successMsg, setSuccessMsg] = useState('');

  // Parent-specific state
  const [selectedTeacherId, setSelectedTeacherId] = useState<number | null>(null);
  const [teacherIdInput, setTeacherIdInput] = useState('');
  const [selectedSlot, setSelectedSlot] = useState<AvailableSlot | null>(null);
  const [showBookModal, setShowBookModal] = useState(false);

  // Teacher schedule
  const [scheduleWeekOf, setScheduleWeekOf] = useState(getMondayOfWeek(new Date()));
  const [schedule, setSchedule] = useState<MeetingBooking[]>([]);
  const [loadingSchedule, setLoadingSchedule] = useState(false);

  const loadMeetings = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [meetingsData] = await Promise.all([listMyMeetings()]);
      setMeetings(meetingsData);
      if (role === 'teacher') {
        const avail = await getMyAvailability();
        setAvailability(avail);
      }
    } catch {
      setError('Failed to load meetings. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [role]);

  useEffect(() => {
    loadMeetings();
  }, [loadMeetings]);

  const loadSchedule = useCallback(async () => {
    if (role !== 'teacher') return;
    setLoadingSchedule(true);
    try {
      const res = await getTeacherSchedule(scheduleWeekOf);
      setSchedule(res.bookings);
    } catch {
      // silently fail
    } finally {
      setLoadingSchedule(false);
    }
  }, [role, scheduleWeekOf]);

  useEffect(() => {
    if (activeTab === 'schedule') {
      loadSchedule();
    }
  }, [activeTab, loadSchedule]);

  const showSuccess = (msg: string) => {
    setSuccessMsg(msg);
    setTimeout(() => setSuccessMsg(''), 3000);
  };

  const handleSaveAvailability = async (slots: AvailabilityCreate[]) => {
    setSavingAvail(true);
    try {
      const result = await setMyAvailability(slots);
      setAvailability(result);
      showSuccess('Availability saved successfully.');
    } catch {
      setError('Failed to save availability.');
    } finally {
      setSavingAvail(false);
    }
  };

  const handleConfirm = async (id: number, videoLink: string) => {
    try {
      await confirmMeeting(id, { video_link: videoLink || undefined });
      showSuccess('Meeting confirmed.');
      loadMeetings();
    } catch {
      setError('Failed to confirm meeting.');
    }
  };

  const handleCancel = async (id: number, reason: string) => {
    try {
      await cancelMeeting(id, { reason: reason || undefined });
      showSuccess('Meeting cancelled.');
      loadMeetings();
    } catch {
      setError('Failed to cancel meeting.');
    }
  };

  const handleComplete = async (id: number, notes: string) => {
    try {
      await completeMeeting(id, { teacher_notes: notes || undefined });
      showSuccess('Meeting marked as completed.');
      loadMeetings();
    } catch {
      setError('Failed to complete meeting.');
    }
  };

  const upcoming = meetings.filter(
    m => new Date(m.proposed_at) >= new Date() || m.status === 'pending',
  );
  const past = meetings.filter(
    m => new Date(m.proposed_at) < new Date() && m.status !== 'pending',
  );

  // Teacher tabs
  const teacherTabs = [
    { key: 'upcoming', label: 'Upcoming' },
    { key: 'past', label: 'Past' },
    { key: 'availability', label: 'Availability' },
    { key: 'schedule', label: 'Week Schedule' },
  ] as const;

  // Parent tabs
  const parentTabs = [
    { key: 'upcoming', label: 'Upcoming' },
    { key: 'past', label: 'Past' },
  ] as const;

  return (
    <DashboardLayout>
      <div className="meeting-scheduler-page">
        <div className="meeting-scheduler-page__header">
          <h1>Meetings</h1>
          <p className="meeting-scheduler-page__subtitle">
            {role === 'teacher'
              ? 'Manage your availability and respond to parent meeting requests.'
              : 'Schedule meetings with your child\'s teachers.'}
          </p>
        </div>

        {successMsg && <div className="alert alert--success">{successMsg}</div>}
        {error && <div className="alert alert--error">{error}</div>}

        {loading ? (
          <div className="loading-state">Loading meetings…</div>
        ) : (
          <>
            {/* Tab navigation */}
            <div className="tabs">
              {(role === 'teacher' ? teacherTabs : parentTabs).map(tab => (
                <button
                  key={tab.key}
                  className={`tab-btn${activeTab === tab.key ? ' tab-btn--active' : ''}`}
                  onClick={() => setActiveTab(tab.key as typeof activeTab)}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* ------ UPCOMING ------ */}
            {activeTab === 'upcoming' && (
              <div className="tab-content">
                {/* Parent: teacher selector + slot picker */}
                {role === 'parent' && (
                  <div className="parent-book-section">
                    <h3>Book a New Meeting</h3>
                    <div className="teacher-selector">
                      <label className="form-label">
                        Teacher ID
                        <div className="teacher-selector__row">
                          <input
                            type="number"
                            className="input-field"
                            value={teacherIdInput}
                            onChange={e => setTeacherIdInput(e.target.value)}
                            placeholder="Enter teacher's user ID"
                          />
                          <button
                            className="btn btn--primary"
                            onClick={() => {
                              const id = parseInt(teacherIdInput, 10);
                              if (!isNaN(id) && id > 0) setSelectedTeacherId(id);
                            }}
                          >
                            Load Slots
                          </button>
                        </div>
                      </label>
                    </div>

                    {selectedTeacherId && (
                      <>
                        <h4>Available Slots — Teacher #{selectedTeacherId}</h4>
                        <SlotPicker
                          teacherId={selectedTeacherId}
                          onSelect={slot => {
                            setSelectedSlot(slot);
                            setShowBookModal(true);
                          }}
                        />
                      </>
                    )}

                    {showBookModal && selectedSlot && selectedTeacherId && (
                      <BookMeetingModal
                        teacherId={selectedTeacherId}
                        selectedSlot={selectedSlot}
                        onClose={() => setShowBookModal(false)}
                        onBooked={() => {
                          loadMeetings();
                          showSuccess('Meeting request sent!');
                        }}
                      />
                    )}
                  </div>
                )}

                <h3 className="section-title">Upcoming Meetings</h3>
                {upcoming.length === 0 ? (
                  <p className="empty-state">No upcoming meetings.</p>
                ) : (
                  upcoming.map(b => (
                    <BookingCard
                      key={b.id}
                      booking={b}
                      role={role}
                      onConfirm={handleConfirm}
                      onCancel={handleCancel}
                      onComplete={handleComplete}
                    />
                  ))
                )}
              </div>
            )}

            {/* ------ PAST ------ */}
            {activeTab === 'past' && (
              <div className="tab-content">
                <h3 className="section-title">Past Meetings</h3>
                {past.length === 0 ? (
                  <p className="empty-state">No past meetings.</p>
                ) : (
                  past.map(b => (
                    <BookingCard
                      key={b.id}
                      booking={b}
                      role={role}
                      onComplete={handleComplete}
                    />
                  ))
                )}
              </div>
            )}

            {/* ------ AVAILABILITY (teacher only) ------ */}
            {activeTab === 'availability' && role === 'teacher' && (
              <div className="tab-content">
                <AvailabilityGrid
                  availability={availability}
                  onSave={handleSaveAvailability}
                  saving={savingAvail}
                />
              </div>
            )}

            {/* ------ WEEK SCHEDULE (teacher only) ------ */}
            {activeTab === 'schedule' && role === 'teacher' && (
              <div className="tab-content">
                <div className="schedule-nav">
                  <button
                    className="btn btn--icon"
                    onClick={() => {
                      const prev = new Date(scheduleWeekOf);
                      prev.setDate(prev.getDate() - 7);
                      setScheduleWeekOf(prev);
                    }}
                  >
                    &#8592;
                  </button>
                  <span className="schedule-nav__label">
                    Week of {scheduleWeekOf.toLocaleDateString(undefined, { month: 'long', day: 'numeric', year: 'numeric' })}
                  </span>
                  <button
                    className="btn btn--icon"
                    onClick={() => {
                      const next = new Date(scheduleWeekOf);
                      next.setDate(next.getDate() + 7);
                      setScheduleWeekOf(next);
                    }}
                  >
                    &#8594;
                  </button>
                </div>
                {loadingSchedule ? (
                  <p className="loading-text">Loading schedule…</p>
                ) : schedule.length === 0 ? (
                  <p className="empty-state">No meetings scheduled this week.</p>
                ) : (
                  schedule.map(b => (
                    <BookingCard
                      key={b.id}
                      booking={b}
                      role={role}
                      onConfirm={handleConfirm}
                      onCancel={handleCancel}
                      onComplete={handleComplete}
                    />
                  ))
                )}
              </div>
            )}
          </>
        )}
      </div>
    </DashboardLayout>
  );
}

export default MeetingSchedulerPage;
