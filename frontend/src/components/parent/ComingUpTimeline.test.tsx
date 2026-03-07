import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ComingUpTimeline } from './ComingUpTimeline'
import type { CalendarAssignment } from '../calendar/types'

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

// Helper to wrap component with router context
function renderTimeline(
  assignments: CalendarAssignment[],
  selectedChild: number | null = null,
  onNavigateStudy = vi.fn(),
) {
  return {
    onNavigateStudy,
    ...render(
      <MemoryRouter>
        <ComingUpTimeline
          calendarAssignments={assignments}
          selectedChild={selectedChild}
          onNavigateStudy={onNavigateStudy}
        />
      </MemoryRouter>,
    ),
  }
}

// Helper to create a date relative to today
function daysFromNow(days: number): Date {
  const d = new Date()
  d.setDate(d.getDate() + days)
  d.setHours(12, 0, 0, 0)
  return d
}

describe('ComingUpTimeline', () => {
  beforeEach(() => {
    mockNavigate.mockClear()
  })

  it('shows empty state when no items', () => {
    renderTimeline([])
    expect(screen.getByText('No upcoming items')).toBeInTheDocument()
  })

  it('renders assignment items', () => {
    const assignments: CalendarAssignment[] = [
      {
        id: 1,
        title: 'Math Homework',
        description: null,
        courseId: 10,
        courseName: 'Math',
        courseColor: '#4a90d9',
        dueDate: daysFromNow(1),
        childName: 'Alice',
        maxPoints: 100,
        itemType: 'assignment',
      },
    ]
    renderTimeline(assignments)
    expect(screen.getByText('Math Homework')).toBeInTheDocument()
    expect(screen.getByText('Assignment')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Study Math Homework/ })).toBeInTheDocument()
  })

  // Regression test for #1047: tasks must appear in Coming Up timeline
  it('renders task items alongside assignments (regression #1047)', () => {
    const items: CalendarAssignment[] = [
      {
        id: 1,
        title: 'Science Project',
        description: null,
        courseId: 10,
        courseName: 'Science',
        courseColor: '#4a90d9',
        dueDate: daysFromNow(1),
        childName: 'Alice',
        maxPoints: 100,
        itemType: 'assignment',
      },
      {
        id: 1_000_001,
        taskId: 1,
        title: 'Study for quiz',
        description: null,
        courseId: 0,
        courseName: '',
        courseColor: '#ff9800',
        dueDate: daysFromNow(0), // due today
        childName: 'Alice',
        maxPoints: null,
        itemType: 'task',
        priority: 'high',
        isCompleted: false,
      },
    ]
    renderTimeline(items)
    expect(screen.getByText('Science Project')).toBeInTheDocument()
    expect(screen.getByText('Study for quiz')).toBeInTheDocument()
    expect(screen.getByText('Task')).toBeInTheDocument()
    expect(screen.getByText('Assignment')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /View Study for quiz/ })).toBeInTheDocument()
  })

  it('excludes completed tasks', () => {
    const items: CalendarAssignment[] = [
      {
        id: 1_000_001,
        taskId: 1,
        title: 'Done task',
        description: null,
        courseId: 0,
        courseName: '',
        courseColor: '#66bb6a',
        dueDate: daysFromNow(0),
        childName: 'Alice',
        maxPoints: null,
        itemType: 'task',
        priority: 'low',
        isCompleted: true,
      },
    ]
    renderTimeline(items)
    expect(screen.getByText('No upcoming items')).toBeInTheDocument()
    expect(screen.queryByText('Done task')).not.toBeInTheDocument()
  })

  // Regression test for #1049/#1051: clicking task row navigates to task detail
  it('clicking a task row navigates to /tasks/:id (regression #1051)', async () => {
    const items: CalendarAssignment[] = [
      {
        id: 1_000_001,
        taskId: 1,
        title: 'Clickable task',
        description: null,
        courseId: 0,
        courseName: '',
        courseColor: '#ff9800',
        dueDate: daysFromNow(0),
        childName: 'Alice',
        maxPoints: null,
        itemType: 'task',
        priority: 'medium',
        isCompleted: false,
      },
    ]
    renderTimeline(items)
    const row = screen.getByText('Clickable task').closest('[role="listitem"]')!
    await userEvent.click(row)
    expect(mockNavigate).toHaveBeenCalledWith('/tasks/1')
  })

  it('clicking an assignment row calls onNavigateStudy (regression #1049)', async () => {
    const onStudy = vi.fn()
    const items: CalendarAssignment[] = [
      {
        id: 42,
        title: 'Clickable assignment',
        description: null,
        courseId: 10,
        courseName: 'Math',
        courseColor: '#4a90d9',
        dueDate: daysFromNow(1),
        childName: 'Alice',
        maxPoints: 100,
        itemType: 'assignment',
      },
    ]
    renderTimeline(items, null, onStudy)
    const row = screen.getByText('Clickable assignment').closest('[role="listitem"]')!
    await userEvent.click(row)
    expect(onStudy).toHaveBeenCalledWith(expect.objectContaining({ id: 42, title: 'Clickable assignment' }))
  })

  // Regression test for #1295: "Overdue" and "Task" must be separate, distinguishable elements
  // (they were visually concatenated as "OverdueTask" on /my-kids due to missing CSS)
  it('renders overdue date and type as separate elements (regression #1295)', () => {
    const items: CalendarAssignment[] = [
      {
        id: 1_000_003,
        taskId: 3,
        title: 'Review: math.set3.5',
        description: null,
        courseId: 0,
        courseName: '',
        courseColor: '#ef5350',
        dueDate: daysFromNow(-2),
        childName: 'Alice',
        maxPoints: null,
        itemType: 'task',
        priority: 'high',
        isCompleted: false,
      },
    ]
    renderTimeline(items)
    // "Overdue" and "Task" must be distinct elements, not concatenated
    const overdue = screen.getByText('Overdue')
    const task = screen.getByText('Task')
    expect(overdue).toBeInTheDocument()
    expect(task).toBeInTheDocument()
    // They must be sibling spans inside pd-timeline-meta
    const meta = overdue.closest('.pd-timeline-meta')
    expect(meta).not.toBeNull()
    expect(meta).toContainElement(task)
    // Verify they are separate DOM nodes
    expect(overdue).not.toBe(task)
  })

  it('shows overdue tasks (regression: overdue tasks were hidden)', () => {
    const items: CalendarAssignment[] = [
      {
        id: 1_000_002,
        taskId: 2,
        title: 'Overdue homework',
        description: null,
        courseId: 0,
        courseName: '',
        courseColor: '#ef5350',
        dueDate: daysFromNow(-3), // 3 days overdue
        childName: 'Bob',
        maxPoints: null,
        itemType: 'task',
        priority: 'high',
        isCompleted: false,
      },
    ]
    renderTimeline(items)
    expect(screen.getByText('Overdue homework')).toBeInTheDocument()
    expect(screen.getByText('Overdue')).toBeInTheDocument()
  })
})
