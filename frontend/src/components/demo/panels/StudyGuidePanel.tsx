import { MarkdownOutput, PanelFrame } from './panelShared';
import type { DemoPanelProps } from './panelTypes';
import { DemoStudyGuideChips, type ChipId } from './study/DemoStudyGuideChips';

/**
 * Study Guide panel (#3787 owner).
 *
 * Renders:
 *   [Topic title — "Study guide — <topic>" with highlighter-yellow emphasis]
 *   [Overview paragraph streamed from /demo/generate]
 *   [Chip grid — 5 chips with scoped waitlist upsells or Ask-tab hand-off]
 *
 * Gamification wiring:
 *   - Overview finishes streaming → orchestrator's existing
 *     `onTabGenerated('study_guide')` path (awards XP + marks quest +
 *     earns first-spark in the modal).
 *   - Gated chip opens its upsell → onChipCuriosity(id)
 *     (parent awards small XP, max once per chip per session).
 *   - "Ask a follow-up" chip → onNavigateToTab('ask'). No XP here — the
 *     Ask turn will award.
 */
export interface StudyGuidePanelProps extends DemoPanelProps {
  /** Topic label rendered in the highlighter-yellow title. */
  topic: string;
  /** Orchestrator-owned active tab — used by chips to dismiss on change. */
  activeTab: string;
  /** Fired when a gated chip opens its scoped upsell. */
  onChipCuriosity?: (id: Exclude<ChipId, 'followup'>) => void;
  /** Switches the demo modal to another tab. */
  onNavigateToTab: (tab: 'ask' | 'study_guide' | 'flash_tutor') => void;
}

export function StudyGuidePanel({
  state,
  onGenerate,
  generateDisabled,
  topic,
  activeTab,
  onChipCuriosity,
  onNavigateToTab,
}: StudyGuidePanelProps) {
  return (
    <>
      <div className="demo-sg-title-row">
        <h3 className="demo-sg-title">
          <span className="demo-sg-title-prefix">Study guide &mdash;&nbsp;</span>
          <span className="demo-sg-title-topic">{topic}</span>
        </h3>
      </div>

      <PanelFrame
        demoType="study_guide"
        state={state}
        onGenerate={onGenerate}
        generateDisabled={generateDisabled}
        renderOutput={(s) => <MarkdownOutput state={s} />}
      />

      {state.status === 'done' && (
        <DemoStudyGuideChips
          activeTab={activeTab}
          onChipOpen={onChipCuriosity}
          onAskFollowUp={() => onNavigateToTab('ask')}
        />
      )}
    </>
  );
}

export default StudyGuidePanel;
