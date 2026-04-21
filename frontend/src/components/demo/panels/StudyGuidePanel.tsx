import { MarkdownOutput, PanelFrame } from './panelShared';
import type { DemoPanelProps } from './panelTypes';

/**
 * Study Guide panel (#3785 owner).
 *
 * Foundation scaffold only — renders the same UI as the pre-refactor
 * `InstantTrialGenerateStep.activeTab === 'study_guide'` branch.
 */
export function StudyGuidePanel({ state, onGenerate }: DemoPanelProps) {
  return (
    <PanelFrame
      demoType="study_guide"
      state={state}
      onGenerate={onGenerate}
      renderOutput={(s) => <MarkdownOutput state={s} />}
    />
  );
}

export default StudyGuidePanel;
