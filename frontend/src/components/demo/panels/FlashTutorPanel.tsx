import { FlashcardDeck } from '../FlashcardDeck';
import { PanelFrame } from './panelShared';
import type { DemoPanelProps } from './panelTypes';

/**
 * Flash Tutor panel (#3786 owner).
 *
 * Foundation scaffold only — renders the same UI as the pre-refactor
 * `InstantTrialGenerateStep.activeTab === 'flash_tutor'` branch, using the
 * existing `FlashcardDeck` component.
 */
export function FlashTutorPanel({ state, onGenerate, generateDisabled }: DemoPanelProps) {
  return (
    <PanelFrame
      demoType="flash_tutor"
      state={state}
      onGenerate={onGenerate}
      generateDisabled={generateDisabled}
      renderOutput={(s) => (
        <FlashcardDeck rawText={s.output} isStreaming={s.status === 'streaming'} />
      )}
    />
  );
}

export default FlashTutorPanel;
