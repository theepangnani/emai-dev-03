/** CB-CMCP-001 M3-A 3A-4 (#4584) — RegenerateModal unit tests.
 *
 * Coverage per acceptance:
 * - Renders form when isOpen=true / nothing when isOpen=false.
 * - Submit posts to ``/api/cmcp/review/{id}/regenerate`` with the merged
 *   payload (baseRequest + difficulty + persona overrides).
 * - Successful response triggers ``onSuccess`` with the artifact body.
 * - Failed response surfaces an inline error inside the modal.
 * - Cancel calls ``onClose``.
 * - Submit button disables + shows "Regenerating..." while in flight.
 *
 * The Axios client is mocked — we ``vi.importActual`` and spread to
 * preserve any non-``api`` exports the component might happen to call,
 * per the mock-shadow check in CLAUDE.md (#4277 lessons).
 *
 * CB-CMCP-001 M3β 3F-2 (#4661) — extended coverage for the optional
 * "Pick SEs" toggle that hooks ``<CurriculumBrowser />`` into the
 * regenerate flow:
 * - Toggle OFF (default) → payload omits ``target_se_codes``.
 * - Toggle ON + selection → payload includes ``target_se_codes``.
 * - Toggle ON then OFF → payload omits ``target_se_codes`` even if
 *   chips were picked while ON (selection preserved in state but not
 *   shipped on the wire).
 *
 * ``CurriculumBrowser`` is mocked at the module boundary so the test
 * does not pull in the curriculum API. The mock exposes a button that
 * synthesises a selection-change so the test can drive the toggle/flow
 * without rendering the full tree.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { RegenerateModal } from '../RegenerateModal';
import type { CMCPGenerateRequestPayload, RegenerateResponse } from '../RegenerateModal';

// Mock the axios client. ``vi.importActual`` + spread preserves all
// other exports (AI_TIMEOUT, etc.) so a future addition to the SUT
// doesn't silently shadow into ``undefined``.
vi.mock('../../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../../api/client')>(
    '../../../api/client'
  );
  return {
    ...actual,
    api: {
      post: vi.fn(),
    },
  };
});

// Mock the CurriculumBrowser component so these tests don't pull in the
// curriculum API. The mock renders two buttons that synthesise
// selection-change events so the tests can drive the flow without
// rendering the real tree/table view. Per the mock-shadow check
// (#4277) we vi.importActual + spread so any other named export the
// SUT calls keeps its real implementation.
vi.mock('../CurriculumBrowser', async () => {
  const actual = await vi.importActual<
    typeof import('../CurriculumBrowser')
  >('../CurriculumBrowser');
  return {
    ...actual,
    CurriculumBrowser: ({
      onSelectionChange,
      initialSelection,
    }: {
      onSelectionChange: (codes: string[]) => void;
      initialSelection?: string[];
      grade?: number;
    }) => {
      return (
        <div data-testid="cmcp-curriculum-browser-mock">
          <span data-testid="cmcp-curriculum-browser-mock-initial">
            {(initialSelection ?? []).join(',')}
          </span>
          <button
            type="button"
            data-testid="cmcp-curriculum-browser-mock-select-math"
            onClick={() => onSelectionChange(['MATH.5.B1.1', 'MATH.5.B1.2'])}
          >
            Pick MATH.5.B1.1 + B1.2
          </button>
          <button
            type="button"
            data-testid="cmcp-curriculum-browser-mock-clear"
            onClick={() => onSelectionChange([])}
          >
            Clear selection
          </button>
        </div>
      );
    },
  };
});

import { api } from '../../../api/client';

const baseRequest: CMCPGenerateRequestPayload = {
  grade: 5,
  subject_code: 'MATH',
  strand_code: 'B',
  content_type: 'STUDY_GUIDE',
  difficulty: 'GRADE_LEVEL',
  target_persona: 'student',
  course_id: 42,
};

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe('RegenerateModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders nothing when isOpen=false', () => {
    const { container } = renderWithClient(
      <RegenerateModal
        artifactId={1}
        baseRequest={baseRequest}
        isOpen={false}
        onClose={() => {}}
        onSuccess={() => {}}
      />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('renders the form when isOpen=true with all radio options', () => {
    renderWithClient(
      <RegenerateModal
        artifactId={1}
        baseRequest={baseRequest}
        isOpen
        onClose={() => {}}
        onSuccess={() => {}}
      />
    );
    expect(screen.getByTestId('cmcp-regenerate-modal')).toBeInTheDocument();
    expect(screen.getByText(/Regenerate with adjustments/i)).toBeInTheDocument();

    // Difficulty options
    expect(screen.getByLabelText(/Approaching/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/At grade/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Extending/i)).toBeInTheDocument();

    // Persona options
    expect(screen.getByLabelText(/Student/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Parent/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Teacher/i)).toBeInTheDocument();
  });

  it('closes the modal on Escape (focus trap binding)', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    renderWithClient(
      <RegenerateModal
        artifactId={1}
        baseRequest={baseRequest}
        isOpen
        onClose={onClose}
        onSuccess={() => {}}
      />
    );

    // Click inside the dialog so the focus-trap container has the active
    // element, then press Escape. The trap binds keydown on its container
    // and calls the onEscape callback.
    await user.click(screen.getByLabelText(/At grade/i));
    await user.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('submits with the adjusted parameters merged into baseRequest', async () => {
    const user = userEvent.setup();
    const mockResponse: RegenerateResponse = {
      id: 7,
      state: 'PENDING_REVIEW',
      content: 'fresh body',
      se_codes: ['MATH.5.B1.1'],
      voice_module_hash: 'abc',
      requested_persona: 'parent',
    };
    (api.post as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      data: mockResponse,
    });
    const onSuccess = vi.fn();

    renderWithClient(
      <RegenerateModal
        artifactId={7}
        baseRequest={baseRequest}
        currentDifficulty="GRADE_LEVEL"
        currentPersona="student"
        isOpen
        onClose={() => {}}
        onSuccess={onSuccess}
      />
    );

    // Tweak difficulty + persona
    await user.click(screen.getByLabelText(/Extending/i));
    await user.click(screen.getByLabelText(/Parent/i));

    await user.click(screen.getByTestId('cmcp-regenerate-submit'));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledTimes(1);
    });

    const [url, body] = (api.post as unknown as ReturnType<typeof vi.fn>).mock
      .calls[0];
    expect(url).toBe('/api/cmcp/review/7/regenerate');
    expect(body).toEqual({
      request: {
        ...baseRequest,
        difficulty: 'EXTENDING',
        target_persona: 'parent',
      },
    });

    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalledWith(mockResponse);
    });
  });

  it('renders an inline error when the API call fails', async () => {
    const user = userEvent.setup();
    (api.post as unknown as ReturnType<typeof vi.fn>).mockRejectedValueOnce({
      response: { data: { detail: 'Rate limit exceeded' } },
      message: 'Request failed',
    });
    const onSuccess = vi.fn();

    renderWithClient(
      <RegenerateModal
        artifactId={3}
        baseRequest={baseRequest}
        isOpen
        onClose={() => {}}
        onSuccess={onSuccess}
      />
    );

    await user.click(screen.getByTestId('cmcp-regenerate-submit'));

    const errorBanner = await screen.findByTestId('cmcp-regenerate-error');
    expect(errorBanner).toHaveTextContent('Rate limit exceeded');
    expect(onSuccess).not.toHaveBeenCalled();

    // Modal should still be visible so the teacher can retry.
    expect(screen.getByTestId('cmcp-regenerate-modal')).toBeInTheDocument();
  });

  it('falls back to a generic error message when the API gives no detail', async () => {
    const user = userEvent.setup();
    (api.post as unknown as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error()
    );

    renderWithClient(
      <RegenerateModal
        artifactId={3}
        baseRequest={baseRequest}
        isOpen
        onClose={() => {}}
        onSuccess={() => {}}
      />
    );

    await user.click(screen.getByTestId('cmcp-regenerate-submit'));

    const errorBanner = await screen.findByTestId('cmcp-regenerate-error');
    expect(errorBanner.textContent).toMatch(/Failed to regenerate/i);
  });

  it('closes the modal when Cancel is clicked', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    renderWithClient(
      <RegenerateModal
        artifactId={3}
        baseRequest={baseRequest}
        isOpen
        onClose={onClose}
        onSuccess={() => {}}
      />
    );

    await user.click(screen.getByTestId('cmcp-regenerate-cancel'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('disables the submit button + shows a spinner while submitting', async () => {
    const user = userEvent.setup();
    let resolvePost: (v: { data: RegenerateResponse }) => void = () => {};
    const pending = new Promise<{ data: RegenerateResponse }>((resolve) => {
      resolvePost = resolve;
    });
    (api.post as unknown as ReturnType<typeof vi.fn>).mockReturnValueOnce(pending);
    const onSuccess = vi.fn();

    renderWithClient(
      <RegenerateModal
        artifactId={3}
        baseRequest={baseRequest}
        isOpen
        onClose={() => {}}
        onSuccess={onSuccess}
      />
    );

    const submit = screen.getByTestId('cmcp-regenerate-submit') as HTMLButtonElement;
    await user.click(submit);

    // Mid-flight: button disabled + label flips
    await waitFor(() => {
      expect(submit).toBeDisabled();
    });
    expect(submit.textContent).toMatch(/Regenerating/i);

    // Resolve + wait for the success callback so React's state update is
    // flushed inside the test scope (avoids "act(...)" warnings).
    resolvePost({
      data: {
        id: 3,
        state: 'PENDING_REVIEW',
        content: '',
        se_codes: [],
        voice_module_hash: null,
        requested_persona: null,
      },
    });
    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalled();
    });
  });

  it('initialises radios from currentDifficulty / currentPersona when supplied', () => {
    renderWithClient(
      <RegenerateModal
        artifactId={3}
        baseRequest={baseRequest}
        currentDifficulty="EXTENDING"
        currentPersona="teacher"
        isOpen
        onClose={() => {}}
        onSuccess={() => {}}
      />
    );

    expect(screen.getByLabelText(/Extending/i)).toBeChecked();
    expect(screen.getByLabelText(/Teacher/i)).toBeChecked();
  });

  // ── 3F-2 (#4661) — Pick-SEs toggle + CurriculumBrowser flow ─────────
  describe('Pick-SEs toggle (3F-2)', () => {
    it('starts with the toggle OFF and the picker hidden by default', () => {
      renderWithClient(
        <RegenerateModal
          artifactId={1}
          baseRequest={baseRequest}
          isOpen
          onClose={() => {}}
          onSuccess={() => {}}
        />
      );

      const toggle = screen.getByTestId(
        'cmcp-regenerate-pick-ses-toggle'
      ) as HTMLInputElement;
      expect(toggle).not.toBeChecked();
      expect(
        screen.queryByTestId('cmcp-regenerate-se-picker')
      ).not.toBeInTheDocument();
      expect(
        screen.queryByTestId('cmcp-curriculum-browser-mock')
      ).not.toBeInTheDocument();
    });

    it('reveals the CurriculumBrowser when the toggle is flipped ON', async () => {
      const user = userEvent.setup();
      renderWithClient(
        <RegenerateModal
          artifactId={1}
          baseRequest={baseRequest}
          isOpen
          onClose={() => {}}
          onSuccess={() => {}}
        />
      );

      await user.click(screen.getByTestId('cmcp-regenerate-pick-ses-toggle'));

      expect(
        screen.getByTestId('cmcp-regenerate-se-picker')
      ).toBeInTheDocument();
      expect(
        screen.getByTestId('cmcp-curriculum-browser-mock')
      ).toBeInTheDocument();
      // Empty-selection summary is visible until the teacher picks at
      // least one SE.
      expect(
        screen.getByTestId('cmcp-regenerate-se-summary').textContent
      ).toMatch(/No SE codes selected/i);
    });

    it('omits target_se_codes from the payload when the toggle is OFF', async () => {
      const user = userEvent.setup();
      const mockResponse: RegenerateResponse = {
        id: 1,
        state: 'PENDING_REVIEW',
        content: 'fresh body',
        se_codes: [],
        voice_module_hash: null,
        requested_persona: 'student',
      };
      (api.post as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        data: mockResponse,
      });

      renderWithClient(
        <RegenerateModal
          artifactId={1}
          baseRequest={baseRequest}
          isOpen
          onClose={() => {}}
          onSuccess={() => {}}
        />
      );

      await user.click(screen.getByTestId('cmcp-regenerate-submit'));

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledTimes(1);
      });

      const [, body] = (api.post as unknown as ReturnType<typeof vi.fn>).mock
        .calls[0];
      expect(body.request).not.toHaveProperty('target_se_codes');
    });

    it('flows selected SE codes into the payload as target_se_codes', async () => {
      const user = userEvent.setup();
      const mockResponse: RegenerateResponse = {
        id: 9,
        state: 'PENDING_REVIEW',
        content: 'fresh body',
        se_codes: ['MATH.5.B1.1', 'MATH.5.B1.2'],
        voice_module_hash: null,
        requested_persona: 'student',
      };
      (api.post as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        data: mockResponse,
      });

      renderWithClient(
        <RegenerateModal
          artifactId={9}
          baseRequest={baseRequest}
          isOpen
          onClose={() => {}}
          onSuccess={() => {}}
        />
      );

      // Flip the toggle ON, then drive the mock CurriculumBrowser to
      // synthesise a two-code selection.
      await user.click(screen.getByTestId('cmcp-regenerate-pick-ses-toggle'));
      await user.click(
        screen.getByTestId('cmcp-curriculum-browser-mock-select-math')
      );

      // Summary updates with the count.
      expect(
        screen.getByTestId('cmcp-regenerate-se-summary').textContent
      ).toMatch(/2 SE codes will be sent/i);

      await user.click(screen.getByTestId('cmcp-regenerate-submit'));

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledTimes(1);
      });

      const [url, body] = (api.post as unknown as ReturnType<typeof vi.fn>).mock
        .calls[0];
      expect(url).toBe('/api/cmcp/review/9/regenerate');
      expect(body).toEqual({
        request: {
          ...baseRequest,
          difficulty: 'GRADE_LEVEL',
          target_persona: 'student',
          target_se_codes: ['MATH.5.B1.1', 'MATH.5.B1.2'],
        },
      });
    });

    it('omits target_se_codes when the toggle is flipped ON then OFF (chips preserved in state but not shipped)', async () => {
      const user = userEvent.setup();
      const mockResponse: RegenerateResponse = {
        id: 1,
        state: 'PENDING_REVIEW',
        content: 'fresh body',
        se_codes: [],
        voice_module_hash: null,
        requested_persona: 'student',
      };
      (api.post as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        data: mockResponse,
      });

      renderWithClient(
        <RegenerateModal
          artifactId={1}
          baseRequest={baseRequest}
          isOpen
          onClose={() => {}}
          onSuccess={() => {}}
        />
      );

      // ON → pick → OFF
      await user.click(screen.getByTestId('cmcp-regenerate-pick-ses-toggle'));
      await user.click(
        screen.getByTestId('cmcp-curriculum-browser-mock-select-math')
      );
      await user.click(screen.getByTestId('cmcp-regenerate-pick-ses-toggle'));

      // Picker is hidden again
      expect(
        screen.queryByTestId('cmcp-regenerate-se-picker')
      ).not.toBeInTheDocument();

      await user.click(screen.getByTestId('cmcp-regenerate-submit'));

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledTimes(1);
      });

      const [, body] = (api.post as unknown as ReturnType<typeof vi.fn>).mock
        .calls[0];
      expect(body.request).not.toHaveProperty('target_se_codes');
    });

    it('omits target_se_codes when the toggle is ON but no SEs were picked (empty selection)', async () => {
      const user = userEvent.setup();
      const mockResponse: RegenerateResponse = {
        id: 1,
        state: 'PENDING_REVIEW',
        content: 'fresh body',
        se_codes: [],
        voice_module_hash: null,
        requested_persona: 'student',
      };
      (api.post as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        data: mockResponse,
      });

      renderWithClient(
        <RegenerateModal
          artifactId={1}
          baseRequest={baseRequest}
          isOpen
          onClose={() => {}}
          onSuccess={() => {}}
        />
      );

      await user.click(screen.getByTestId('cmcp-regenerate-pick-ses-toggle'));
      // Submit without picking any SEs — toggle is ON but selection is [].
      await user.click(screen.getByTestId('cmcp-regenerate-submit'));

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledTimes(1);
      });

      const [, body] = (api.post as unknown as ReturnType<typeof vi.fn>).mock
        .calls[0];
      expect(body.request).not.toHaveProperty('target_se_codes');
    });

    it('initialises the toggle ON when baseRequest already carries target_se_codes', () => {
      const seededBase: CMCPGenerateRequestPayload = {
        ...baseRequest,
        target_se_codes: ['MATH.5.B1.1'],
      };
      renderWithClient(
        <RegenerateModal
          artifactId={1}
          baseRequest={seededBase}
          isOpen
          onClose={() => {}}
          onSuccess={() => {}}
        />
      );

      const toggle = screen.getByTestId(
        'cmcp-regenerate-pick-ses-toggle'
      ) as HTMLInputElement;
      expect(toggle).toBeChecked();
      expect(
        screen.getByTestId('cmcp-regenerate-se-picker')
      ).toBeInTheDocument();
      // The seeded codes are passed through to the mock as initialSelection
      // so the embedded browser can hydrate its chip list.
      expect(
        screen.getByTestId('cmcp-curriculum-browser-mock-initial').textContent
      ).toBe('MATH.5.B1.1');
    });

    it('strips a stale target_se_codes carried in baseRequest when the toggle is OFF after submission', async () => {
      const user = userEvent.setup();
      const seededBase: CMCPGenerateRequestPayload = {
        ...baseRequest,
        target_se_codes: ['MATH.5.B1.1'],
      };
      const mockResponse: RegenerateResponse = {
        id: 1,
        state: 'PENDING_REVIEW',
        content: 'fresh body',
        se_codes: [],
        voice_module_hash: null,
        requested_persona: 'student',
      };
      (api.post as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        data: mockResponse,
      });

      renderWithClient(
        <RegenerateModal
          artifactId={1}
          baseRequest={seededBase}
          isOpen
          onClose={() => {}}
          onSuccess={() => {}}
        />
      );

      // Toggle starts ON because of the seeded codes — flip it OFF.
      await user.click(screen.getByTestId('cmcp-regenerate-pick-ses-toggle'));
      await user.click(screen.getByTestId('cmcp-regenerate-submit'));

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledTimes(1);
      });

      const [, body] = (api.post as unknown as ReturnType<typeof vi.fn>).mock
        .calls[0];
      expect(body.request).not.toHaveProperty('target_se_codes');
    });
  });
});
