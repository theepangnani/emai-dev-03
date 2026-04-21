/**
 * CrossDeviceBar — CB-LAND-001 S10 (§6.136.1 §8, issue #3810).
 *
 * Study-anywhere device row + compatibility chips. Mindgrasp "Study anywhere"
 * pattern adapted to ClassBridge's multi-surface roadmap:
 *   Web (available now) · iOS (TestFlight, Phase 2) · Chrome Extension (Phase 4).
 *
 * Compatibility strip advertises the data sources and channels ClassBridge
 * already integrates with (Google Classroom, YRDSB board email, WhatsApp, Gmail).
 *
 * Strictly scoped under [data-landing="v2"]; never mounted by the legacy
 * LaunchLandingPage. Do not import into CB-DEMO-001 surfaces.
 */

import { Link } from 'react-router-dom'
import './CrossDeviceBar.css'

type DeviceStatus = 'available' | 'phase2' | 'phase4'

type DeviceCard = {
  id: string
  name: string
  glyph: string
  description: string
  status: DeviceStatus
  badgeLabel: string
  ctaLabel: string
  ctaHref: string | null
}

type CompatChip = {
  id: string
  label: string
  glyph: string
}

const DEVICES: ReadonlyArray<DeviceCard> = [
  {
    id: 'web',
    name: 'Web app',
    glyph: '🌐',
    description: 'Full ClassBridge on any modern browser — no install required.',
    status: 'available',
    badgeLabel: 'Available now',
    ctaLabel: 'Open ClassBridge',
    ctaHref: '/login',
  },
  {
    id: 'ios',
    name: 'iOS app',
    glyph: '',
    description: 'Native Expo build for iPhone and iPad — joining TestFlight in Phase 2.',
    status: 'phase2',
    badgeLabel: 'TestFlight — Phase 2',
    ctaLabel: 'Coming soon',
    ctaHref: null,
  },
  {
    id: 'chrome',
    name: 'Chrome Extension',
    glyph: '🧩',
    description: 'Capture board announcements and class pages straight from the browser bar.',
    status: 'phase4',
    badgeLabel: 'Coming Phase 4',
    ctaLabel: 'Coming soon',
    ctaHref: null,
  },
]

const COMPAT_CHIPS: ReadonlyArray<CompatChip> = [
  { id: 'classroom', label: 'Google Classroom', glyph: '◎' },
  { id: 'yrdsb', label: 'YRDSB (board email)', glyph: '✉' },
  { id: 'whatsapp', label: 'WhatsApp', glyph: '💬' },
  { id: 'gmail', label: 'Gmail', glyph: '✦' },
]

function CrossDeviceBar() {
  return (
    <section
      data-landing="v2"
      className="landing-devices"
      aria-labelledby="landing-devices-heading"
    >
      <div className="landing-devices__inner">
        <div className="landing-devices__copy">
          <h2 id="landing-devices-heading" className="landing-devices__headline">
            Wherever learning <em>happens.</em>
          </h2>
          <p className="landing-devices__sub">
            ClassBridge follows the student. Start on the web, carry the conversation
            to iOS when Phase 2 lands, and scoop up board announcements with the Chrome
            extension in Phase 4 — one account, every surface, no re-uploads.
          </p>
        </div>

        <div className="landing-devices__right">
          <ul className="landing-devices__cards" role="list">
            {DEVICES.map((device) => {
              const isAvailable = device.status === 'available'
              return (
                <li
                  key={device.id}
                  className={`landing-devices__card landing-devices__card--${device.status}`}
                  data-device={device.id}
                >
                  <div className="landing-devices__card-head">
                    <span className="landing-devices__glyph" aria-hidden="true">
                      {device.glyph || '◻'}
                    </span>
                    <span
                      className={`landing-devices__badge landing-devices__badge--${device.status}`}
                    >
                      {device.badgeLabel}
                    </span>
                  </div>
                  <h3 className="landing-devices__card-name">{device.name}</h3>
                  <p className="landing-devices__card-desc">{device.description}</p>
                  {isAvailable && device.ctaHref ? (
                    <Link
                      to={device.ctaHref}
                      className="landing-devices__cta landing-devices__cta--primary"
                    >
                      {device.ctaLabel}
                      <span aria-hidden="true"> →</span>
                    </Link>
                  ) : (
                    <button
                      type="button"
                      className="landing-devices__cta landing-devices__cta--disabled"
                      disabled
                      aria-disabled="true"
                    >
                      {device.ctaLabel}
                    </button>
                  )}
                </li>
              )
            })}
          </ul>

          <div
            className="landing-devices__compat"
            aria-labelledby="landing-devices-compat-label"
          >
            <span
              id="landing-devices-compat-label"
              className="landing-devices__compat-label"
            >
              Compatible with
            </span>
            <ul className="landing-devices__compat-list" role="list">
              {COMPAT_CHIPS.map((chip) => (
                <li key={chip.id} className="landing-devices__compat-chip">
                  <span className="landing-devices__compat-glyph" aria-hidden="true">
                    {chip.glyph}
                  </span>
                  <span className="landing-devices__compat-text">{chip.label}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  )
}

export default CrossDeviceBar

// Section registry entry consumed by LandingPageV2 (CB-LAND-001 §6.136.3).
// eslint-disable-next-line react-refresh/only-export-components
export const section = {
  id: 'devices',
  order: 80,
  component: CrossDeviceBar,
}
