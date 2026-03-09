import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import UploadMaterialWizard from '../components/UploadMaterialWizard'
import UploadWizardStep2 from '../components/UploadWizardStep2'
import type { StudyMaterialType } from '../components/UploadMaterialWizard'

vi.mock('../components/UploadMaterialWizard.css', () => ({}))

vi.mock('../api/courses', () => ({
  coursesApi: {
    list: vi.fn().mockResolvedValue([]),
    create: vi.fn().mockResolvedValue({ id: 1, name: 'Test Course' }),
  },
}))

// Mock URL.createObjectURL / revokeObjectURL for pasted image thumbnails
beforeEach(() => {
  global.URL.createObjectURL = vi.fn(() => 'blob:mock')
  global.URL.revokeObjectURL = vi.fn()
})

const defaultProps = {
  open: true,
  onClose: vi.fn(),
  onGenerate: vi.fn(),
  isGenerating: false,
}

describe('UploadMaterialWizard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('returns null when open=false', () => {
    const { container } = render(
      <UploadMaterialWizard {...defaultProps} open={false} />,
    )
    expect(container.innerHTML).toBe('')
  })

  it('renders modal with "Upload Class Material" title when open=true', () => {
    render(<UploadMaterialWizard {...defaultProps} />)
    expect(screen.getByText('Upload Class Material')).toBeInTheDocument()
  })

  it('shows "Step 1 of 2" indicator on initial render', () => {
    render(<UploadMaterialWizard {...defaultProps} />)
    expect(screen.getByText('Step 1 of 2')).toBeInTheDocument()
  })

  it('shows file drop zone on Step 1', () => {
    render(<UploadMaterialWizard {...defaultProps} />)
    expect(screen.getByText(/drag & drop files here/i)).toBeInTheDocument()
  })

  it('"Next" button is disabled when no content provided', () => {
    render(<UploadMaterialWizard {...defaultProps} />)
    const nextBtn = screen.getByText(/Next/i)
    expect(nextBtn).toBeDisabled()
  })

  it('"Next" button advances to Step 2 when content exists', async () => {
    render(<UploadMaterialWizard {...defaultProps} />)

    // Type text into the textarea to provide content
    const textarea = screen.getByPlaceholderText(/paste text/i)
    await userEvent.type(textarea, 'Some study content')

    const nextBtn = screen.getByText(/Next/i)
    expect(nextBtn).not.toBeDisabled()
    await userEvent.click(nextBtn)

    expect(screen.getByText('Step 2 of 2')).toBeInTheDocument()
  })

  it('"Back" button on Step 2 returns to Step 1', async () => {
    render(<UploadMaterialWizard {...defaultProps} />)

    // Go to step 2
    const textarea = screen.getByPlaceholderText(/paste text/i)
    await userEvent.type(textarea, 'content')
    await userEvent.click(screen.getByText(/Next/i))
    expect(screen.getByText('Step 2 of 2')).toBeInTheDocument()

    // Click back arrow
    const backBtn = screen.getByText('\u2190')
    await userEvent.click(backBtn)

    expect(screen.getByText('Step 1 of 2')).toBeInTheDocument()
  })

  it('"Just Upload" calls onGenerate with empty types array', async () => {
    const onGenerate = vi.fn()
    render(<UploadMaterialWizard {...defaultProps} onGenerate={onGenerate} />)

    const textarea = screen.getByPlaceholderText(/paste text/i)
    await userEvent.type(textarea, 'some content')

    await userEvent.click(screen.getByText('Just Upload'))
    expect(onGenerate).toHaveBeenCalledOnce()
    expect(onGenerate.mock.calls[0][0].types).toEqual([])
  })

  it('"Skip" on Step 2 calls onGenerate with empty types array', async () => {
    const onGenerate = vi.fn()
    render(<UploadMaterialWizard {...defaultProps} onGenerate={onGenerate} />)

    // Go to step 2
    const textarea = screen.getByPlaceholderText(/paste text/i)
    await userEvent.type(textarea, 'content')
    await userEvent.click(screen.getByText(/Next/i))

    // Click Skip
    await userEvent.click(screen.getByText('Skip'))
    expect(onGenerate).toHaveBeenCalledOnce()
    expect(onGenerate.mock.calls[0][0].types).toEqual([])
  })

  it('shows parent note when showParentNote=true', () => {
    render(<UploadMaterialWizard {...defaultProps} showParentNote={true} />)
    expect(
      screen.getByText('Your parent will be notified about this upload.'),
    ).toBeInTheDocument()
  })

  it('shows duplicate check warning when duplicateCheck.exists=true', () => {
    render(
      <UploadMaterialWizard
        {...defaultProps}
        duplicateCheck={{ exists: true, message: 'Material already exists' }}
        onViewExisting={vi.fn()}
        onRegenerate={vi.fn()}
        onDismissDuplicate={vi.fn()}
      />,
    )
    expect(screen.getByText('Material already exists')).toBeInTheDocument()
    expect(screen.getByText('View Existing')).toBeInTheDocument()
    expect(screen.getByText('Regenerate')).toBeInTheDocument()
  })
})

describe('UploadWizardStep2', () => {
  const step2Defaults = {
    selectedFiles: [new File(['content'], 'test.pdf', { type: 'application/pdf' })],
    studyContent: '',
    pastedImages: [] as File[],
    selectedTypes: new Set<StudyMaterialType>(),
    onToggleType: vi.fn(),
    studyTitle: 'Test Title',
    onStudyTitleChange: vi.fn(),
    focusPrompt: '',
    onFocusPromptChange: vi.fn(),
    isGenerating: false,
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders 3 tool cards (Study Guide, Practice Quiz, Flashcards)', () => {
    render(<UploadWizardStep2 {...step2Defaults} />)
    expect(screen.getByText('Study Guide')).toBeInTheDocument()
    expect(screen.getByText('Practice Quiz')).toBeInTheDocument()
    expect(screen.getByText('Flashcards')).toBeInTheDocument()
  })

  it('clicking a card calls onToggleType with correct type', async () => {
    const onToggleType = vi.fn()
    render(<UploadWizardStep2 {...step2Defaults} onToggleType={onToggleType} />)

    await userEvent.click(screen.getByText('Study Guide'))
    expect(onToggleType).toHaveBeenCalledWith('study_guide')

    await userEvent.click(screen.getByText('Practice Quiz'))
    expect(onToggleType).toHaveBeenCalledWith('quiz')

    await userEvent.click(screen.getByText('Flashcards'))
    expect(onToggleType).toHaveBeenCalledWith('flashcards')
  })

  it('shows summary bar with file info', () => {
    render(<UploadWizardStep2 {...step2Defaults} />)
    expect(screen.getByText('test.pdf ready')).toBeInTheDocument()
  })

  it('focus prompt visible only when types selected', () => {
    const { rerender } = render(<UploadWizardStep2 {...step2Defaults} />)
    expect(screen.queryByLabelText(/focus on/i)).not.toBeInTheDocument()

    rerender(
      <UploadWizardStep2
        {...step2Defaults}
        selectedTypes={new Set<StudyMaterialType>(['study_guide'])}
      />,
    )
    expect(screen.getByLabelText(/focus on/i)).toBeInTheDocument()
  })
})
