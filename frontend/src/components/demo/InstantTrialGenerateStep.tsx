import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { streamGenerate, type DemoType } from '../../api/demo';
import { ConversionCard } from './ConversionCard';
import { SourcePicker, type SourceKind } from './SourcePicker';
import { AskPanel } from './panels/AskPanel';
import { StudyGuidePanel } from './panels/StudyGuidePanel';
import { FlashTutorPanel } from './panels/FlashTutorPanel';
import type { ChipId } from './panels/study/DemoStudyGuideChips';
import { INITIAL_PANEL_STREAM_STATE, type PanelStreamState } from './panels/panelTypes';
import { DEFAULT_QUESTIONS, SAMPLE_TEXT, SAMPLE_TITLE, TABS, countWords } from './demoSamples';
import { TAB_META } from './instantTrialHelpers';

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
 * Orchestrator for the three demo tabs.
 *
 * Post-refactor responsibilities (CB-DEMO-001 foundation):
 *   - Tab selection + shared chrome (tab row, source picker, conversion card).
 *   - Owns per-tab streaming state so output survives tab switches (#3762).
 *   - Delegates per-tab rendering to panel components:
 *       AskPanel / StudyGuidePanel / FlashTutorPanel.
 *   - Exposes `onTabGenerated` so the modal's game-state hook can react.
 */
export function InstantTrialGenerateStep({
  sessionJwt,
  waitlistPreviewPosition,
  onVerify,
  onTabGenerated,
  onStudyGuideChipCuriosity,
}: Props) {
  const [activeTab, setActiveTab] = useState<DemoType>('ask');
  const [source, setSource] = useState<SourceKind>('sample');
  const [customText, setCustomText] = useState('');
  const [askQuestion, setAskQuestion] = useState(DEFAULT_QUESTIONS.ask);
  // Lazy init — avoid allocating a fresh initial object on every render.
  const [streams, setStreams] = useState<PerTabStreamState>(buildInitialStreams);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const resetAllStreams = useCallback(() => {
    abortRef.current?.abort();
    setStreams(buildInitialStreams());
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
          question: tab === 'ask' ? askQuestion : undefined,
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
    [sessionJwt, sourceText, askQuestion, onTabGenerated],
  );

  const generatedTypes = useMemo(
    () => new Set(TABS.filter((t) => streams[t.id].status === 'done').map((t) => t.id)),
    [streams],
  );
  const remainingTabs = TABS.filter((t) => t.id !== activeTab && !generatedTypes.has(t.id));
  const activeState = streams[activeTab];
  const anyDone = generatedTypes.size > 0;
  const disableGenerate = overLimit;

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
      />

      {activeTab === 'ask' && (
        <AskPanel
          sessionJwt={sessionJwt}
          sourceText={sourceText}
          state={activeState}
          question={askQuestion}
          onQuestionChange={setAskQuestion}
          onGenerate={() => runGenerate('ask')}
          generateDisabled={disableGenerate}
        />
      )}
      {activeTab === 'study_guide' && (
        <StudyGuidePanel
          sessionJwt={sessionJwt}
          sourceText={sourceText}
          state={activeState}
          onGenerate={() => runGenerate('study_guide')}
          generateDisabled={disableGenerate}
          topic={source === 'paste' && customText.trim() ? 'your source' : SAMPLE_TITLE}
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
