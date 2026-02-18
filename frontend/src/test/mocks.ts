/**
 * Mock factories for test data.
 * Each factory returns a complete object with sensible defaults.
 * Pass partial overrides to customise per test.
 */

import type {
  ConversationSummary,
  ConversationDetail,
  MessageResponse,
  NotificationResponse,
  RecipientOption,
  AdminUserItem,
  AdminStats,
  ChildSummary,
  ChildHighlight,
  ParentDashboardData,
  ChildOverview,
  InviteResponse,
  TaskItem,
  BroadcastItem,
} from '../api/client'

// ── Incrementing ID helper ──────────────────────────────────────
let _nextId = 1000
function nextId() {
  return _nextId++
}

/** Reset the ID counter (call in beforeEach if needed). */
export function resetMockIds() {
  _nextId = 1000
}

// ── User ────────────────────────────────────────────────────────
export interface MockUser {
  id: number
  email: string
  full_name: string
  role: string
  roles: string[]
  is_active: boolean
  google_connected: boolean
}

export function createMockUser(overrides: Partial<MockUser> = {}): MockUser {
  const id = overrides.id ?? nextId()
  return {
    id,
    email: `user${id}@example.com`,
    full_name: 'Test User',
    role: 'parent',
    roles: ['parent'],
    is_active: true,
    google_connected: false,
    ...overrides,
  }
}

// ── Conversation ────────────────────────────────────────────────
export function createMockConversation(
  overrides: Partial<ConversationSummary> = {},
): ConversationSummary {
  const id = overrides.id ?? nextId()
  return {
    id,
    other_participant_id: 2,
    other_participant_name: 'Other User',
    other_participant_role: 'teacher',
    student_id: null,
    student_name: null,
    subject: `Conversation ${id}`,
    last_message_preview: 'Hello there',
    last_message_at: '2026-02-14T12:00:00Z',
    unread_count: 0,
    created_at: '2026-02-14T10:00:00Z',
    ...overrides,
  }
}

export function createMockConversationDetail(
  overrides: Partial<ConversationDetail> = {},
): ConversationDetail {
  const id = overrides.id ?? nextId()
  return {
    id,
    participant_1_id: 1,
    participant_1_name: 'Test User',
    participant_2_id: 2,
    participant_2_name: 'Other User',
    student_id: null,
    student_name: null,
    subject: `Conversation ${id}`,
    messages: [],
    messages_total: 0,
    messages_offset: 0,
    messages_limit: 50,
    created_at: '2026-02-14T10:00:00Z',
    ...overrides,
  }
}

// ── Message ─────────────────────────────────────────────────────
export function createMockMessage(
  overrides: Partial<MessageResponse> = {},
): MessageResponse {
  const id = overrides.id ?? nextId()
  return {
    id,
    conversation_id: 1,
    sender_id: 1,
    sender_name: 'Test User',
    content: 'Test message content',
    is_read: false,
    read_at: null,
    created_at: '2026-02-14T12:00:00Z',
    ...overrides,
  }
}

// ── Notification ────────────────────────────────────────────────
export function createMockNotification(
  overrides: Partial<NotificationResponse> = {},
): NotificationResponse {
  const id = overrides.id ?? nextId()
  return {
    id,
    user_id: 1,
    type: 'system',
    title: `Notification ${id}`,
    content: 'Test notification content',
    link: null,
    read: false,
    created_at: '2026-02-14T12:00:00Z',
    requires_ack: false,
    acked_at: null,
    source_type: null,
    source_id: null,
    reminder_count: 0,
    ...overrides,
  }
}

// ── Recipient ───────────────────────────────────────────────────
export function createMockRecipient(
  overrides: Partial<RecipientOption> = {},
): RecipientOption {
  const userId = overrides.user_id ?? nextId()
  return {
    user_id: userId,
    full_name: `Recipient ${userId}`,
    role: 'teacher',
    student_names: [],
    ...overrides,
  }
}

// ── Admin User ──────────────────────────────────────────────────
export function createMockAdminUser(
  overrides: Partial<AdminUserItem> = {},
): AdminUserItem {
  const id = overrides.id ?? nextId()
  return {
    id,
    email: `user${id}@example.com`,
    full_name: `User ${id}`,
    role: 'parent',
    roles: ['parent'],
    is_active: true,
    created_at: '2026-02-14T10:00:00Z',
    ...overrides,
  }
}

