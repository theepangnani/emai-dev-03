import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import UploadMaterialWizard from '../UploadMaterialWizard'

// Mock CreateClassModal — it calls useAuth() which requires AuthProvider
vi.mock('../CreateClassModal', () => ({
  default: () => null,
}))

// Mock coursesApi used by the wizard on open
vi.mock('../../api/courses', () => ({
  coursesApi: {
    list: vi.fn().mockResolvedValue([{ id: 1, name: 'Math 101' }]),
    create: vi.fn(),
    getDefault: vi.fn().mockResolvedValue({ id: 1 }),
  },
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

describe('UploadMaterialWizard — Step 1 (file/text selection)', () => {
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

  it('oversized files (>30 MB) show error message', async () => {
    render(<UploadMaterialWizard {...defaultProps} />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const bigFile = makeFile('huge.pdf', 35)
    await userEvent.upload(input, bigFile)

    expect(screen.getByText(/exceed.*30 MB/i)).toBeInTheDocument()
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

  it('no class selector on step 1 (moved to step 2)', () => {
    const courses = [{ id: 1, name: 'Math 101' }]
    render(<UploadMaterialWizard {...defaultProps} courses={courses} />)

    // Class selector should not be on step 1
    expect(screen.queryByLabelText(/^class$/i)).not.toBeInTheDocument()
  })
})

describe('UploadMaterialWizard — Step 2 (student + class selection)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  async function goToStep2(extraProps = {}) {
    const user = userEvent.setup()
    render(<UploadMaterialWizard {...defaultProps} {...extraProps} />)

    // Add a file so Next is enabled
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file = makeFile('chapter5.pdf', 1)
    await user.upload(input, file)

    const nextBtn = screen.getByRole('button', { name: /next/i })
    await user.click(nextBtn)
    return user
  }

  it('shows class selector and title on step 2', async () => {
    await goToStep2({ courses: [{ id: 1, name: 'Math 101' }] })

    await waitFor(() => {
      expect(screen.getByLabelText(/class/i)).toBeInTheDocument()
    })
    expect(screen.getByLabelText(/title/i)).toBeInTheDocument()
  })

  it('title auto-filled from filename', async () => {
    await goToStep2({ courses: [{ id: 1, name: 'Math 101' }] })

    const titleInput = screen.getByLabelText(/title/i)
    expect(titleInput).toHaveValue('chapter5')
  })

  it('shows child selector when multiple children provided', async () => {
    const children = [
      { id: 1, name: 'Alice' },
      { id: 2, name: 'Bob' },
    ]
    await goToStep2({ children, onChildChange: vi.fn() })

    expect(screen.getByLabelText(/student/i)).toBeInTheDocument()
  })

  it('Upload button calls onGenerate with empty types', async () => {
    const onGenerate = vi.fn()
    const user = await goToStep2({
      onGenerate,
      courses: [{ id: 1, name: 'Math 101' }],
    })

    // Select a course
    const courseSelect = screen.getByLabelText(/class/i)
    await user.selectOptions(courseSelect, '1')

    const uploadBtn = screen.getByRole('button', { name: /^upload$/i })
    await user.click(uploadBtn)

    expect(onGenerate).toHaveBeenCalledOnce()
    expect(onGenerate.mock.calls[0][0].types).toEqual([])
    expect(onGenerate.mock.calls[0][0].courseId).toBe(1)
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

  it('"Back" button on step 2 returns to step 1', async () => {
    const user = userEvent.setup()
    render(<UploadMaterialWizard {...defaultProps} />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    await user.upload(input, makeFile('notes.pdf', 1))

    await user.click(screen.getByRole('button', { name: /next/i }))
    expect(screen.getByText(/step 2 of 2/i)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /back/i }))
    expect(screen.getByText(/step 1 of 2/i)).toBeInTheDocument()
  })

  it('showParentNote=true shows parent note text', () => {
    render(<UploadMaterialWizard {...defaultProps} showParentNote={true} />)
    expect(screen.getByText(/your parent will be notified/i)).toBeInTheDocument()
  })
})
