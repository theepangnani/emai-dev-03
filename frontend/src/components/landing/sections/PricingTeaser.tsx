import './PricingTeaser.css'
import { emitCtaClick } from '../analytics'
import { useSectionViewTracker } from '../useSectionViewTracker'
import { useLandingCtas } from '../useLandingCtas'
import { LANDING_SECTION_ID } from '../sectionIds'

// TODO: drive from /api/pricing-tiers
const FAMILY_TIER_MONTHLY = '$9.99'

function PricingTeaser() {
  const sectionRef = useSectionViewTracker<HTMLElement>('pricing')
  const { secondaryLabel, secondaryHref, pricingMode } = useLandingCtas()
  const isWaitlist = pricingMode === 'waitlist'
  return (
    <section ref={sectionRef} data-landing="v2" className="landing-pricing">
      <div className="landing-pricing__inner">
        <h2 className="landing-pricing__headline">
          {isWaitlist ? (
            <>
              Free while you&rsquo;re on the waitlist.{' '}
              <em>Premium when you&rsquo;re ready.</em>
            </>
          ) : (
            <em>Premium when you&rsquo;re ready.</em>
          )}
        </h2>

        <div className="landing-pricing__grid" role="list">
          <article className="landing-pricing__card" role="listitem">
            <header className="landing-pricing__card-head">
              <h3 className="landing-pricing__tier">Free</h3>
              <p className="landing-pricing__price">
                <span className="landing-pricing__price-amount">$0</span>
              </p>
              <p className="landing-pricing__tagline">
                {isWaitlist
                  ? 'During waitlist. AI usage limits apply.'
                  : 'Free tier with daily AI usage limits.'}
              </p>
            </header>
            <ul className="landing-pricing__bullets">
              <li>Core ClassBridge access</li>
              <li>Limited daily AI usage</li>
              <li>Community support</li>
            </ul>
            <a
              className="landing-pricing__cta landing-pricing__cta--secondary"
              href={secondaryHref}
              onClick={() => emitCtaClick('secondary', 'pricing')}
            >
              {secondaryLabel}
            </a>
          </article>

          <article
            className="landing-pricing__card landing-pricing__card--featured"
            role="listitem"
            aria-label="Family plan, most popular"
          >
            <span className="landing-pricing__ribbon" aria-hidden="true">
              Most popular
            </span>
            <header className="landing-pricing__card-head">
              <h3 className="landing-pricing__tier">Family</h3>
              <p className="landing-pricing__price">
                <span className="landing-pricing__price-amount">{FAMILY_TIER_MONTHLY}</span>
                <span className="landing-pricing__price-period"> / month</span>
              </p>
              <p className="landing-pricing__tagline">For households ready to unlock every study tool.</p>
            </header>
            <ul className="landing-pricing__bullets">
              <li>Unlimited AI study guides</li>
              <li>Flash Tutor for the whole family</li>
              <li>Priority support</li>
            </ul>
            {isWaitlist ? (
              <a
                className="landing-pricing__cta landing-pricing__cta--primary"
                href={secondaryHref}
                onClick={() => emitCtaClick('primary', 'pricing')}
              >
                {secondaryLabel}
              </a>
            ) : (
              <>
                <span
                  className="landing-pricing__cta landing-pricing__cta--primary landing-pricing__cta--disabled"
                  role="button"
                  aria-disabled="true"
                >
                  Coming soon
                </span>
                <p className="landing-pricing__coming-soon-note">
                  Billing launches with Family tier &mdash;{' '}
                  <a href="/register">join the early-access list</a>
                </p>
              </>
            )}
          </article>

          <article className="landing-pricing__card" role="listitem">
            <header className="landing-pricing__card-head">
              <h3 className="landing-pricing__tier">School Board</h3>
              <p className="landing-pricing__price">
                <span className="landing-pricing__price-amount">Custom</span>
              </p>
              <p className="landing-pricing__tagline">Partnership pricing for districts.</p>
            </header>
            <ul className="landing-pricing__bullets">
              <li>Bulk-licensed for staff + families</li>
              <li>Compliance (MFIPPA/FIPPA)</li>
              <li>White-glove onboarding</li>
            </ul>
            <a
              className="landing-pricing__cta landing-pricing__cta--secondary"
              href="mailto:partners@classbridge.ca"
              onClick={() => emitCtaClick('board', 'pricing')}
            >
              Contact for Board Partnership
            </a>
          </article>
        </div>
      </div>
    </section>
  )
}

export default PricingTeaser

export const section = { id: LANDING_SECTION_ID.pricing, order: 90, component: PricingTeaser }
