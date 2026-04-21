import { useCallback, useReducer } from 'react';
import type { DemoType } from '../../../api/demo';

/**
 * Demo gamification game state (CB-DEMO-001 foundation, epic #3599).
 *
 * This is the rails for the four Wave 2 feature streams — XP bar, quest
 * tracker, streak flame, achievement stickers, level-up overlay. The foundation
 * PR only ships the state machine + primitive scaffolds; feature streams wire
 * the visible polish on top.
 *
 * Design decisions:
 * - XP caps at 100 (one level-up).
 * - Level flips to 2 as soon as XP reaches 100.
 * - `completedQuests` and `achievements` are Sets so "mark again" is a no-op.
 * - `resetAll()` returns to the initial state for re-opening the modal fresh.
 */

export type AchievementId = 'first-spark' | 'bullseye' | 'warmup' | 'triple' | 'levelup';
export type QuestId = DemoType;
export type DemoLevel = 1 | 2;

const XP_MAX = 100;

export interface DemoGameState {
  xp: number;
  level: DemoLevel;
  streak: number;
  completedQuests: Set<QuestId>;
  achievements: Set<AchievementId>;
}

type Action =
  | { type: 'AWARD_XP'; amount: number }
  | { type: 'MARK_QUEST'; quest: QuestId }
  | { type: 'INCREMENT_STREAK' }
  | { type: 'RESET_STREAK' }
  | { type: 'EARN_ACHIEVEMENT'; id: AchievementId }
  | { type: 'RESET_ALL' };

export function initialDemoGameState(): DemoGameState {
  return {
    xp: 0,
    level: 1,
    streak: 0,
    completedQuests: new Set(),
    achievements: new Set(),
  };
}

export function demoGameReducer(state: DemoGameState, action: Action): DemoGameState {
  switch (action.type) {
    case 'AWARD_XP': {
      const next = Math.min(XP_MAX, Math.max(0, state.xp + action.amount));
      return {
        ...state,
        xp: next,
        level: next >= XP_MAX ? 2 : state.level,
      };
    }
    case 'MARK_QUEST': {
      if (state.completedQuests.has(action.quest)) return state;
      const next = new Set(state.completedQuests);
      next.add(action.quest);
      return { ...state, completedQuests: next };
    }
    case 'INCREMENT_STREAK':
      return { ...state, streak: state.streak + 1 };
    case 'RESET_STREAK':
      return { ...state, streak: 0 };
    case 'EARN_ACHIEVEMENT': {
      if (state.achievements.has(action.id)) return state;
      const next = new Set(state.achievements);
      next.add(action.id);
      return { ...state, achievements: next };
    }
    case 'RESET_ALL':
      return initialDemoGameState();
    default:
      return state;
  }
}

export interface DemoGameActions {
  awardXP: (amount: number) => void;
  markQuest: (tab: QuestId) => void;
  incrementStreak: () => void;
  resetStreak: () => void;
  earnAchievement: (id: AchievementId) => void;
  resetAll: () => void;
}

export interface UseDemoGameStateResult {
  state: DemoGameState;
  actions: DemoGameActions;
}

export function useDemoGameState(): UseDemoGameStateResult {
  const [state, dispatch] = useReducer(demoGameReducer, undefined, initialDemoGameState);

  const awardXP = useCallback((amount: number) => dispatch({ type: 'AWARD_XP', amount }), []);
  const markQuest = useCallback(
    (tab: QuestId) => dispatch({ type: 'MARK_QUEST', quest: tab }),
    [],
  );
  const incrementStreak = useCallback(() => dispatch({ type: 'INCREMENT_STREAK' }), []);
  const resetStreak = useCallback(() => dispatch({ type: 'RESET_STREAK' }), []);
  const earnAchievement = useCallback(
    (id: AchievementId) => dispatch({ type: 'EARN_ACHIEVEMENT', id }),
    [],
  );
  const resetAll = useCallback(() => dispatch({ type: 'RESET_ALL' }), []);

  return {
    state,
    actions: { awardXP, markQuest, incrementStreak, resetStreak, earnAchievement, resetAll },
  };
}

export const DEMO_GAME_XP_MAX = XP_MAX;
