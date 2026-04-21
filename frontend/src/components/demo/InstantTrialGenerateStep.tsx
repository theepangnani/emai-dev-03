import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { streamGenerate, type DemoType } from '../../api/demo';
import { ConversionCard } from './ConversionCard';
import { SourcePicker, type SourceKind } from './SourcePicker';
import { AskPanel } from './panels/AskPanel';
import { StudyGuidePanel } from './panels/StudyGuidePanel';
import { FlashTutorPanel } from './panels/FlashTutorPanel';
import type { ChipId } from './panels/study/DemoStudyGuideChips';
import { INITIAL_PANEL_STREAM_STATE, type PanelStreamState } from './panels/panelTypes';
import { SAMPLE_TEXT, SAMPLE_TITLE, TABS, countWords } from './demoSamples';
import { TAB_META } from './instantTrialHelpers';
import type { DemoGameActions, DemoGameState } from './gamification/useDemoGameState';

interface Props {
  sessionJwt: string;
  waitlistPreviewPosition: number;
  onVerify: () => void;
  /**
   * Optional hook for Wave 2 feature streams — fires whenever a tab's
   * generation finishes successfully. The foundation PR wires the modal
   * header's game-state hook through this; feature streams will award XP,
   * mark quests, and trigger achievements from here.
   */
  onTabGenerated?: (tab: DemoType) => void;
  /**
   * Study-guide-specific curiosity reward hook (#3787) — fires when the
   * user opens a gated chip's scoped upsell. Max once per chip per session
   * is enforced inside `DemoStudyGuideChips`.
   */
  onStudyGuideChipCuriosity?: (id: Exclude<ChipId, 'followup'>) => void;
  /**
   * Optional gamification state + actions. Used by:
   *   - FlashTutorPanel (#3786) for per-card XP + streaks + achievements.
   *   - AskPanel (§6.135.5, #3785) for per-turn XP + first-spark. The
   *     panel reads ``gameState.xp`` to detect whether the session has
   *     earned any XP yet (drives the first-spark achievement).
   * Panels that don't accept these simply ignore them.
   */
  gameState?: DemoGameState;
  gameActions?: DemoGameActions;
}

type PerTabStreamState = Record<DemoType, PanelStreamState>;

/** Factory so reset paths never accidentally share object identity. */
function buildInitialStreams(): PerTabStreamState {
  return {
    ask: { ...INITIAL_PANEL_STREAM_STATE },
    study_guide: { ...INITIAL_PANEL_STREAM_STATE },
    flash_tutor: { ...INITIAL_PANEL_STREAM_STATE },
  };
}

/**
 * Derive the Study Guide title from the current source (#3787).
 * - Sample source → the canonical SAMPLE_TITLE.
 * - Paste with content → the first line of the paste, clipped to 60 chars.
 * - Empty paste → fall back to SAMPLE_TITLE so the title is never blank.
 */
