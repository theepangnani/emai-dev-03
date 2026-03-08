import './VideoEmbed.css'

interface VideoEmbedProps {
  url: string;
  title: string;
  provider: 'youtube' | 'loom' | 'other';
}

/**
 * Extract a YouTube video ID from common URL formats:
 * - https://www.youtube.com/watch?v=VIDEO_ID
 * - https://youtu.be/VIDEO_ID
 * - https://www.youtube.com/embed/VIDEO_ID
 */
export function extractYouTubeId(url: string): string | null {
  try {
    const u = new URL(url)

    // youtube.com/watch?v=ID
    if (u.hostname.includes('youtube.com') && u.searchParams.has('v')) {
      return u.searchParams.get('v')
    }

    // youtu.be/ID
    if (u.hostname === 'youtu.be') {
      const id = u.pathname.slice(1).split('/')[0]
      return id || null
    }

    // youtube.com/embed/ID
    if (u.hostname.includes('youtube.com') && u.pathname.startsWith('/embed/')) {
      const id = u.pathname.split('/embed/')[1]?.split(/[?/]/)[0]
      return id || null
    }
  } catch {
    // invalid URL
  }
  return null
}

/**
 * Extract a Loom video ID from common URL formats:
 * - https://www.loom.com/share/VIDEO_ID
 * - https://www.loom.com/embed/VIDEO_ID
 */
export function extractLoomId(url: string): string | null {
  try {
    const u = new URL(url)
    if (!u.hostname.includes('loom.com')) return null

    const match = u.pathname.match(/\/(share|embed)\/([a-zA-Z0-9]+)/)
    return match ? match[2] : null
  } catch {
    return null
  }
}

export function VideoEmbed({ url, title, provider }: VideoEmbedProps) {
  if (provider === 'youtube') {
    const videoId = extractYouTubeId(url)
    if (!videoId) return <LinkCard url={url} title={title} />

    return (
      <div className="video-embed">
        <iframe
          src={`https://www.youtube-nocookie.com/embed/${videoId}`}
          title={title}
          sandbox="allow-scripts allow-same-origin allow-popups"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          loading="lazy"
          referrerPolicy="no-referrer"
          allowFullScreen
        />
        <p className="video-embed-title">{title}</p>
        <a
          className="video-embed-external"
          href={url}
          target="_blank"
          rel="noopener noreferrer"
        >
          Open in YouTube ↗
        </a>
      </div>
    )
  }

  if (provider === 'loom') {
    const videoId = extractLoomId(url)
    if (!videoId) return <LinkCard url={url} title={title} />

    return (
      <div className="video-embed">
        <iframe
          src={`https://www.loom.com/embed/${videoId}`}
          title={title}
          sandbox="allow-scripts allow-same-origin allow-popups"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          loading="lazy"
          referrerPolicy="no-referrer"
          allowFullScreen
        />
        <p className="video-embed-title">{title}</p>
        <a
          className="video-embed-external"
          href={url}
          target="_blank"
          rel="noopener noreferrer"
        >
          Open in Loom ↗
        </a>
      </div>
    )
  }

  // provider === 'other'
  return <LinkCard url={url} title={title} />
}

function LinkCard({ url, title }: { url: string; title: string }) {
  return (
    <div className="video-embed">
      <div className="video-embed-link-card">
        <span className="video-embed-link-icon" aria-hidden="true">🔗</span>
        <span className="video-embed-link-card-title">{title}</span>
      </div>
      <a
        className="video-embed-external"
        href={url}
        target="_blank"
        rel="noopener noreferrer"
      >
        Open link ↗
      </a>
    </div>
  )
}
