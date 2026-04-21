import type { DemoType } from '../../../api/demo';
import type { StreamStatus } from '../instantTrialHelpers';

/**
 * Shared streaming-state shape used by every panel (#3784, #3785, #3786,
 * #3787 foundation). Kept in the orchestrator so per-tab output survives tab
 * switches (#3762 per-tab cache).
 */
export interface PanelStreamState {
  output: string;
  status: StreamStatus;
  error: string;
}

export const INITIAL_PANEL_STREAM_STATE: PanelStreamState = {
  output: '',
  status: 'idle',
  error: '',
};

/**
 * Base props every panel accepts. The orchestrator owns the streaming state
 * and `streamGenerate` invocation — this lets it preserve cache across tab
 * switches and pass a single `onGenerated(demoType)` callback for the
 * gamification hooks.
 *
 * `onGenerated` is wired at the panel prop level for forward-compatibility:
 * today the orchestrator fires a single `onTabGenerated` via `runGenerate`'s
 * `onDone`; Wave 2 feature streams that move streaming into individual
 * panels will fire it from the panel itself (at which point the orchestrator
 * must stop firing it to avoid a double-fire).
 */
export interface DemoPanelProps {
  sessionJwt: string;
  sourceText: string;
  state: PanelStreamState;
  onGenerate: () => void;
  /** Disable the Generate button (e.g. source over the 500-word limit). */
  generateDisabled?: boolean;
  onGenerated?: (demoType: DemoType) => void;
}
