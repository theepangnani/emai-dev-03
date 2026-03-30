import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { resourceLinksApi, type ResourceLinkGroup, type ResourceLinkItem, type SearchResourceResult } from '../../api/resourceLinks';
import './VideosLinksTab.css';

interface VideosLinksTabProps {
  courseContentId: number;
  topicName?: string;
  gradLevel?: string;
  courseName?: string;
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

function SearchIcon({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <circle cx="7" cy="7" r="4.5" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M10.5 10.5L14 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  );
}

function PinIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M9.5 2L14 6.5 8.5 12 4 7.5 9.5 2z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/>
      <path d="M2 14l3.5-3.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
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

/* ── AI-Suggested Icons ─────────────────────────── */

function SparkleIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M8 1v3M8 12v3M1 8h3M12 8h3M3.5 3.5l2 2M10.5 10.5l2 2M12.5 3.5l-2 2M5.5 10.5l-2 2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
    </svg>
  );
}

/* ── AI-Suggested Link Card ────────────────────── */

function AISuggestedLinkCard({
  link,
  onPin,
  onDismiss,
}: {
  link: ResourceLinkItem;
  onPin: (id: number) => void;
  onDismiss: (id: number) => void;
}) {
  const displayUrl = link.url.length > 60 ? link.url.slice(0, 57) + '...' : link.url;
  return (
    <div className="vl-ai-link-row">
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
            <span className="vl-link-title">
              {link.title || 'Untitled link'}
              <span className="vl-ai-badge">AI-suggested</span>
            </span>
            <span className="vl-link-url">{displayUrl}</span>
          </div>
        </div>
      </a>
      <button
        className="vl-pin-btn"
        title="Pin as permanent resource"
        onClick={() => onPin(link.id)}
      >
        <PinIcon />
      </button>
      <button
        className="vl-delete-btn"
        title="Dismiss suggestion"
        onClick={() => onDismiss(link.id)}
      >
        <DeleteIcon />
      </button>
    </div>
  );
}

/* ── AI-Suggested YouTube Card ─────────────────── */

function AISuggestedYouTubeCard({
  link,
  onPin,
  onDismiss,
}: {
  link: ResourceLinkItem;
  onPin: (id: number) => void;
  onDismiss: (id: number) => void;
}) {
  return (
    <div className="vl-youtube-item">
      <YouTubeEmbed
        videoId={link.youtube_video_id!}
        title={link.title}
        description={link.description}
      />
      <span className="vl-ai-badge vl-ai-badge--floating">AI-suggested</span>
      <div className="vl-ai-youtube-actions">
        <button
          className="vl-pin-btn"
          title="Pin as permanent resource"
          onClick={() => onPin(link.id)}
        >
          <PinIcon />
        </button>
        <button
          className="vl-delete-btn"
          title="Dismiss suggestion"
          onClick={() => onDismiss(link.id)}
        >
          <DeleteIcon />
        </button>
      </div>
    </div>
  );
}

/* ── AI-Suggested Section ──────────────────────── */