// ── Admin Stats ─────────────────────────────────────────────────
export function createMockAdminStats(
  overrides: Partial<AdminStats> = {},
): AdminStats {
  return {
    total_users: 50,
    users_by_role: { parent: 20, student: 20, teacher: 8, admin: 2 },
    total_courses: 10,
    total_assignments: 30,
    ...overrides,
  }
}

// ── Child / Parent Dashboard ────────────────────────────────────
export function createMockChild(
  overrides: Partial<ChildSummary> = {},
): ChildSummary {
  const studentId = overrides.student_id ?? nextId()
  return {
    student_id: studentId,
    user_id: studentId + 1000,
    full_name: `Child ${studentId}`,
    email: `child${studentId}@example.com`,
    grade_level: 8,
    school_name: 'Test School',
    date_of_birth: null,
    phone: null,
    address: null,
    city: null,
    province: null,
    postal_code: null,
    notes: null,
    relationship_type: 'guardian',
    invite_link: null,
    course_count: 2,
    active_task_count: 3,
    ...overrides,
  }
}

export function createMockChildHighlight(
  overrides: Partial<ChildHighlight> = {},
): ChildHighlight {
  const studentId = overrides.student_id ?? nextId()
  return {
    student_id: studentId,
    user_id: studentId + 1000,
    full_name: `Child ${studentId}`,
    grade_level: 8,
    overdue_count: 1,
    due_today_count: 2,
    upcoming_count: 3,
    completed_today_count: 0,
    courses: [],
    overdue_items: [],
    due_today_items: [],
    ...overrides,
  }
}

export function createMockParentDashboard(
  overrides: Partial<ParentDashboardData> = {},
): ParentDashboardData {
  return {
    children: [createMockChild()],
    google_connected: false,
    unread_messages: 0,
    total_overdue: 1,
    total_due_today: 2,
    total_tasks: 5,
    child_highlights: [createMockChildHighlight()],
    all_assignments: [],
    all_tasks: [],
    ...overrides,
  }
}

export function createMockChildOverview(
  overrides: Partial<ChildOverview> = {},
): ChildOverview {
  const studentId = overrides.student_id ?? nextId()
  return {
    student_id: studentId,
    user_id: studentId + 1000,
    full_name: `Child ${studentId}`,
    grade_level: 8,
    google_connected: false,
    courses: [],
    assignments: [],
    study_guides_count: 0,
    ...overrides,
  }
}

// ── Invite ──────────────────────────────────────────────────────
export function createMockInvite(
  overrides: Partial<InviteResponse> = {},
): InviteResponse {
  const id = overrides.id ?? nextId()
  return {
    id,
    email: `invite${id}@example.com`,
    invite_type: 'student',
    token: `token-${id}`,
    expires_at: '2026-02-21T12:00:00Z',
    invited_by_user_id: 1,
    metadata_json: null,
    accepted_at: null,
    last_resent_at: null,
    created_at: '2026-02-14T12:00:00Z',
    status: overrides.accepted_at ? 'accepted' as const : 'pending' as const,
    ...overrides,
  }
}

// ── Task ────────────────────────────────────────────────────────
export function createMockTask(
  overrides: Partial<TaskItem> = {},
): TaskItem {
  const id = overrides.id ?? nextId()
  return {
    id,
    created_by_user_id: 1,
    assigned_to_user_id: null,
    title: `Task ${id}`,
    description: null,
    due_date: '2026-02-15T23:59:00Z',
    is_completed: false,
    completed_at: null,
    archived_at: null,
    priority: 'medium',
    category: null,
    creator_name: 'Test User',
    assignee_name: null,
    course_id: null,
    course_content_id: null,
    study_guide_id: null,
    course_name: null,
    course_content_title: null,
    study_guide_title: null,
    study_guide_type: null,
    created_at: '2026-02-14T10:00:00Z',
    updated_at: null,
    ...overrides,
  }
}

// ── Broadcast ───────────────────────────────────────────────────
export function createMockBroadcast(
  overrides: Partial<BroadcastItem> = {},
): BroadcastItem {
  const id = overrides.id ?? nextId()
  return {
    id,
    subject: `Broadcast ${id}`,
    recipient_count: 50,
    email_count: 45,
    created_at: '2026-02-14T12:00:00Z',
    ...overrides,
  }
}
