import { useEffect, useMemo, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import './RoleSwitcher.css';

type RoleKey = 'parent' | 'student' | 'teacher' | 'admin';

interface RoleContent {
  title: string;
  content_items: string[];
}

interface RoleSwitcherData {
  event: string;
  roles: Record<RoleKey, RoleContent>;
}

const ROLE_ORDER: RoleKey[] = ['parent', 'student', 'teacher', 'admin'];

const ROLE_ICONS: Record<RoleKey, string> = {
  parent: '👪',
  student: '🎒',
  teacher: '📘',
  admin: '🏫',
};

const FADE_MS = 150;

interface RoleSwitcherProps {
  onCtaClick?: () => void;
  contentUrl?: string;
}

export default function RoleSwitcher({ onCtaClick, contentUrl = '/content/role-switcher/field-trip-rom.json' }: RoleSwitcherProps) {
  const [data, setData] = useState<RoleSwitcherData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeRole, setActiveRole] = useState<RoleKey>('parent');
  const [isFading, setIsFading] = useState(false);
  const tabRefs = useRef<Record<RoleKey, HTMLButtonElement | null>>({
    parent: null,
    student: null,
    teacher: null,
    admin: null,
  });

  const prefersReducedMotion = useMemo(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return false;
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetch(contentUrl)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((json: RoleSwitcherData) => {
        if (!cancelled) setData(json);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load');
      });
    return () => { cancelled = true; };
  }, [contentUrl]);

  const switchRole = (next: RoleKey) => {
    if (next === activeRole) return;
    if (prefersReducedMotion) {
      setActiveRole(next);
      return;
    }
    setIsFading(true);
    window.setTimeout(() => {
      setActiveRole(next);
      setIsFading(false);
    }, FADE_MS);
  };

  const focusTab = (role: RoleKey) => {
    tabRefs.current[role]?.focus();
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLButtonElement>) => {
    const currentIdx = ROLE_ORDER.indexOf(activeRole);
    let nextRole: RoleKey | null = null;
    if (e.key === 'ArrowRight') {
      nextRole = ROLE_ORDER[(currentIdx + 1) % ROLE_ORDER.length];
    } else if (e.key === 'ArrowLeft') {
      nextRole = ROLE_ORDER[(currentIdx - 1 + ROLE_ORDER.length) % ROLE_ORDER.length];
    } else if (e.key === 'Home') {
      nextRole = ROLE_ORDER[0];
    } else if (e.key === 'End') {
      nextRole = ROLE_ORDER[ROLE_ORDER.length - 1];
    }
    if (nextRole) {
      e.preventDefault();
      switchRole(nextRole);
      focusTab(nextRole);
    }
  };

  const handleCtaClick = () => {
    if (onCtaClick) {
      onCtaClick();
    } else if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('demo:open-modal'));
    }
  };

  if (error) {
    return (
      <div className="role-switcher role-switcher--error" role="alert">
        Unable to load demo content.
      </div>
    );
  }

  if (!data) {
    return (
      <div className="role-switcher role-switcher--loading" aria-busy="true">
        Loading demo…
      </div>
    );
  }

  const panelId = (role: RoleKey) => `role-panel-${role}`;
  const tabId = (role: RoleKey) => `role-tab-${role}`;

  return (
    <section className="role-switcher" aria-label="Role perspective switcher">
      <h3 className="role-switcher__event">{data.event}</h3>
      <div
        className="role-switcher__tablist"
        role="tablist"
        aria-label="Switch role perspective"
      >
        {ROLE_ORDER.map((role) => {
          const isActive = role === activeRole;
          return (
            <button
              key={role}
              id={tabId(role)}
              ref={(el) => { tabRefs.current[role] = el; }}
              type="button"
              role="tab"
              aria-selected={isActive}
              aria-controls={panelId(role)}
              tabIndex={isActive ? 0 : -1}
              className={`role-switcher__tab${isActive ? ' role-switcher__tab--active' : ''}`}
              onClick={() => switchRole(role)}
              onKeyDown={handleKeyDown}
            >
              <span aria-hidden="true" className="role-switcher__tab-icon">{ROLE_ICONS[role]}</span>
              <span className="role-switcher__tab-label">{data.roles[role].title}</span>
            </button>
          );
        })}
      </div>
      <div
        id={panelId(activeRole)}
        role="tabpanel"
        aria-labelledby={tabId(activeRole)}
        tabIndex={0}
        className={`role-switcher__panel${isFading ? ' role-switcher__panel--fading' : ''}`}
        data-role={activeRole}
      >
        <ul className="role-switcher__items">
          {data.roles[activeRole].content_items.map((item, idx) => (
            <li key={idx} className="role-switcher__item">
              <span aria-hidden="true" className="role-switcher__bullet">•</span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>
      <button
        type="button"
        className="role-switcher__cta"
        onClick={handleCtaClick}
      >
        See this in my own school's context
      </button>
    </section>
  );
}
