/** CB-EDIGEST-002 E5 (#4593) — DashboardHeader unit tests. */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DashboardHeader } from './DashboardHeader';

afterEach(() => {
  vi.useRealTimers();
});

describe('DashboardHeader', () => {
  it('renders parent name + relative time', () => {
    // Pin clock so the "5 minutes ago" assertion is deterministic.
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-29T12:00:00Z'));
    const five = new Date('2026-04-29T11:55:00Z').toISOString();
    render(
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
    render(
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
    render(
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
    render(
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
});
