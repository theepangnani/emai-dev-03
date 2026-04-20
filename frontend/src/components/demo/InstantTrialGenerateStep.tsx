import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { streamGenerate, type DemoType } from '../../api/demo';
import { ConversionCard } from './ConversionCard';
import { StreamingMarkdown } from '../StreamingMarkdown';
import { DemoMascot } from './DemoMascot';
import { FlashcardDeck } from './FlashcardDeck';
import { GatedActionBar } from './GatedActionBar';
import { SourcePicker, type SourceKind } from './SourcePicker';
import { IconSparkles, IconCopy } from './icons';
import { SAMPLE_TEXT, TABS, countWords } from './demoSamples';
import {
  TAB_META,
  GATED_ACTIONS,
  INITIAL_TAB_STATE,
  copyToClipboard,
  type TabState,
} from './instantTrialHelpers';

interface Props {
  sessionJwt: string;
  waitlistPreviewPosition: number;
  onVerify: () => void;
}

export function InstantTrialGenerateStep({ sessionJwt, waitlistPreviewPosition, onVerify }: Props) {
  const [activeTab, setActiveTab] = useState<DemoType>('ask');
  const [source, setSource] = useState<SourceKind>('sample');
  const [customText, setCustomText] = useState('');
  const [tabState, setTabState] = useState<Record<DemoType, TabState>>(INITIAL_TAB_STATE);
  const [copied, setCopied] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const copyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current);
    };
  }, []);

  const resetAllTabs = () => {
    abortRef.current?.abort();
    setTabState(INITIAL_TAB_STATE);
  };

  const handleSourceChange = (next: SourceKind) => { setSource(next); resetAllTabs(); };
  const handleCustomTextChange = (text: string) => {
    setCustomText(text);
    if (source === 'paste') resetAllTabs();
  };
  const updateTab = (tab: DemoType, patch: Partial<TabState>) =>
    setTabState((prev) => ({ ...prev, [tab]: { ...prev[tab], ...patch } }));

  const wordCount = countWords(customText);
  const overLimit = wordCount > 500;
  const current = tabState[activeTab];
  const { status, output } = current;

  const runGenerate = useCallback(
    (tab: DemoType) => {
      abortRef.current?.abort();
      const question = tabState[tab].question;
      setTabState((prev) => ({
        ...prev,
        [tab]: { ...prev[tab], output: '', error: '', status: 'streaming' },
      }));
      const controller = streamGenerate(
        sessionJwt,
        {
          demo_type: tab,
          source_text: source === 'paste' && customText.trim() ? customText.trim() : SAMPLE_TEXT,
          question: tab === 'ask' ? question : undefined,
        },
        {
          onToken: (chunk: string) =>
            setTabState((prev) => ({
              ...prev,
              [tab]: { ...prev[tab], output: prev[tab].output + chunk },
            })),
          onDone: () => updateTab(tab, { status: 'done' }),
          onError: (message: string) => updateTab(tab, { status: 'error', error: message }),
        },
      );
      abortRef.current = controller;
    },
    [sessionJwt, source, customText, tabState],
  );

  const handleCopy = async () => {
    const ok = await copyToClipboard(output);
    if (!ok) return;
    setCopied(true);
    if (copyTimerRef.current) clearTimeout(copyTimerRef.current);
    copyTimerRef.current = setTimeout(() => setCopied(false), 2000);
  };

  const generatedTypes = useMemo(
    () => new Set(TABS.filter((t) => tabState[t.id].status === 'done').map((t) => t.id)),
    [tabState],
  );
  const remainingTabs = TABS.filter((t) => t.id !== activeTab && !generatedTypes.has(t.id));
  const activeMeta = TAB_META[activeTab];
  const mascotMood =
    status === 'streaming' ? 'streaming' : status === 'done' ? 'complete' : 'thinking';
  const anyDone = generatedTypes.size > 0;

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
        <div className="demo-form-group">
          <label htmlFor="demo-question">Your question</label>
          <input
            id="demo-question"
            type="text"
            value={current.question}
            onChange={(e) => updateTab('ask', { question: e.target.value })}
            maxLength={500}
          />
        </div>
      )}

      <div className="demo-generate-row">
        <button
          type="button"
          className="demo-btn-primary demo-btn-generate"
          disabled={status === 'streaming' || overLimit}
          onClick={() => runGenerate(activeTab)}
        >
          {status === 'streaming' ? (
            <>
              <span className="demo-generate-dots" aria-hidden="true">
                <span className="demo-typing-dot" />
                <span className="demo-typing-dot" />
                <span className="demo-typing-dot" />
              </span>
              <span>Generating...</span>
            </>
          ) : (
            <>
              <IconSparkles size={18} />
              <span>Generate {activeMeta.label}</span>
            </>
          )}
        </button>
      </div>

      {(status !== 'idle' || output) && (
        <div className="demo-output-layout" aria-busy={status === 'streaming'} aria-live="polite">
          <div className="demo-output-mascot" aria-hidden="true">
            <DemoMascot size={44} mood={mascotMood} />
          </div>
          <div className="demo-output-bubble">
            <div className="demo-output-bubble-header">
              <span className="demo-watermark">Demo sample</span>
            </div>
            {activeTab === 'flash_tutor' ? (
              <FlashcardDeck rawText={output} isStreaming={status === 'streaming'} />
            ) : (
              <StreamingMarkdown
                content={output}
                isStreaming={status === 'streaming'}
                className="demo-output-md"
              />
            )}
          </div>
        </div>
      )}
      {current.error && <div className="demo-output-error" role="alert">{current.error}</div>}

      {output && status === 'done' && (
        <>
          <div className="demo-output-actions">
            <button
              type="button"
              className="demo-btn-secondary demo-btn-copy"
              onClick={handleCopy}
              aria-label="Copy demo output to clipboard"
            >
              <IconCopy size={16} />
              <span>{copied ? 'Copied!' : 'Copy'}</span>
            </button>
          </div>
          <GatedActionBar actions={GATED_ACTIONS[activeTab]} />
        </>
      )}

      {status === 'done' && remainingTabs.length > 0 && (
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
