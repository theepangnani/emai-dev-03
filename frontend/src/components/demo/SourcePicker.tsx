import { useState } from 'react';
import {
  IconArrowRight,
  IconClose,
  IconStudyGuide,
  IconSparkles,
  IconMail,
} from './icons';
import { SAMPLE_TEXT, SAMPLE_TITLE, countWords } from './demoSamples';

export type SourceKind = 'sample' | 'paste';

export interface SourcePickerProps {
  value: SourceKind;
  onChange: (next: SourceKind) => void;
  customText: string;
  onCustomTextChange: (text: string) => void;
}

interface OptionDef {
  id: SourceKind | 'upload';
  label: string;
  sub: string;
  Icon: typeof IconStudyGuide;
}

const OPTIONS: OptionDef[] = [
  { id: 'sample', label: 'Try a sample', sub: 'Grade 8 Cells reading', Icon: IconStudyGuide },
  { id: 'paste', label: 'Paste your own text', sub: 'Up to 500 words', Icon: IconSparkles },
  { id: 'upload', label: 'Upload a document', sub: 'PDF, DOCX (coming soon)', Icon: IconMail },
];

export function SourcePicker({ value, onChange, customText, onCustomTextChange }: SourcePickerProps) {
  const [uploadUpsellOpen, setUploadUpsellOpen] = useState(false);

  const wordCount = countWords(customText);
  const overLimit = wordCount > 500;

  return (
    <div className="demo-source-picker">
      <div className="demo-source-grid" role="radiogroup" aria-label="Demo source">
        {OPTIONS.map(({ id, label, sub, Icon }) => {
          const isUpload = id === 'upload';
          const checked = !isUpload && value === id;
          const handleSelect = () => {
            if (isUpload) {
              setUploadUpsellOpen(true);
              return;
            }
            onChange(id);
          };
          return (
            <label
              key={id}
              className={`demo-role-card demo-source-card${checked ? ' is-checked' : ''}${isUpload ? ' demo-source-card--gated' : ''}`}
            >
              <input
                type="radio"
                name="demo-source"
                value={id}
                checked={checked}
                onChange={isUpload ? undefined : () => onChange(id as SourceKind)}
                disabled={isUpload}
                aria-disabled={isUpload || undefined}
                aria-hidden={isUpload || undefined}
              />
              {isUpload && (
                <button
                  type="button"
                  className="demo-source-card__overlay"
                  aria-label={`${label} — waitlist only`}
                  aria-expanded={uploadUpsellOpen}
                  onClick={handleSelect}
                />
              )}
              <span className="demo-role-card__icon" aria-hidden="true">
                <Icon size={22} aria-hidden />
              </span>
              <span className="demo-role-card__label">{label}</span>
              <span className="demo-source-card__sub">{sub}</span>
            </label>
          );
        })}
      </div>

      {uploadUpsellOpen && (
        <section
          className="demo-source-upsell"
          role="region"
          aria-label="Upload unlocks with waitlist"
        >
          <button
            type="button"
            className="demo-gated-upsell__close"
            aria-label="Dismiss"
            onClick={() => setUploadUpsellOpen(false)}
          >
            <IconClose size={18} aria-hidden />
          </button>
          <h4 className="demo-gated-upsell__headline">Uploads unlock when you join the waitlist</h4>
          <p className="demo-gated-upsell__body">
            We&rsquo;ll let you know when document uploads are ready. For now, try the sample or paste your own text.
          </p>
          <a className="demo-gated-cta" href="/waitlist">
            <span>Join the waitlist</span>
            <IconArrowRight size={16} aria-hidden />
          </a>
        </section>
      )}

      {value === 'sample' && (
        <>
          <p className="demo-panel-label demo-panel-label--iconed">
            <IconStudyGuide size={16} />
            <span>Sample reading — Grade 8 Science</span>
          </p>
          <div
            className="demo-sample-panel"
            aria-label={`Pre-loaded sample: ${SAMPLE_TITLE}`}
            tabIndex={0}
          >
            {SAMPLE_TEXT}
          </div>
        </>
      )}

      {value === 'paste' && (
        <>
          <textarea
            className="demo-textarea"
            value={customText}
            onChange={(e) => onCustomTextChange(e.target.value)}
            placeholder="Paste a short reading or notes (max 500 words)..."
            aria-label="Your own text"
          />
          <p className="demo-word-count" aria-live="polite">
            {wordCount} / 500 words{overLimit ? ' — too long' : ''}
          </p>
        </>
      )}
    </div>
  );
}

export default SourcePicker;
