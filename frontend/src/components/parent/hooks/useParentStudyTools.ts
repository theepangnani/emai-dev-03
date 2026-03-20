import { useState } from 'react';
import { studyApi } from '../../../api/client';
import { courseContentsApi, coursesApi } from '../../../api/courses';
import { useAIUsage } from '../../../hooks/useAIUsage';
import type { DuplicateCheckResponse } from '../../../api/client';
import type { StudyMaterialGenerateParams } from '../../UploadMaterialWizard';
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

  // AI credits
  const { atLimit, remaining, invalidate: refreshAIUsage } = useAIUsage();
  const [showLimitModal, setShowLimitModal] = useState(false);

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
    courseId?: number;
    courseContentId?: number;
    documentType?: string;
    studyGoal?: string;
    studyGoalText?: string;
  }) => {
    const typeLabel = params.type === 'study_guide' ? 'Study Guide' : params.type === 'quiz' ? 'Quiz' : 'Flashcards';
    setBackgroundGeneration({ status: 'generating', type: typeLabel });

    (async () => {
      try {
        // Multi-file: upload via upload-multi to create SourceFile records + hierarchy
        let content = params.content;
        if (params.files && params.files.length > 1) {
          const targetCourseId = await resolveTargetCourseId(params.courseId);
          const cc = await courseContentsApi.uploadMultiFiles(
            params.files,
            targetCourseId,
            params.title || undefined,
            'notes',
          );
          params.courseContentId = cc.id;
          content = cc.text_content || '';
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
            course_id: params.courseId,
            course_content_id: params.courseContentId,
            document_type: params.documentType,
            study_goal: params.studyGoal,
            study_goal_text: params.studyGoalText,
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
            course_id: params.courseId,
            course_content_id: params.courseContentId,
            document_type: params.documentType,
            study_goal: params.studyGoal,
            study_goal_text: params.studyGoalText,
          });
        } else if (params.type === 'study_guide') {
          result = await studyApi.generateGuide({
            title: params.title || undefined,
            content: content || undefined,
            regenerate_from_id: params.regenerateId,
            focus_prompt: params.focusPrompt,
            course_id: params.courseId,
            course_content_id: params.courseContentId,
            document_type: params.documentType,
            study_goal: params.studyGoal,
            study_goal_text: params.studyGoalText,
          });
        } else if (params.type === 'quiz') {
          result = await studyApi.generateQuiz({
            topic: params.title || undefined,
            content: content || undefined,
            num_questions: 10,
            regenerate_from_id: params.regenerateId,
            focus_prompt: params.focusPrompt,
            course_id: params.courseId,
            course_content_id: params.courseContentId,
          });
        } else if (params.type === 'flashcards') {
          result = await studyApi.generateFlashcards({
            topic: params.title || undefined,
            content: content || undefined,
            num_cards: 15,
            regenerate_from_id: params.regenerateId,
            focus_prompt: params.focusPrompt,
            course_id: params.courseId,
            course_content_id: params.courseContentId,
          });
        }

        const resultId = result?.course_content_id ?? undefined;
        setBackgroundGeneration({ status: 'success', type: typeLabel, resultId });
        refreshAIUsage();
      } catch (err: any) {
        const raw = err?.response?.data?.detail || err?.message || 'Generation failed';
        const detail = typeof raw === 'string' && raw.length > 150 ? raw.slice(0, 147) + '...' : raw;
        setBackgroundGeneration({ status: 'error', type: typeLabel, error: detail });
      }
    })();
  };

  const resolveTargetCourseId = async (overrideCourseId?: number): Promise<number> => {
    if (overrideCourseId) return overrideCourseId;
    const defaultCourse = await coursesApi.getDefault();
    return defaultCourse.id;
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
      setBackgroundGeneration({ status: 'generating', type: 'Material' });
      (async () => {
        try {
          const targetCourseId = await resolveTargetCourseId(modalParams.courseId);
          if (files.length === 1) {
            await courseContentsApi.uploadFile(
              files[0],
              targetCourseId,
              modalParams.title || undefined,
              'notes',
            );
          } else if (isMultiFile) {
            await courseContentsApi.uploadMultiFiles(
              files,
              targetCourseId,
              modalParams.title || undefined,
              'notes',
            );
          } else if (modalParams.pastedImages && modalParams.pastedImages.length > 0) {
            // Pasted images: upload as files so backend can store and extract text
            const imagesToUpload = modalParams.pastedImages;
            if (imagesToUpload.length === 1 && !modalParams.content?.trim()) {
              await courseContentsApi.uploadFile(
                imagesToUpload[0],
                targetCourseId,
                modalParams.title || undefined,
                'notes',
              );
            } else {
              // Multiple images or images + text: upload all as multi-file
              const allFiles = [...imagesToUpload];
              // If there's text content, include it as a text file so it's preserved
              if (modalParams.content?.trim()) {
                const textBlob = new Blob([modalParams.content], { type: 'text/plain' });
                const textFile = new File([textBlob], 'pasted-content.txt', { type: 'text/plain' });
                allFiles.unshift(textFile);
              }
              await courseContentsApi.uploadMultiFiles(
                allFiles,
                targetCourseId,
                modalParams.title || undefined,
                'notes',
              );
            }
          } else {
            await courseContentsApi.create({
              course_id: targetCourseId,
              title: modalParams.title || 'Uploaded material',
              text_content: modalParams.content || undefined,
              content_type: 'notes',
            });
          }
          setBackgroundGeneration({ status: 'success', type: 'Material' });
        } catch {
          setBackgroundGeneration({ status: 'error', type: 'Material', error: 'Upload failed' });
        }
      })();
      return;
    }

    // Pre-flight: block AI generation if credits exhausted
    if (atLimit) {
      setShowLimitModal(true);
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
        const targetCourseId = await resolveTargetCourseId(modalParams.courseId);
        if (isMultiFile) {
          const cc = await courseContentsApi.uploadMultiFiles(
            files,
            targetCourseId,
            modalParams.title || undefined,
            'notes',
          );
          sharedCourseContentId = cc.id;
        } else if (modalParams.mode === 'file' && files.length === 1) {
          const cc = await courseContentsApi.uploadFile(
            files[0],
            targetCourseId,
            modalParams.title || undefined,
            'notes',
          );
          sharedCourseContentId = cc.id;
        } else if (modalParams.pastedImages && modalParams.pastedImages.length > 0) {
          // Pasted images: upload as files for shared content
          const allFiles = [...modalParams.pastedImages];
          if (modalParams.content?.trim()) {
            const textBlob = new Blob([modalParams.content], { type: 'text/plain' });
            const textFile = new File([textBlob], 'pasted-content.txt', { type: 'text/plain' });
            allFiles.unshift(textFile);
          }
          if (allFiles.length === 1) {
            const cc = await courseContentsApi.uploadFile(
              allFiles[0],
              targetCourseId,
              modalParams.title || undefined,
              'notes',
            );
            sharedCourseContentId = cc.id;
          } else {
            const cc = await courseContentsApi.uploadMultiFiles(
              allFiles,
              targetCourseId,
              modalParams.title || undefined,
              'notes',
            );
            sharedCourseContentId = cc.id;
          }
        } else {
          const cc = await courseContentsApi.create({
            course_id: targetCourseId,
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
        courseId: modalParams.courseId,
        courseContentId: sharedCourseContentId,
        documentType: modalParams.documentType,
        studyGoal: modalParams.studyGoal,
        studyGoalText: modalParams.studyGoalText,
      });
    }
  };

  const handleOneClickStudy = async (assignment: CalendarAssignment) => {
    if (generatingStudyId) return;
    if (atLimit) {
      setShowLimitModal(true);
      return;
    }
    setGeneratingStudyId(assignment.id);
    try {
      const dupResult = await studyApi.checkDuplicate({
        title: assignment.title,
        guide_type: 'study_guide',
      });
      if (dupResult.exists && dupResult.existing_guide) {
        const guide = dupResult.existing_guide;
        let path: string;
        if (guide.course_content_id) {
          const tabMap: Record<string, string> = { quiz: 'quiz', flashcards: 'flashcards', study_guide: 'guide', mind_map: 'mindmap' };
          path = `/course-materials/${guide.course_content_id}?tab=${tabMap[guide.guide_type] || 'guide'}`;
        } else if (guide.guide_type === 'quiz') path = `/study/quiz/${guide.id}`;
        else if (guide.guide_type === 'flashcards') path = `/study/flashcards/${guide.id}`;
        else path = `/study/guide/${guide.id}`;
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
    // AI credits
    showLimitModal, setShowLimitModal, atLimit, remaining,
  };
}
