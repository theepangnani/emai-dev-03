import { useCallback, useEffect, useRef, useState } from 'react';
import { streamGenerate, type DemoType } from '../../api/demo';
import { ConversionCard } from './ConversionCard';
import { StreamingMarkdown } from '../StreamingMarkdown';
import { DemoMascot } from './DemoMascot';
import {
  IconAsk,
  IconStudyGuide,
  IconFlashTutor,
  IconSparkles,
  IconCopy,
} from './icons';
import {
  DEFAULT_QUESTIONS,
  SAMPLE_TEXT,
  SAMPLE_TITLE,
  TABS,
  countWords,
} from './demoSamples';

interface Props {
  sessionJwt: string;
  waitlistPreviewPosition: number;
  onVerify: () => void;
}

type StreamStatus = 'idle' | 'streaming' | 'done' | 'error';

const TAB_META: Record<DemoType, { label: string; sub: string; Icon: typeof IconAsk }> = {
  ask: { label: 'Ask', sub: 'Get an answer', Icon: IconAsk },
  study_guide: { label: 'Study Guide', sub: 'Key points + Q&A', Icon: IconStudyGuide },
  flash_tutor: { label: 'Flash Tutor', sub: '5 flashcards', Icon: IconFlashTutor },
};

/** Write `text` to the clipboard — async API first, execCommand fallback (#3698). */
async function copyToClipboard(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // Fall through to execCommand fallback below.
  }
  try {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'absolute';
    ta.style.left = '-9999px';
    ta.style.top = '0';
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}

/** Step 2 — sample panel, tabs, streaming output, and conversion card. */
export function InstantTrialGenerateStep({ sessionJwt, waitlistPreviewPosition, onVerify }: Props) {
  const [activeTab, setActiveTab] = useState<DemoType>('ask');
  const [showCustom, setShowCustom] = useState(false);
  const [customText, setCustomText] = useState('');
  const [question, setQuestion] = useState<string>(DEFAULT_QUESTIONS.ask);
  const [status, setStatus] = useState<StreamStatus>('idle');
  const [output, setOutput] = useState<string>('');
  const [error, setError] = useState<string>('');
  const [generatedTypes, setGeneratedTypes] = useState<Set<DemoType>>(new Set());
  const [copied, setCopied] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const copyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current);
    };
  }, []);

  // Reset question when switching tabs back to default.
  const selectTab = (tab: DemoType) => {
    setActiveTab(tab);
    setQuestion(DEFAULT_QUESTIONS[tab]);
    setOutput('');
    setError('');
    setStatus('idle');
  };

  const wordCount = countWords(customText);
  const overLimit = wordCount > 500;

  const runGenerate = useCallback(
    (tab: DemoType) => {
      abortRef.current?.abort();
      setOutput('');
      setError('');
      setStatus('streaming');
      const controller = streamGenerate(
        sessionJwt,
        {
          demo_type: tab,
          source_text: (showCustom && customText.trim()) ? customText.trim() : SAMPLE_TEXT,
          question: tab === 'ask' ? question : undefined,
        },
        {
          onToken: (chunk: string) => setOutput((prev) => prev + chunk),
          onDone: () => {
            setStatus('done');
            setGeneratedTypes((prev) => new Set(prev).add(tab));
          },
          onError: (message: string) => {
            setError(message);
            setStatus('error');
          },
        },
      );
      abortRef.current = controller;
    },
    [sessionJwt, showCustom, customText, question],
  );

  const handleCopy = async () => {
    const ok = await copyToClipboard(output);
    if (ok) {
      setCopied(true);
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current);
      copyTimerRef.current = setTimeout(() => setCopied(false), 2000);
    }
  };

  const remainingTabs = TABS.filter((t) => t.id !== activeTab && !generatedTypes.has(t.id));
  const activeMeta = TAB_META[activeTab];
  const mascotMood: 'streaming' | 'complete' | 'thinking' =
    status === 'streaming' ? 'streaming' : status === 'done' ? 'complete' : 'thinking';

  return (
    <div>
      <div className="demo-tabs demo-tabs--iconed" role="tablist" aria-label="Demo type">
        {TABS.map((tab) => {
          const meta = TAB_META[tab.id];
          const Icon = meta.Icon;
          const selected = tab.id === activeTab;
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={selected}
              className="demo-tab demo-tab--iconed"
              onClick={() => selectTab(tab.id)}
            >
              <span className="demo-tab-icon" aria-hidden="true">
                <Icon size={22} />
              </span>
              <span className="demo-tab-label">{meta.label}</span>
              <span className="demo-tab-sub">{meta.sub}</span>
            </button>
          );
        })}
      </div>

      <p className="demo-panel-label demo-panel-label--iconed">
        <IconStudyGuide size={16} />
        <span>Sample reading — Grade 8 Science</span>
      </p>
      <div className="demo-sample-panel" aria-label={`Pre-loaded sample: ${SAMPLE_TITLE}`} tabIndex={0}>
        {SAMPLE_TEXT}
      </div>

      <button
        type="button"
        className="demo-toggle-text"
        aria-expanded={showCustom}
        onClick={() => setShowCustom((v) => !v)}
      >
        {showCustom ? '\u2212 Hide my own text' : '+ Use my own text (optional, \u2264500 words)'}
      </button>
      {showCustom && (
        <>
          <textarea
            className="demo-textarea"
            value={customText}
            onChange={(e) => setCustomText(e.target.value)}
            placeholder="Paste a short reading or notes (max 500 words)..."
            aria-label="Your own text"
          />
          <p className="demo-word-count" aria-live="polite">
            {wordCount} / 500 words{overLimit ? ' — too long' : ''}
          </p>
        </>
      )}

      {activeTab === 'ask' && (
        <div className="demo-form-group">
          <label htmlFor="demo-question">Your question</label>
          <input
            id="demo-question"
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
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
        <div
          className="demo-output-layout"
          aria-busy={status === 'streaming'}
          aria-live="polite"
        >
          <div className="demo-output-mascot" aria-hidden="true">
            <DemoMascot size={44} mood={mascotMood} />
          </div>
          <div className="demo-output-bubble">
            <div className="demo-output-bubble-header">
              <span className="demo-watermark">Demo sample</span>
            </div>
            <StreamingMarkdown
              content={output}
              isStreaming={status === 'streaming'}
              className="demo-output-md"
            />
          </div>
        </div>
      )}
      {error && <div className="demo-output-error" role="alert">{error}</div>}

      {output && status === 'done' && (
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
      )}

      {status === 'done' && remainingTabs.length > 0 && (
        <div className="demo-chips-row" aria-label="Try another demo">
          {remainingTabs.map((tab) => {
            const meta = TAB_META[tab.id];
            const ChipIcon = meta.Icon;
            return (
              <button
                key={tab.id}
                type="button"
                className="demo-chip demo-chip--iconed"
                onClick={() => selectTab(tab.id)}
              >
                <ChipIcon size={14} />
                <span>Try {meta.label}</span>
              </button>
            );
          })}
        </div>
      )}

      {status === 'done' && (
        <ConversionCard
          position={waitlistPreviewPosition}
          onVerify={onVerify}
        />
      )}
    </div>
  );
}

export default InstantTrialGenerateStep;
