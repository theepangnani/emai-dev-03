import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { FlashTutorPanel } from './FlashTutorPanel';
import type { PanelStreamState } from './panelTypes';
import type { DemoGameActions } from '../gamification/useDemoGameState';

const THREE_CARDS = JSON.stringify([
  { front: 'What is a cell?', back: 'The smallest living unit of an organism.' },
  { front: 'What does the nucleus do?', back: 'Controls cell activities and stores DNA.' },
  { front: 'What do mitochondria do?', back: 'Release energy from food.' },
]);

function makeState(overrides: Partial<PanelStreamState> = {}): PanelStreamState {
  return {
    output: THREE_CARDS,
    status: 'done',
    error: '',
    ...overrides,
  };
}

function makeGameActions(): DemoGameActions {
  return {
    awardXP: vi.fn(),
    markQuest: vi.fn(),
    incrementStreak: vi.fn(),
    resetStreak: vi.fn(),
    earnAchievement: vi.fn(),
    resetAll: vi.fn(),
  };
}

describe('FlashTutorPanel — rendering', () => {
  it('renders the Generate button when idle (no cycle yet)', () => {
    render(
      <FlashTutorPanel
        sessionJwt="jwt"
        sourceText="topic"
        state={{ output: '', status: 'idle', error: '' }}
        onGenerate={() => {}}
      />,
    );
    expect(
      screen.getByRole('button', { name: /generate flash tutor/i }),
    ).toBeInTheDocument();
    // No cycle chrome until output arrives.
    expect(
      screen.queryByRole('progressbar', { name: /mastery/i }),
    ).not.toBeInTheDocument();
  });

  it('renders the mastery ring, trail, and first card front on done', () => {
    render(
      <FlashTutorPanel
        sessionJwt="jwt"
        sourceText="topic"
        state={makeState()}
        onGenerate={() => {}}
      />,
    );
    expect(screen.getByRole('progressbar', { name: /mastery/i })).toBeInTheDocument();
    expect(screen.getByRole('list', { name: /mastery trail/i })).toBeInTheDocument();
    expect(screen.getByText(/card 1 of 3/i)).toBeInTheDocument();
    expect(screen.getByText('What is a cell?')).toBeInTheDocument();
  });
});

