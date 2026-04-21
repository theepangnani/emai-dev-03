import { useEffect, useRef, useState } from 'react';
import type { DemoType } from '../../../api/demo';
import { DemoMascot } from '../DemoMascot';
import { GatedActionBar } from '../GatedActionBar';
import { StreamingMarkdown } from '../../StreamingMarkdown';
import { IconSparkles, IconCopy } from '../icons';
import { GATED_ACTIONS, TAB_META, copyToClipboard } from '../instantTrialHelpers';
import type { PanelStreamState } from './panelTypes';

/**
 * Shared "Generate" button + output bubble + copy + gated-action-bar chrome.
 * Panels embed this around their per-tab input + output renderer.
 */
export interface PanelFrameProps {
  demoType: DemoType;
  state: PanelStreamState;
  onGenerate: () => void;
  generateDisabled?: boolean;
  renderOutput: (state: PanelStreamState) => React.ReactNode;
}

export function PanelFrame({
  demoType,
  state,
  onGenerate,
  generateDisabled,
  renderOutput,
}: PanelFrameProps) {
  const [copied, setCopied] = useState(false);
  const copyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current);
    };
  }, []);

  const meta = TAB_META[demoType];
  const { status, output, error } = state;
  const mascotMood: 'streaming' | 'complete' | 'thinking' =
    status === 'streaming' ? 'streaming' : status === 'done' ? 'complete' : 'thinking';

  const handleCopy = async () => {
    const ok = await copyToClipboard(output);
    if (!ok) return;
    setCopied(true);
    if (copyTimerRef.current) clearTimeout(copyTimerRef.current);
    copyTimerRef.current = setTimeout(() => setCopied(false), 2000);
  };

  return (
    <>
      <div className="demo-generate-row">
        <button
          type="button"
          className="demo-btn-primary demo-btn-generate"
          disabled={status === 'streaming' || generateDisabled}
          onClick={onGenerate}
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
              <span>Generate {meta.label}</span>
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
            {renderOutput(state)}
          </div>
        </div>
      )}
      {error && <div className="demo-output-error" role="alert">{error}</div>}

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
          <GatedActionBar actions={GATED_ACTIONS[demoType]} />
        </>
      )}
    </>
  );
}

/** Default markdown renderer used by Ask + Study Guide panels. */
export function MarkdownOutput({ state }: { state: PanelStreamState }) {
  return (
    <StreamingMarkdown
      content={state.output}
      isStreaming={state.status === 'streaming'}
      className="demo-output-md"
    />
  );
}
