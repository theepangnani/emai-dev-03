/**
 * Regression tests for #4020 — render true_false and fill_blank
 * quiz question types in the ASGF slide-anchored quiz bridge.
 */
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect } from 'vitest';
import { ASGFQuizBridge } from './ASGFQuizBridge';
import type { ASGFQuizQuestion } from '../../api/asgf';

const baseMCQ: ASGFQuizQuestion = {
  question_text: 'What is 2 + 2?',
  options: ['3', '4', '5', '6'],
  correct_index: 1,
  bloom_tier: 'recall',
  slide_reference: 0,
  hint_text: 'Look at slide 1',
  explanation: 'Two plus two equals four.',
};

describe('ASGFQuizBridge — #4020 true_false + fill_blank rendering', () => {
  it('true_false: renders 2 buttons (True / False) and selecting True marks correct', async () => {
    const question: ASGFQuizQuestion = {
      question_text: 'The sky is blue.',
      options: ['True', 'False'],
      correct_index: 0,
      bloom_tier: 'recall',
      slide_reference: 0,
      hint_text: 'Look outside.',
      explanation: 'On a clear day, the sky appears blue.',
      format: 'true_false',
    };

    render(
      <ASGFQuizBridge questions={[question]} sessionId="s-1" />,
    );

    // Question shows
    expect(screen.getByText('The sky is blue.')).toBeInTheDocument();

    // Two radio buttons labelled True and False
    const trueBtn = screen.getByRole('radio', { name: 'True' });
    const falseBtn = screen.getByRole('radio', { name: 'False' });
    expect(trueBtn).toBeInTheDocument();
    expect(falseBtn).toBeInTheDocument();
    expect(screen.getByRole('radiogroup', { name: 'True or False' })).toBeInTheDocument();

    // No A/B/C/D letter badges rendered
    expect(screen.queryByText('A')).not.toBeInTheDocument();

    // Click True → explanation / Next button appears (correct path)
    const user = userEvent.setup();
    await user.click(trueBtn);

    await waitFor(() => {
      expect(screen.getByText('Why correct')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /see results/i })).toBeInTheDocument();
  });

  it('fill_blank: renders input + submit, typing correct answer marks correct', async () => {
    const question: ASGFQuizQuestion = {
      question_text: 'The capital of France is ____.',
      options: ['Paris', '', '', ''],
      correct_index: 0,
      bloom_tier: 'recall',
      slide_reference: 0,
      hint_text: 'Think of the Eiffel Tower.',
      explanation: 'Paris is the capital of France.',
      format: 'fill_blank',
    };

    render(
      <ASGFQuizBridge questions={[question]} sessionId="s-2" />,
    );

    expect(screen.getByText('The capital of France is ____.')).toBeInTheDocument();

    // Input with label
    const input = screen.getByLabelText(/your answer/i) as HTMLInputElement;
    expect(input).toBeInTheDocument();
    expect(input.tagName).toBe('INPUT');

    // No A/B/C/D letter badges and no radiogroup
    expect(screen.queryByRole('radiogroup')).not.toBeInTheDocument();

    const user = userEvent.setup();
    await user.type(input, 'Paris');
    await user.click(screen.getByRole('button', { name: /submit answer/i }));

    await waitFor(() => {
      expect(screen.getByText('Why correct')).toBeInTheDocument();
    });
    // Typed answer is echoed back — scope to the feedback region so we don't
    // accidentally match another "Paris" elsewhere on the page (#4031 S5).
    const typedFeedback = document.querySelector('.asgf-quiz-typed-answer');
    expect(typedFeedback).not.toBeNull();
    expect(within(typedFeedback as HTMLElement).getByText('Paris')).toBeInTheDocument();
  });

  it('fill_blank: normalizes punctuation, case, and whitespace (#4030 I3)', async () => {
    const question: ASGFQuizQuestion = {
      question_text: 'The capital of France is ____.',
      options: ['Paris', '', '', ''],
      correct_index: 0,
      bloom_tier: 'recall',
      slide_reference: 0,
      hint_text: 'Think of the Eiffel Tower.',
      explanation: 'Paris is the capital of France.',
      format: 'fill_blank',
    };

    const { unmount } = render(
      <ASGFQuizBridge questions={[question]} sessionId="s-norm-punct" />,
    );

    // 1) Trailing punctuation should match
    const input = screen.getByLabelText(/your answer/i) as HTMLInputElement;
    const user = userEvent.setup();
    await user.type(input, 'Paris!');
    await user.click(screen.getByRole('button', { name: /submit answer/i }));
    await waitFor(() => {
      expect(screen.getByText('Why correct')).toBeInTheDocument();
    });
    unmount();

    // 2) Case + surrounding whitespace should match
    const { unmount: unmount2 } = render(
      <ASGFQuizBridge questions={[question]} sessionId="s-norm-case" />,
    );
    const input2 = screen.getByLabelText(/your answer/i) as HTMLInputElement;
    await user.type(input2, '  paris  ');
    await user.click(screen.getByRole('button', { name: /submit answer/i }));
    await waitFor(() => {
      expect(screen.getByText('Why correct')).toBeInTheDocument();
    });
    unmount2();

    // 3) Period at end should match
    render(<ASGFQuizBridge questions={[question]} sessionId="s-norm-period" />);
    const input3 = screen.getByLabelText(/your answer/i) as HTMLInputElement;
    await user.type(input3, 'paris.');
    await user.click(screen.getByRole('button', { name: /submit answer/i }));
    await waitFor(() => {
      expect(screen.getByText('Why correct')).toBeInTheDocument();
    });
  });

  it('fill_blank: normalizer preserves word boundaries — "it\'s" ≠ "its" (#4034 I1)', async () => {
    // Canonical answer: "its". Typed: "it's" → normalizes to "it s" (two tokens),
    // so must NOT match.
    const question: ASGFQuizQuestion = {
      question_text: 'Fill in: The dog wagged ____ tail.',
      options: ['its', '', '', ''],
      correct_index: 0,
      bloom_tier: 'recall',
      slide_reference: 0,
      hint_text: 'Possessive form, no apostrophe.',
      explanation: '"its" is the possessive form.',
      format: 'fill_blank',
    };

    render(<ASGFQuizBridge questions={[question]} sessionId="s-4034-its" />);
    const input = screen.getByLabelText(/your answer/i) as HTMLInputElement;
    const user = userEvent.setup();
    await user.type(input, "it's");
    await user.click(screen.getByRole('button', { name: /submit answer/i }));

    // Should be WRONG — hint visible, no "Why correct"
    await waitFor(() => {
      expect(screen.getByRole('status', { name: /hint for attempt/i })).toBeInTheDocument();
    });
    expect(screen.queryByText('Why correct')).not.toBeInTheDocument();
  });

  it('fill_blank: normalizer preserves word boundaries — "12-7" ≠ "127" (#4034 I1)', async () => {
    // Canonical: "127". Typed: "12-7" → normalizes to "12 7", must NOT match.
    const question: ASGFQuizQuestion = {
      question_text: 'What is the number?',
      options: ['127', '', '', ''],
      correct_index: 0,
      bloom_tier: 'recall',
      slide_reference: 0,
      hint_text: 'One hundred twenty-seven.',
      explanation: '127 is the answer.',
      format: 'fill_blank',
    };

    render(<ASGFQuizBridge questions={[question]} sessionId="s-4034-127" />);
    const input = screen.getByLabelText(/your answer/i) as HTMLInputElement;
    const user = userEvent.setup();
    await user.type(input, '12-7');
    await user.click(screen.getByRole('button', { name: /submit answer/i }));

    await waitFor(() => {
      expect(screen.getByRole('status', { name: /hint for attempt/i })).toBeInTheDocument();
    });
    expect(screen.queryByText('Why correct')).not.toBeInTheDocument();
  });

  it('fill_blank: normalizer converts comma to space — "Ontario, Canada" matches "ontario canada" (#4034 I1)', async () => {
    const question: ASGFQuizQuestion = {
      question_text: 'Where is Toronto?',
      options: ['ontario canada', '', '', ''],
      correct_index: 0,
      bloom_tier: 'recall',
      slide_reference: 0,
      hint_text: 'Province, Country.',
      explanation: 'Toronto is in Ontario, Canada.',
      format: 'fill_blank',
    };

    render(<ASGFQuizBridge questions={[question]} sessionId="s-4034-ontario" />);
    const input = screen.getByLabelText(/your answer/i) as HTMLInputElement;
    const user = userEvent.setup();
    await user.type(input, 'Ontario, Canada');
    await user.click(screen.getByRole('button', { name: /submit answer/i }));

    // "Ontario, Canada" → "ontario canada" (comma → space, then collapsed).
    await waitFor(() => {
      expect(screen.getByText('Why correct')).toBeInTheDocument();
    });
  });

  it('true_false: after correct answer, the other option is disabled (#4030 I7)', async () => {
    const question: ASGFQuizQuestion = {
      question_text: 'The sky is blue.',
      options: ['True', 'False'],
      correct_index: 0,
      bloom_tier: 'recall',
      slide_reference: 0,
      hint_text: 'Look outside.',
      explanation: 'On a clear day, the sky appears blue.',
      format: 'true_false',
    };

    render(<ASGFQuizBridge questions={[question]} sessionId="s-tf-disable" />);

    const trueBtn = screen.getByRole('radio', { name: 'True' });
    const falseBtn = screen.getByRole('radio', { name: 'False' });

    const user = userEvent.setup();
    await user.click(trueBtn);

    await waitFor(() => {
      expect(screen.getByText('Why correct')).toBeInTheDocument();
    });

    // Both the correct AND the non-correct button must be disabled after success
    expect(trueBtn).toBeDisabled();
    expect(falseBtn).toBeDisabled();
  });

  it('multiple_choice: after correct answer, all other options are disabled (#4030 I7)', async () => {
    render(<ASGFQuizBridge questions={[baseMCQ]} sessionId="s-mcq-disable" />);

    const optA = screen.getByRole('radio', { name: /Option A: 3/ });
    const optB = screen.getByRole('radio', { name: /Option B: 4/ });
    const optC = screen.getByRole('radio', { name: /Option C: 5/ });
    const optD = screen.getByRole('radio', { name: /Option D: 6/ });

    const user = userEvent.setup();
    await user.click(optB); // correct

    await waitFor(() => {
      expect(screen.getByText('Why correct')).toBeInTheDocument();
    });

    // All 4 options disabled after correct answer
    expect(optA).toBeDisabled();
    expect(optB).toBeDisabled();
    expect(optC).toBeDisabled();
    expect(optD).toBeDisabled();
  });

  it('fill_blank uses maxLength=200 while short_answer uses maxLength=500 (#4030 S4)', () => {
    const fillBlank: ASGFQuizQuestion = {
      question_text: 'Capital?',
      options: ['Paris', '', '', ''],
      correct_index: 0,
      bloom_tier: 'recall',
      slide_reference: 0,
      hint_text: 'h',
      explanation: 'e',
      format: 'fill_blank',
    };
    const { unmount } = render(
      <ASGFQuizBridge questions={[fillBlank]} sessionId="s-max-fb" />,
    );
    const fbInput = screen.getByLabelText(/your answer/i) as HTMLInputElement;
    expect(fbInput.maxLength).toBe(200);
    unmount();

    const shortAnswer: ASGFQuizQuestion = {
      ...fillBlank,
      format: 'short_answer',
    };
    render(<ASGFQuizBridge questions={[shortAnswer]} sessionId="s-max-sa" />);
    const saInput = screen.getByLabelText(/your answer/i) as HTMLInputElement;
    expect(saInput.maxLength).toBe(500);
  });

  it('multiple_choice (default, no format field): still renders A/B/C/D (regression)', async () => {
    render(
      <ASGFQuizBridge questions={[baseMCQ]} sessionId="s-3" />,
    );
    expect(screen.getByRole('radio', { name: /Option A: 3/ })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /Option B: 4/ })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /Option C: 5/ })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /Option D: 6/ })).toBeInTheDocument();
  });
});
