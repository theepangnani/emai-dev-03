import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import PricingTeaser, { section } from './PricingTeaser'

describe('PricingTeaser', () => {
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

  it('renders headline with italic second sentence', () => {
    const { container } = render(<PricingTeaser />)
    const headline = container.querySelector('.landing-pricing__headline')
    expect(headline).toBeInTheDocument()
    expect(headline?.textContent).toMatch(/Free while you.?re on the waitlist\./)
    const em = headline?.querySelector('em')
    expect(em).not.toBeNull()
    expect(em?.textContent).toMatch(/Premium when you.?re ready\./)
  })

  it('renders $9.99 placeholder for Family tier', () => {
    render(<PricingTeaser />)
    expect(screen.getByText('$9.99')).toBeInTheDocument()
  })

  it('Join Waitlist CTAs link to /waitlist; Board CTA uses mailto', () => {
    render(<PricingTeaser />)
    const waitlistCtas = screen.getAllByRole('link', { name: /Join Waitlist/i })
    expect(waitlistCtas).toHaveLength(2)
    waitlistCtas.forEach((link) => {
      expect(link).toHaveAttribute('href', '/waitlist')
    })
    const boardCta = screen.getByRole('link', { name: /Contact for Board Partnership/i })
    expect(boardCta).toHaveAttribute('href', 'mailto:partners@classbridge.ca')
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
