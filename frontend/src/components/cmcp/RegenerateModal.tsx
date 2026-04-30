/**
 * CB-CMCP-001 M3-A 3A-4 (#4584) — One-click regenerate modal.
 *
 * Drives the teacher's "regenerate this artifact with these adjustments"
 * flow on top of 3A-1's ``POST /api/cmcp/review/{id}/regenerate`` endpoint.
 * The modal lets the teacher tweak two parameters before re-running the
 * prompt-build pipeline:
 *
 * - difficulty: APPROACHING / GRADE_LEVEL / EXTENDING
 * - target_persona override: student / parent / teacher
 *
 * The rest of the ``CMCPGenerateRequest`` payload (grade, subject_code,
 * strand_code, content_type, course_id, topic) is supplied by the parent
 * via ``baseRequest`` — the modal does not re-derive it from the artifact
 * because the route accepts a full ``CMCPGenerateRequest`` and the
 * teacher's intent here is "tweak THESE two knobs", not "rebuild the
 * whole spec".
 *
 * Wiring contract with 3A-2:
 * - ``onSuccess(updatedArtifact)`` fires with the regenerate response
 *   (same id, ``state=PENDING_REVIEW``, fresh content + edit_history).
 *   The parent's ArtifactDetailPanel uses this to swap the rendered
 *   body without a refetch.
 * - Submission disables the form + shows a spinner; failure surfaces an
 *   inline error inside the modal so the teacher can retry without
 *   losing their tweaks (no toast — the modal owns its own UX).
 */
import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { api } from '../../api/client';
import { useFocusTrap } from '../../hooks/useFocusTrap';
import './RegenerateModal.css';

// HTTP-side enums mirrored from app/schemas/cmcp.py (kept narrow + local
// so the modal doesn't grow a fan-in dependency on a bigger CMCP types
// module that may not exist yet — 3A-2 / 3A-3 can promote these later).
export type HTTPDifficulty = 'APPROACHING' | 'GRADE_LEVEL' | 'EXTENDING';
export type TargetPersona = 'student' | 'parent' | 'teacher';
export type HTTPContentType =
  | 'STUDY_GUIDE'
  | 'WORKSHEET'
  | 'QUIZ'
  | 'SAMPLE_TEST'
  | 'ASSIGNMENT'
  | 'PARENT_COMPANION';

export interface CMCPGenerateRequestPayload {
  grade: number;
  subject_code: string;
  strand_code?: string | null;
  topic?: string | null;
  content_type: HTTPContentType;
  difficulty?: HTTPDifficulty;
  target_persona?: TargetPersona | null;
  course_id?: number | null;
}

export interface RegenerateResponse {
  id: number;
  state: string;
  content: string;
  se_codes: string[];
  voice_module_hash: string | null;
  requested_persona: string | null;
  // Other ReviewArtifactDetail fields exist; keep this typed-loose so the
  // parent (3A-2) can refine via ``as`` cast onto its full type.
  [key: string]: unknown;
}

export interface RegenerateModalProps {
  artifactId: number;
  /** Original generation params; modal overrides difficulty + persona only. */
  baseRequest: CMCPGenerateRequestPayload;
  currentDifficulty?: HTTPDifficulty;
  currentPersona?: TargetPersona;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (updatedArtifact: RegenerateResponse) => void;
}

const DIFFICULTY_OPTIONS: { value: HTTPDifficulty; label: string; helper: string }[] = [
  { value: 'APPROACHING', label: 'Approaching', helper: 'Below grade level' },
  { value: 'GRADE_LEVEL', label: 'At grade', helper: 'Grade level (default)' },
  { value: 'EXTENDING', label: 'Extending', helper: 'Above grade level' },
];

const PERSONA_OPTIONS: { value: TargetPersona; label: string; helper: string }[] = [
  { value: 'student', label: 'Student', helper: 'Student-facing voice' },
  { value: 'parent', label: 'Parent', helper: 'Parent companion voice' },
  { value: 'teacher', label: 'Teacher', helper: 'Teacher-facing voice' },
];

