import { screen } from '@testing-library/react'
import { renderWithProviders } from '../test/helpers'
import { CompliancePage } from './CompliancePage'

// The badge hrefs in compliance-badges.json point here. These anchor ids
// must match exactly or Proof Wall deep-links will 404-equivalent (scroll
// to top with no target).
const REQUIRED_ANCHORS = ['hosting', 'mfippa', 'pipeda', 'stack'] as const

describe('CompliancePage', () => {
  function renderPage() {
    return renderWithProviders(<CompliancePage />, { initialEntries: ['/compliance'] })
  }

  it('is a public route (renders without auth provider)', () => {
    // renderWithProviders does NOT supply AuthProvider — if CompliancePage
    // required auth it would throw here.
    expect(() => renderPage()).not.toThrow()
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
  })

  it('renders all four section headings', () => {
    renderPage()
    expect(
      screen.getByRole('heading', { level: 2, name: /Hosted in Canada/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 2, name: /MFIPPA-aligned/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 2, name: /PIPEDA-compliant/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 2, name: /Canadian-hosted stack/i }),
    ).toBeInTheDocument()
  })

  it('exposes the anchor ids expected by compliance-badges.json', () => {
    const { container } = renderPage()
    for (const id of REQUIRED_ANCHORS) {
      const section = container.querySelector(`#${id}`)
      expect(section).not.toBeNull()
      expect(section?.tagName.toLowerCase()).toBe('section')
    }
  })

  it('renders a table of contents whose links point to the correct anchors', () => {
    const { container } = renderPage()
    const toc = container.querySelector('.compliance-toc')
    expect(toc).not.toBeNull()

    const hrefs = Array.from(toc!.querySelectorAll('a')).map((a) => a.getAttribute('href'))
    expect(hrefs).toEqual(['#hosting', '#mfippa', '#pipeda', '#stack'])
  })

  it('keeps PIPEDA language as self-attested (audit requires hedging)', () => {
    renderPage()
    // "self-attested" appears in both the section heading and the caveat body.
    expect(screen.getAllByText(/self-attested/i).length).toBeGreaterThan(0)
  })

  it('keeps MFIPPA language as aligned (not certified)', () => {
    renderPage()
    // Body text should disambiguate "aligned" vs "certified"
    expect(screen.getByText(/not .{0,10}MFIPPA-certified/i)).toBeInTheDocument()
  })

  it('shows a last-updated date', () => {
    renderPage()
    expect(screen.getByText(/Last updated:/i)).toBeInTheDocument()
  })

  it('links back to the main site', () => {
    renderPage()
    const backLinks = screen.getAllByRole('link', { name: /Back to ClassBridge/i })
    expect(backLinks.length).toBeGreaterThan(0)
    expect(backLinks[0]).toHaveAttribute('href', '/')
  })
})
