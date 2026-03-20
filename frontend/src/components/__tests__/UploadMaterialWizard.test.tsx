import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import UploadMaterialWizard from '../UploadMaterialWizard'

// Mock coursesApi used by the wizard on open
vi.mock('../../api/courses', () => ({
  coursesApi: {
    list: vi.fn().mockResolvedValue([]),
    create: vi.fn(),
    getDefault: vi.fn().mockResolvedValue({ id: 1 }),
  },
}))

vi.mock('../../api/study', () => ({
  classifyDocument: vi.fn().mockResolvedValue({ document_type: 'custom', confidence: 0 }),
}))

const defaultProps = {
  open: true,
  onClose: vi.fn(),
  onGenerate: vi.fn(),
  isGenerating: false,
}

function makeFile(name: string, sizeMB: number = 1): File {
  const bytes = sizeMB * 1024 * 1024
  return new File([new Uint8Array(bytes)], name, { type: 'application/pdf' })
}

describe('UploadMaterialWizard — Step 1 (default)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders file drop zone and text area', () => {
    render(<UploadMaterialWizard {...defaultProps} />)

    expect(screen.getByText(/drag.*drop files here/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/paste text, notes/i)).toBeInTheDocument()
  })

  it('file selection via input updates file list', async () => {
    render(<UploadMaterialWizard {...defaultProps} />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    expect(input).toBeTruthy()

    const file = makeFile('test-doc.pdf', 1)
    await userEvent.upload(input, file)

    expect(screen.getByText('test-doc.pdf')).toBeInTheDocument()
  })

  it('oversized files (>20 MB) show error message', async () => {
    render(<UploadMaterialWizard {...defaultProps} />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const bigFile = makeFile('huge.pdf', 25)
    await userEvent.upload(input, bigFile)

    expect(screen.getByText(/exceed.*20 MB/i)).toBeInTheDocument()
  })

  it('max file limit (10) enforced', async () => {
    render(<UploadMaterialWizard {...defaultProps} />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const files = Array.from({ length: 11 }, (_, i) => makeFile(`file${i + 1}.pdf`, 1))
    await userEvent.upload(input, files)

    await waitFor(() => {
      expect(screen.getByText(/maximum 10 files/i)).toBeInTheDocument()
    })
  })

  it('class selector shown only when courses prop provided', async () => {
    const courses = [{ id: 1, name: 'Math 101' }]

    const { unmount } = render(<UploadMaterialWizard {...defaultProps} courses={courses} />)

    await waitFor(() => {
      expect(screen.getByLabelText(/class/i)).toBeInTheDocument()
    })

    unmount()

    render(<UploadMaterialWizard {...defaultProps} courses={undefined} />)
    // coursesApi.list returns [] so no selector should appear
    await waitFor(() => {
      expect(screen.queryByLabelText(/class/i)).not.toBeInTheDocument()
    })
  })
})

describe('UploadMaterialWizard — Step 2', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  async function goToStep2() {
    const user = userEvent.setup()
    render(<UploadMaterialWizard {...defaultProps} />)

    // Add a file so Next is enabled
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file = makeFile('chapter5.pdf', 1)
    await user.upload(input, file)

    const nextBtn = screen.getByRole('button', { name: /next/i })
    await user.click(nextBtn)
    return user
  }

  it('renders 3 tool cards (Study Guide, Quiz, Flashcards)', async () => {
    await goToStep2()

    expect(screen.getByText('Study Guide')).toBeInTheDocument()
    expect(screen.getByText('Practice Quiz')).toBeInTheDocument()
    expect(screen.getByText('Flashcards')).toBeInTheDocument()
  })

  it('card toggle on click (selected/deselected)', async () => {
    const user = await goToStep2()

    const studyGuideCard = screen.getByRole('button', { name: /study guide/i })
    expect(studyGuideCard).not.toHaveClass('selected')

    await user.click(studyGuideCard)
    expect(studyGuideCard).toHaveClass('selected')

    await user.click(studyGuideCard)
    expect(studyGuideCard).not.toHaveClass('selected')
  })

  it('title auto-filled from filename', async () => {
    await goToStep2()

    const titleInput = screen.getByRole('textbox', { name: /title/i })
    expect(titleInput).toHaveValue('chapter5')
  })

  it('focus prompt field visible when a tool is selected', async () => {
    const user = await goToStep2()

    expect(screen.queryByLabelText(/focus on/i)).not.toBeInTheDocument()

    const studyGuideCard = screen.getByRole('button', { name: /study guide/i })
    await user.click(studyGuideCard)

    expect(screen.getByLabelText(/focus on/i)).toBeInTheDocument()
  })
})

