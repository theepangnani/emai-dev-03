import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { resourceLinksApi, type ResourceLinkGroup, type ResourceLinkItem } from '../../api/resourceLinks';
import './VideosLinksTab.css';

interface VideosLinksTabProps {
  courseContentId: number;
}

/* ── Icons ──────────────────────────────────────── */

function VideoIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="2" y="4" width="20" height="16" rx="3" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M10 9l5 3-5 3V9z" fill="currentColor"/>
    </svg>
  );
}

function ExternalLinkIcon({ size = 14 }: { size?: number }) {
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
      className={`vl-chevron${open ? ' open' : ''}`}
    >
      <path d="M6 4l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M8 3v10M3 8h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  );
}

function DeleteIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  );
}

/* ── YouTubeEmbed ───────────────────────────────── */

function YouTubeEmbed({ videoId, title, description }: { videoId: string; title: string | null; description: string | null }) {
  return (
    <div className="vl-youtube-card">
      <div className="vl-youtube-wrapper">
        <iframe
          src={`https://www.youtube.com/embed/${videoId}`}
          style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%' }}
          frameBorder="0"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowFullScreen
          loading="lazy"
          title={title || 'YouTube video'}
        />
      </div>
      <div className="vl-youtube-info">
        {title && <p className="vl-youtube-title">{title}</p>}
        {description && <p className="vl-youtube-desc">{description}</p>}
        <a
          href={`https://www.youtube.com/watch?v=${videoId}`}
          target="_blank"
          rel="noopener noreferrer"
          className="vl-open-external"
        >
          Open in YouTube <ExternalLinkIcon size={12} />
        </a>
      </div>
    </div>
  );
}

/* ── LinkCard ───────────────────────────────────── */

function LinkCard({ link }: { link: ResourceLinkItem }) {
  const displayUrl = link.url.length > 60 ? link.url.slice(0, 57) + '...' : link.url;
  return (
    <a
      href={link.url}
      target="_blank"
      rel="noopener noreferrer"
      className="vl-link-card"
    >
      <div className="vl-link-card-body">
        <span className="vl-link-icon">
          <ExternalLinkIcon size={16} />
        </span>
        <div className="vl-link-info">
          <span className="vl-link-title">{link.title || 'Untitled link'}</span>
          <span className="vl-link-url">{displayUrl}</span>
        </div>
      </div>
    </a>
  );
}

/* ── TopicGroup ─────────────────────────────────── */

