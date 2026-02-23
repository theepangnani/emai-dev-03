/**
 * Utilities for printing and downloading content as PDF.
 */

const PRINT_STYLES = `
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #1a1a2e; line-height: 1.6; padding: 24px; max-width: 800px; margin: 0 auto; }
  h1, h2, h3, h4 { margin-top: 1.2em; margin-bottom: 0.5em; }
  h1 { font-size: 1.6rem; border-bottom: 2px solid #49b8c0; padding-bottom: 0.4rem; }
  h2 { font-size: 1.3rem; color: #6c3eb8; }
  h3 { font-size: 1.1rem; }
  table { border-collapse: collapse; width: 100%; margin: 1em 0; }
  th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; }
  th { background: #f5f5f5; font-weight: 600; }
  ul, ol { padding-left: 1.5em; }
  .print-title { font-size: 1.6rem; font-weight: 700; margin-bottom: 0.25em; }
  .print-subtitle { color: #666; font-size: 0.9rem; margin-bottom: 1.5em; }
  .print-quiz-item { margin-bottom: 1.5em; padding-bottom: 1em; border-bottom: 1px solid #eee; }
  .print-quiz-question { font-weight: 600; margin-bottom: 0.4em; }
  .print-quiz-options { list-style: none; padding-left: 0.5em; margin: 0.3em 0; }
  .print-quiz-options li { padding: 0.2em 0.4em; margin: 0.15em 0; border-radius: 4px; }
  .print-quiz-options li.correct { background: #e8f5e9; font-weight: 500; }
  .print-quiz-explanation { color: #555; font-size: 0.9em; font-style: italic; margin-top: 0.3em; }
  .print-fc-item { display: flex; gap: 1em; padding: 0.6em 0; border-bottom: 1px solid #eee; }
  .print-fc-num { font-weight: 700; color: #6c3eb8; min-width: 2em; }
  .print-fc-front { font-weight: 600; min-width: 40%; }
  .print-fc-back { color: #444; }
  .content-card-body h1, .content-card-body h2, .content-card-body h3 { margin-top: 1em; }
  .content-card-body p { margin: 0.5em 0; }
  .content-card-body ul, .content-card-body ol { margin: 0.5em 0; }
  .content-card-ocr-notice { display: none; }
  @media print { body { padding: 0; } }
`;

/** Open a print dialog with only the given element's content. */
export function printElement(element: HTMLElement, title: string) {
  const win = window.open('', '_blank');
  if (!win) return;

  win.document.write(`<!DOCTYPE html><html><head><meta charset="utf-8"><title>${title}</title><style>${PRINT_STYLES}</style></head><body>${element.innerHTML}</body></html>`);
  win.document.close();

  // Wait for content to load before printing
  win.onload = () => {
    win.print();
    win.close();
  };
  // Fallback for browsers where onload doesn't fire reliably
  setTimeout(() => {
    if (!win.closed) {
      win.print();
      win.close();
    }
  }, 500);
}

/** Download the given element as a PDF file. */
export async function downloadAsPdf(element: HTMLElement, filename: string) {
  const html2pdf = (await import('html2pdf.js')).default;
  const opt = {
    margin: [10, 10, 10, 10] as [number, number, number, number],
    filename: filename.endsWith('.pdf') ? filename : `${filename}.pdf`,
    image: { type: 'jpeg' as const, quality: 0.95 },
    html2canvas: { scale: 2, useCORS: true, logging: false },
    jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' as const },
  };
  await html2pdf().set(opt).from(element).save();
}
