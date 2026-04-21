/**
 * Tests for useDemoGameState (CB-DEMO-001 foundation, epic #3599).
 *
 * We exercise the pure reducer for determinism; the hook is a thin
 * `useReducer` + `useCallback` wrapper, so reducer coverage is enough.
 */
import { describe, expect, it } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import {
  DEMO_GAME_XP_MAX,
  demoGameReducer,
  initialDemoGameState,
  useDemoGameState,
} from './useDemoGameState';

describe('demoGameReducer — XP', () => {
  it('starts at 0 XP, level 1', () => {
    const s = initialDemoGameState();
    expect(s.xp).toBe(0);
    expect(s.level).toBe(1);
  });

  it('caps XP at 100 even on large awards', () => {
    const s0 = initialDemoGameState();
    const s1 = demoGameReducer(s0, { type: 'AWARD_XP', amount: 999 });
    expect(s1.xp).toBe(DEMO_GAME_XP_MAX);
  });

  it('accumulates XP additively below the cap', () => {
    let s = initialDemoGameState();
    s = demoGameReducer(s, { type: 'AWARD_XP', amount: 30 });
    s = demoGameReducer(s, { type: 'AWARD_XP', amount: 20 });
    expect(s.xp).toBe(50);
  });

  it('flips level to 2 when XP reaches 100', () => {
    let s = initialDemoGameState();
    s = demoGameReducer(s, { type: 'AWARD_XP', amount: 99 });
    expect(s.level).toBe(1);
    s = demoGameReducer(s, { type: 'AWARD_XP', amount: 1 });
    expect(s.level).toBe(2);
    expect(s.xp).toBe(100);
  });

  it('stays at level 2 after further XP awards', () => {
    let s = initialDemoGameState();
    s = demoGameReducer(s, { type: 'AWARD_XP', amount: 100 });
    s = demoGameReducer(s, { type: 'AWARD_XP', amount: 50 });
    expect(s.level).toBe(2);
    expect(s.xp).toBe(100);
  });

  it('clamps negative awards at 0', () => {
    let s = initialDemoGameState();
    s = demoGameReducer(s, { type: 'AWARD_XP', amount: 20 });
    s = demoGameReducer(s, { type: 'AWARD_XP', amount: -999 });
    expect(s.xp).toBe(0);
  });
});

describe('demoGameReducer — streak', () => {
  it('increments streak', () => {
    let s = initialDemoGameState();
    s = demoGameReducer(s, { type: 'INCREMENT_STREAK' });
    s = demoGameReducer(s, { type: 'INCREMENT_STREAK' });
    expect(s.streak).toBe(2);
  });

  it('resets streak to 0', () => {
    let s = initialDemoGameState();
    s = demoGameReducer(s, { type: 'INCREMENT_STREAK' });
    s = demoGameReducer(s, { type: 'INCREMENT_STREAK' });
    s = demoGameReducer(s, { type: 'RESET_STREAK' });
    expect(s.streak).toBe(0);
  });
});

describe('demoGameReducer — achievements (additive)', () => {
  it('adds an achievement', () => {
    const s = demoGameReducer(initialDemoGameState(), {
      type: 'EARN_ACHIEVEMENT',
      id: 'first-spark',
    });
    expect(s.achievements.has('first-spark')).toBe(true);
  });

  it('de-dupes repeated achievements (additive + idempotent)', () => {
    let s = initialDemoGameState();
    s = demoGameReducer(s, { type: 'EARN_ACHIEVEMENT', id: 'first-spark' });
    s = demoGameReducer(s, { type: 'EARN_ACHIEVEMENT', id: 'first-spark' });
    expect(s.achievements.size).toBe(1);
  });

  it('keeps previously earned achievements when adding new ones', () => {
    let s = initialDemoGameState();
    s = demoGameReducer(s, { type: 'EARN_ACHIEVEMENT', id: 'first-spark' });
    s = demoGameReducer(s, { type: 'EARN_ACHIEVEMENT', id: 'bullseye' });
    expect(s.achievements.has('first-spark')).toBe(true);
    expect(s.achievements.has('bullseye')).toBe(true);
    expect(s.achievements.size).toBe(2);
  });
});

describe('demoGameReducer — quests (additive)', () => {
  it('marks a quest complete', () => {
    const s = demoGameReducer(initialDemoGameState(), { type: 'MARK_QUEST', quest: 'ask' });
    expect(s.completedQuests.has('ask')).toBe(true);
  });

  it('de-dupes repeated quest marks', () => {
    let s = initialDemoGameState();
    s = demoGameReducer(s, { type: 'MARK_QUEST', quest: 'ask' });
    s = demoGameReducer(s, { type: 'MARK_QUEST', quest: 'ask' });
    expect(s.completedQuests.size).toBe(1);
  });

  it('accumulates multiple quests', () => {
    let s = initialDemoGameState();
    s = demoGameReducer(s, { type: 'MARK_QUEST', quest: 'ask' });
    s = demoGameReducer(s, { type: 'MARK_QUEST', quest: 'study_guide' });
    s = demoGameReducer(s, { type: 'MARK_QUEST', quest: 'flash_tutor' });
    expect(s.completedQuests.size).toBe(3);
  });
});

describe('demoGameReducer — resetAll', () => {
  it('returns to the initial state', () => {
    let s = initialDemoGameState();
    s = demoGameReducer(s, { type: 'AWARD_XP', amount: 50 });
    s = demoGameReducer(s, { type: 'INCREMENT_STREAK' });
    s = demoGameReducer(s, { type: 'MARK_QUEST', quest: 'ask' });
    s = demoGameReducer(s, { type: 'EARN_ACHIEVEMENT', id: 'first-spark' });
    const reset = demoGameReducer(s, { type: 'RESET_ALL' });
    expect(reset.xp).toBe(0);
    expect(reset.level).toBe(1);
    expect(reset.streak).toBe(0);
    expect(reset.completedQuests.size).toBe(0);
    expect(reset.achievements.size).toBe(0);
  });
});

describe('useDemoGameState hook', () => {
  it('exposes action creators that mutate state via dispatch', () => {
    const { result } = renderHook(() => useDemoGameState());
    expect(result.current.state.xp).toBe(0);

    act(() => result.current.actions.awardXP(40));
    expect(result.current.state.xp).toBe(40);

    act(() => result.current.actions.markQuest('ask'));
    expect(result.current.state.completedQuests.has('ask')).toBe(true);

    act(() => result.current.actions.incrementStreak());
    act(() => result.current.actions.incrementStreak());
    expect(result.current.state.streak).toBe(2);

    act(() => result.current.actions.earnAchievement('levelup'));
    expect(result.current.state.achievements.has('levelup')).toBe(true);

    act(() => result.current.actions.resetStreak());
    expect(result.current.state.streak).toBe(0);

    act(() => result.current.actions.resetAll());
    expect(result.current.state.xp).toBe(0);
    expect(result.current.state.completedQuests.size).toBe(0);
    expect(result.current.state.achievements.size).toBe(0);
  });

  it('flips level to 2 when XP≥100 via the hook', () => {
    const { result } = renderHook(() => useDemoGameState());
    act(() => result.current.actions.awardXP(100));
    expect(result.current.state.level).toBe(2);
  });
});
