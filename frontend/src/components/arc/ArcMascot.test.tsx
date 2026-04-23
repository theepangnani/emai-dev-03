import { render } from '@testing-library/react'
import { ArcMascot } from './ArcMascot'

describe('ArcMascot accessibility', () => {
  it('default: renders with role="img" and an aria-label', () => {
    const { container } = render(<ArcMascot />)
    const svg = container.querySelector('svg')
    expect(svg).not.toBeNull()
    expect(svg?.getAttribute('role')).toBe('img')
    expect(svg?.getAttribute('aria-label')).toBe('ClassBridge companion')
    expect(svg?.getAttribute('aria-hidden')).toBeNull()
  })

  it('default: respects a custom label', () => {
    const { container } = render(<ArcMascot label="Hello Arc" />)
    const svg = container.querySelector('svg')
    expect(svg?.getAttribute('aria-label')).toBe('Hello Arc')
  })

  it('decorative: has aria-hidden="true" and no role/aria-label', () => {
    const { container } = render(<ArcMascot decorative />)
    const svg = container.querySelector('svg')
    expect(svg).not.toBeNull()
    expect(svg?.getAttribute('aria-hidden')).toBe('true')
    expect(svg?.getAttribute('role')).toBeNull()
    expect(svg?.getAttribute('aria-label')).toBeNull()
    expect(svg?.getAttribute('focusable')).toBe('false')
  })
})
