import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import MaterialTypeSuggestionChips, { getChips, getHeader, CHIP_SETS } from '../MaterialTypeSuggestionChips';

describe('MaterialTypeSuggestionChips', () => {
  const defaultProps = {
    documentType: 'teacher_notes',
    detectedSubject: 'math' as string | null,
    onChipClick: vi.fn(),
    generatingAction: null as string | null,
    disabled: false,
    remainingCredits: 10 as number | null,
    atLimit: false,
  };

  it('renders chips for teacher_notes', () => {
    render(<MaterialTypeSuggestionChips {...defaultProps} />);
    expect(screen.getByText('Generate Worksheets')).toBeInTheDocument();
    expect(screen.getByText('Create Sample Test')).toBeInTheDocument();
    expect(screen.getByText('High Level Summary')).toBeInTheDocument();
  });

  it('renders correct header for past_exam', () => {
    render(<MaterialTypeSuggestionChips {...defaultProps} documentType="past_exam" />);
    expect(screen.getByText(/had a test/i)).toBeInTheDocument();
  });

  it('renders default header for unknown document type', () => {
    render(<MaterialTypeSuggestionChips {...defaultProps} documentType="unknown_type" />);
    expect(screen.getByText(/what we can do with this document/i)).toBeInTheDocument();
  });

  it('calls onChipClick with action when chip clicked', () => {
    const onClick = vi.fn();
    render(<MaterialTypeSuggestionChips {...defaultProps} onChipClick={onClick} />);
    fireEvent.click(screen.getByText('Generate Worksheets'));
    expect(onClick).toHaveBeenCalledWith('worksheet', undefined);
  });

  it('disables chips when at limit', () => {
    render(<MaterialTypeSuggestionChips {...defaultProps} atLimit={true} />);
    const buttons = screen.getAllByRole('button');
    buttons.forEach((btn) => {
      expect(btn).toBeDisabled();
    });
  });

  it('shows spinner on generating chip', () => {
    const { container } = render(
      <MaterialTypeSuggestionChips {...defaultProps} generatingAction="worksheet" />,
    );
    expect(container.querySelector('.mt-chip-spinner')).toBeInTheDocument();
  });

  it('shows remaining credits', () => {
    render(<MaterialTypeSuggestionChips {...defaultProps} remainingCredits={5} />);
    expect(screen.getByText(/5 credits remaining/)).toBeInTheDocument();
  });

  it('shows credit cost for expensive actions', () => {
    render(<MaterialTypeSuggestionChips {...defaultProps} documentType="past_exam" />);
    expect(screen.getByText(/2 credits/)).toBeInTheDocument();
  });
});

describe('getChips', () => {
  it('returns teacher_notes chips for teacher_notes', () => {
    const chips = getChips('teacher_notes');
    expect(chips.length).toBeGreaterThan(0);
    expect(chips[0].action).toBe('worksheet');
  });

  it('returns custom chips for unknown type', () => {
    const chips = getChips('nonexistent_type');
    expect(chips).toEqual(CHIP_SETS.custom);
  });
});

describe('Solve with Explanations chip', () => {
  const defaultProps = {
    documentType: 'worksheet',
    detectedSubject: 'math' as string | null,
    onChipClick: vi.fn(),
    generatingAction: null as string | null,
    disabled: false,
    remainingCredits: 10 as number | null,
    atLimit: false,
  };

  it('appears in worksheet chip set', () => {
    render(<MaterialTypeSuggestionChips {...defaultProps} documentType="worksheet" />);
    expect(screen.getByText('Solve with Explanations')).toBeInTheDocument();
  });
});

describe('getHeader', () => {
  it('returns specific header for worksheet', () => {
    expect(getHeader('worksheet')).toContain('worksheet');
  });

  it('returns default header for unknown type', () => {
    expect(getHeader('unknown')).toContain('what we can do');
  });
});