function TopicGroup({
  heading,
  links,
  onDelete,
}: {
  heading: string;
  links: ResourceLinkItem[];
  onDelete: (id: number) => void;
}) {
  const [open, setOpen] = useState(true);
  const youtubeLinks = links.filter(l => l.resource_type === 'youtube' && l.youtube_video_id);
  const otherLinks = links.filter(l => l.resource_type !== 'youtube' || !l.youtube_video_id);

  return (
    <div className="vl-topic-group">
      <button className="vl-topic-heading" onClick={() => setOpen(v => !v)}>
        <ChevronIcon open={open} />
        <span>{heading}</span>
        <span className="vl-topic-count">{links.length}</span>
      </button>
      {open && (
        <div className="vl-topic-body">
          {youtubeLinks.length > 0 && (
            <div className="vl-youtube-grid">
              {youtubeLinks.map(link => (
                <div key={link.id} className="vl-youtube-item">
                  <YouTubeEmbed
                    videoId={link.youtube_video_id!}
                    title={link.title}
                    description={link.description}
                  />
                  <button
                    className="vl-delete-btn"
                    title="Remove link"
                    onClick={() => onDelete(link.id)}
                  >
                    <DeleteIcon />
                  </button>
                </div>
              ))}
            </div>
          )}
          {otherLinks.length > 0 && (
            <div className="vl-links-list">
              {otherLinks.map(link => (
                <div key={link.id} className="vl-link-row">
                  <LinkCard link={link} />
                  <button
                    className="vl-delete-btn"
                    title="Remove link"
                    onClick={() => onDelete(link.id)}
                  >
                    <DeleteIcon />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ── AddLinkForm ────────────────────────────────── */

function AddLinkForm({
  courseContentId,
  onAdded,
  onCancel,
}: {
  courseContentId: number;
  onAdded: () => void;
  onCancel: () => void;
}) {
  const [url, setUrl] = useState('');
  const [title, setTitle] = useState('');
  const [topic, setTopic] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await resourceLinksApi.add(courseContentId, {
        url: url.trim(),
        title: title.trim() || undefined,
        topic_heading: topic.trim() || undefined,
      });
      onAdded();
    } catch {
      setError('Failed to add link');
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className="vl-add-form" onSubmit={handleSubmit}>
      <div className="vl-add-form-row">
        <input
          type="url"
          placeholder="https://..."
          value={url}
          onChange={e => setUrl(e.target.value)}
          required
          className="vl-add-input"
          autoFocus
        />
      </div>
      <div className="vl-add-form-row vl-add-form-row--split">
        <input
          type="text"
          placeholder="Title (optional)"
          value={title}
          onChange={e => setTitle(e.target.value)}
          className="vl-add-input"
        />
        <input
          type="text"
          placeholder="Topic heading (optional)"
          value={topic}
          onChange={e => setTopic(e.target.value)}
          className="vl-add-input"
        />
      </div>
      {error && <p className="vl-add-error">{error}</p>}
      <div className="vl-add-form-actions">
        <button type="button" className="cm-action-btn" onClick={onCancel} disabled={saving}>
          Cancel
        </button>
        <button type="submit" className="cm-action-btn primary" disabled={saving || !url.trim()}>
          {saving ? 'Adding...' : 'Add Link'}
        </button>
      </div>
    </form>
  );
}

/* ── Main Tab ───────────────────────────────────── */

export function VideosLinksTab({ courseContentId }: VideosLinksTabProps) {
  const queryClient = useQueryClient();
  const [showAddForm, setShowAddForm] = useState(false);

  const { data: groups = [], isLoading } = useQuery<ResourceLinkGroup[]>({
    queryKey: ['resource-links', courseContentId],
    queryFn: () => resourceLinksApi.list(courseContentId),
  });

  const totalCount = groups.reduce((sum, g) => sum + g.links.length, 0);

  const handleDelete = async (linkId: number) => {
    try {
      await resourceLinksApi.delete(linkId);
      queryClient.invalidateQueries({ queryKey: ['resource-links', courseContentId] });
    } catch {
      // silently fail; user can retry
    }
  };

  const handleAdded = () => {
    setShowAddForm(false);
    queryClient.invalidateQueries({ queryKey: ['resource-links', courseContentId] });
  };

  if (isLoading) {
    return (
      <div className="cm-tab-card">
        <div className="cm-tab-skeleton">
          <div className="skeleton" />
          <div className="skeleton" />
          <div className="skeleton" />
        </div>
      </div>
    );
  }

  if (totalCount === 0 && !showAddForm) {
    return (
      <div className="cm-empty-tab">
        <div className="cm-empty-tab-icon"><VideoIcon /></div>
        <h3>No videos or links found</h3>
        <p>No videos or links were found in this material. You can add links manually.</p>
        <button className="cm-empty-generate-btn" onClick={() => setShowAddForm(true)}>
          <PlusIcon /> Add Link
        </button>
        {showAddForm && (
          <AddLinkForm
            courseContentId={courseContentId}
            onAdded={handleAdded}
            onCancel={() => setShowAddForm(false)}
          />
        )}
      </div>
    );
  }

  return (
    <div className="vl-tab">
      <div className="vl-toolbar">
        <span className="vl-count">{totalCount} {totalCount === 1 ? 'link' : 'links'}</span>
        <button
          className="cm-action-btn"
          onClick={() => setShowAddForm(v => !v)}
        >
          <PlusIcon /> Add Link
        </button>
      </div>

      {showAddForm && (
        <AddLinkForm
          courseContentId={courseContentId}
          onAdded={handleAdded}
          onCancel={() => setShowAddForm(false)}
        />
      )}

      {groups.map(group => (
        <TopicGroup
          key={group.topic_heading || '__other'}
          heading={group.topic_heading || 'Other Resources'}
          links={group.links}
          onDelete={handleDelete}
        />
      ))}
    </div>
  );
}