const TOPIC_MAX_LEN = 60;
function deriveStudyGuideTopic(source: SourceKind, customText: string): string {
  if (source === 'paste') {
    const trimmed = customText.trim();
    if (trimmed) {
      // Strip leading markdown heading markers (e.g. `# `, `## `) so a pasted
      // title renders as "Study guide — My Topic" not "# My Topic".
      const firstLine = trimmed.split('\n')[0].trim().replace(/^#+\s*/, '');
      if (firstLine) {
        return firstLine.length > TOPIC_MAX_LEN
          ? firstLine.slice(0, TOPIC_MAX_LEN - 1) + '\u2026'
          : firstLine;
      }
    }
  }
  return SAMPLE_TITLE;
}

/**
 * Orchestrator for the three demo tabs.
 *
 * Post-refactor responsibilities (CB-DEMO-001 foundation):
 *   - Tab selection + shared chrome (tab row, source picker, conversion card).
 *   - Owns per-tab streaming state so output survives tab switches (#3762).
 *   - Delegates per-tab rendering to panel components:
 *       AskPanel / StudyGuidePanel / FlashTutorPanel.
 *   - Exposes `onTabGenerated` so the modal's game-state hook can react.
 *
 * Special case: the Ask tab (§6.135.5, #3785) is a self-contained multi-
 * turn chatbox and owns its own streaming + per-turn state. The orches-
 * trator only tracks whether any Ask turn has completed (via the
 * ``onTurnComplete`` callback) so the conversion card + "try another"
 * chips still appear at the right moment.
 */
export function InstantTrialGenerateStep({
  sessionJwt,
  waitlistPreviewPosition,
  onVerify,
  onTabGenerated,
  onStudyGuideChipCuriosity,
  gameState,
  gameActions,
}: Props) {
  const [activeTab, setActiveTab] = useState<DemoType>('ask');
  const [source, setSource] = useState<SourceKind>('sample');
  const [customText, setCustomText] = useState('');
  // Lazy init — avoid allocating a fresh initial object on every render.
  const [streams, setStreams] = useState<PerTabStreamState>(buildInitialStreams);
  // Bumped on source change so AskPanel clears its thread in lockstep
  // with the study_guide / flash_tutor per-tab streams.
  const [askResetKey, setAskResetKey] = useState(0);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const resetAllStreams = useCallback(() => {
    abortRef.current?.abort();
    setStreams(buildInitialStreams());
    setAskResetKey((k) => k + 1);
  }, []);

  const handleSourceChange = (next: SourceKind) => {
    setSource(next);
    resetAllStreams();
  };

  const handleCustomTextChange = (text: string) => {
    setCustomText(text);
    if (source === 'paste') resetAllStreams();
  };

  const wordCount = countWords(customText);
  const overLimit = wordCount > 500;
  const sourceText =
    source === 'paste' && customText.trim() ? customText.trim() : SAMPLE_TEXT;

  const runGenerate = useCallback(
    (tab: DemoType) => {
      abortRef.current?.abort();
      setStreams((prev) => ({
        ...prev,
        [tab]: { output: '', status: 'streaming', error: '' },
      }));
      const controller = streamGenerate(
        sessionJwt,
        {
          demo_type: tab,
          source_text: sourceText,
        },
        {
          onToken: (chunk: string) =>
            setStreams((inner) => ({
              ...inner,
              [tab]: { ...inner[tab], output: inner[tab].output + chunk },
            })),
          onDone: () => {
            setStreams((inner) => ({
              ...inner,
              [tab]: { ...inner[tab], status: 'done' },
            }));
            onTabGenerated?.(tab);
          },
          onError: (message: string) =>
            setStreams((inner) => ({
              ...inner,
              [tab]: { ...inner[tab], status: 'error', error: message },
            })),
        },
      );
      abortRef.current = controller;
    },
    [sessionJwt, sourceText, onTabGenerated],
  );

  /** Fires when the multi-turn Ask panel finishes a streaming turn. It
   *  flips the ask stream to 'done' so the conversion card + "try
   *  another" chips appear, and re-uses the shared onTabGenerated hook
   *  for parity with the other panels. */
  const handleAskTurnComplete = useCallback(
    (tab: DemoType) => {
      setStreams((prev) =>
        prev[tab].status === 'done'
          ? prev
          : { ...prev, [tab]: { ...prev[tab], status: 'done' } },
      );
      onTabGenerated?.(tab);
    },
    [onTabGenerated],
  );

  const generatedTypes = useMemo(
    () => new Set(TABS.filter((t) => streams[t.id].status === 'done').map((t) => t.id)),
    [streams],
  );
  const remainingTabs = TABS.filter((t) => t.id !== activeTab && !generatedTypes.has(t.id));
  const activeState = streams[activeTab];
  const anyDone = generatedTypes.size > 0;
  const disableGenerate = overLimit;

  const isFirstXpOfSession = (gameState?.xp ?? 0) === 0;

  return (
    <div>
      <div className="demo-tabs demo-tabs--iconed" role="tablist" aria-label="Demo type">
        {TABS.map((tab) => {
          const { Icon, label, sub } = TAB_META[tab.id];
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={tab.id === activeTab}
              className="demo-tab demo-tab--iconed"
              onClick={() => setActiveTab(tab.id)}
            >
              <span className="demo-tab-icon" aria-hidden="true"><Icon size={22} /></span>
              <span className="demo-tab-label">{label}</span>
              <span className="demo-tab-sub">{sub}</span>
            </button>
          );
        })}
      </div>

      <SourcePicker
        value={source}
        onChange={handleSourceChange}
        customText={customText}
        onCustomTextChange={handleCustomTextChange}
        activeTab={activeTab}
      />

      {/* The Ask panel is always mounted so its multi-turn thread state
          survives tab-switches (#3762 per-tab cache contract). Hidden
          with ``hidden`` when it is not the active tab. */}
      <div hidden={activeTab !== 'ask'}>
        <AskPanel
          sessionJwt={sessionJwt}
          resetKey={askResetKey}
          onTurnComplete={handleAskTurnComplete}
          gameActions={gameActions}
          isFirstXpOfSession={isFirstXpOfSession}
        />
      </div>
      {activeTab === 'study_guide' && (
        <StudyGuidePanel
          sessionJwt={sessionJwt}
          sourceText={sourceText}
          state={activeState}
          onGenerate={() => runGenerate('study_guide')}
          generateDisabled={disableGenerate}
          topic={deriveStudyGuideTopic(source, customText)}
          activeTab={activeTab}
          onChipCuriosity={onStudyGuideChipCuriosity}
          onNavigateToTab={setActiveTab}
        />
      )}
      {activeTab === 'flash_tutor' && (
        <FlashTutorPanel
          sessionJwt={sessionJwt}
          sourceText={sourceText}
          state={activeState}
          onGenerate={() => runGenerate('flash_tutor')}
          generateDisabled={disableGenerate}
          gameActions={gameActions}
        />
      )}

      {activeState.status === 'done' && remainingTabs.length > 0 && (
        <div className="demo-chips-row" aria-label="Try another demo">
          {remainingTabs.map((tab) => {
            const { Icon: ChipIcon, label } = TAB_META[tab.id];
            return (
              <button
                key={tab.id}
                type="button"
                className="demo-chip demo-chip--iconed"
                onClick={() => setActiveTab(tab.id)}
              >
                <ChipIcon size={14} />
                <span>Try {label}</span>
              </button>
            );
          })}
        </div>
      )}

      {anyDone && (
        <ConversionCard position={waitlistPreviewPosition} onVerify={onVerify} />
      )}
    </div>
  );
}

export default InstantTrialGenerateStep;
