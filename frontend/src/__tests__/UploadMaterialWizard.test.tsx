import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import UploadMaterialWizard from '../components/UploadMaterialWizard'

vi.mock('../components/UploadMaterialWizard.css', () => ({}))

// Mock CreateClassModal — it calls useAuth() which requires AuthProvider
vi.mock('../components/CreateClassModal', () => ({
  default: () => null,
}))

vi.mock('../api/courses', () => ({
  coursesApi: {
    list: vi.fn().mockResolvedValue([{ id: 1, name: 'Math 101' }]),
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

    // Click back button
    await userEvent.click(screen.getByText(/back/i))

    expect(screen.getByText('Step 1 of 2')).toBeInTheDocument()
  })

  it('Step 2 shows class selector and title', async () => {
    render(<UploadMaterialWizard {...defaultProps} courses={[{ id: 1, name: 'Math 101' }]} />)

    const textarea = screen.getByPlaceholderText(/paste text/i)
    await userEvent.type(textarea, 'content')
    await userEvent.click(screen.getByText(/Next/i))

    expect(screen.getByLabelText(/class/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/title/i)).toBeInTheDocument()
  })

  it('"Upload" button on Step 2 calls onGenerate with empty types', async () => {
    const onGenerate = vi.fn()
    render(
      <UploadMaterialWizard
        {...defaultProps}
        onGenerate={onGenerate}
        courses={[{ id: 1, name: 'Math 101' }]}
      />,
    )

    const textarea = screen.getByPlaceholderText(/paste text/i)
    await userEvent.type(textarea, 'content')
    await userEvent.click(screen.getByText(/Next/i))

    // Select course
    const courseSelect = screen.getByLabelText(/class/i)
    await userEvent.selectOptions(courseSelect, '1')

    await userEvent.click(screen.getByRole('button', { name: /^upload$/i }))
    expect(onGenerate).toHaveBeenCalledOnce()
    expect(onGenerate.mock.calls[0][0].types).toEqual([])
  })

  it('shows parent note when showParentNote=true', () => {
    render(<UploadMaterialWizard {...defaultProps} showParentNote={true} />)
    expect(
      screen.getByText('Your parent will be notified about this upload.'),
    ).toBeInTheDocument()
  })
})
