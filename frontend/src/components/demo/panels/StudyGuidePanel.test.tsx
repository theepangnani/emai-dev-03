import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { StudyGuidePanel } from './StudyGuidePanel';
import type { PanelStreamState } from './panelTypes';

function makeState(overrides: Partial<PanelStreamState> = {}): PanelStreamState {
  return {
    output: '',
    status: 'idle',
    error: '',
    ...overrides,
  };
}

describe('StudyGuidePanel (#3787)', () => {
  it('renders the highlighter-yellow topic title', () => {
    render(
      <StudyGuidePanel
        sessionJwt="jwt"
        sourceText="sample"
        state={makeState()}
        onGenerate={() => {}}
        topic="Photosynthesis"
        activeTab="study_guide"
        onNavigateToTab={() => {}}
      />,
    );
    const heading = screen.getByRole('heading', { level: 3 });
    expect(heading.textContent).toMatch(/Study guide/i);
    expect(heading.textContent).toMatch(/Photosynthesis/);
    // Highlighter-yellow emphasis is applied to the topic span specifically.
    const topicSpan = heading.querySelector('.demo-sg-title-topic');
    expect(topicSpan?.textContent).toBe('Photosynthesis');
  });

  it('does not render chips until the overview is done', () => {
    render(
      <StudyGuidePanel
        sessionJwt="jwt"
        sourceText="sample"
        state={makeState({ status: 'streaming', output: 'overview in progress...' })}
        onGenerate={() => {}}
        topic="Photosynthesis"
        activeTab="study_guide"
        onNavigateToTab={() => {}}
      />,
    );
    expect(screen.queryByRole('group', { name: /study guide next steps/i })).toBeNull();
  });

  it('renders the 5 chips and the overview once status is done', () => {
    render(
      <StudyGuidePanel
        sessionJwt="jwt"
        sourceText="sample"
        state={makeState({ status: 'done', output: 'A concise overview.' })}
        onGenerate={() => {}}
        topic="Photosynthesis"
        activeTab="study_guide"
        onNavigateToTab={() => {}}
      />,
    );

    expect(screen.getByText('A concise overview.')).toBeInTheDocument();

    const grid = screen.getByRole('group', { name: /study guide next steps/i });
    expect(grid).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /generate a worksheet/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /make a quiz/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /create flashcards/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /go deeper on this topic/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /ask a follow-up/i })).toBeInTheDocument();
  });

  it('opens a scoped upsell when a gated chip is clicked and fires onChipCuriosity once', async () => {
    const user = userEvent.setup();
    const onChipCuriosity = vi.fn();
    render(
      <StudyGuidePanel
        sessionJwt="jwt"
        sourceText="sample"
        state={makeState({ status: 'done', output: 'Overview.' })}
        onGenerate={() => {}}
        topic="Photosynthesis"
        activeTab="study_guide"
        onChipCuriosity={onChipCuriosity}
        onNavigateToTab={() => {}}
      />,
    );

    const worksheetChip = screen.getByRole('button', { name: /generate a worksheet/i });
    await user.click(worksheetChip);

    expect(screen.getByRole('region', { name: /unlock (ai|flashcard|topic)/i })).toBeInTheDocument();
    expect(screen.getByText(/Unlock AI worksheets/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /join the waitlist/i })).toHaveAttribute(
      'href',
      '/waitlist',
    );
    expect(onChipCuriosity).toHaveBeenCalledTimes(1);
    expect(onChipCuriosity).toHaveBeenCalledWith('worksheet');

    // Re-opening the same chip (toggle close then reopen) must NOT fire curiosity again.
    await user.click(worksheetChip); // close
    await user.click(worksheetChip); // reopen
    expect(onChipCuriosity).toHaveBeenCalledTimes(1);
  });

  it('closes the upsell when the close button is clicked', async () => {
    const user = userEvent.setup();
    render(
      <StudyGuidePanel
        sessionJwt="jwt"
        sourceText="sample"
        state={makeState({ status: 'done', output: 'Overview.' })}
        onGenerate={() => {}}
        topic="Photosynthesis"
        activeTab="study_guide"
        onNavigateToTab={() => {}}
      />,
    );

    await user.click(screen.getByRole('button', { name: /make a quiz/i }));
    expect(screen.getByRole('region', { name: /unlock (ai|flashcard|topic)/i })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /close upsell/i }));
    expect(screen.queryByRole('region', { name: /unlock (ai|flashcard|topic)/i })).toBeNull();
  });

  it('invokes onNavigateToTab("ask") when "Ask a follow-up" is clicked and does NOT open an upsell', async () => {
    const user = userEvent.setup();
    const onNavigateToTab = vi.fn();
    const onChipCuriosity = vi.fn();
    render(
      <StudyGuidePanel
        sessionJwt="jwt"
        sourceText="sample"
        state={makeState({ status: 'done', output: 'Overview.' })}
        onGenerate={() => {}}
        topic="Photosynthesis"
        activeTab="study_guide"
        onChipCuriosity={onChipCuriosity}
        onNavigateToTab={onNavigateToTab}
      />,
    );

    await user.click(screen.getByRole('button', { name: /ask a follow-up/i }));
    expect(onNavigateToTab).toHaveBeenCalledWith('ask');
    expect(screen.queryByRole('region', { name: /unlock (ai|flashcard|topic)/i })).toBeNull();
    expect(onChipCuriosity).not.toHaveBeenCalled();
  });

  it('dismisses an open upsell when activeTab changes', async () => {
    const user = userEvent.setup();
    const { rerender } = render(
      <StudyGuidePanel
        sessionJwt="jwt"
        sourceText="sample"
        state={makeState({ status: 'done', output: 'Overview.' })}
        onGenerate={() => {}}
        topic="Photosynthesis"
        activeTab="study_guide"
        onNavigateToTab={() => {}}
      />,
    );

    await user.click(screen.getByRole('button', { name: /create flashcards/i }));
    expect(screen.getByRole('region', { name: /unlock (ai|flashcard|topic)/i })).toBeInTheDocument();

    rerender(
      <StudyGuidePanel
        sessionJwt="jwt"
        sourceText="sample"
        state={makeState({ status: 'done', output: 'Overview.' })}
        onGenerate={() => {}}
        topic="Photosynthesis"
        activeTab="ask"
        onNavigateToTab={() => {}}
      />,
    );

    expect(screen.queryByRole('region', { name: /unlock (ai|flashcard|topic)/i })).toBeNull();
  });

  it('closes the upsell when Esc is pressed while focus is inside', async () => {
    const user = userEvent.setup();
    render(
      <StudyGuidePanel
        sessionJwt="jwt"
        sourceText="sample"
        state={makeState({ status: 'done', output: 'Overview.' })}
        onGenerate={() => {}}
        topic="Photosynthesis"
        activeTab="study_guide"
        onNavigateToTab={() => {}}
      />,
    );

    await user.click(screen.getByRole('button', { name: /go deeper on this topic/i }));
    expect(screen.getByRole('region', { name: /unlock (ai|flashcard|topic)/i })).toBeInTheDocument();

    await user.keyboard('{Escape}');
    expect(screen.queryByRole('region', { name: /unlock (ai|flashcard|topic)/i })).toBeNull();
  });

  it('chips expose aria-describedby scope hints', () => {
    render(
      <StudyGuidePanel
        sessionJwt="jwt"
        sourceText="sample"
        state={makeState({ status: 'done', output: 'Overview.' })}
        onGenerate={() => {}}
        topic="Photosynthesis"
        activeTab="study_guide"
        onNavigateToTab={() => {}}
      />,
    );

    const worksheetChip = screen.getByRole('button', { name: /generate a worksheet/i });
    expect(worksheetChip).toHaveAttribute('aria-describedby', 'demo-sg-chip-desc-worksheet');
    expect(document.getElementById('demo-sg-chip-desc-worksheet')).toHaveTextContent(
      /unlocks with waitlist/i,
    );

    const followupChip = screen.getByRole('button', { name: /ask a follow-up/i });
    expect(followupChip).toHaveAttribute('aria-describedby', 'demo-sg-chip-desc-followup');
    expect(document.getElementById('demo-sg-chip-desc-followup')).toHaveTextContent(
      /free — switches to Ask tab/i,
    );
  });
});
