import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { GenerateSubGuideModal } from '../GenerateSubGuideModal';

const defaultProps = {
  open: true,
  selectedText: 'This is some selected text from a study guide.',
  onClose: vi.fn(),
  onGenerate: vi.fn().mockResolvedValue(undefined),
  aiAvailable: true,
  aiRemaining: 5,
};

function renderModal(overrides: Partial<typeof defaultProps> = {}) {
  const props = { ...defaultProps, ...overrides };
  return render(
    <MemoryRouter>
      <GenerateSubGuideModal {...props} />
    </MemoryRouter>
  );
}

describe('GenerateSubGuideModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('does not render when closed', () => {
    renderModal({ open: false });
    expect(screen.queryByTestId('generate-sub-guide-modal')).not.toBeInTheDocument();
  });

  it('renders when open with selected text preview', () => {
    renderModal();
    expect(screen.getByTestId('generate-sub-guide-modal')).toBeInTheDocument();
    expect(screen.getByTestId('selected-text-preview')).toHaveTextContent(
      'This is some selected text from a study guide.'
    );
  });

  it('truncates long selected text to 200 chars', () => {
    const longText = 'A'.repeat(300);
    renderModal({ selectedText: longText });
    const preview = screen.getByTestId('selected-text-preview').textContent!;
    expect(preview.length).toBe(203); // 200 chars + '...'
    expect(preview.endsWith('...')).toBe(true);
  });

  it('shows three guide type options', () => {
    renderModal();
    expect(screen.getByText('Study Guide')).toBeInTheDocument();
    expect(screen.getByText('Quiz')).toBeInTheDocument();
    expect(screen.getByText('Flashcards')).toBeInTheDocument();
  });

  it('study_guide is selected by default', () => {
    renderModal();
    expect(screen.getByTestId('type-study_guide')).toHaveAttribute('aria-checked', 'true');
    expect(screen.getByTestId('type-quiz')).toHaveAttribute('aria-checked', 'false');
    expect(screen.getByTestId('type-flashcards')).toHaveAttribute('aria-checked', 'false');
  });

  it('can switch selected type', () => {
    renderModal();
    fireEvent.click(screen.getByTestId('type-quiz'));
    expect(screen.getByTestId('type-quiz')).toHaveAttribute('aria-checked', 'true');
    expect(screen.getByTestId('type-study_guide')).toHaveAttribute('aria-checked', 'false');
  });

  it('shows AI credits info', () => {
    renderModal({ aiRemaining: 5 });
    expect(screen.getByTestId('credits-info')).toHaveTextContent(
      'Uses 1 AI credit · 5 remaining'
    );
  });

  it('calls onGenerate with selected type', async () => {
    const onGenerate = vi.fn().mockResolvedValue(undefined);
    renderModal({ onGenerate });
    fireEvent.click(screen.getByTestId('generate-btn'));
    await waitFor(() => {
      expect(onGenerate).toHaveBeenCalledWith('study_guide', undefined, undefined, undefined);
    });
  });

  it('calls onGenerate with custom prompt', async () => {
    const onGenerate = vi.fn().mockResolvedValue(undefined);
    renderModal({ onGenerate });
    fireEvent.change(screen.getByTestId('custom-prompt-input'), {
      target: { value: 'Focus on chapter 3' },
    });
    fireEvent.click(screen.getByTestId('generate-btn'));
    await waitFor(() => {
      expect(onGenerate).toHaveBeenCalledWith('study_guide', 'Focus on chapter 3', undefined, undefined);
    });
  });

  it('disables generate when AI unavailable', () => {
    renderModal({ aiAvailable: false });
    expect(screen.getByTestId('generate-btn')).toBeDisabled();
  });

  it('calls onClose when cancel clicked', () => {
    const onClose = vi.fn();
    renderModal({ onClose });
    fireEvent.click(screen.getByTestId('cancel-btn'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('does not call onClose when overlay clicked (#3750)', () => {
    const onClose = vi.fn();
    renderModal({ onClose });
    fireEvent.click(screen.getByTestId('generate-sub-guide-modal'));
    expect(onClose).not.toHaveBeenCalled();
  });
});