describe('FlashTutorPanel — flip + grade flow', () => {
  it('flip reveals the back; grade buttons appear only after flip', async () => {
    const user = userEvent.setup();
    render(
      <FlashTutorPanel
        sessionJwt="jwt"
        sourceText="topic"
        state={makeState()}
        onGenerate={() => {}}
      />,
    );

    // Grade buttons hidden before flip.
    expect(
      screen.queryByRole('group', { name: /self-grade/i }),
    ).not.toBeInTheDocument();

    const cardBtn = screen.getByRole('button', { name: /reveal answer/i });
    await user.click(cardBtn);

    // Back is visible.
    expect(screen.getByText('The smallest living unit of an organism.')).toBeInTheDocument();
    // Grade buttons now present.
    const group = screen.getByRole('group', { name: /self-grade/i });
    expect(within(group).getByRole('button', { name: /missed/i })).toBeInTheDocument();
    expect(within(group).getByRole('button', { name: /almost/i })).toBeInTheDocument();
    expect(within(group).getByRole('button', { name: /got it/i })).toBeInTheDocument();
  });

  it('grading "Got it" awards 15 XP, increments streak, advances to card 2', async () => {
    const user = userEvent.setup();
    const actions = makeGameActions();
    render(
      <FlashTutorPanel
        sessionJwt="jwt"
        sourceText="topic"
        state={makeState()}
        onGenerate={() => {}}
        gameActions={actions}
      />,
    );

    await user.click(screen.getByRole('button', { name: /reveal answer/i }));
    await user.click(screen.getByRole('button', { name: /got it/i }));

    expect(actions.awardXP).toHaveBeenCalledWith(15);
    expect(actions.incrementStreak).toHaveBeenCalledTimes(1);
    expect(actions.earnAchievement).toHaveBeenCalledWith('bullseye');

    // Advance delay is 500ms — wait for card 2.
    await waitFor(() => {
      expect(screen.getByText(/card 2 of 3/i)).toBeInTheDocument();
    });
    expect(screen.getByText('What does the nucleus do?')).toBeInTheDocument();
  });

  it('grading "Missed it" awards 5 XP and resets streak', async () => {
    const user = userEvent.setup();
    const actions = makeGameActions();
    render(
      <FlashTutorPanel
        sessionJwt="jwt"
        sourceText="topic"
        state={makeState()}
        onGenerate={() => {}}
        gameActions={actions}
      />,
    );

    await user.click(screen.getByRole('button', { name: /reveal answer/i }));
    await user.click(screen.getByRole('button', { name: /missed/i }));

    expect(actions.awardXP).toHaveBeenCalledWith(5);
    expect(actions.resetStreak).toHaveBeenCalledTimes(1);
    expect(actions.incrementStreak).not.toHaveBeenCalled();
  });

  it('grading "Almost" awards 10 XP and resets streak', async () => {
    const user = userEvent.setup();
    const actions = makeGameActions();
    render(
      <FlashTutorPanel
        sessionJwt="jwt"
        sourceText="topic"
        state={makeState()}
        onGenerate={() => {}}
        gameActions={actions}
      />,
    );

    await user.click(screen.getByRole('button', { name: /reveal answer/i }));
    await user.click(screen.getByRole('button', { name: /almost/i }));

    expect(actions.awardXP).toHaveBeenCalledWith(10);
    expect(actions.resetStreak).toHaveBeenCalledTimes(1);
  });

  it('two consecutive "Got it" grades fire the warmup achievement', async () => {
    const user = userEvent.setup();
    const actions = makeGameActions();
    render(
      <FlashTutorPanel
        sessionJwt="jwt"
        sourceText="topic"
        state={makeState()}
        onGenerate={() => {}}
        gameActions={actions}
      />,
    );

    await user.click(screen.getByRole('button', { name: /reveal answer/i }));
    await user.click(screen.getByRole('button', { name: /got it/i }));

    // Wait for card 2.
    await waitFor(() => {
      expect(screen.getByText(/card 2 of 3/i)).toBeInTheDocument();
    });
    await user.click(screen.getByRole('button', { name: /reveal answer/i }));
    await user.click(screen.getByRole('button', { name: /got it/i }));

    const achievements = (actions.earnAchievement as ReturnType<typeof vi.fn>).mock.calls.map(
      (c) => c[0],
    );
    expect(achievements).toContain('bullseye');
    expect(achievements).toContain('warmup');
  });

  it('grading all 3 cards marks the flash_tutor quest and shows the completion banner', async () => {
    const user = userEvent.setup();
    const actions = makeGameActions();
    render(
      <FlashTutorPanel
        sessionJwt="jwt"
        sourceText="topic"
        state={makeState()}
        onGenerate={() => {}}
        gameActions={actions}
      />,
    );

    // Card 1
    await user.click(screen.getByRole('button', { name: /reveal answer/i }));
    await user.click(screen.getByRole('button', { name: /got it/i }));
    await waitFor(() => {
      expect(screen.getByText(/card 2 of 3/i)).toBeInTheDocument();
    });
    // Card 2
    await user.click(screen.getByRole('button', { name: /reveal answer/i }));
    await user.click(screen.getByRole('button', { name: /almost/i }));
    await waitFor(() => {
      expect(screen.getByText(/card 3 of 3/i)).toBeInTheDocument();
    });
    // Card 3
    await user.click(screen.getByRole('button', { name: /reveal answer/i }));
    await user.click(screen.getByRole('button', { name: /missed/i }));

    await waitFor(() => {
      expect(actions.markQuest).toHaveBeenCalledWith('flash_tutor');
    });

    // Completion banner: "Nice run — you mastered 1 of 3."
    expect(screen.getByText(/nice run/i)).toBeInTheDocument();
    expect(screen.getByText(/mastered 1 of 3/i)).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: /join the waitlist/i }),
    ).toBeInTheDocument();

    // No grade buttons once done.
    expect(
      screen.queryByRole('group', { name: /self-grade/i }),
    ).not.toBeInTheDocument();
  });

  it('updates the mastery ring progressbar aria-valuenow after each grade', async () => {
    const user = userEvent.setup();
    render(
      <FlashTutorPanel
        sessionJwt="jwt"
        sourceText="topic"
        state={makeState()}
        onGenerate={() => {}}
      />,
    );

    const ring = screen.getByRole('progressbar', { name: /mastery/i });
    expect(ring).toHaveAttribute('aria-valuenow', '0');
    expect(ring).toHaveAttribute('aria-valuemax', '3');

    await user.click(screen.getByRole('button', { name: /reveal answer/i }));
    await user.click(screen.getByRole('button', { name: /got it/i }));

    await waitFor(() => {
      expect(screen.getByRole('progressbar', { name: /mastery/i })).toHaveAttribute(
        'aria-valuenow',
        '1',
      );
    });
  });
});
