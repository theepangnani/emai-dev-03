import { describe, it, expect } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import CrossDeviceBar, { section } from './CrossDeviceBar'

function renderBar() {
  return render(
    <MemoryRouter>
      <CrossDeviceBar />
    </MemoryRouter>,
  )
}

describe('CrossDeviceBar (CB-LAND-001 S10)', () => {
  it('renders the required section heading with italic accent', () => {
    renderBar()
    const heading = screen.getByRole('heading', { level: 2 })
    expect(heading.textContent?.toLowerCase()).toMatch(/wherever learning happens\./)
    // the italic accent word is wrapped in <em>
    expect(heading.querySelector('em')?.textContent).toBe('happens.')
  }, 20000)

  it('wraps itself in <section data-landing="v2" class="landing-devices">', () => {
    const { container } = renderBar()
    const root = container.querySelector('section[data-landing="v2"].landing-devices')
    expect(root).not.toBeNull()
  })

  it('renders exactly 3 device cards (Web, iOS, Chrome) with correct badges', () => {
    renderBar()
    const cards = screen.getAllByRole('listitem', { hidden: false }).filter((li) =>
      li.className.includes('landing-devices__card'),
    )
    expect(cards).toHaveLength(3)

    expect(screen.getByText('Web app')).toBeInTheDocument()
    expect(screen.getByText('iOS app')).toBeInTheDocument()
    expect(screen.getByText('Chrome Extension')).toBeInTheDocument()

    expect(screen.getByText('Available now')).toBeInTheDocument()
    expect(screen.getByText('TestFlight — Phase 2')).toBeInTheDocument()
    expect(screen.getByText('Coming Phase 4')).toBeInTheDocument()
  })

  it('Web app card renders an enabled "Open ClassBridge" link to /login', () => {
    renderBar()
    const link = screen.getByRole('link', { name: /open classbridge/i })
    expect(link).toHaveAttribute('href', '/login')
  })

  it('iOS and Chrome CTAs are disabled buttons (not links)', () => {
    renderBar()
    const buttons = screen.getAllByRole('button', { name: /coming soon/i })
    expect(buttons).toHaveLength(2)
    buttons.forEach((btn) => {
      expect(btn).toBeDisabled()
      expect(btn).toHaveAttribute('aria-disabled', 'true')
    })
  })

  it('renders the 4 compatibility chips (Classroom, YRDSB, WhatsApp, Gmail)', () => {
    renderBar()
    const compatList = screen
      .getByText(/compatible with/i)
      .parentElement?.querySelector('ul')
    expect(compatList).not.toBeNull()
    const chips = within(compatList as HTMLElement).getAllByRole('listitem')
    expect(chips).toHaveLength(4)

    expect(within(compatList as HTMLElement).getByText('Google Classroom')).toBeInTheDocument()
    expect(within(compatList as HTMLElement).getByText('YRDSB (board email)')).toBeInTheDocument()
    expect(within(compatList as HTMLElement).getByText('WhatsApp')).toBeInTheDocument()
    expect(within(compatList as HTMLElement).getByText('Gmail')).toBeInTheDocument()
  })

  it('exports a section registry entry with id="devices" and order=80', () => {
    expect(section.id).toBe('devices')
    expect(section.order).toBe(80)
    expect(section.component).toBe(CrossDeviceBar)
  })
})