export function RegenerateModal({
  artifactId,
  baseRequest,
  currentDifficulty,
  currentPersona,
  isOpen,
  onClose,
  onSuccess,
}: RegenerateModalProps) {
  const [difficulty, setDifficulty] = useState<HTTPDifficulty>(
    currentDifficulty ?? baseRequest.difficulty ?? 'GRADE_LEVEL'
  );
  const [persona, setPersona] = useState<TargetPersona>(
    currentPersona ?? baseRequest.target_persona ?? 'student'
  );
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const mutation = useMutation<RegenerateResponse, Error, void>({
    mutationFn: async () => {
      const payload = {
        request: {
          ...baseRequest,
          difficulty,
          target_persona: persona,
        },
      };
      const res = await api.post<RegenerateResponse>(
        `/api/cmcp/review/${artifactId}/regenerate`,
        payload,
        { timeout: 120_000 } // AI generation timeout
      );
      return res.data;
    },
    onSuccess: (data) => {
      setErrorMessage(null);
      onSuccess(data);
    },
    onError: (err) => {
      // Best-effort message — surface API detail when present, fall back
      // to a generic string so the inline error always renders something.
      const maybeAxios = err as unknown as {
        response?: { data?: { detail?: string } };
        message?: string;
      };
      // Use a chained-truthy fallback so empty strings (e.g., a bare
      // ``new Error()`` with ``message: ""``) still drop through to the
      // generic copy. ``??`` only catches null/undefined, which would
      // surface a blank inline banner.
      const detail =
        (maybeAxios?.response?.data?.detail && String(maybeAxios.response.data.detail)) ||
        (maybeAxios?.message && String(maybeAxios.message)) ||
        'Failed to regenerate. Please try again.';
      setErrorMessage(detail);
    },
  });

  const isSubmitting = mutation.isPending;

  // Trap keyboard focus inside the dialog + bind Escape→cancel, matching
  // the convention shared with ConfirmModal / EditStudyGuideModal. The
  // hook also restores focus to the previously focused element on close.
  // Hooks must be called unconditionally — the early-``return null`` for
  // ``!isOpen`` lives below this call. The hook itself no-ops when
  // ``active=false``.
  const trapRef = useFocusTrap<HTMLDivElement>(isOpen, () => {
    if (!isSubmitting) onClose();
  });

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    mutation.mutate();
  };

  const handleCancel = () => {
    if (isSubmitting) return;
    onClose();
  };

  return (
    <div className="modal-overlay" data-testid="cmcp-regenerate-modal-overlay">
      <div
        ref={trapRef}
        className="modal cmcp-regenerate-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="cmcp-regenerate-title"
        data-testid="cmcp-regenerate-modal"
      >
        <h2 id="cmcp-regenerate-title">Regenerate with adjustments</h2>
        <p className="modal-desc">
          Tweak the difficulty and persona, then re-run the prompt. The
          artifact stays in the review queue with the same id.
        </p>

        {errorMessage && (
          <div
            className="modal-error"
            role="alert"
            data-testid="cmcp-regenerate-error"
          >
            <span className="error-icon" aria-hidden="true">!</span>
            <span className="error-message">{errorMessage}</span>
          </div>
        )}

        <form className="modal-form cmcp-regenerate-form" onSubmit={handleSubmit}>
          <fieldset
            className="cmcp-regenerate-fieldset"
            disabled={isSubmitting}
          >
            <legend>Difficulty</legend>
            {DIFFICULTY_OPTIONS.map((opt) => (
              <label
                key={opt.value}
                className="cmcp-regenerate-radio"
                htmlFor={`cmcp-regen-difficulty-${opt.value}`}
              >
                <input
                  type="radio"
                  id={`cmcp-regen-difficulty-${opt.value}`}
                  name="cmcp-regen-difficulty"
                  value={opt.value}
                  checked={difficulty === opt.value}
                  onChange={() => setDifficulty(opt.value)}
                />
                <span className="cmcp-regenerate-radio-label">
                  <span className="cmcp-regenerate-radio-name">{opt.label}</span>
                  <span className="cmcp-regenerate-radio-helper">{opt.helper}</span>
                </span>
              </label>
            ))}
          </fieldset>

          <fieldset
            className="cmcp-regenerate-fieldset"
            disabled={isSubmitting}
          >
            <legend>Persona override</legend>
            {PERSONA_OPTIONS.map((opt) => (
              <label
                key={opt.value}
                className="cmcp-regenerate-radio"
                htmlFor={`cmcp-regen-persona-${opt.value}`}
              >
                <input
                  type="radio"
                  id={`cmcp-regen-persona-${opt.value}`}
                  name="cmcp-regen-persona"
                  value={opt.value}
                  checked={persona === opt.value}
                  onChange={() => setPersona(opt.value)}
                />
                <span className="cmcp-regenerate-radio-label">
                  <span className="cmcp-regenerate-radio-name">{opt.label}</span>
                  <span className="cmcp-regenerate-radio-helper">{opt.helper}</span>
                </span>
              </label>
            ))}
          </fieldset>

          <div className="modal-actions">
            <button
              type="button"
              className="cancel-btn"
              onClick={handleCancel}
              disabled={isSubmitting}
              data-testid="cmcp-regenerate-cancel"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="generate-btn"
              disabled={isSubmitting}
              aria-busy={isSubmitting}
              data-testid="cmcp-regenerate-submit"
            >
              {isSubmitting ? (
                <>
                  <span className="btn-spinner" aria-hidden="true" /> Regenerating...
                </>
              ) : (
                'Regenerate'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
