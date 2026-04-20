import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SourcePicker } from './SourcePicker';

describe('SourcePicker', () => {
  function setup(overrides: Partial<React.ComponentProps<typeof SourcePicker>> = {}) {
    const onChange = vi.fn();
    const onCustomTextChange = vi.fn();
    const utils = render(
      <SourcePicker
        value="sample"
        customText=""
        onChange={onChange}
        onCustomTextChange={onCustomTextChange}
        {...overrides}
      />,
    );
    return { onChange, onCustomTextChange, ...utils };
  }

  it('renders the sample radio as checked by default', () => {
    setup();
    const radios = screen.getAllByRole('radio');
    const sampleRadio = radios.find((r) => (r as HTMLInputElement).value === 'sample') as HTMLInputElement;
    expect(sampleRadio).toBeTruthy();
    expect(sampleRadio.checked).toBe(true);
    // Sample preview panel visible by default.
    expect(screen.getByLabelText(/Pre-loaded sample/i)).toBeInTheDocument();
  });

  it('calls onChange with "paste" when the paste option is clicked', async () => {
    const user = userEvent.setup();
    const { onChange } = setup();
    const pasteLabel = screen.getByText(/paste your own text/i).closest('label')!;
    await user.click(pasteLabel);
    expect(onChange).toHaveBeenCalledWith('paste');
  });

  it('calls onCustomTextChange when the user types in the textarea', async () => {
    const user = userEvent.setup();
    const { onCustomTextChange } = setup({ value: 'paste', customText: '' });
    const textarea = screen.getByRole('textbox', { name: /your own text/i });
    await user.type(textarea, 'H');
    expect(onCustomTextChange).toHaveBeenCalled();
    expect(onCustomTextChange.mock.calls[0][0]).toBe('H');
  });

  it('clicking Upload opens the upsell, keeps radio unchecked, does NOT call onChange', async () => {
    const user = userEvent.setup();
    const { onChange, container } = setup();
    expect(screen.queryByRole('region', { name: /upload/i })).toBeNull();
    const uploadBtn = screen.getByRole('button', { name: /upload a document/i });
    await user.click(uploadBtn);
    expect(screen.getByRole('region', { name: /upload/i })).toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();
    const uploadRadio = container.querySelector<HTMLInputElement>('input[type="radio"][value="upload"]');
    expect(uploadRadio).not.toBeNull();
    expect(uploadRadio!.checked).toBe(false);
    expect(uploadRadio!).toBeDisabled();
    expect(uploadRadio!.getAttribute('aria-hidden')).toBe('true');
  });

  it('dismiss button collapses the upload upsell', async () => {
    const user = userEvent.setup();
    setup();
    await user.click(screen.getByRole('button', { name: /upload a document/i }));
    expect(screen.getByRole('region', { name: /upload/i })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /dismiss/i }));
    expect(screen.queryByRole('region', { name: /upload/i })).toBeNull();
  });

  it('shows word count and too-long warning when pasted text exceeds 500 words', () => {
    const longText = Array.from({ length: 501 }, (_, i) => `w${i}`).join(' ');
    setup({ value: 'paste', customText: longText });
    expect(screen.getByText(/501 \/ 500 words — too long/i)).toBeInTheDocument();
  });
});
