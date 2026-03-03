import { useState } from 'react';
import { studyApi } from '../../../api/client';
import { courseContentsApi, coursesApi } from '../../../api/courses';
import type { DuplicateCheckResponse } from '../../../api/client';
import type { StudyMaterialGenerateParams } from '../../CreateStudyMaterialModal';
import type { CalendarAssignment } from '../../calendar/types';

interface UseParentStudyToolsParams {
  selectedChildUserId: number | null;
  navigate: (path: string, options?: { state?: Record<string, unknown> }) => void;
}

export function useParentStudyTools({
  selectedChildUserId,
  navigate,
}: UseParentStudyToolsParams) {
  // Study tools modal state
  const [showStudyModal, setShowStudyModal] = useState(false);
  const [isGenerating] = useState(false);
  const [duplicateCheck, setDuplicateCheck] = useState<DuplicateCheckResponse | null>(null);
  const [studyModalInitialTitle, setStudyModalInitialTitle] = useState('');
  const [studyModalInitialContent, setStudyModalInitialContent] = useState('');

  // One-click study generation state
  const [generatingStudyId, setGeneratingStudyId] = useState<number | null>(null);

  // Background generation tracking
  const [backgroundGeneration, setBackgroundGeneration] = useState<{
    status: 'generating' | 'success' | 'error';
    type: string;
    resultId?: number;
    error?: string;
  } | null>(null);

  const resetStudyModal = () => {
    setShowStudyModal(false);
    setDuplicateCheck(null);
    setStudyModalInitialTitle('');
    setStudyModalInitialContent('');
  };

  const dismissBackgroundGeneration = () => setBackgroundGeneration(null);

  const extractCombinedText = async (files: File[]): Promise<string> => {
    const parts: string[] = [];
    for (const f of files) {
      try {
        const result = await studyApi.extractTextFromFile(f);
        parts.push(`--- [${f.name}] ---\n${result.text}`);
      } catch (err: any) {
        const status = err?.response?.status;
        const detail = status === 429
          ? 'rate limit exceeded — try again in a moment'
          : 'text extraction failed';
        parts.push(`--- [${f.name}] ---\n(${detail})`);
      }
    }
    return parts.join('\n\n');
  };

  const runGenerationInBackground = (params: {
    title: string;
    content: string;
    type: 'study_guide' | 'quiz' | 'flashcards';
    focusPrompt?: string;
    mode: string;
    file?: File;
    files?: File[];  // multi-file: text extraction happens inside the background task
    pastedImages?: File[];
    regenerateId?: number;
    courseContentId?: number;
  }) => {
    const typeLabel = params.type === 'study_guide' ? 'Study Guide' : params.type === 'quiz' ? 'Quiz' : 'Flashcards';
    setBackgroundGeneration({ status: 'generating', type: typeLabel });

    (async () => {
      try {
        // Multi-file: extract combined text now that we're running in the background
        let content = params.content;
        if (params.files && params.files.length > 1) {
          content = await extractCombinedText(params.files);
        }

        let result: any;
        if (params.mode === 'file' && params.file) {
          result = await studyApi.generateFromFile({
            file: params.file,
            title: params.title || undefined,
            guide_type: params.type,
            num_questions: params.type === 'quiz' ? 10 : undefined,
            num_cards: params.type === 'flashcards' ? 15 : undefined,
            focus_prompt: params.focusPrompt,
            course_content_id: params.courseContentId,
          });
        } else if (params.pastedImages && params.pastedImages.length > 0) {
          result = await studyApi.generateFromTextAndImages({
            content: content || '',
            images: params.pastedImages,
            title: params.title || undefined,
            guide_type: params.type,
            num_questions: params.type === 'quiz' ? 10 : undefined,
            num_cards: params.type === 'flashcards' ? 15 : undefined,
            focus_prompt: params.focusPrompt,
            course_content_id: params.courseContentId,
          });
        } else if (params.type === 'study_guide') {
          result = await studyApi.generateGuide({
            title: params.title || undefined,
            content: content || undefined,
            regenerate_from_id: params.regenerateId,
            focus_prompt: params.focusPrompt,
            course_content_id: params.courseContentId,
          });
        } else if (params.type === 'quiz') {
          result = await studyApi.generateQuiz({
            topic: params.title || undefined,
            content: content || undefined,
            num_questions: 10,
            regenerate_from_id: params.regenerateId,
            focus_prompt: params.focusPrompt,
            course_content_id: params.courseContentId,
          });
        } else if (params.type === 'flashcards') {
          result = await studyApi.generateFlashcards({
            topic: params.title || undefined,
            content: content || undefined,
            num_cards: 15,
            regenerate_from_id: params.regenerateId,
            focus_prompt: params.focusPrompt,
            course_content_id: params.courseContentId,
          });
        }

        const resultId = result?.id || result?.course_content_id;
        setBackgroundGeneration({ status: 'success', type: typeLabel, resultId });
      } catch (err: any) {
        setBackgroundGeneration({ status: 'error', type: typeLabel, error: err?.message || 'Generation failed' });
      }
    })();
  };

  const handleGenerateFromModal = async (modalParams: StudyMaterialGenerateParams) => {
    const files = modalParams.files ?? (modalParams.file ? [modalParams.file] : []);
    const isMultiFile = files.length > 1;

    // Always close modal immediately — never leave it open in a "Generating..." state.
    // Background work (duplicate check, extraction, AI generation) continues after close.
    resetStudyModal();

    if (modalParams.types.length === 0) {
      // Upload-only: navigate then run upload/extraction in background
      navigate('/course-materials', { state: { selectedChild: selectedChildUserId } });
      (async () => {
        try {
          const defaultCourse = await coursesApi.getDefault();
          if (files.length === 1) {
            await courseContentsApi.uploadFile(
              files[0],
              defaultCourse.id,
              modalParams.title || undefined,
              'notes',
            );
          } else if (isMultiFile) {
            const combinedText = await extractCombinedText(files);
            await courseContentsApi.create({
              course_id: defaultCourse.id,
              title: modalParams.title || files.map(f => f.name).join(', '),
              text_content: combinedText,
              content_type: 'notes',
            });
          } else {
            await courseContentsApi.create({
              course_id: defaultCourse.id,
              title: modalParams.title || 'Uploaded material',
              text_content: modalParams.content || undefined,
              content_type: 'notes',
            });
          }
        } catch { /* silently ignore */ }
      })();
      return;
    }

    // Duplicate check runs after modal close — if found, re-open modal with warning
    if (!isMultiFile && modalParams.types.length === 1 && modalParams.mode === 'text' && !modalParams.pastedImages?.length) {
      try {
        const dupResult = await studyApi.checkDuplicate({ title: modalParams.title || undefined, guide_type: modalParams.types[0] });
        if (dupResult.exists) {
          setDuplicateCheck(dupResult);
          setShowStudyModal(true);
          return;
        }
      } catch { /* Continue */ }
    }

    // When multiple AI tools are selected, pre-create a single CourseContent
    // so all parallel generation calls share the same material (#1061)
    let sharedCourseContentId: number | undefined;
    if (modalParams.types.length > 1) {
      try {
        const defaultCourse = await coursesApi.getDefault();
        if (isMultiFile) {
          const combinedText = await extractCombinedText(files);
          const cc = await courseContentsApi.create({
            course_id: defaultCourse.id,
            title: modalParams.title || files.map(f => f.name).join(', '),
            text_content: combinedText,
            content_type: 'notes',
          });
          sharedCourseContentId = cc.id;
        } else if (modalParams.mode === 'file' && files.length === 1) {
          const cc = await courseContentsApi.uploadFile(
            files[0],
            defaultCourse.id,
            modalParams.title || undefined,
            'notes',
          );
          sharedCourseContentId = cc.id;
        } else {
          const cc = await courseContentsApi.create({
            course_id: defaultCourse.id,
            title: modalParams.title || 'Uploaded material',
            text_content: modalParams.content || undefined,
            content_type: 'notes',
          });
          sharedCourseContentId = cc.id;
        }
      } catch {
        // If pre-creation fails, fall through — each generation creates its own
      }
    }

    for (const type of modalParams.types) {
      runGenerationInBackground({
        title: modalParams.title,
        content: modalParams.content,
        type,
        focusPrompt: modalParams.focusPrompt,
        mode: sharedCourseContentId ? 'text' : (isMultiFile ? 'text' : modalParams.mode),
        file: sharedCourseContentId ? undefined : (isMultiFile ? undefined : modalParams.file),
        files: sharedCourseContentId ? undefined : (isMultiFile ? files : undefined),
        pastedImages: sharedCourseContentId ? undefined : modalParams.pastedImages,
        regenerateId: duplicateCheck?.existing_guide?.id,
        courseContentId: sharedCourseContentId,
      });
    }
  };

  const handleOneClickStudy = async (assignment: CalendarAssignment) => {
    if (generatingStudyId) return;
    setGeneratingStudyId(assignment.id);
    try {
      const dupResult = await studyApi.checkDuplicate({
        title: assignment.title,
        guide_type: 'study_guide',
      });
      if (dupResult.exists && dupResult.existing_guide) {
        const guide = dupResult.existing_guide;
        const path = guide.guide_type === 'quiz' ? `/study/quiz/${guide.id}`
          : guide.guide_type === 'flashcards' ? `/study/flashcards/${guide.id}`
          : `/study/guide/${guide.id}`;
        navigate(path);
        return;
      }
      if (!assignment.description?.trim()) {
        setStudyModalInitialTitle(assignment.title);
        setStudyModalInitialContent('');
        setShowStudyModal(true);
        return;
      }
      runGenerationInBackground({
        title: assignment.title,
        content: assignment.description,
        type: 'study_guide',
        mode: 'text',
      });
      // Don't navigate — user stays on dashboard
    } catch {
      setStudyModalInitialTitle(assignment.title);
      setStudyModalInitialContent(assignment.description || '');
      setShowStudyModal(true);
    } finally {
      setGeneratingStudyId(null);
    }
  };

  const handleViewStudyGuides = () => {
    navigate('/course-materials', { state: { selectedChild: selectedChildUserId } });
  };

  return {
    // Study Tools
    showStudyModal, setShowStudyModal, isGenerating,
    studyModalInitialTitle, studyModalInitialContent,
    duplicateCheck, setDuplicateCheck,
    resetStudyModal, handleGenerateFromModal,
    generatingStudyId, handleOneClickStudy, handleViewStudyGuides,
    // Background generation
    backgroundGeneration, dismissBackgroundGeneration,
  };
}
