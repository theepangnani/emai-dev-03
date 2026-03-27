import { render, screen } from '@testing-library/react';
import { vi, describe, it, expect } from 'vitest';
import type { CourseContentItem } from '../../../api/client';

// Mock heavy dependencies
vi.mock('../../../api/client', () => ({
  courseContentsApi: { update: vi.fn() },
}));

vi.mock('../../../components/ContentCard', () => ({
  ContentCard: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  MarkdownBody: ({ content }: { content: string }) => <div>{content}</div>,
  MarkdownErrorBoundary: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock('../../../utils/exportUtils', () => ({
  printElement: vi.fn(),
  downloadAsPdf: vi.fn(),
}));

vi.mock('../SourceFilesSection', () => ({
  SourceFilesSection: () => <div data-testid="source-files-section" />,
}));

import { DocumentTab } from '../DocumentTab';

function makeContent(overrides: Partial<CourseContentItem> = {}): CourseContentItem {
  return {
    id: 100,
    course_id: 1,
    course_name: 'Math',
    title: 'Test Document',
    description: null,
    text_content: 'Some content',
    content_type: 'notes',
    reference_url: null,
    google_classroom_url: null,
    created_by_user_id: 1,
    google_classroom_material_id: null,
    has_file: false,
    original_filename: null,
    file_size: null,
    mime_type: null,
    source_files_count: 0,
    category: null,
    display_order: 0,
    parent_content_id: null,
    is_master: true,
    material_group_id: null,
    created_at: '2026-03-14T00:00:00Z',
    updated_at: null,
    archived_at: null,
    last_viewed_at: null,
    ...overrides,
  };
}

const defaultProps = {
  downloading: false,
  onDownload: vi.fn(),
  onShowReplaceModal: vi.fn(),
  onContentUpdated: vi.fn(),
  showToast: vi.fn(),
  onShowRegenPrompt: vi.fn(),
  onReloadData: vi.fn().mockResolvedValue(undefined),
  onAddMoreFiles: vi.fn(),
};

describe('DocumentTab — hide OCR text when source files exist', () => {
  it('shows source files info card instead of OCR text when source_files_count > 0', () => {
    render(
      <DocumentTab
        content={makeContent({ has_file: false, text_content: 'OCR extracted text', source_files_count: 1, original_filename: 'test.pdf' })}
        {...defaultProps}
      />
    );
    expect(screen.getByText('Original document available in Source Files below.')).toBeInTheDocument();
    expect(screen.queryByText('Text Content')).not.toBeInTheDocument();
  });

  it('shows text content when no file and no source files', () => {
    render(
      <DocumentTab
        content={makeContent({ has_file: false, text_content: 'Some notes', source_files_count: 0 })}
        {...defaultProps}
      />
    );
    expect(screen.getByText('Text Content')).toBeInTheDocument();
  });
});

describe('DocumentTab — Add More Files button', () => {
  it('shows Add More Files button for master material', () => {
    render(
      <DocumentTab
        content={makeContent({ is_master: true, parent_content_id: null })}
        {...defaultProps}
      />
    );
    expect(screen.getByText(/Add More Files/)).toBeInTheDocument();
  });

  it('shows Add More Files button for standalone material', () => {
    render(
      <DocumentTab
        content={makeContent({ is_master: false, parent_content_id: null })}
        {...defaultProps}
      />
    );
    expect(screen.getByText(/Add More Files/)).toBeInTheDocument();
  });

  it('hides Add More Files button for sub-material', () => {
    render(
      <DocumentTab
        content={makeContent({ parent_content_id: 123 })}
        {...defaultProps}
      />
    );
    expect(screen.queryByText(/Add More Files/)).not.toBeInTheDocument();
  });
});
