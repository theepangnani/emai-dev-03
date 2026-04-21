import type { DemoType } from '../../../api/demo';
import type { QuestId } from './useDemoGameState';

export interface DemoQuestTrackerProps {
  completedQuests: Set<QuestId>;
}

const QUEST_ORDER: { id: DemoType; label: string }[] = [
  { id: 'ask', label: 'Ask' },
  { id: 'study_guide', label: 'Study Guide' },
  { id: 'flash_tutor', label: 'Flash Tutor' },
];

/**
 * Gamification primitive — quest tracker (CB-DEMO-001 foundation).
 *
 * Scaffold only: renders 3 diamond dots, filled when that demo's quest is
 * complete. Wave 2 streams will add tooltips, glow animations, and the
 * "all three done" celebration.
 */
export function DemoQuestTracker({ completedQuests }: DemoQuestTrackerProps) {
  const completedCount = QUEST_ORDER.filter((q) => completedQuests.has(q.id)).length;
  return (
    <div
      className="demo-quest-tracker"
      role="group"
      aria-label={`Quests completed: ${completedCount} of ${QUEST_ORDER.length}`}
    >
      {QUEST_ORDER.map(({ id, label }) => {
        const done = completedQuests.has(id);
        return (
          <span
            key={id}
            className={`demo-quest-dot${done ? ' demo-quest-dot--done' : ''}`}
            aria-label={`${label}${done ? ' — completed' : ''}`}
            title={label}
          />
        );
      })}
    </div>
  );
}

export default DemoQuestTracker;
