import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/helpers'
import { SubGuidesPanel } from './SubGuidesPanel'

const MOCK_CHILDREN = [
  {
    id: 10,
    user_id: 1,
    assignment_id: null,
    course_id: 5,
    course_content_id: null,
    title: 'Quadratic Equations Deep Dive',
    content: 'content...',
    guide_type: 'study_guide',
    version: 1,
    parent_guide_id: 1,
    focus_prompt: null,
    created_at: '2026-03-15T10:00:00Z',
    archived_at: null,
  },
  {
    id: 11,
    user_id: 1,
    assignment_id: null,
    course_id: 5,
    course_content_id: 42,
    title: 'Chapter 5 Practice Quiz',
    content: '{}',
    guide_type: 'quiz',
    version: 1,
    parent_guide_id: 1,
    focus_prompt: null,
    created_at: '2026-03-16T10:00:00Z',
    archived_at: null,
  },
  {
    id: 12,
    user_id: 1,
    assignment_id: null,
    course_id: 5,
    course_content_id: null,
    title: 'Key Terms Flashcards',
    content: '{}',
    guide_type: 'flashcards',
    version: 1,
    parent_guide_id: 1,
    focus_prompt: null,
    created_at: '2026-03-17T10:00:00Z',
    archived_at: null,
  },
]

describe('SubGuidesPanel', () => {
  it('renders with count in header', () => {
    renderWithProviders(
      <SubGuidesPanel childGuides={MOCK_CHILDREN} parentGuideId={1} />
    )
    expect(screen.getByText('Sub-Guides (3)')).toBeInTheDocument()
  })

  it('starts expanded when there are children', () => {
    renderWithProviders(
      <SubGuidesPanel childGuides={MOCK_CHILDREN} parentGuideId={1} />
    )
    expect(screen.getByTestId('sub-guides-list')).toBeInTheDocument()
    expect(screen.getByText('Quadratic Equations Deep Dive')).toBeInTheDocument()
    expect(screen.getByText('Chapter 5 Practice Quiz')).toBeInTheDocument()
    expect(screen.getByText('Key Terms Flashcards')).toBeInTheDocument()
  })

  it('shows "No sub-guides yet" when empty and expanded', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <SubGuidesPanel childGuides={[]} parentGuideId={1} />
    )
    // Starts collapsed when 0 children
    expect(screen.queryByText('No sub-guides yet')).not.toBeInTheDocument()

    // Expand
    await user.click(screen.getByText('Sub-Guides (0)'))
    expect(screen.getByText('No sub-guides yet')).toBeInTheDocument()
  })

  it('starts collapsed when there are no children', () => {
    renderWithProviders(
      <SubGuidesPanel childGuides={[]} parentGuideId={1} />
    )
    expect(screen.queryByTestId('sub-guides-list')).not.toBeInTheDocument()
    expect(screen.queryByTestId('sub-guides-empty')).not.toBeInTheDocument()
  })

  it('collapses and expands on toggle click', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <SubGuidesPanel childGuides={MOCK_CHILDREN} parentGuideId={1} />
    )
    // Initially expanded
    expect(screen.getByTestId('sub-guides-list')).toBeInTheDocument()

    // Collapse
    await user.click(screen.getByText('Sub-Guides (3)'))
    expect(screen.queryByTestId('sub-guides-list')).not.toBeInTheDocument()

    // Expand again
    await user.click(screen.getByText('Sub-Guides (3)'))
    expect(screen.getByTestId('sub-guides-list')).toBeInTheDocument()
  })

  it('renders View links with correct URLs', () => {
    renderWithProviders(
      <SubGuidesPanel childGuides={MOCK_CHILDREN} parentGuideId={1} />
    )
    const viewLinks = screen.getAllByText('View')
    expect(viewLinks).toHaveLength(3)

    // All sub-guides link to their own study guide page
    expect(viewLinks[0].closest('a')).toHaveAttribute('href', '/study/guide/10')
    expect(viewLinks[1].closest('a')).toHaveAttribute('href', '/study/guide/11')
    expect(viewLinks[2].closest('a')).toHaveAttribute('href', '/study/guide/12')
  })

  it('shows guide type labels in meta text', () => {
    renderWithProviders(
      <SubGuidesPanel childGuides={MOCK_CHILDREN} parentGuideId={1} />
    )
    // Each item has a meta span with the guide type label and date
    const metaElements = document.querySelectorAll('.subguides-panel-item-meta')
    expect(metaElements).toHaveLength(3)
    expect(metaElements[0].textContent).toContain('Study Guide')
    expect(metaElements[1].textContent).toContain('Quiz')
    expect(metaElements[2].textContent).toContain('Flashcards')
  })
})
