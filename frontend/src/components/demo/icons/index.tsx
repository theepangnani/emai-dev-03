/**
 * Demo icon primitives — 18 inline SVG components for CB-DEMO-001.
 * All stroke-based, 20px default, currentColor, stroke-width 1.75, rounded linecaps.
 * aria-hidden defaults to true; callers wrap in labelled buttons/links.
 */

import type { SVGProps } from 'react';

export interface IconProps extends Omit<SVGProps<SVGSVGElement>, 'ref'> {
  size?: number;
  className?: string;
  'aria-hidden'?: boolean;
}

export function baseProps(size: number, className?: string, rest?: Omit<IconProps, 'size' | 'className'>) {
  return {
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.75,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    xmlns: 'http://www.w3.org/2000/svg',
    className,
    'aria-hidden': rest?.['aria-hidden'] ?? true,
    ...rest,
  };
}

export const IconAsk = ({ size = 20, className, ...rest }: IconProps) => (
  <svg {...baseProps(size, className, rest)}>
    <path d="M4 12c0-3.87 3.58-7 8-7s8 3.13 8 7-3.58 7-8 7c-1 0-1.96-.14-2.83-.4L5 20l1.4-3.17C5.52 15.57 4 13.9 4 12Z" />
    <path d="M9 11h6M9 14h4" />
  </svg>
);

export const IconStudyGuide = ({ size = 20, className, ...rest }: IconProps) => (
  <svg {...baseProps(size, className, rest)}>
    <path d="M6 3h10a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" />
    <path d="M9 8h6M9 12h6M9 16h4" />
  </svg>
);

export const IconFlashTutor = ({ size = 20, className, ...rest }: IconProps) => (
  <svg {...baseProps(size, className, rest)}>
    <path d="M13 3 4 14h7l-1 7 9-11h-7l1-7Z" />
  </svg>
);

export const IconSparkles = ({ size = 20, className, ...rest }: IconProps) => (
  <svg {...baseProps(size, className, rest)}>
    <path d="M12 3v4M12 17v4M3 12h4M17 12h4" />
    <path d="M12 8c0 2.2 1.8 4 4 4-2.2 0-4 1.8-4 4 0-2.2-1.8-4-4-4 2.2 0 4-1.8 4-4Z" />
  </svg>
);

export const IconCheck = ({ size = 20, className, ...rest }: IconProps) => (
  <svg {...baseProps(size, className, rest)}>
    <path d="m5 12 4.5 4.5L19 7" />
  </svg>
);

export const IconArrowRight = ({ size = 20, className, ...rest }: IconProps) => (
  <svg {...baseProps(size, className, rest)}>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </svg>
);

export const IconCopy = ({ size = 20, className, ...rest }: IconProps) => (
  <svg {...baseProps(size, className, rest)}>
    <rect x="9" y="9" width="11" height="11" rx="2" />
    <path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1" />
  </svg>
);

export const IconSend = ({ size = 20, className, ...rest }: IconProps) => (
  <svg {...baseProps(size, className, rest)}>
    <path d="M21 3 3 10l7 3 3 7 8-17Z" />
    <path d="m10 13 4-4" />
  </svg>
);

export const IconClock = ({ size = 20, className, ...rest }: IconProps) => (
  <svg {...baseProps(size, className, rest)}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3.5 2" />
  </svg>
);

export const IconShield = ({ size = 20, className, ...rest }: IconProps) => (
  <svg {...baseProps(size, className, rest)}>
    <path d="M12 3 4 6v6c0 4.5 3.2 8.5 8 9 4.8-.5 8-4.5 8-9V6l-8-3Z" />
    <path d="m9 12 2 2 4-4" />
  </svg>
);

export const IconMail = ({ size = 20, className, ...rest }: IconProps) => (
  <svg {...baseProps(size, className, rest)}>
    <rect x="3" y="5" width="18" height="14" rx="2" />
    <path d="m3 7 9 6 9-6" />
  </svg>
);

export const IconParent = ({ size = 20, className, ...rest }: IconProps) => (
  <svg {...baseProps(size, className, rest)}>
    <circle cx="9" cy="7" r="3" />
    <circle cx="17" cy="9" r="2" />
    <path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6" />
    <path d="M15 20c.2-1.6 1-3 2-4" />
  </svg>
);

export const IconStudent = ({ size = 20, className, ...rest }: IconProps) => (
  <svg {...baseProps(size, className, rest)}>
    <path d="m3 9 9-4 9 4-9 4-9-4Z" />
    <path d="M7 11v4c0 1.5 2.2 3 5 3s5-1.5 5-3v-4" />
    <path d="M21 9v5" />
  </svg>
);

export const IconTeacher = ({ size = 20, className, ...rest }: IconProps) => (
  <svg {...baseProps(size, className, rest)}>
    <circle cx="12" cy="7" r="3" />
    <path d="M5 20c0-3.3 3.1-6 7-6s7 2.7 7 6" />
    <path d="M16 4v2M12 2v2" />
  </svg>
);

export const IconOther = ({ size = 20, className, ...rest }: IconProps) => (
  <svg {...baseProps(size, className, rest)}>
    <circle cx="12" cy="12" r="9" />
    <path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.8.3-1 .9-1 1.7M12 17h.01" />
  </svg>
);

export const IconPeople = ({ size = 20, className, ...rest }: IconProps) => (
  <svg {...baseProps(size, className, rest)}>
    <circle cx="8" cy="8" r="3" />
    <circle cx="17" cy="9" r="2.5" />
    <path d="M2 19c0-3.3 2.7-6 6-6s6 2.7 6 6" />
    <path d="M14 19c.2-2.5 2-4.5 4.5-5" />
  </svg>
);

export const IconQuote = ({ size = 20, className, ...rest }: IconProps) => (
  <svg {...baseProps(size, className, rest)}>
    <path d="M7 7c-2 0-3 1.5-3 3v7h6v-7H6c0-1.5 1-3 3-3" />
    <path d="M17 7c-2 0-3 1.5-3 3v7h6v-7h-4c0-1.5 1-3 3-3" />
  </svg>
);

export const IconClose = ({ size = 20, className, ...rest }: IconProps) => (
  <svg {...baseProps(size, className, rest)}>
    <path d="M6 6l12 12M18 6 6 18" />
  </svg>
);

export { IconDownload } from './IconDownload';
export { IconBookmark } from './IconBookmark';
