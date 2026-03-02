import { useState, useEffect, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { DashboardLayout } from '../components/DashboardLayout';
import { useAuth } from '../context/AuthContext';
import {
  getCourseAttendance,
  bulkMarkAttendance,
  getCourseReport,
  getMyAttendanceSummary,
  getParentChildAttendance,
  type AttendanceStatus,
  type AttendanceRecord,
  type BulkAttendanceEntry,
  type AttendanceSummary,
  type CourseAttendanceReport,
} from '../api/attendance';
import apiClient from '../api/client';
import './AttendancePage.css';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function todayISO(): string {
  return new Date().toISOString().split('T')[0];
}

function monthStart(isoDate: string): string {
  return isoDate.slice(0, 7) + '-01';
}

function monthEnd(isoDate: string): string {
  const d = new Date(isoDate);
  const last = new Date(d.getFullYear(), d.getMonth() + 1, 0);
  return last.toISOString().split('T')[0];
}

function daysInMonth(year: number, month: number): number {
  return new Date(year, month + 1, 0).getDate();
}

interface CourseOption {
  id: number;
  name: string;
}

interface StudentOption {
  id: number;
  name: string;
  user_id: number;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

const STATUS_LABELS: Record<AttendanceStatus, string> = {
  present: 'Present',
  absent: 'Absent',
  late: 'Late',
  excused: 'Excused',
};

const STATUS_CLASSES: Record<AttendanceStatus, string> = {
  present: 'att-btn att-present',
  absent: 'att-btn att-absent',
  late: 'att-btn att-late',
  excused: 'att-btn att-excused',
};

function StatusButton({
  status,
  active,
  onClick,
}: {
  status: AttendanceStatus;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={`${STATUS_CLASSES[status]}${active ? ' att-btn--active' : ''}`}
      onClick={onClick}
      title={STATUS_LABELS[status]}
    >
      {STATUS_LABELS[status]}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Teacher view
// ---------------------------------------------------------------------------

function TeacherView() {
  const queryClient = useQueryClient();
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(null);
  const [selectedDate, setSelectedDate] = useState(todayISO());
  const [statusMap, setStatusMap] = useState<Record<number, AttendanceStatus>>({});
  const [noteMap, setNoteMap] = useState<Record<number, string>>({});
  const [activeTab, setActiveTab] = useState<'mark' | 'report'>('mark');
  const [reportStart, setReportStart] = useState(monthStart(todayISO()));
  const [reportEnd, setReportEnd] = useState(monthEnd(todayISO()));
  const [submitMsg, setSubmitMsg] = useState('');

  // Fetch teacher's courses
  const { data: courses = [] } = useQuery<CourseOption[]>({
    queryKey: ['teacher-courses'],
    queryFn: async () => {
      const { data } = await apiClient.get('/api/courses/');
      return (data as { id: number; name: string }[]).map((c) => ({ id: c.id, name: c.name }));
    },
  });

  // Auto-select first course
  useEffect(() => {
    if (courses.length > 0 && selectedCourseId === null) {
      setSelectedCourseId(courses[0].id);
    }
  }, [courses, selectedCourseId]);

  // Fetch students enrolled in course
  const { data: students = [] } = useQuery<StudentOption[]>({
    queryKey: ['course-students', selectedCourseId],
    enabled: !!selectedCourseId,
    queryFn: async () => {
      const { data } = await apiClient.get(`/api/courses/${selectedCourseId}`);
      const raw = data as { students?: { id: number; user?: { id: number; full_name: string } }[] };
      return (raw.students ?? []).map((s) => ({
        id: s.id,
        user_id: s.user?.id ?? s.id,
        name: s.user?.full_name ?? `Student ${s.id}`,
      }));
    },
  });

  // Load existing records for selected date
  const { data: existingRecords = [] } = useQuery<AttendanceRecord[]>({
    queryKey: ['course-attendance', selectedCourseId, selectedDate],
    enabled: !!selectedCourseId,
    queryFn: () => getCourseAttendance(selectedCourseId!, selectedDate),
  });

  // Populate statusMap from existing records
  useEffect(() => {
    const map: Record<number, AttendanceStatus> = {};
    const nmap: Record<number, string> = {};
    for (const r of existingRecords) {
      map[r.student_id] = r.status;
      if (r.note) nmap[r.student_id] = r.note;
    }
    setStatusMap(map);
    setNoteMap(nmap);
  }, [existingRecords]);

  const setStatus = useCallback(
    (userId: number, status: AttendanceStatus) =>
      setStatusMap((prev) => ({ ...prev, [userId]: status })),
    [],
  );

  const markAllPresent = useCallback(() => {
    const map: Record<number, AttendanceStatus> = {};
    for (const s of students) map[s.user_id] = 'present';
    setStatusMap(map);
  }, [students]);

  const bulkMutation = useMutation({
    mutationFn: bulkMarkAttendance,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['course-attendance', selectedCourseId] });
      setSubmitMsg('Attendance saved successfully.');
      setTimeout(() => setSubmitMsg(''), 3000);
    },
    onError: () => setSubmitMsg('Failed to save attendance.'),
  });

  const handleSubmit = () => {
    if (!selectedCourseId) return;
    const records: BulkAttendanceEntry[] = students
      .filter((s) => statusMap[s.user_id])
      .map((s) => ({
        student_id: s.user_id,
        status: statusMap[s.user_id],
        note: noteMap[s.user_id] || undefined,
      }));
    if (records.length === 0) {
      setSubmitMsg('No status selected for any student.');
      return;
    }
    bulkMutation.mutate({
      course_id: selectedCourseId,
      date: selectedDate,
      records,
    });
  };

  // Course report
  const { data: report } = useQuery<CourseAttendanceReport>({
    queryKey: ['course-report', selectedCourseId, reportStart, reportEnd],
    enabled: !!selectedCourseId && activeTab === 'report',
    queryFn: () => getCourseReport(selectedCourseId!, reportStart, reportEnd),
  });

  return (
    <div className="att-container">
      <h1 className="att-title">Attendance</h1>

      <div className="att-tabs">
        <button
          className={`att-tab${activeTab === 'mark' ? ' att-tab--active' : ''}`}
          onClick={() => setActiveTab('mark')}
        >
          Mark Attendance
        </button>
        <button
          className={`att-tab${activeTab === 'report' ? ' att-tab--active' : ''}`}
          onClick={() => setActiveTab('report')}
        >
          Report
        </button>
      </div>

      {/* Course + Date selectors */}
      <div className="att-controls">
        <div className="att-control-group">
          <label htmlFor="att-course-select">Course</label>
          <select
            id="att-course-select"
            value={selectedCourseId ?? ''}
            onChange={(e) => setSelectedCourseId(Number(e.target.value))}
          >
            {courses.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
        {activeTab === 'mark' && (
          <div className="att-control-group">
            <label htmlFor="att-date-pick">Date</label>
            <input
              id="att-date-pick"
              type="date"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
            />
          </div>
        )}
        {activeTab === 'report' && (
          <>
            <div className="att-control-group">
              <label htmlFor="att-report-start">From</label>
              <input
                id="att-report-start"
                type="date"
                value={reportStart}
                onChange={(e) => setReportStart(e.target.value)}
              />
            </div>
            <div className="att-control-group">
              <label htmlFor="att-report-end">To</label>
              <input
                id="att-report-end"
                type="date"
                value={reportEnd}
                onChange={(e) => setReportEnd(e.target.value)}
              />
            </div>
          </>
        )}
      </div>

      {/* Mark Attendance Tab */}
      {activeTab === 'mark' && (
        <>
          <div className="att-mark-header">
            <button type="button" className="att-mark-all-btn" onClick={markAllPresent}>
              Mark All Present
            </button>
          </div>
          <div className="att-roster">
            {students.length === 0 ? (
              <p className="att-empty">No students enrolled in this course.</p>
            ) : (
              <table className="att-table">
                <thead>
                  <tr>
                    <th>Student</th>
                    <th>Status</th>
                    <th>Note</th>
                  </tr>
                </thead>
                <tbody>
                  {students.map((s) => (
                    <tr key={s.user_id}>
                      <td className="att-student-name">{s.name}</td>
                      <td>
                        <div className="att-status-group">
                          {(['present', 'absent', 'late', 'excused'] as AttendanceStatus[]).map((st) => (
                            <StatusButton
                              key={st}
                              status={st}
                              active={statusMap[s.user_id] === st}
                              onClick={() => setStatus(s.user_id, st)}
                            />
                          ))}
                        </div>
                      </td>
                      <td>
                        <input
                          type="text"
                          className="att-note-input"
                          placeholder="Optional note"
                          value={noteMap[s.user_id] ?? ''}
                          onChange={(e) =>
                            setNoteMap((prev) => ({ ...prev, [s.user_id]: e.target.value }))
                          }
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          {submitMsg && (
            <p
              className={`att-msg${submitMsg.includes('success') ? ' att-msg--ok' : ' att-msg--err'}`}
            >
              {submitMsg}
            </p>
          )}
          <button
            type="button"
            className="att-submit-btn"
            onClick={handleSubmit}
            disabled={bulkMutation.isPending || students.length === 0}
          >
            {bulkMutation.isPending ? 'Saving...' : 'Submit Attendance'}
          </button>
        </>
      )}

      {/* Report Tab */}
      {activeTab === 'report' && (
        <div className="att-report">
          {!report ? (
            <p className="att-empty">Loading report...</p>
          ) : report.student_summaries.length === 0 ? (
            <p className="att-empty">No attendance data for this period.</p>
          ) : (
            <>
              <h2 className="att-report-title">
                {report.course_name} — {report.start_date} to {report.end_date}
              </h2>
              <table className="att-table att-report-table">
                <thead>
                  <tr>
                    <th>Student</th>
                    <th>Present</th>
                    <th>Absent</th>
                    <th>Late</th>
                    <th>Excused</th>
                    <th>Attendance %</th>
                  </tr>
                </thead>
                <tbody>
                  {report.student_summaries.map((s) => (
                    <tr key={s.student_id}>
                      <td>{s.student_name}</td>
                      <td className="att-cell-present">{s.present_count}</td>
                      <td className="att-cell-absent">{s.absent_count}</td>
                      <td className="att-cell-late">{s.late_count}</td>
                      <td className="att-cell-excused">{s.excused_count}</td>
                      <td>
                        <div className="att-pct-bar-wrap">
                          <div
                            className="att-pct-bar"
                            style={{ width: `${s.attendance_pct}%` }}
                          />
                          <span className="att-pct-label">{s.attendance_pct}%</span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Student / Parent summary card
// ---------------------------------------------------------------------------

function SummaryCards({ summary }: { summary: AttendanceSummary }) {
  return (
    <div className="att-summary-cards">
      <div className="att-card att-card--present">
        <div className="att-card-value">{summary.attendance_pct}%</div>
        <div className="att-card-label">Attendance Rate</div>
      </div>
      <div className="att-card att-card--absent">
        <div className="att-card-value">{summary.absent_count}</div>
        <div className="att-card-label">Absences</div>
      </div>
      <div className="att-card att-card--late">
        <div className="att-card-value">{summary.late_count}</div>
        <div className="att-card-label">Late Arrivals</div>
      </div>
      <div className="att-card att-card--excused">
        <div className="att-card-value">{summary.excused_count}</div>
        <div className="att-card-label">Excused</div>
      </div>
    </div>
  );
}

// A simple monthly calendar dot view — shows dots for each day the student
// has an attendance record.  Without a full "per day" endpoint we render a
// placeholder calendar showing the current month.
function MonthCalendar({ year, month }: { year: number; month: number }) {
  const days = daysInMonth(year, month);
  const firstDow = new Date(year, month, 1).getDay(); // 0=Sun
  const cells: (number | null)[] = Array(firstDow).fill(null);
  for (let d = 1; d <= days; d++) cells.push(d);
  while (cells.length % 7 !== 0) cells.push(null);

  const DOW = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  return (
    <div className="att-calendar">
      <div className="att-calendar-grid att-calendar-header">
        {DOW.map((d) => (
          <div key={d} className="att-calendar-dow">
            {d}
          </div>
        ))}
      </div>
      <div className="att-calendar-grid">
        {cells.map((day, i) => (
          <div key={i} className={`att-calendar-cell${day === null ? ' att-calendar-cell--empty' : ''}`}>
            {day}
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Student view
// ---------------------------------------------------------------------------

function StudentView() {
  const today = new Date();
  const { data: summary } = useQuery<AttendanceSummary>({
    queryKey: ['my-attendance-summary'],
    queryFn: () => getMyAttendanceSummary(),
  });

  return (
    <div className="att-container">
      <h1 className="att-title">My Attendance</h1>
      {summary ? (
        <>
          <SummaryCards summary={summary} />
          <h2 className="att-section-title">
            {today.toLocaleString('default', { month: 'long', year: 'numeric' })}
          </h2>
          <MonthCalendar year={today.getFullYear()} month={today.getMonth()} />
        </>
      ) : (
        <p className="att-empty">Loading attendance data...</p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Parent view
// ---------------------------------------------------------------------------

interface ChildOption {
  student_id: number;
  user_id: number;
  name: string;
}

function ParentView() {
  const [selectedChildUserId, setSelectedChildUserId] = useState<number | null>(null);
  const [children, setChildren] = useState<ChildOption[]>([]);
  const today = new Date();

  // Fetch parent's linked children
  useEffect(() => {
    apiClient
      .get('/api/parent/my-students')
      .then(({ data }) => {
        const raw = data as { id: number; user?: { id: number; full_name: string } }[];
        const opts: ChildOption[] = raw.map((s) => ({
          student_id: s.id,
          user_id: s.user?.id ?? s.id,
          name: s.user?.full_name ?? `Student ${s.id}`,
        }));
        setChildren(opts);
        if (opts.length > 0) setSelectedChildUserId(opts[0].user_id);
      })
      .catch(() => {});
  }, []);

  const { data: summary } = useQuery<AttendanceSummary>({
    queryKey: ['parent-child-attendance', selectedChildUserId],
    enabled: !!selectedChildUserId,
    queryFn: () => getParentChildAttendance(selectedChildUserId!),
  });

  return (
    <div className="att-container">
      <h1 className="att-title">Child Attendance</h1>

      {children.length > 1 && (
        <div className="att-controls">
          <div className="att-control-group">
            <label htmlFor="att-child-select">Child</label>
            <select
              id="att-child-select"
              value={selectedChildUserId ?? ''}
              onChange={(e) => setSelectedChildUserId(Number(e.target.value))}
            >
              {children.map((c) => (
                <option key={c.user_id} value={c.user_id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}

      {summary ? (
        <>
          <SummaryCards summary={summary} />
          <h2 className="att-section-title">
            {today.toLocaleString('default', { month: 'long', year: 'numeric' })}
          </h2>
          <MonthCalendar year={today.getFullYear()} month={today.getMonth()} />
          <h2 className="att-section-title">Breakdown by Course</h2>
          <p className="att-empty-sub">Overall: {summary.present_count} present / {summary.total_days} total days</p>
        </>
      ) : (
        <p className="att-empty">
          {selectedChildUserId === null
            ? 'No children linked to your account.'
            : 'Loading attendance data...'}
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page component
// ---------------------------------------------------------------------------

export function AttendancePage() {
  const { user } = useAuth();
  const role = user?.role;

  return (
    <DashboardLayout welcomeSubtitle="Attendance Tracker">
      {role === 'teacher' || role === 'admin' ? (
        <TeacherView />
      ) : role === 'parent' ? (
        <ParentView />
      ) : (
        <StudentView />
      )}
    </DashboardLayout>
  );
}

export default AttendancePage;
