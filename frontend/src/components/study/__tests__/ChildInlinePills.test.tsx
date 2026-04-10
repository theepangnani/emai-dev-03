import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ChildInlinePills, detectGradeConflict } from '../ChildInlinePills';
import type { Child } from '../ChildInlinePills';

describe('ChildInlinePills', () => {
  const children: Child[] = [
    { id: 1, name: 'Emma', grade: '5' },
    { id: 2, name: 'Liam', grade: '8' },
  ];

  beforeEach(() => {
    localStorage.clear();
  });

  it('renders nothing for single child', () => {
    const { container } = render(
      <ChildInlinePills
        children={[children[0]]}
        selectedChildId={null}
        suggestedChildId={null}
        courseId={100}
        onSelect={vi.fn()}
      />,
    );
    expect(container.innerHTML).toBe('');
  });

  it('renders pills for multiple children', () => {
    render(
      <ChildInlinePills
        children={children}
        selectedChildId={null}
        suggestedChildId={null}
        courseId={100}
        onSelect={vi.fn()}
      />,
    );
    expect(screen.getByText('Emma')).toBeInTheDocument();
    expect(screen.getByText('Liam')).toBeInTheDocument();
    expect(screen.getByText(/which child/i)).toBeInTheDocument();
  });

  it('marks selected child as pressed', () => {
    render(
      <ChildInlinePills
        children={children}
        selectedChildId={1}
        suggestedChildId={null}
        courseId={100}
        onSelect={vi.fn()}
      />,
    );
    const emmaBtn = screen.getByText('Emma').closest('button')!;
    expect(emmaBtn).toHaveAttribute('aria-pressed', 'true');
  });

  it('calls onSelect when pill clicked', () => {
    const onSelect = vi.fn();
    render(
      <ChildInlinePills
        children={children}
        selectedChildId={null}
        suggestedChildId={null}
        courseId={100}
        onSelect={onSelect}
      />,
    );
    fireEvent.click(screen.getByText('Liam').closest('button')!);
    expect(onSelect).toHaveBeenCalledWith(2);
  });

  it('shows grade badge', () => {
    render(
      <ChildInlinePills
        children={children}
        selectedChildId={null}
        suggestedChildId={null}
        courseId={100}
        onSelect={vi.fn()}
      />,
    );
    expect(screen.getByText(/Grade 5/)).toBeInTheDocument();
    expect(screen.getByText(/Grade 8/)).toBeInTheDocument();
  });

  it('highlights suggested child', () => {
    const { container } = render(
      <ChildInlinePills
        children={children}
        selectedChildId={null}
        suggestedChildId={2}
        courseId={100}
        onSelect={vi.fn()}
      />,
    );
    expect(container.querySelector('.child-inline-pill--suggested')).toBeInTheDocument();
  });
});

describe('detectGradeConflict', () => {
  const children: Child[] = [
    { id: 1, name: 'Emma', grade: '5' },
    { id: 2, name: 'Liam', grade: '8' },
  ];

  it('returns null suggestion when no grade detected', () => {
    const result = detectGradeConflict(children, null);
    expect(result.suggestedChildId).toBeNull();
    expect(result.isConflict).toBe(false);
  });

  it('suggests matching child when grade detected', () => {
    const result = detectGradeConflict(children, '5');
    expect(result.suggestedChildId).toBe(1);
    expect(result.isConflict).toBe(false);
  });

  it('flags conflict when no child matches detected grade', () => {
    const result = detectGradeConflict(children, '10');
    expect(result.suggestedChildId).toBeNull();
    expect(result.isConflict).toBe(true);
  });

  it('returns no suggestion for single child', () => {
    const result = detectGradeConflict([children[0]], '5');
    expect(result.suggestedChildId).toBeNull();
    expect(result.isConflict).toBe(false);
  });
});
