import { useState, type ComponentType } from 'react';
import { IconAsk, IconArrowRight, IconClose, IconFlashTutor, type IconProps } from './icons';
import { IconDownload } from './icons/IconDownload';
import { IconBookmark } from './icons/IconBookmark';

export type GatedActionId = 'download' | 'save' | 'follow_up' | 'more_flashcards';

interface GatedActionBarProps {
  actions: GatedActionId[];
  onUpsell?: (actionId: GatedActionId) => void;
  waitlistHref?: string;
}

interface ActionDef {
  id: GatedActionId;
  label: string;
  headline: string;
  Icon: ComponentType<IconProps>;
}

const ACTION_DEFS: Record<GatedActionId, ActionDef> = {
  download: {
    id: 'download',
    label: 'Download PDF',
    headline: 'Want to save these as PDF?',
    Icon: IconDownload,
  },
  save: {
    id: 'save',
    label: 'Save to library',
    headline: 'Want to save this to your library?',
    Icon: IconBookmark,
  },
  follow_up: {
    id: 'follow_up',
    label: 'Ask a follow-up',
    headline: 'Want to keep the conversation going?',
    Icon: IconAsk,
  },
  more_flashcards: {
    id: 'more_flashcards',
    label: 'More flashcards',
    headline: 'Want more flashcards?',
    Icon: IconFlashTutor,
  },
};

export function GatedActionBar({
  actions,
  onUpsell,
  waitlistHref = '/waitlist',
}: GatedActionBarProps) {
  const [activeUpsell, setActiveUpsell] = useState<GatedActionId | null>(null);

  const handleClick = (id: GatedActionId) => {
    onUpsell?.(id);
    setActiveUpsell(id);
  };

  const activeDef = activeUpsell ? ACTION_DEFS[activeUpsell] : null;

  return (
    <div className="demo-gated-bar">
      {activeDef ? (
        <section
          id="demo-gated-upsell"
          role="region"
          aria-label="Unlock this feature"
          className="demo-gated-upsell"
        >
          <button
            type="button"
            className="demo-gated-upsell__close"
            aria-label="Dismiss"
            onClick={() => setActiveUpsell(null)}
          >
            <IconClose size={18} aria-hidden />
          </button>
          <h4 className="demo-gated-upsell__headline">{activeDef.headline}</h4>
          <p className="demo-gated-upsell__body">
            Create a free account to unlock — join the waitlist for early access.
          </p>
          <a className="demo-gated-cta" href={waitlistHref}>
            <span>Join the waitlist</span>
            <IconArrowRight size={16} aria-hidden />
          </a>
        </section>
      ) : null}
      <div className="demo-gated-bar__row">
        {actions.map((id) => {
          const def = ACTION_DEFS[id];
          const isActive = activeUpsell === id;
          return (
            <button
              key={id}
              type="button"
              className="demo-gated-bar__btn"
              aria-expanded={isActive}
              aria-controls="demo-gated-upsell"
              onClick={() => handleClick(id)}
            >
              <def.Icon size={18} aria-hidden />
              <span>{def.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default GatedActionBar;
