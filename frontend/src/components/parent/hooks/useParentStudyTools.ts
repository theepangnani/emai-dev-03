import { useState } from 'react';
import { courseContentsApi, coursesApi } from '../../../api/courses';
import type { StudyMaterialGenerateParams } from '../../UploadMaterialWizard';

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
  const [studyModalInitialTitle, setStudyModalInitialTitle] = useState('');
  const [studyModalInitialContent, setStudyModalInitialContent] = useState('');

  // Background upload tracking
  const [backgroundGeneration, setBackgroundGeneration] = useState<{
    status: 'generating' | 'success' | 'error';
    type: string;
    resultId?: number;
    error?: string;
  } | null>(null);

  const resetStudyModal = () => {
    setShowStudyModal(false);
    setStudyModalInitialTitle('');
    setStudyModalInitialContent('');
  };

  const dismissBackgroundGeneration = () => setBackgroundGeneration(null);

  const resolveTargetCourseId = async (overrideCourseId?: number): Promise<number> => {
    if (overrideCourseId) return overrideCourseId;
    const defaultCourse = await coursesApi.getDefault();
    return defaultCourse.id;
  };

  const handleGenerateFromModal = async (modalParams: StudyMaterialGenerateParams) => {
    // Question mode: create CourseContent with question as text, tagged as parent_question (#2861)
    if (modalParams.mode === 'question') {
      resetStudyModal();
      setIsGenerating(true);
      setBackgroundGeneration({ status: 'generating', type: 'Study Guide' });

      try {
        const targetCourseId = await resolveTargetCourseId(modalParams.courseId);
        const created = await courseContentsApi.create({
          course_id: targetCourseId,
          title: modalParams.title || 'Parent Question',
          text_content: modalParams.content || undefined,
          content_type: 'notes',
          document_type: modalParams.documentType,
          study_goal: modalParams.studyGoal,
        });

        setBackgroundGeneration({ status: 'success', type: 'Study Guide', resultId: created.id });
        navigate(`/course-materials/${created.id}`, { state: { selectedChild: selectedChildUserId } });
      } catch {
        setBackgroundGeneration({ status: 'error', type: 'Study Guide', error: 'Generation failed' });
      } finally {
        setIsGenerating(false);
      }
      return;
    }

    const files = modalParams.files ?? (modalParams.file ? [modalParams.file] : []);
    const isMultiFile = files.length > 1;

    // Close modal immediately — upload continues in background
    resetStudyModal();
    setIsGenerating(true);
    setBackgroundGeneration({ status: 'generating', type: 'Material' });

    try {
      const targetCourseId = await resolveTargetCourseId(modalParams.courseId);
      let created: { id: number };

      if (files.length === 1) {
        created = await courseContentsApi.uploadFile(
          files[0],
          targetCourseId,
          modalParams.title || undefined,
          'notes',
        );
      } else if (isMultiFile) {
        created = await courseContentsApi.uploadMultiFiles(
          files,
          targetCourseId,
          modalParams.title || undefined,
          'notes',
        );
      } else if (modalParams.pastedImages && modalParams.pastedImages.length > 0) {
        // Pasted images: upload as files so backend can store and extract text
        const imagesToUpload = modalParams.pastedImages;
        if (imagesToUpload.length === 1 && !modalParams.content?.trim()) {
          created = await courseContentsApi.uploadFile(
            imagesToUpload[0],
            targetCourseId,
            modalParams.title || undefined,
            'notes',
          );
        } else {
          // Multiple images or images + text: upload all as multi-file
          const allFiles = [...imagesToUpload];
          if (modalParams.content?.trim()) {
            const textBlob = new Blob([modalParams.content], { type: 'text/plain' });
            const textFile = new File([textBlob], 'pasted-content.txt', { type: 'text/plain' });
            allFiles.unshift(textFile);
          }
          created = await courseContentsApi.uploadMultiFiles(
            allFiles,
            targetCourseId,
            modalParams.title || undefined,
            'notes',
          );
        }
      } else {
        created = await courseContentsApi.create({
          course_id: targetCourseId,
          title: modalParams.title || 'Uploaded material',
          text_content: modalParams.content || undefined,
          content_type: 'notes',
        });
      }

      setBackgroundGeneration({ status: 'success', type: 'Material', resultId: created.id });
      // Navigate to the detail page — user can generate study guides from there
      navigate(`/course-materials/${created.id}`, { state: { selectedChild: selectedChildUserId } });
    } catch {
      setBackgroundGeneration({ status: 'error', type: 'Material', error: 'Upload failed' });
    } finally {
      setIsGenerating(false);
    }
  };

  const handleViewStudyGuides = () => {
    navigate('/course-materials', { state: { selectedChild: selectedChildUserId } });
  };

  const getBackgroundGenerationRoute = (): string => {
    const bg = backgroundGeneration;
    if (!bg) return '/course-materials';
    if (bg.resultId) return `/course-materials/${bg.resultId}`;
    return '/course-materials';
  };

  return {
    // Study Tools
    showStudyModal, setShowStudyModal, isGenerating,
    studyModalInitialTitle, studyModalInitialContent,
    resetStudyModal, handleGenerateFromModal,
    handleViewStudyGuides,
    // Background generation
    backgroundGeneration, dismissBackgroundGeneration, getBackgroundGenerationRoute,
  };
}
