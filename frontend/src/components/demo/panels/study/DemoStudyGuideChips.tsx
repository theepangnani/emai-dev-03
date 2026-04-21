import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Chip grid + scoped waitlist upsell for the Demo Study Guide tab (#3787).
 *
 * Labels are hard-coded in v1 (not AI-generated) to keep the surface
 * deterministic and cheap (§6.135.7). Clicking a non-followup chip opens a
 * scoped upsell panel directly below the chip. `Ask a follow-up` calls
 * `onAskFollowUp` so the parent orchestrator can switch tabs — it does not
 * open an upsell and does not award XP here (the Ask turn will award).
 *
 * `activeTab` is accepted so the parent can change it and this component
 * auto-dismisses any open upsell — mirrors the dismiss-on-tab-change
 * pattern introduced for SourcePicker by Stream A (#3784).
 */

export type ChipId = 'worksheet' | 'quiz' | 'flashcards' | 'deeper' | 'followup';

interface ChipDef {
  id: ChipId;
  emoji: string;
  label: string;
  /** Short scope hint for aria-describedby. */
  scope: 'gated' | 'free';
}

const CHIPS: ChipDef[] = [
  { id: 'worksheet', emoji: '\u{1F4DD}', label: 'Generate a worksheet', scope: 'gated' },
  { id: 'quiz', emoji: '\u{1F3AF}', label: 'Make a quiz', scope: 'gated' },
  { id: 'flashcards', emoji: '\u{1F5C2}\u{FE0F}', label: 'Create flashcards', scope: 'gated' },
  { id: 'deeper', emoji: '\u{1F52C}', label: 'Go deeper on this topic', scope: 'gated' },
  { id: 'followup', emoji: '\u{1F4AC}', label: 'Ask a follow-up', scope: 'free' },
];

const UPSELL_COPY: Record<Exclude<ChipId, 'followup'>, { title: string; body: string }> = {
  worksheet: {
    title: 'Unlock AI worksheets',
    body: "Join the waitlist and we'll auto-generate a printable worksheet on this topic.",
  },
  quiz: {
    title: 'Unlock AI quizzes',
    body: 'Personalized, adaptive, waitlist-only for now.',
  },
  flashcards: {
    title: 'Unlock flashcard decks',
    body: 'Build and review cards that remember what you miss. Waitlist-only.',
  },
  deeper: {
    title: 'Unlock topic deep-dives',
    body: 'Drill into any sub-topic with Socratic guidance. Waitlist members first.',
  },
};

export interface DemoStudyGuideChipsProps {
  /** Orchestrator-owned active tab — any change closes the scoped upsell. */
  activeTab: string;
  /** Awards a small curiosity reward when a gated chip opens its upsell. Max once per chip per session. */
  onChipOpen?: (id: Exclude<ChipId, 'followup'>) => void;
  /** Called when `Ask a follow-up` is clicked. Parent should navigate to the Ask tab. */
  onAskFollowUp: () => void;
}

export function DemoStudyGuideChips({
  activeTab,
  onChipOpen,
  onAskFollowUp,
}: DemoStudyGuideChipsProps) {
  const [openChip, setOpenChip] = useState<Exclude<ChipId, 'followup'> | null>(null);
  const [trackedTab, setTrackedTab] = useState(activeTab);
  const upsellRef = useRef<HTMLDivElement | null>(null);
  const chipRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const closeBtnRef = useRef<HTMLButtonElement | null>(null);
  const lastActiveChipRef = useRef<ChipId | null>(null);
  /**
   * Track which chips have already fired their `onChipOpen` curiosity reward
   * this session. Max once per chip per session (scope §5 Gamification).
   */
  const rewardedChipsRef = useRef<Set<Exclude<ChipId, 'followup'>>>(new Set());

  // Dismiss on tab change (mirrors Stream A SourcePicker pattern, #3784).
  // Derived-state reset during render avoids the set-state-in-effect warning.
  if (activeTab !== trackedTab) {
    setTrackedTab(activeTab);
    if (openChip !== null) setOpenChip(null);
  }

  // Focus the close button when an upsell opens (focus trap entry point).
  useEffect(() => {
    if (openChip) {
      closeBtnRef.current?.focus();
    }
  }, [openChip]);

  // Esc closes; focus-trap Tab / Shift+Tab inside the upsell.
  const handleUpsellKeyDown = useCallback((e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      setOpenChip(null);
      return;
    }
    if (e.key !== 'Tab') return;
    const container = upsellRef.current;
    if (!container) return;
    const focusable = container.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
    );
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey) {
      if (document.activeElement === first) {
        e.preventDefault();
        last.focus();
      }
    } else {
      if (document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  }, []);

  // When the upsell closes, restore focus to the originating chip.
  const closeUpsell = useCallback(() => {
    const chipId = lastActiveChipRef.current;
    setOpenChip(null);
    if (chipId) {
      // Wait a tick so React removes the panel first.
      setTimeout(() => {
        chipRefs.current[chipId]?.focus();
      }, 0);
    }
  }, []);

  const handleChipClick = (chip: ChipDef) => {
    if (chip.id === 'followup') {
      onAskFollowUp();
      return;
    }
    const gatedId = chip.id as Exclude<ChipId, 'followup'>;
    lastActiveChipRef.current = chip.id;
    // Toggle off if the same chip is clicked again.
    setOpenChip((prev) => (prev === gatedId ? null : gatedId));
    if (openChip !== gatedId && !rewardedChipsRef.current.has(gatedId)) {
      rewardedChipsRef.current.add(gatedId);
      onChipOpen?.(gatedId);
    }
  };

  return (
    <div className="demo-sg-chips-wrap">
      <div className="demo-sg-chips-label" id="demo-sg-chips-label">
        Where to next?
      </div>
      <div
        className="demo-sg-chips-grid"
        role="group"
        aria-label="Study guide next steps"
      >
        {CHIPS.map((chip) => {
          const describedById = `demo-sg-chip-desc-${chip.id}`;
          const isOpen = openChip === chip.id;
          return (
            <button
              key={chip.id}
              ref={(el) => {
                chipRefs.current[chip.id] = el;
              }}
              type="button"
              className={`demo-sg-chip${isOpen ? ' demo-sg-chip--open' : ''}`}
              onClick={() => handleChipClick(chip)}
              aria-describedby={describedById}
              aria-expanded={chip.id !== 'followup' ? isOpen : undefined}
            >
              <span className="demo-sg-chip-icon" aria-hidden="true">{chip.emoji}</span>
              <span className="demo-sg-chip-label">{chip.label}</span>
              {chip.scope === 'gated' && (
                <span className="demo-sg-chip-lock" aria-label="Waitlist required">
                  {'\u{1F512}'}
                </span>
              )}
              <span id={describedById} className="sr-only">
                {chip.scope === 'gated'
                  ? 'unlocks with waitlist'
                  : 'free — switches to Ask tab'}
              </span>
            </button>
          );
        })}
      </div>

      {openChip && (
        <div
          ref={upsellRef}
          className="demo-sg-upsell"
          role="dialog"
          aria-modal="false"
          aria-labelledby={`demo-sg-upsell-title-${openChip}`}
          onKeyDown={handleUpsellKeyDown}
        >
          <div className="demo-sg-upsell-body">
            <h4
              id={`demo-sg-upsell-title-${openChip}`}
              className="demo-sg-upsell-title"
            >
              {UPSELL_COPY[openChip].title}
            </h4>
            <p className="demo-sg-upsell-text">{UPSELL_COPY[openChip].body}</p>
            <a
              href="/waitlist"
              className="demo-sg-upsell-cta"
            >
              Join the waitlist &rarr;
            </a>
          </div>
          <button
            ref={closeBtnRef}
            type="button"
            className="demo-sg-upsell-close"
            onClick={closeUpsell}
            aria-label="Close upsell"
          >
            &times;
          </button>
        </div>
      )}
    </div>
  );
}

export default DemoStudyGuideChips;
