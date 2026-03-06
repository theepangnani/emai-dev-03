import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useParentStudyTools } from './useParentStudyTools'

// ── Mocks ──────────────────────────────────────────────────────
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

vi.mock('../../../api/client', () => ({
  studyApi: {
    extractTextFromFile: vi.fn(),
    checkDuplicate: vi.fn().mockResolvedValue({ exists: false }),
    generateGuide: vi.fn().mockResolvedValue({ id: 1 }),
    generateQuiz: vi.fn().mockResolvedValue({ id: 2 }),
    generateFlashcards: vi.fn().mockResolvedValue({ id: 3 }),
    generateFromFile: vi.fn().mockResolvedValue({ id: 4 }),
    generateFromTextAndImages: vi.fn().mockResolvedValue({ id: 5 }),
  },
}))

const mockNavigate = vi.fn()

function createImageFile(name = 'image.png'): File {
  return new File(['fake-image-data'], name, { type: 'image/png' })
}

describe('useParentStudyTools – pasted images upload', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetDefault.mockResolvedValue({ id: 100 })
    mockCreate.mockResolvedValue({ id: 1 })
    mockUploadFile.mockResolvedValue({ id: 2 })
    mockUploadMultiFiles.mockResolvedValue({ id: 3 })
  })

  it('uploads single pasted image via uploadFile when no AI types selected', async () => {
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

    // Should navigate to course-materials
    expect(mockNavigate).toHaveBeenCalledWith('/course-materials', expect.any(Object))

    // Wait for background async to complete
    await vi.waitFor(() => {
      expect(mockUploadFile).toHaveBeenCalledWith(
        expect.any(File),
        100,
        'Test',
        'notes',
      )
    })

    // Should NOT create empty text-only content
    expect(mockCreate).not.toHaveBeenCalled()
  })

  it('uploads multiple pasted images via uploadMultiFiles when no AI types selected', async () => {
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
