import { useCallback, useEffect, useRef, useState } from 'react';
import { streamGenerate, type DemoType } from '../../api/demo';
import { ConversionCard } from './ConversionCard';
import { StreamingMarkdown } from '../StreamingMarkdown';
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
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => abortRef.current?.abort();
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
    try {
      await navigator.clipboard.writeText(output);
    } catch {
      // best-effort — no toast to keep scope minimal
    }
  };

  const remainingTabs = TABS.filter((t) => t.id !== activeTab && !generatedTypes.has(t.id));

  return (
    <div>
      <div className="demo-tabs" role="tablist" aria-label="Demo type">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={tab.id === activeTab}
            className="demo-tab"
            onClick={() => selectTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <p className="demo-panel-label">Sample reading — {SAMPLE_TITLE}</p>
      <div className="demo-sample-panel" aria-label="Pre-loaded sample" tabIndex={0}>
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

      <div className="demo-modal-actions" style={{ padding: 0, border: 'none' }}>
        <button
          type="button"
          className="demo-btn-primary"
          disabled={status === 'streaming' || overLimit}
          onClick={() => runGenerate(activeTab)}
        >
          {status === 'streaming' ? 'Generating...' : `Generate ${TABS.find((t) => t.id === activeTab)?.label}`}
        </button>
      </div>

      {(status !== 'idle' || output) && (
        <div
          className="demo-output-wrap"
          aria-busy={status === 'streaming'}
          aria-live="polite"
        >
          <span className="demo-watermark" aria-hidden="true">Demo sample</span>
          <StreamingMarkdown
            content={output}
            isStreaming={status === 'streaming'}
            className="demo-output-md"
          />
        </div>
      )}
      {error && <div className="demo-output-error" role="alert">{error}</div>}

      {output && status === 'done' && (
        <div className="demo-output-actions">
          <button type="button" className="demo-btn-secondary" onClick={handleCopy}>
            Copy
          </button>
        </div>
      )}

      {status === 'done' && remainingTabs.length > 0 && (
        <div className="demo-chips-row" aria-label="Try another demo">
          {remainingTabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              className="demo-chip"
              onClick={() => selectTab(tab.id)}
            >
              Try {tab.label}
            </button>
          ))}
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
