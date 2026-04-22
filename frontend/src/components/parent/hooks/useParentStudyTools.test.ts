import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useParentStudyTools } from './useParentStudyTools'

// ── Mocks ──────────────────────────────────────────────────────
const mockInvalidateQueries = vi.fn()
vi.mock('@tanstack/react-query', () => ({
  useQueryClient: () => ({ invalidateQueries: mockInvalidateQueries }),
}))

const mockGetDefault = vi.fn()
const mockCreate = vi.fn()
const mockUploadFile = vi.fn()
const mockUploadMultiFiles = vi.fn()

vi.mock('../../../api/courses', () => ({
  coursesApi: {
    getDefault: (...args: unknown[]) => mockGetDefault(...args),
  },
  courseContentsApi: {
    create: (...args: unknown[]) => mockCreate(...args),
    uploadFile: (...args: unknown[]) => mockUploadFile(...args),
    uploadMultiFiles: (...args: unknown[]) => mockUploadMultiFiles(...args),
  },
}))

const mockNavigate = vi.fn()

function createImageFile(name = 'image.png'): File {
  return new File(['fake-image-data'], name, { type: 'image/png' })
}

describe('useParentStudyTools – upload-only flow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetDefault.mockResolvedValue({ id: 100 })
    mockCreate.mockResolvedValue({ id: 1 })
    mockUploadFile.mockResolvedValue({ id: 2 })
    mockUploadMultiFiles.mockResolvedValue({ id: 3 })
  })

  it('always uses upload-only path regardless of types passed', async () => {
    mockCreate.mockResolvedValue({ id: 42 })

    const { result } = renderHook(() =>
      useParentStudyTools({ selectedChildUserId: 1, navigate: mockNavigate }),
    )

    await act(async () => {
      await result.current.handleGenerateFromModal({
        title: 'Test',
        content: 'Content',
        types: ['study_guide'],
        mode: 'text',
      })
    })

    // Should navigate to detail page without autoGenerate
    await vi.waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith(
        '/course-materials/42',
        expect.objectContaining({ state: expect.objectContaining({ selectedChild: 1 }) }),
      )
    })

    // Should create content via text-only path
    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        course_id: 100,
        title: 'Test',
        text_content: 'Content',
      }),
    )
  })

  it('shows upload error in backgroundGeneration on failure', async () => {
    mockCreate.mockRejectedValueOnce(new Error('Upload failed'))

    const { result } = renderHook(() =>
      useParentStudyTools({ selectedChildUserId: 1, navigate: mockNavigate }),
    )

    await act(async () => {
      await result.current.handleGenerateFromModal({
        title: 'Test',
        content: 'Content',
        types: [],
        mode: 'text',
      })
    })

    await vi.waitFor(() => {
      expect(result.current.backgroundGeneration).not.toBeNull()
      expect(result.current.backgroundGeneration!.status).toBe('error')
      expect(result.current.backgroundGeneration!.error).toBe('Upload failed')
    })
  })
})

