import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

// #3889 — mock useFeature so we can exercise both waitlist-on and waitlist-off
// branches of the PricingTeaser headline + tagline + CTA copy.
const useFeatureMock = vi.fn<(key: string) => boolean>()
vi.mock('../../../hooks/useFeatureToggle', () => ({
  useFeature: (key: string) => useFeatureMock(key),
}))

import PricingTeaser, { section } from './PricingTeaser'

describe('PricingTeaser', () => {
  beforeEach(() => {
    useFeatureMock.mockReset()
    useFeatureMock.mockReturnValue(true) // default pre-launch posture
  })

  it('renders 3 tier cards (Free, Family, School Board)', () => {
    const { container } = render(<PricingTeaser />)
    expect(screen.getByRole('heading', { name: /^Free$/ })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /^Family$/ })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /^School Board$/ })).toBeInTheDocument()
    const cards = container.querySelectorAll('.landing-pricing__card')
    expect(cards).toHaveLength(3)
  })

  it('shows "Most popular" ribbon on Family card', () => {
    render(<PricingTeaser />)
    const familyCard = screen.getByLabelText(/Family plan, most popular/i)
    expect(familyCard).toBeInTheDocument()
    expect(familyCard.className).toMatch(/landing-pricing__card--featured/)
    expect(familyCard.textContent).toMatch(/Most popular/i)
  })

  it('renders headline with italic second sentence (waitlist-on)', () => {
    const { container } = render(<PricingTeaser />)
    const headline = container.querySelector('.landing-pricing__headline')
    expect(headline).toBeInTheDocument()
    expect(headline?.textContent).toMatch(/Free while you.?re on the waitlist\./)
    const em = headline?.querySelector('em')
    expect(em).not.toBeNull()
    expect(em?.textContent).toMatch(/Premium when you.?re ready\./)
  })

  it('renders launch-mode headline without the waitlist sentence when waitlist_enabled is false (#3889)', () => {
    useFeatureMock.mockReturnValue(false)
    const { container } = render(<PricingTeaser />)
    const headline = container.querySelector('.landing-pricing__headline')
    expect(headline).toBeInTheDocument()
    expect(headline?.textContent).not.toMatch(/waitlist/i)
    const em = headline?.querySelector('em')
    expect(em?.textContent).toMatch(/Premium when you.?re ready\./)
  })

  it('swaps the Free-tier tagline to the launch-mode copy when waitlist_enabled is false (#3889)', () => {
    useFeatureMock.mockReturnValue(false)
    render(<PricingTeaser />)
    expect(screen.getByText(/free tier with daily ai usage limits\./i)).toBeInTheDocument()
    expect(screen.queryByText(/during waitlist\./i)).not.toBeInTheDocument()
  })

  it('renders $9.99 placeholder for Family tier', () => {
    render(<PricingTeaser />)
    expect(screen.getByText('$9.99')).toBeInTheDocument()
  })

  it('waitlist CTAs link to /waitlist when waitlist_enabled is true; Board CTA uses mailto', () => {
    render(<PricingTeaser />)
    // Copy is now driven by `useLandingCtas` — "Join the waitlist".
    const waitlistCtas = screen.getAllByRole('link', { name: /Join the waitlist/i })
    expect(waitlistCtas).toHaveLength(2)
    waitlistCtas.forEach((link) => {
      expect(link).toHaveAttribute('href', '/waitlist')
    })
    const boardCta = screen.getByRole('link', { name: /Contact for Board Partnership/i })
    expect(boardCta).toHaveAttribute('href', 'mailto:partners@classbridge.ca')
  })

  it('routes Free CTA to /register with "Get Started" copy when waitlist_enabled is false (#3889)', () => {
    useFeatureMock.mockReturnValue(false)
    render(<PricingTeaser />)
    // No /waitlist anywhere in the tree.
    expect(
      screen.queryByRole('link', { name: /Join Waitlist/i }),
    ).not.toBeInTheDocument()
    const launchCtas = screen.getAllByRole('link', { name: /Get Started/i })
    // #3893 — Family-tier CTA is now a disabled "Coming soon" span in launch
    // mode, so only the Free-tier "Get Started" link routes to /register.
    expect(launchCtas).toHaveLength(1)
    launchCtas.forEach((link) => {
      expect(link).toHaveAttribute('href', '/register')
    })
  })

  it('gates Family-tier CTA as disabled "Coming soon" in launch mode (#3893)', () => {
    useFeatureMock.mockReturnValue(false)
    const { container } = render(<PricingTeaser />)
    const familyCard = screen.getByLabelText(/Family plan, most popular/i)
    const disabledCta = familyCard.querySelector(
      '[role="button"][aria-disabled="true"]',
    )
    expect(disabledCta).not.toBeNull()
    expect(disabledCta?.textContent).toMatch(/Coming soon/i)
    // The "early-access list" phrase links to /register.
    const earlyAccessLink = screen.getByRole('link', {
      name: /early-access list/i,
    })
    expect(earlyAccessLink).toHaveAttribute('href', '/register')
    // No /waitlist links anywhere in any tier card.
    const tierCards = container.querySelectorAll('.landing-pricing__card')
    tierCards.forEach((card) => {
      const waitlistLinks = card.querySelectorAll('a[href="/waitlist"]')
      expect(waitlistLinks).toHaveLength(0)
    })
  })

  it('wraps content in <section data-landing="v2" class="landing-pricing">', () => {
    const { container } = render(<PricingTeaser />)
    const section = container.querySelector('section[data-landing="v2"].landing-pricing')
    expect(section).not.toBeNull()
  })

  it('exports section registration with id/order/component', () => {
    expect(section.id).toBe('pricing')
    expect(section.order).toBe(90)
    expect(section.component).toBe(PricingTeaser)
  })
})
