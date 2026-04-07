import { useState, useEffect } from 'react';
import { resourceLinksApi, type ResourceLinkGroup, type ResourceLinkItem } from '../api/resourceLinks';
import './ResourceLinksSection.css';

/** Only allow http/https URLs to prevent javascript: XSS */
function safeHref(url: string): string {
  try {
    const parsed = new URL(url);
    if (parsed.protocol === 'http:' || parsed.protocol === 'https:') return url;
  } catch { /* invalid URL */ }
  return '#';
}

interface ResourceLinksSectionProps {
  courseContentId: number;
}

/* ── Icons ──────────────────────────────────── */

function BookLinkIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <path d="M4 2h12a1 1 0 011 1v14a1 1 0 01-1 1H4a1 1 0 01-1-1V3a1 1 0 011-1z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"/>
      <path d="M7 2v16" stroke="currentColor" strokeWidth="1.4"/>
      <path d="M10 7h4M10 10h4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
    </svg>
  );
}

function ExternalLinkIcon({ size = 12 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M6 3H3a1 1 0 00-1 1v9a1 1 0 001 1h9a1 1 0 001-1v-3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
      <path d="M9 2h5v5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M14 2L7 9" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
    </svg>
  );
}

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
      style={{ transform: open ? 'rotate(90deg)' : 'none', transition: 'transform 0.15s' }}
    >
      <path d="M6 4l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

/* ── YouTube thumbnail card ──────────────────── */

function YouTubeLinkCard({ link }: { link: ResourceLinkItem }) {
  // Validate video ID format (alphanumeric, hyphens, underscores only)
  const safeVideoId = link.youtube_video_id && /^[\w-]{6,20}$/.test(link.youtube_video_id)
    ? link.youtube_video_id : null;
  const rawThumb = link.thumbnail_url || (safeVideoId
    ? `https://img.youtube.com/vi/${safeVideoId}/mqdefault.jpg`
    : null);
  // Sanitize thumbnail URL — only allow http/https
  const thumbnailUrl = rawThumb ? safeHref(rawThumb) : null;

  return (
    <a
      href={safeHref(link.url)}
      target="_blank"
      rel="noopener noreferrer"
      className="rl-card rl-card--youtube"
    >
      {thumbnailUrl && (
        <div className="rl-card-thumb">
          <img src={thumbnailUrl} alt="" loading="lazy" />
          <span className="rl-card-play" aria-hidden="true">&#9654;</span>
        </div>
      )}
      <div className="rl-card-body">
        <span className="rl-card-title">{link.title || 'YouTube Video'}</span>
        {link.description && (
          <span className="rl-card-desc">{link.description.length > 100 ? link.description.slice(0, 97) + '...' : link.description}</span>
        )}
        <span className="rl-card-domain">youtube.com <ExternalLinkIcon /></span>
      </div>
    </a>
  );
}

/* ── External link card ─────────────────────── */

function ExtLinkCard({ link }: { link: ResourceLinkItem }) {
  let domain = '';
  try {
    domain = new URL(link.url).hostname.replace(/^www\./, '');
  } catch { /* ignore */ }

  const faviconUrl = domain ? `https://icons.duckduckgo.com/ip3/${domain}.ico` : null;

  return (
    <a
      href={safeHref(link.url)}
      target="_blank"
      rel="noopener noreferrer"
      className="rl-card rl-card--ext"
    >
      <div className="rl-card-icon">
        {faviconUrl ? (
          <img src={faviconUrl} alt="" width="20" height="20" loading="lazy" />
        ) : (
          <ExternalLinkIcon size={18} />
        )}
      </div>
      <div className="rl-card-body">
        <span className="rl-card-title">{link.title || 'External Resource'}</span>
        {link.description && (
          <span className="rl-card-desc">{link.description.length > 100 ? link.description.slice(0, 97) + '...' : link.description}</span>
        )}
        <span className="rl-card-domain">{domain} <ExternalLinkIcon /></span>
      </div>
    </a>
  );
}

/* ── Topic group ────────────────────────────── */

function TopicGroup({ heading, links, groupId }: { heading: string; links: ResourceLinkItem[]; groupId: string }) {
  const [open, setOpen] = useState(true);
  const youtubeLinks = links.filter(l => l.resource_type === 'youtube' && l.youtube_video_id);
  const otherLinks = links.filter(l => l.resource_type !== 'youtube' || !l.youtube_video_id);
  const bodyId = `rl-group-${groupId}`;

  return (
    <div className="rl-topic-group">
      <button className="rl-topic-heading" onClick={() => setOpen(v => !v)} aria-expanded={open} aria-controls={bodyId} type="button">
        <ChevronIcon open={open} />
        <span>{heading}</span>
        <span className="rl-topic-count">{links.length}</span>
      </button>
      <div id={bodyId} className="rl-topic-body" hidden={!open}>
        <div className="rl-cards-grid">
          {youtubeLinks.map(link => (
            <YouTubeLinkCard key={link.id} link={link} />
          ))}
          {otherLinks.map(link => (
            <ExtLinkCard key={link.id} link={link} />
          ))}
        </div>
      </div>
    </div>
  );
}

/* ── Main section ───────────────────────────── */

export function ResourceLinksSection({ courseContentId }: ResourceLinksSectionProps) {
  const [groups, setGroups] = useState<ResourceLinkGroup[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    resourceLinksApi.list(courseContentId)
      .then(data => { if (!cancelled) setGroups(data); })
      .catch(() => { /* silently fail */ })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [courseContentId]);

  if (loading) {
    return (
      <div className="rl-section rl-section--loading" aria-busy="true">
        <div className="rl-skeleton-header" />
        <div className="rl-skeleton-card" />
        <div className="rl-skeleton-card" />
      </div>
    );
  }

  const totalLinks = groups.reduce((sum, g) => sum + g.links.length, 0);
  if (totalLinks === 0) return null;

  return (
    <div className="rl-section">
      <div className="rl-section-header">
        <BookLinkIcon />
        <h3 className="rl-section-title">Helpful Resources</h3>
        <span className="rl-curated-label">AI-curated resources</span>
      </div>
      {groups.map((group, i) => (
        <TopicGroup
          key={group.topic_heading || `__other_${i}`}
          groupId={`${i}`}
          heading={group.topic_heading || 'Other Resources'}
          links={group.links}
        />
      ))}
    </div>
  );
}