describe('useParentStudyTools – pasted images upload', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetDefault.mockResolvedValue({ id: 100 })
    mockCreate.mockResolvedValue({ id: 1 })
    mockUploadFile.mockResolvedValue({ id: 2 })
    mockUploadMultiFiles.mockResolvedValue({ id: 3 })
  })

  it('uploads single pasted image via uploadFile', async () => {
    const { result } = renderHook(() =>
      useParentStudyTools({ selectedChildUserId: 1, navigate: mockNavigate }),
    )

    await act(async () => {
      await result.current.handleGenerateFromModal({
        title: 'Test',
        content: '',
        types: [],
        mode: 'text',
        pastedImages: [createImageFile()],
      })
    })

    // Should navigate to the specific course-material detail page
    await vi.waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/course-materials/2', expect.any(Object))
    })

    expect(mockUploadFile).toHaveBeenCalledWith(
      expect.any(File),
      100,
      'Test',
      'notes',
    )

    // Should NOT create empty text-only content
    expect(mockCreate).not.toHaveBeenCalled()
  })

  it('uploads multiple pasted images via uploadMultiFiles', async () => {
    const { result } = renderHook(() =>
      useParentStudyTools({ selectedChildUserId: 1, navigate: mockNavigate }),
    )

    await act(async () => {
      await result.current.handleGenerateFromModal({
        title: 'Multi images',
        content: '',
        types: [],
        mode: 'text',
        pastedImages: [createImageFile('img1.png'), createImageFile('img2.png')],
      })
    })

    await vi.waitFor(() => {
      expect(mockUploadMultiFiles).toHaveBeenCalledWith(
        expect.arrayContaining([expect.any(File), expect.any(File)]),
        100,
        'Multi images',
        'notes',
      )
    })

    expect(mockCreate).not.toHaveBeenCalled()
  })

  it('includes text content as a file when pasting images with text', async () => {
    const { result } = renderHook(() =>
      useParentStudyTools({ selectedChildUserId: 1, navigate: mockNavigate }),
    )

    await act(async () => {
      await result.current.handleGenerateFromModal({
        title: 'With text',
        content: 'Some pasted text',
        types: [],
        mode: 'text',
        pastedImages: [createImageFile()],
      })
    })

    await vi.waitFor(() => {
      // Should use uploadMultiFiles (text file + image)
      expect(mockUploadMultiFiles).toHaveBeenCalledWith(
        expect.arrayContaining([expect.any(File)]),
        100,
        'With text',
        'notes',
      )
      // First file should be the text file
      const files = mockUploadMultiFiles.mock.calls[0][0] as File[]
      expect(files.length).toBe(2)
      expect(files[0].name).toBe('pasted-content.txt')
    })
  })

  it('creates text-only content when no images and no files (no regression)', async () => {
    const { result } = renderHook(() =>
      useParentStudyTools({ selectedChildUserId: 1, navigate: mockNavigate }),
    )

    await act(async () => {
      await result.current.handleGenerateFromModal({
        title: 'Text only',
        content: 'Just text',
        types: [],
        mode: 'text',
      })
    })

    await vi.waitFor(() => {
      expect(mockCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          course_id: 100,
          title: 'Text only',
          text_content: 'Just text',
        }),
      )
    })

    expect(mockUploadFile).not.toHaveBeenCalled()
    expect(mockUploadMultiFiles).not.toHaveBeenCalled()
  })
})

// #3955 — question mode redirects to /ask (ASGFPage) instead of creating a CourseContent.
describe('useParentStudyTools – question mode redirects to /ask', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetDefault.mockResolvedValue({ id: 100 })
    mockCreate.mockResolvedValue({ id: 1 })
  })

  it('navigates to /ask with encoded question when content provided', async () => {
    const { result } = renderHook(() =>
      useParentStudyTools({ selectedChildUserId: 7, navigate: mockNavigate }),
    )

    await act(async () => {
      await result.current.handleGenerateFromModal({
        title: '',
        content: 'How can I help my child with fractions?',
        types: [],
        mode: 'question',
        documentType: 'parent_question',
        studyGoal: 'parent_review',
      })
    })

    expect(mockNavigate).toHaveBeenCalledWith(
      `/ask?question=${encodeURIComponent('How can I help my child with fractions?')}`,
      expect.objectContaining({ state: expect.objectContaining({ selectedChild: 7 }) }),
    )
    // Must not take the legacy CourseContent + autoGenerate path
    expect(mockCreate).not.toHaveBeenCalled()
  })

  it('navigates to bare /ask when question content is empty', async () => {
    const { result } = renderHook(() =>
      useParentStudyTools({ selectedChildUserId: null, navigate: mockNavigate }),
    )

    await act(async () => {
      await result.current.handleGenerateFromModal({
        title: '',
        content: '   ',
        types: [],
        mode: 'question',
      })
    })

    expect(mockNavigate).toHaveBeenCalledWith('/ask', expect.any(Object))
    expect(mockCreate).not.toHaveBeenCalled()
  })
})
