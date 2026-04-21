import { MarkdownOutput, PanelFrame } from './panelShared';
import type { DemoPanelProps } from './panelTypes';

export interface AskPanelProps extends DemoPanelProps {
  question: string;
  onQuestionChange: (q: string) => void;
}

/**
 * Ask panel (#3784 owner).
 *
 * Foundation scaffold only — renders the same UI as the pre-refactor
 * `InstantTrialGenerateStep.activeTab === 'ask'` branch. State lives in the
 * orchestrator so the per-tab cache (#3762) is preserved across tab switches.
 */
export function AskPanel({
  state,
  question,
  onQuestionChange,
  onGenerate,
  generateDisabled,
}: AskPanelProps) {
  return (
    <>
      <div className="demo-form-group">
        <label htmlFor="demo-question">Your question</label>
        <input
          id="demo-question"
          type="text"
          value={question}
          onChange={(e) => onQuestionChange(e.target.value)}
          maxLength={500}
        />
      </div>

      <PanelFrame
        demoType="ask"
        state={state}
        onGenerate={onGenerate}
        generateDisabled={generateDisabled}
        renderOutput={(s) => <MarkdownOutput state={s} />}
      />
    </>
  );
}

export default AskPanel;
