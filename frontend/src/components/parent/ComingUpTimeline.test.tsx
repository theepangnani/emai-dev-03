import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ComingUpTimeline } from './ComingUpTimeline'
import type { CalendarAssignment } from '../calendar/types'

// Helper to wrap component with router context
function renderTimeline(assignments: CalendarAssignment[], selectedChild: number | null = null) {
  return render(
    <MemoryRouter>
      <ComingUpTimeline
        calendarAssignments={assignments}
        selectedChild={selectedChild}
        onNavigateStudy={vi.fn()}
      />
    </MemoryRouter>,
  )
}

// Helper to create a date relative to today
function daysFromNow(days: number): Date {
  const d = new Date()
  d.setDate(d.getDate() + days)
  d.setHours(12, 0, 0, 0)
  return d
}

describe('ComingUpTimeline', () => {
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
        courseColor: '#49b8c0',
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
        courseColor: '#49b8c0',
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
