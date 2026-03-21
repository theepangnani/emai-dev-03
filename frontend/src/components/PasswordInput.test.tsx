import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { PasswordInput } from './PasswordInput'

describe('PasswordInput', () => {
  it('renders a password input by default', () => {
    render(<PasswordInput value="" onChange={() => {}} id="pw" />)

    const input = document.getElementById('pw')!
    expect(input).toHaveAttribute('type', 'password')
  })

  it('toggles input type when eye button is clicked', async () => {
    const user = userEvent.setup()
    render(<PasswordInput value="secret" onChange={() => {}} id="pw" />)

    const input = document.getElementById('pw')!
    const toggleBtn = screen.getByRole('button', { name: /show password/i })

    expect(input).toHaveAttribute('type', 'password')

    await user.click(toggleBtn)
    expect(input).toHaveAttribute('type', 'text')

    // aria-label should update
    expect(screen.getByRole('button', { name: /hide password/i })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /hide password/i }))
    expect(input).toHaveAttribute('type', 'password')
    expect(screen.getByRole('button', { name: /show password/i })).toBeInTheDocument()
  })

  it('renders eye-open icon when password is hidden', () => {
    render(<PasswordInput value="" onChange={() => {}} />)

    const btn = screen.getByRole('button', { name: /show password/i })
    // Open eye SVG has a circle element (the iris)
    const svg = btn.querySelector('svg')!
    expect(svg.querySelector('circle')).toBeInTheDocument()
  })

  it('renders slashed-eye icon when password is visible', async () => {
    const user = userEvent.setup()
    render(<PasswordInput value="" onChange={() => {}} />)

    await user.click(screen.getByRole('button', { name: /show password/i }))

    const btn = screen.getByRole('button', { name: /hide password/i })
    const svg = btn.querySelector('svg')!
    // Slashed eye SVG has a line element (the slash)
    expect(svg.querySelector('line')).toBeInTheDocument()
    // And no circle
    expect(svg.querySelector('circle')).not.toBeInTheDocument()
  })

  it('passes through html attributes', () => {
    render(
      <PasswordInput
        value="test"
        onChange={() => {}}
        id="my-pw"
        name="password"
        placeholder="Enter password"
        required
        minLength={8}
        autoComplete="new-password"
      />
    )

    const input = document.getElementById('my-pw')!
    expect(input).toHaveAttribute('name', 'password')
    expect(input).toHaveAttribute('placeholder', 'Enter password')
    expect(input).toBeRequired()
    expect(input).toHaveAttribute('minLength', '8')
    expect(input).toHaveAttribute('autoComplete', 'new-password')
  })

  it('supports disabled state', () => {
    render(<PasswordInput value="" onChange={() => {}} id="pw" disabled />)

    const input = document.getElementById('pw')!
    expect(input).toBeDisabled()
  })
})
