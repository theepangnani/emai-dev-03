import { screen, waitFor } from '@testing-library/react'
import { renderWithProviders } from '../test/helpers'
import { StudyGuideBreadcrumb } from './StudyGuideBreadcrumb'

const mockGetGuideTree = vi.fn()

vi.mock('../api/client', () => ({
  studyApi: {
    getGuideTree: (...args: unknown[]) => mockGetGuideTree(...args),
  },
}))

describe('StudyGuideBreadcrumb', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('renders breadcrumb segments from tree path', async () => {
    mockGetGuideTree.mockResolvedValue({
      root: {
        id: 1,
        title: 'Math Chapter 5',
        guide_type: 'study_guide',
        created_at: '2026-01-01T00:00:00Z',
        children: [
          {
            id: 2,
            title: 'Quadratic Equations',
            guide_type: 'study_guide',
            created_at: '2026-01-02T00:00:00Z',
            children: [
              {
                id: 3,
                title: 'Practice Quiz',
                guide_type: 'quiz',
                created_at: '2026-01-03T00:00:00Z',
                children: [],
              },
            ],
          },
        ],
      },
      current_path: [1, 2, 3],
    })

    renderWithProviders(<StudyGuideBreadcrumb guideId={3} />)

    await waitFor(() => {
      expect(screen.getByTestId('study-guide-breadcrumb')).toBeInTheDocument()
    })

    // First two items should be links, last should be current (not a link)
    const links = screen.getAllByRole('link')
    const linkTexts = links.map(l => l.textContent)
    expect(linkTexts).toContain('Math Chapter 5')
    expect(linkTexts).toContain('Quadratic Equations')

    // Current page should be plain text, not a link
    expect(screen.getByText('Practice Quiz')).toBeInTheDocument()
    expect(screen.getByText('Practice Quiz').tagName).toBe('SPAN')
  })

  it('does not render when path has only one item (root guide)', async () => {
    mockGetGuideTree.mockResolvedValue({
      root: {
        id: 1,
        title: 'Root Guide',
        guide_type: 'study_guide',
        created_at: '2026-01-01T00:00:00Z',
        children: [],
      },
      current_path: [1],
    })

    const { container } = renderWithProviders(<StudyGuideBreadcrumb guideId={1} />)

    // Wait for the API call to complete
    await waitFor(() => {
      expect(mockGetGuideTree).toHaveBeenCalledWith(1)
    })

    // Should not render breadcrumb nav
    expect(container.querySelector('[data-testid="study-guide-breadcrumb"]')).toBeNull()
  })

  it('does not render when API call fails', async () => {
    mockGetGuideTree.mockRejectedValue(new Error('Network error'))

    const { container } = renderWithProviders(<StudyGuideBreadcrumb guideId={999} />)

    await waitFor(() => {
      expect(mockGetGuideTree).toHaveBeenCalledWith(999)
    })

    expect(container.querySelector('[data-testid="study-guide-breadcrumb"]')).toBeNull()
  })
})
