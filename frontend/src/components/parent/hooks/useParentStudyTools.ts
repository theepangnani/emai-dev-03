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
  const [isGenerating, setIsGenerating] = useState(false);
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

  const runGenerationInBackground = (params: {
    title: string;
    content: string;
    type: 'study_guide' | 'quiz' | 'flashcards';
    focusPrompt?: string;
    mode: string;
    file?: File;
    pastedImages?: File[];
    regenerateId?: number;
  }) => {
    const typeLabel = params.type === 'study_guide' ? 'Study Guide' : params.type === 'quiz' ? 'Quiz' : 'Flashcards';
    setBackgroundGeneration({ status: 'generating', type: typeLabel });

    (async () => {
      try {
        let result: any;
        if (params.mode === 'file' && params.file) {
          result = await studyApi.generateFromFile({
            file: params.file,
            title: params.title || undefined,
            guide_type: params.type,
            num_questions: params.type === 'quiz' ? 10 : undefined,
            num_cards: params.type === 'flashcards' ? 15 : undefined,
            focus_prompt: params.focusPrompt,
          });
        } else if (params.pastedImages && params.pastedImages.length > 0) {
          result = await studyApi.generateFromTextAndImages({
            content: params.content || '',
            images: params.pastedImages,
            title: params.title || undefined,
            guide_type: params.type,
            num_questions: params.type === 'quiz' ? 10 : undefined,
            num_cards: params.type === 'flashcards' ? 15 : undefined,
            focus_prompt: params.focusPrompt,
          });
        } else if (params.type === 'study_guide') {
          result = await studyApi.generateGuide({
            title: params.title || undefined,
            content: params.content || undefined,
            regenerate_from_id: params.regenerateId,
            focus_prompt: params.focusPrompt,
          });
        } else if (params.type === 'quiz') {
          result = await studyApi.generateQuiz({
            topic: params.title || undefined,
            content: params.content || undefined,
            num_questions: 10,
            regenerate_from_id: params.regenerateId,
            focus_prompt: params.focusPrompt,
          });
        } else if (params.type === 'flashcards') {
          result = await studyApi.generateFlashcards({
            topic: params.title || undefined,
            content: params.content || undefined,
            num_cards: 15,
            regenerate_from_id: params.regenerateId,
            focus_prompt: params.focusPrompt,
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
    setIsGenerating(true);
    try {
      if (modalParams.types.length === 0) {
        try {
          const defaultCourse = await coursesApi.getDefault();
          if (modalParams.mode === 'file' && modalParams.file) {
            await courseContentsApi.uploadFile(
              modalParams.file,
              defaultCourse.id,
              modalParams.title || undefined,
              'notes',
            );
          } else {
            await courseContentsApi.create({
              course_id: defaultCourse.id,
              title: modalParams.title || 'Uploaded material',
              text_content: modalParams.content || undefined,
              content_type: 'notes',
            });
          }
        } catch { /* continue */ }
        setDuplicateCheck(null);
        resetStudyModal();
        navigate('/course-materials', { state: { selectedChild: selectedChildUserId } });
        return;
      }

      if (modalParams.types.length === 1 && modalParams.mode === 'text' && !modalParams.pastedImages?.length) {
        try {
          const dupResult = await studyApi.checkDuplicate({ title: modalParams.title || undefined, guide_type: modalParams.types[0] });
          if (dupResult.exists) { setDuplicateCheck(dupResult); return; }
        } catch { /* Continue */ }
      }

      for (const type of modalParams.types) {
        runGenerationInBackground({
          title: modalParams.title,
          content: modalParams.content,
          type,
          focusPrompt: modalParams.focusPrompt,
          mode: modalParams.mode,
          file: modalParams.file,
          pastedImages: modalParams.pastedImages,
          regenerateId: duplicateCheck?.existing_guide?.id,
        });
      }
      setDuplicateCheck(null);
      resetStudyModal();
      // Don't navigate — user stays on dashboard
    } finally {
      setIsGenerating(false);
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