describe('UploadMaterialWizard — shell behaviour', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('step 1 shown by default', () => {
    render(<UploadMaterialWizard {...defaultProps} />)
    expect(screen.getByText(/step 1 of 2/i)).toBeInTheDocument()
  })

  it('"Next" button advances to step 2', async () => {
    const user = userEvent.setup()
    render(<UploadMaterialWizard {...defaultProps} />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    await user.upload(input, makeFile('notes.pdf', 1))

    await user.click(screen.getByRole('button', { name: /next/i }))

    expect(screen.getByText(/step 2 of 2/i)).toBeInTheDocument()
  })

  it('"Back" arrow returns to step 1', async () => {
    const user = userEvent.setup()
    render(<UploadMaterialWizard {...defaultProps} />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    await user.upload(input, makeFile('notes.pdf', 1))

    await user.click(screen.getByRole('button', { name: /next/i }))
    expect(screen.getByText(/step 2 of 2/i)).toBeInTheDocument()

    // Back button (← arrow)
    await user.click(screen.getByRole('button', { name: /←/i }))
    expect(screen.getByText(/step 1 of 2/i)).toBeInTheDocument()
  })

  it('"Just Upload" calls onGenerate with empty types array', async () => {
    const onGenerate = vi.fn()
    const user = userEvent.setup()
    render(<UploadMaterialWizard {...defaultProps} onGenerate={onGenerate} />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    await user.upload(input, makeFile('doc.pdf', 1))

    await user.click(screen.getByRole('button', { name: /just upload/i }))

    expect(onGenerate).toHaveBeenCalledOnce()
    expect(onGenerate.mock.calls[0][0].types).toEqual([])
  })

  it('"Upload & Create" calls onGenerate with selected types', async () => {
    const onGenerate = vi.fn()
    const user = userEvent.setup()
    render(<UploadMaterialWizard {...defaultProps} onGenerate={onGenerate} />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    await user.upload(input, makeFile('doc.pdf', 1))

    await user.click(screen.getByRole('button', { name: /next/i }))

    await user.click(screen.getByRole('button', { name: /study guide/i }))
    await user.click(screen.getByRole('button', { name: /upload & create/i }))

    expect(onGenerate).toHaveBeenCalledOnce()
    expect(onGenerate.mock.calls[0][0].types).toContain('study_guide')
  })

  it('"Skip" on step 2 calls onGenerate with empty types', async () => {
    const onGenerate = vi.fn()
    const user = userEvent.setup()
    render(<UploadMaterialWizard {...defaultProps} onGenerate={onGenerate} />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    await user.upload(input, makeFile('doc.pdf', 1))

    await user.click(screen.getByRole('button', { name: /next/i }))
    await user.click(screen.getByRole('button', { name: /skip/i }))

    expect(onGenerate).toHaveBeenCalledOnce()
    expect(onGenerate.mock.calls[0][0].types).toEqual([])
  })

  it('showParentNote=true shows parent note text', () => {
    render(<UploadMaterialWizard {...defaultProps} showParentNote={true} />)
    expect(screen.getByText(/your parent will be notified/i)).toBeInTheDocument()
  })

  it('disabled state during isGenerating', () => {
    render(<UploadMaterialWizard {...defaultProps} isGenerating={true} />)

    const cancelBtn = screen.getByRole('button', { name: /cancel/i })
    expect(cancelBtn).toBeDisabled()

    // Just Upload should also be disabled (no content)
    const justUploadBtn = screen.getByRole('button', { name: /just upload/i })
    expect(justUploadBtn).toBeDisabled()
  })
})
