import { useState } from 'react';
import { studyApi } from '../../../api/client';
import { courseContentsApi, coursesApi } from '../../../api/courses';
import { queueStudyGeneration } from '../../../pages/StudyGuidesPage';
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

  const resetStudyModal = () => {
    setShowStudyModal(false);
    setDuplicateCheck(null);
    setStudyModalInitialTitle('');
    setStudyModalInitialContent('');
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
        queueStudyGeneration({
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
      navigate('/course-materials', { state: { selectedChild: selectedChildUserId } });
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
      queueStudyGeneration({
        title: assignment.title,
        content: assignment.description,
        type: 'study_guide',
        mode: 'text',
      });
      navigate('/course-materials', { state: { selectedChild: selectedChildUserId } });
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
  };
}
