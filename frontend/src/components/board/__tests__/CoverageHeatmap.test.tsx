/**
 * CB-CMCP-001 M3-H 3H-1 (#4663) — CoverageHeatmap unit tests.
 *
 * Coverage:
 *   - Renders a strand × grade grid with mocked data.
 *   - Cell colour buckets follow the spec: 0=red, 1-3=amber, 4+=green.
 *   - Strands without artifacts at a given grade still render a 0-cell
 *     so columns line up across rows.
 *   - Empty map → empty-state card (no grid).
 *   - All-zero map → empty-state card (no grid).
 *   - Legend renders when grid is shown.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { CoverageHeatmap, type CoverageMap } from '../CoverageHeatmap';

describe('CoverageHeatmap', () => {
  it('renders the grid with strand rows + grade columns + count cells', () => {
    const map: CoverageMap = {
      A: { 5: 2, 6: 5 },
      B: { 5: 0, 6: 1 },
    };
    render(<CoverageHeatmap coverageMap={map} />);

    // Grid container present.
    const grid = screen.getByTestId('coverage-heatmap');
    expect(grid).toBeInTheDocument();

    // Row headers — one per strand.
    expect(screen.getByText('A')).toBeInTheDocument();
    expect(screen.getByText('B')).toBeInTheDocument();

    // Column headers — one per grade in union of all strands.
    expect(screen.getByText('G5')).toBeInTheDocument();
    expect(screen.getByText('G6')).toBeInTheDocument();

    // Cells exist with the expected counts and bucket attributes.
    const cellA5 = screen.getByTestId('coverage-cell-A-5');
    expect(cellA5).toHaveAttribute('data-count', '2');
    expect(cellA5).toHaveAttribute('data-bucket', 'sparse');

    const cellA6 = screen.getByTestId('coverage-cell-A-6');
    expect(cellA6).toHaveAttribute('data-count', '5');
    expect(cellA6).toHaveAttribute('data-bucket', 'covered');

    const cellB5 = screen.getByTestId('coverage-cell-B-5');
    expect(cellB5).toHaveAttribute('data-count', '0');
    expect(cellB5).toHaveAttribute('data-bucket', 'empty');

    const cellB6 = screen.getByTestId('coverage-cell-B-6');
    expect(cellB6).toHaveAttribute('data-count', '1');
    expect(cellB6).toHaveAttribute('data-bucket', 'sparse');
  });

  it('fills 0-cells when a strand has no artifacts at a column grade', () => {
    // Strand B has no entry for grade 6 in the input map — the heatmap
    // should still render a 0-cell at (B, 6) so columns line up.
    const map: CoverageMap = {
      A: { 5: 1, 6: 4 },
      B: { 5: 1 },
    };
    render(<CoverageHeatmap coverageMap={map} />);

    const cellB6 = screen.getByTestId('coverage-cell-B-6');
    expect(cellB6).toHaveAttribute('data-count', '0');
    expect(cellB6).toHaveAttribute('data-bucket', 'empty');
  });

  it('shows legend with three bucket swatches', () => {
    const map: CoverageMap = { A: { 5: 1 } };
    render(<CoverageHeatmap coverageMap={map} />);
    expect(screen.getByText('0 (none)')).toBeInTheDocument();
    expect(screen.getByText(/1.*3.*sparse/)).toBeInTheDocument();
    expect(screen.getByText(/4\+.*covered/)).toBeInTheDocument();
  });

  it('renders empty-state card when coverage map is empty', () => {
    render(<CoverageHeatmap coverageMap={{}} />);
    expect(screen.getByTestId('coverage-heatmap-empty')).toBeInTheDocument();
    expect(screen.queryByTestId('coverage-heatmap')).not.toBeInTheDocument();
    expect(screen.getByText('No coverage yet')).toBeInTheDocument();
  });

  it('renders empty-state card when every cell is zero', () => {
    const map: CoverageMap = { A: { 5: 0, 6: 0 }, B: { 5: 0 } };
    render(<CoverageHeatmap coverageMap={map} />);
    expect(screen.getByTestId('coverage-heatmap-empty')).toBeInTheDocument();
    expect(screen.queryByTestId('coverage-heatmap')).not.toBeInTheDocument();
  });

  it('renders empty-state card when there are strands but no grades', () => {
    // Pathological shape: a strand with an empty grade dict. The grid
    // cannot render meaningfully without grade columns, so empty-state
    // is the correct fallback.
    const map: CoverageMap = { A: {} };
    render(<CoverageHeatmap coverageMap={map} />);
    expect(screen.getByTestId('coverage-heatmap-empty')).toBeInTheDocument();
  });
});
