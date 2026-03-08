import { render, screen } from '@testing-library/react'
import { extractYouTubeId, extractLoomId, VideoEmbed } from '../VideoEmbed'

// ── URL Parsing ─────────────────────────────────────────────────

describe('extractYouTubeId', () => {
  it('extracts ID from youtube.com/watch?v=', () => {
    expect(extractYouTubeId('https://www.youtube.com/watch?v=dQw4w9WgXcQ')).toBe('dQw4w9WgXcQ')
  })

  it('extracts ID from youtu.be/', () => {
    expect(extractYouTubeId('https://youtu.be/dQw4w9WgXcQ')).toBe('dQw4w9WgXcQ')
  })

  it('extracts ID from youtube.com/embed/', () => {
    expect(extractYouTubeId('https://www.youtube.com/embed/dQw4w9WgXcQ')).toBe('dQw4w9WgXcQ')
  })

  it('extracts ID with extra query params', () => {
    expect(extractYouTubeId('https://www.youtube.com/watch?v=abc123&t=30')).toBe('abc123')
  })

  it('returns null for invalid URL', () => {
    expect(extractYouTubeId('not-a-url')).toBeNull()
  })

  it('returns null for non-YouTube URL', () => {
    expect(extractYouTubeId('https://vimeo.com/12345')).toBeNull()
  })
})

describe('extractLoomId', () => {
  it('extracts ID from loom.com/share/', () => {
    expect(extractLoomId('https://www.loom.com/share/abc123def456')).toBe('abc123def456')
  })

  it('extracts ID from loom.com/embed/', () => {
    expect(extractLoomId('https://www.loom.com/embed/abc123def456')).toBe('abc123def456')
  })

  it('returns null for non-Loom URL', () => {
    expect(extractLoomId('https://youtube.com/watch?v=abc')).toBeNull()
  })

  it('returns null for invalid URL', () => {
    expect(extractLoomId('not-a-url')).toBeNull()
  })
})

// ── Component Rendering ─────────────────────────────────────────

describe('VideoEmbed', () => {
  it('renders YouTube iframe with correct src', () => {
    render(
      <VideoEmbed
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        title="Test Video"
        provider="youtube"
      />
    )

    const iframe = document.querySelector('iframe')
    expect(iframe).not.toBeNull()
    expect(iframe!.src).toBe('https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ')
    expect(iframe!.title).toBe('Test Video')
    expect(screen.getByText('Test Video')).toBeInTheDocument()
    expect(screen.getByText('Open in YouTube ↗')).toBeInTheDocument()
  })

  it('renders Loom iframe with correct src', () => {
    render(
      <VideoEmbed
        url="https://www.loom.com/share/abc123def456"
        title="Loom Recording"
        provider="loom"
      />
    )

    const iframe = document.querySelector('iframe')
    expect(iframe).not.toBeNull()
    expect(iframe!.src).toBe('https://www.loom.com/embed/abc123def456')
    expect(screen.getByText('Open in Loom ↗')).toBeInTheDocument()
  })

  it('renders link card for other provider', () => {
    render(
      <VideoEmbed
        url="https://example.com/video"
        title="External Video"
        provider="other"
      />
    )

    expect(document.querySelector('iframe')).toBeNull()
    expect(screen.getByText('External Video')).toBeInTheDocument()
    expect(screen.getByText('Open link ↗')).toBeInTheDocument()
  })

  it('renders link card when YouTube ID cannot be extracted', () => {
    render(
      <VideoEmbed
        url="https://youtube.com/invalid"
        title="Bad Link"
        provider="youtube"
      />
    )

    expect(document.querySelector('iframe')).toBeNull()
    expect(screen.getByText('Open link ↗')).toBeInTheDocument()
  })

  it('external link has target="_blank" and rel="noopener noreferrer"', () => {
    render(
      <VideoEmbed
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        title="Test"
        provider="youtube"
      />
    )

    const link = screen.getByText('Open in YouTube ↗')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('iframe has security attributes', () => {
    render(
      <VideoEmbed
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        title="Test"
        provider="youtube"
      />
    )

    const iframe = document.querySelector('iframe')!
    expect(iframe.getAttribute('sandbox')).toBe('allow-scripts allow-same-origin allow-popups')
    expect(iframe.getAttribute('loading')).toBe('lazy')
    expect(iframe.getAttribute('referrerpolicy')).toBe('no-referrer')
  })
})