function AISuggestedSection({
  links,
  onPin,
  onDismiss,
}: {
  links: ResourceLinkItem[];
  onPin: (id: number) => void;
  onDismiss: (id: number) => void;
}) {
  const [open, setOpen] = useState(true);
  const youtubeLinks = links.filter(l => l.resource_type === 'youtube' && l.youtube_video_id);
  const otherLinks = links.filter(l => l.resource_type !== 'youtube' || !l.youtube_video_id);

  if (links.length === 0) return null;

  return (
    <div className="vl-topic-group vl-ai-section">
      <button className="vl-topic-heading vl-ai-heading" onClick={() => setOpen(v => !v)}>
        <ChevronIcon open={open} />
        <SparkleIcon />
        <span>AI-Suggested Resources</span>
        <span className="vl-topic-count">{links.length}</span>
      </button>
      {open && (
        <div className="vl-topic-body">
          {youtubeLinks.length > 0 && (
            <div className="vl-youtube-grid">
              {youtubeLinks.map(link => (
                <AISuggestedYouTubeCard
                  key={link.id}
                  link={link}
                  onPin={onPin}
                  onDismiss={onDismiss}
                />
              ))}
            </div>
          )}
          {otherLinks.length > 0 && (
            <div className="vl-links-list">
              {otherLinks.map(link => (
                <AISuggestedLinkCard
                  key={link.id}
                  link={link}
                  onPin={onPin}
                  onDismiss={onDismiss}
                />
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

/* ── SearchResultCard ──────────────────────────── */

function SearchResultCard({
  result,
  onPin,
  onDismiss,
  pinning,
}: {
  result: SearchResourceResult;
  onPin: (id: number) => void;
  onDismiss: (id: number) => void;
  pinning: boolean;
}) {
  return (
    <div className="vl-search-result">
      {result.youtube_video_id ? (
        <div className="vl-youtube-card">
          <div className="vl-youtube-wrapper">
            <iframe
              src={`https://www.youtube.com/embed/${result.youtube_video_id}`}
              style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%' }}
              frameBorder="0"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
              loading="lazy"
              title={result.title || 'YouTube video'}
            />
          </div>
          <div className="vl-youtube-info">
            {result.title && <p className="vl-youtube-title">{result.title}</p>}
            {result.channel_name && <p className="vl-search-channel">{result.channel_name}</p>}
            {result.description && <p className="vl-youtube-desc">{result.description}</p>}
          </div>
        </div>
      ) : (
        <div className="vl-link-card" style={{ cursor: 'default' }}>
          <div className="vl-link-card-body">
            <span className="vl-link-icon"><ExternalLinkIcon size={16} /></span>
            <div className="vl-link-info">
              <span className="vl-link-title">{result.title || 'Untitled'}</span>
              {result.channel_name && <span className="vl-search-channel">{result.channel_name}</span>}
              {result.description && <span className="vl-link-url">{result.description}</span>}
            </div>
          </div>
        </div>
      )}
      <div className="vl-search-actions">
        <button
          className="cm-action-btn vl-pin-btn"
          onClick={() => onPin(result.id)}
          disabled={pinning}
          title="Pin to saved resources"
        >
          <PinIcon /> Pin
        </button>
        <button
          className="vl-delete-btn"
          onClick={() => onDismiss(result.id)}
          title="Dismiss"
        >
          <DeleteIcon />
        </button>
      </div>
    </div>
  );
}

/* ── LiveSearchSection ─────────────────────────── */

function LiveSearchSection({
  courseContentId,
  initialTopic,
  gradeLevel,
  courseName,
  onResultPinned,
}: {
  courseContentId: number;
  initialTopic: string;
  gradeLevel?: string;
  courseName?: string;
  onResultPinned: () => void;
}) {
  const [query, setQuery] = useState(initialTopic);
  const [results, setResults] = useState<SearchResourceResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(true);
  const [pinningIds, setPinningIds] = useState<Set<number>>(new Set());
  const [dismissedIds, setDismissedIds] = useState<Set<number>>(new Set());

  const handleSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);
    setError(null);
    setSearched(true);
    try {
      const data = await resourceLinksApi.searchResources(courseContentId, {
        topic: query.trim(),
        grade_level: gradeLevel,
        course_name: courseName,
      });
      setResults(data);
      setDismissedIds(new Set());
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 429) {
        setError('YouTube search quota exhausted. Please try again later.');
      } else {
        setError('Search failed. Please check your connection and try again.');
      }
      setResults([]);
    } finally {
      setSearching(false);
    }
  };

  const handlePin = async (linkId: number) => {
    setPinningIds(prev => new Set(prev).add(linkId));
    try {
      await resourceLinksApi.pinResource(linkId);
      setResults(prev => prev.filter(r => r.id !== linkId));
      onResultPinned();
    } catch {
      // silently fail; user can retry
    } finally {
      setPinningIds(prev => {
        const next = new Set(prev);
        next.delete(linkId);
        return next;
      });
    }
  };

  const handleDismiss = async (linkId: number) => {
    try {
      await resourceLinksApi.dismissResource(linkId);
      setDismissedIds(prev => new Set(prev).add(linkId));
    } catch {
      // silently fail
    }
  };

  const visibleResults = results.filter(r => !dismissedIds.has(r.id));

  return (
    <div className="vl-topic-group vl-search-section">
      <button className="vl-topic-heading" onClick={() => setOpen(v => !v)}>
        <ChevronIcon open={open} />
        <span>Live Search Results</span>
        <span className="vl-badge vl-badge--live"><SearchIcon size={11} /> Live search</span>
      </button>
      {open && (
        <div className="vl-topic-body">
          <div className="vl-search-bar">
            <input
              type="text"
              className="vl-add-input vl-search-input"
              placeholder="Search topic..."
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') handleSearch(); }}
            />
            <button
              className="cm-action-btn primary"
              onClick={handleSearch}
              disabled={searching || !query.trim()}
            >
              {searching ? 'Searching...' : 'Search again'}
            </button>
          </div>

          {searching && (
            <div className="vl-search-loading">
              <div className="vl-spinner" />
              <span>Searching YouTube...</span>
            </div>
          )}

          {error && <p className="vl-add-error">{error}</p>}

          {!searching && searched && visibleResults.length === 0 && !error && (
            <p className="vl-search-empty">No results found. Try a different search term.</p>
          )}

          {visibleResults.length > 0 && (
            <div className="vl-youtube-grid">
              {visibleResults.map(result => (
                <SearchResultCard
                  key={result.id}
                  result={result}
                  onPin={handlePin}
                  onDismiss={handleDismiss}
                  pinning={pinningIds.has(result.id)}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ── Main Tab ───────────────────────────────────── */

export function VideosLinksTab({ courseContentId, topicName, gradLevel, courseName }: VideosLinksTabProps) {
  const queryClient = useQueryClient();
  const [showAddForm, setShowAddForm] = useState(false);
  const [showSearch, setShowSearch] = useState(false);

  const { data: groups = [], isLoading } = useQuery<ResourceLinkGroup[]>({
    queryKey: ['resource-links', courseContentId],
    queryFn: () => resourceLinksApi.list(courseContentId),
  });

  const { data: youtubeAvailable } = useQuery({
    queryKey: ['youtube-search-available'],
    queryFn: () => resourceLinksApi.checkYoutubeSearchAvailable(),
    staleTime: 5 * 60 * 1000,
  });

  // Separate teacher links from AI-suggested links
  const teacherGroups = groups.map(g => ({
    ...g,
    links: g.links.filter(l => l.source !== 'ai_suggested'),
  })).filter(g => g.links.length > 0);

  const aiSuggestedLinks = groups.flatMap(g =>
    g.links.filter(l => l.source === 'ai_suggested')
  );

  const totalCount = groups.reduce((sum, g) => sum + g.links.length, 0);

  const handleDelete = async (linkId: number) => {
    try {
      await resourceLinksApi.delete(linkId);
      queryClient.invalidateQueries({ queryKey: ['resource-links', courseContentId] });
    } catch {
      // silently fail; user can retry
    }
  };

  const handlePin = async (linkId: number) => {
    try {
      await resourceLinksApi.pin(linkId);
      queryClient.invalidateQueries({ queryKey: ['resource-links', courseContentId] });
    } catch {
      // silently fail; user can retry
    }
  };

  const handleDismiss = async (linkId: number) => {
    try {
      await resourceLinksApi.dismiss(linkId);
      queryClient.invalidateQueries({ queryKey: ['resource-links', courseContentId] });
    } catch {
      // silently fail; user can retry
    }
  };

  const handleAdded = () => {
    setShowAddForm(false);
    queryClient.invalidateQueries({ queryKey: ['resource-links', courseContentId] });
  };

  const handleResultPinned = () => {
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

  if (totalCount === 0 && !showAddForm && !showSearch) {
    return (
      <div className="cm-empty-tab">
        <div className="cm-empty-tab-icon"><VideoIcon /></div>
        <h3>No videos or links found</h3>
        <p>No videos or links were found in this material. You can add links manually.</p>
        <div className="vl-empty-actions">
          <button className="cm-empty-generate-btn" onClick={() => setShowAddForm(true)}>
            <PlusIcon /> Add Link
          </button>
          {youtubeAvailable?.available && (
            <button className="cm-empty-generate-btn vl-find-more-btn" onClick={() => setShowSearch(true)}>
              <SearchIcon /> Find More Resources
            </button>
          )}
        </div>
        {showAddForm && (
          <AddLinkForm
            courseContentId={courseContentId}
            onAdded={handleAdded}
            onCancel={() => setShowAddForm(false)}
          />
        )}
        {showSearch && (
          <LiveSearchSection
            courseContentId={courseContentId}
            initialTopic={topicName || ''}
            gradeLevel={gradLevel}
            courseName={courseName}
            onResultPinned={handleResultPinned}
          />
        )}
      </div>
    );
  }

  return (
    <div className="vl-tab">
      <div className="vl-toolbar">
        <span className="vl-count">{totalCount} {totalCount === 1 ? 'link' : 'links'}</span>
        <div className="vl-toolbar-actions">
          {youtubeAvailable?.available && (
            <button
              className="cm-action-btn vl-find-more-btn"
              onClick={() => setShowSearch(v => !v)}
            >
              <SearchIcon /> Find More Resources
            </button>
          )}
          <button
            className="cm-action-btn"
            onClick={() => setShowAddForm(v => !v)}
          >
            <PlusIcon /> Add Link
          </button>
        </div>
      </div>

      {showAddForm && (
        <AddLinkForm
          courseContentId={courseContentId}
          onAdded={handleAdded}
          onCancel={() => setShowAddForm(false)}
        />
      )}

      {teacherGroups.map(group => (
        <TopicGroup
          key={group.topic_heading || '__other'}
          heading={group.topic_heading || 'Other Resources'}
          links={group.links}
          onDelete={handleDelete}
        />
      ))}

      <AISuggestedSection
        links={aiSuggestedLinks}
        onPin={handlePin}
        onDismiss={handleDismiss}
      />

      {showSearch && (
        <LiveSearchSection
          courseContentId={courseContentId}
          initialTopic={topicName || ''}
          gradeLevel={gradLevel}
          courseName={courseName}
          onResultPinned={handleResultPinned}
        />
      )}
    </div>
  );
}
