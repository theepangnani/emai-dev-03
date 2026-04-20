import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import {
  IconAsk,
  IconStudyGuide,
  IconFlashTutor,
  IconSparkles,
  IconCheck,
  IconArrowRight,
  IconCopy,
  IconSend,
  IconClock,
  IconShield,
  IconMail,
  IconParent,
  IconStudent,
  IconTeacher,
  IconOther,
  IconPeople,
  IconQuote,
  IconClose,
  IconDownload,
  IconBookmark,
} from './index';

const icons = [
  ['IconAsk', IconAsk],
  ['IconStudyGuide', IconStudyGuide],
  ['IconFlashTutor', IconFlashTutor],
  ['IconSparkles', IconSparkles],
  ['IconCheck', IconCheck],
  ['IconArrowRight', IconArrowRight],
  ['IconCopy', IconCopy],
  ['IconSend', IconSend],
  ['IconClock', IconClock],
  ['IconShield', IconShield],
  ['IconMail', IconMail],
  ['IconParent', IconParent],
  ['IconStudent', IconStudent],
  ['IconTeacher', IconTeacher],
  ['IconOther', IconOther],
  ['IconPeople', IconPeople],
  ['IconQuote', IconQuote],
  ['IconClose', IconClose],
  ['IconDownload', IconDownload],
  ['IconBookmark', IconBookmark],
] as const;

describe('demo icons', () => {
  it('exports 20 distinct icon components', () => {
    expect(icons.length).toBe(20);
  });

  it.each(icons)('renders %s as an SVG with viewBox 0 0 24 24', (_name, Component) => {
    const { container } = render(<Component />);
    const svg = container.querySelector('svg');
    expect(svg).not.toBeNull();
    expect(svg!.getAttribute('viewBox')).toBe('0 0 24 24');
  });

  it.each(icons)('%s respects the size prop', (_name, Component) => {
    const { container } = render(<Component size={32} />);
    const svg = container.querySelector('svg');
    expect(svg!.getAttribute('width')).toBe('32');
    expect(svg!.getAttribute('height')).toBe('32');
  });

  it.each(icons)('%s defaults to aria-hidden="true"', (_name, Component) => {
    const { container } = render(<Component />);
    const svg = container.querySelector('svg');
    expect(svg!.getAttribute('aria-hidden')).toBe('true');
  });

  it.each(icons)('%s applies a custom className', (_name, Component) => {
    const { container } = render(<Component className="my-icon" />);
    const svg = container.querySelector('svg');
    expect(svg!.getAttribute('class')).toContain('my-icon');
  });

  it.each(icons)('%s uses currentColor stroke with consistent weight', (_name, Component) => {
    const { container } = render(<Component />);
    const svg = container.querySelector('svg');
    expect(svg!.getAttribute('stroke')).toBe('currentColor');
    expect(svg!.getAttribute('stroke-width')).toBe('1.75');
  });
});
