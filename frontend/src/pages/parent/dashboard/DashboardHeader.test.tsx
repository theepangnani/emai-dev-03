/** CB-EDIGEST-002 E5 (#4593) — DashboardHeader unit tests. */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { ReactElement } from 'react';
import { DashboardHeader } from './DashboardHeader';

// DashboardHeader renders <Link to="..."> so all tests need a router context.
function renderWithRouter(ui: ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

afterEach(() => {
  vi.useRealTimers();
});

describe('DashboardHeader', () => {
  it('renders parent name + relative time', () => {
    // Pin clock so the "5 minutes ago" assertion is deterministic.
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-29T12:00:00Z'));
    const five = new Date('2026-04-29T11:55:00Z').toISOString();
    renderWithRouter(
      <DashboardHeader
        parentName="Theepan"
        lastRefreshedAt={five}
        isRefreshing={false}
        onRefresh={() => {}}
      />,
    );
    expect(screen.getByText(/Hi Theepan, here's today's view/)).toBeInTheDocument();
    expect(screen.getByText(/Last updated 5 minutes ago/)).toBeInTheDocument();
  });

  it('calls onRefresh when the refresh button is clicked', () => {
    const onRefresh = vi.fn();
    renderWithRouter(
      <DashboardHeader
        parentName="Maya"
        lastRefreshedAt={null}
        isRefreshing={false}
        onRefresh={onRefresh}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /refresh digest/i }));
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });

  it('disables the button and shows the Updating spinner state when isRefreshing=true', () => {
    renderWithRouter(
      <DashboardHeader
        parentName="Maya"
        lastRefreshedAt={null}
        isRefreshing={true}
        onRefresh={() => {}}
      />,
    );
    const btn = screen.getByRole('button', { name: /refreshing digest/i });
    expect(btn).toBeDisabled();
    expect(btn).toHaveAttribute('aria-busy', 'true');
    expect(screen.getByText(/Updating\.\.\./)).toBeInTheDocument();
  });

  it('enables the button when isRefreshing=false', () => {
    renderWithRouter(
      <DashboardHeader
        parentName="Maya"
        lastRefreshedAt={null}
        isRefreshing={false}
        onRefresh={() => {}}
      />,
    );
    const btn = screen.getByRole('button', { name: /refresh digest/i });
    expect(btn).not.toBeDisabled();
    expect(screen.getByText(/^Refresh$/)).toBeInTheDocument();
  });

  // #4682 — Settings link must be rendered next to Refresh so parents can
  // reach the settings UI when the dashboard flag is ON.
  it('renders a Settings link pointing to /email-digest/settings', () => {
    renderWithRouter(
      <DashboardHeader
        parentName="Maya"
        lastRefreshedAt={null}
        isRefreshing={false}
        onRefresh={() => {}}
      />,
    );
    const link = screen.getByRole('link', { name: /open digest settings/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', '/email-digest/settings');
  });
});
