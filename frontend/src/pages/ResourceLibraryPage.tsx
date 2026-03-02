import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { DashboardLayout } from '../components/DashboardLayout';
import { resourceLibraryApi } from '../api/resourceLibrary';
import type {
  TeacherResource,
  ResourceCollection,
  ResourceType,
  SearchParams,
  PaginatedResourceResponse,
} from '../api/resourceLibrary';
import './ResourceLibraryPage.css';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const RESOURCE_TYPE_LABELS: Record<ResourceType, string> = {
  lesson_plan: 'Lesson Plan',
  worksheet: 'Worksheet',
  presentation: 'Presentation',
  assessment: 'Assessment',
  video_link: 'Video Link',
  activity: 'Activity',
  rubric: 'Rubric',
  other: 'Other',
};

const GRADE_LEVELS = [
  'Grade 1', 'Grade 2', 'Grade 3', 'Grade 4', 'Grade 5', 'Grade 6',
  'Grade 7', 'Grade 8', 'Grade 9', 'Grade 10', 'Grade 11', 'Grade 12',
];

const RESOURCE_TYPES: ResourceType[] = [
  'lesson_plan', 'worksheet', 'presentation', 'assessment',
  'video_link', 'activity', 'rubric', 'other',
];

// ---------------------------------------------------------------------------
// Star rating display component
// ---------------------------------------------------------------------------

function StarRating({ rating, count, onRate }: { rating: number; count: number; onRate?: (r: number) => void }) {
  const [hovered, setHovered] = useState(0);
  return (
    <div className="rl-stars" title={`${rating.toFixed(1)} / 5 (${count} rating${count !== 1 ? 's' : ''})`}>
      {[1, 2, 3, 4, 5].map((star) => (
        <span
          key={star}
          className={`rl-star${star <= (hovered || Math.round(rating)) ? ' filled' : ''}`}
          onMouseEnter={() => onRate && setHovered(star)}
          onMouseLeave={() => onRate && setHovered(0)}
          onClick={() => onRate && onRate(star)}
          role={onRate ? 'button' : undefined}
          aria-label={onRate ? `Rate ${star} star${star !== 1 ? 's' : ''}` : undefined}
        >
          &#9733;
        </span>
      ))}
      {count > 0 && <span className="rl-rating-count">({count})</span>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Resource card
// ---------------------------------------------------------------------------

function ResourceCard({ resource, onOpen }: { resource: TeacherResource; onOpen: (r: TeacherResource) => void }) {
  return (
    <div className="rl-card" onClick={() => onOpen(resource)} role="button" tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onOpen(resource)}>
      <div className="rl-card-header">
        <span className={`rl-type-badge rl-type-${resource.resource_type}`}>
          {RESOURCE_TYPE_LABELS[resource.resource_type]}
        </span>
        {!resource.is_public && <span className="rl-private-badge">Private</span>}
      </div>
      <h3 className="rl-card-title">{resource.title}</h3>
      {resource.description && (
        <p className="rl-card-desc">{resource.description.slice(0, 120)}{resource.description.length > 120 ? '...' : ''}</p>
      )}
      <div className="rl-card-meta">
        {resource.subject && <span className="rl-tag">{resource.subject}</span>}
        {resource.grade_level && <span className="rl-tag">{resource.grade_level}</span>}
        {(resource.tags || []).slice(0, 3).map((t) => (
          <span key={t} className="rl-tag rl-tag-secondary">{t}</span>
        ))}
      </div>
      <div className="rl-card-footer">
        <StarRating rating={resource.avg_rating} count={resource.rating_count} />
        <span className="rl-downloads">{resource.download_count} views</span>
        {resource.teacher_name && (
          <span className="rl-teacher">by {resource.teacher_name}</span>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Resource Detail Modal
// ---------------------------------------------------------------------------

function ResourceDetailModal({
  resource,
  onClose,
  onRate,
  onRemix,
  isOwner,
}: {
  resource: TeacherResource;
  onClose: () => void;
  onRate: (rating: number, comment: string) => Promise<void>;
  onRemix: () => Promise<void>;
  isOwner: boolean;
}) {
  const [ratingValue, setRatingValue] = useState(0);
  const [ratingComment, setRatingComment] = useState('');
  const [ratingSubmitting, setRatingSubmitting] = useState(false);
  const [ratingSuccess, setRatingSuccess] = useState(false);
  const [remixing, setRemixing] = useState(false);
  const [remixMsg, setRemixMsg] = useState('');

  const handleRate = async () => {
    if (ratingValue < 1) return;
    setRatingSubmitting(true);
    try {
      await onRate(ratingValue, ratingComment);
      setRatingSuccess(true);
    } finally {
      setRatingSubmitting(false);
    }
  };

  const handleRemix = async () => {
    setRemixing(true);
    try {
      await onRemix();
      setRemixMsg('Lesson plan created! Go to Lesson Planner to edit it.');
    } catch {
      setRemixMsg('Failed to remix. Please try again.');
    } finally {
      setRemixing(false);
    }
  };

  const resourceUrl = resource.file_key
    ? `/api/storage/${resource.file_key}`
    : resource.external_url || null;

  return (
    <div className="rl-modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div className="rl-modal" onClick={(e) => e.stopPropagation()}>
        <button className="rl-modal-close" onClick={onClose} aria-label="Close">&#x2715;</button>

        <div className="rl-modal-header">
          <span className={`rl-type-badge rl-type-${resource.resource_type}`}>
            {RESOURCE_TYPE_LABELS[resource.resource_type]}
          </span>
          <h2 className="rl-modal-title">{resource.title}</h2>
          {resource.teacher_name && (
            <p className="rl-modal-teacher">Published by {resource.teacher_name}</p>
          )}
        </div>

        {resource.description && (
          <p className="rl-modal-desc">{resource.description}</p>
        )}

        <div className="rl-modal-meta">
          {resource.subject && <div><strong>Subject:</strong> {resource.subject}</div>}
          {resource.grade_level && <div><strong>Grade:</strong> {resource.grade_level}</div>}
          {resource.curriculum_expectation && (
            <div><strong>Curriculum:</strong> {resource.curriculum_expectation}</div>
          )}
          {(resource.tags || []).length > 0 && (
            <div className="rl-modal-tags">
              <strong>Tags:</strong>
              {resource.tags.map((t) => <span key={t} className="rl-tag">{t}</span>)}
            </div>
          )}
        </div>

        <div className="rl-modal-stats">
          <StarRating rating={resource.avg_rating} count={resource.rating_count} />
          <span className="rl-downloads">{resource.download_count} views</span>
        </div>

        <div className="rl-modal-actions">
          {resourceUrl && (
            <a href={resourceUrl} target="_blank" rel="noopener noreferrer" className="rl-btn rl-btn-primary">
              {resource.file_key ? 'Download' : 'Visit Link'}
            </a>
          )}
          {!isOwner && (
            <button className="rl-btn rl-btn-secondary" onClick={handleRemix} disabled={remixing}>
              {remixing ? 'Remixing...' : 'Remix into Lesson Plan'}
            </button>
          )}
        </div>
        {remixMsg && <p className="rl-info-msg">{remixMsg}</p>}

        {!isOwner && !ratingSuccess && (
          <div className="rl-rating-section">
            <h3>Rate this resource</h3>
            <StarRating rating={ratingValue} count={0} onRate={setRatingValue} />
            <textarea
              className="rl-comment-input"
              placeholder="Leave a comment (optional)"
              value={ratingComment}
              onChange={(e) => setRatingComment(e.target.value)}
              rows={3}
            />
            <button
              className="rl-btn rl-btn-primary"
              onClick={handleRate}
              disabled={ratingSubmitting || ratingValue < 1}
            >
              {ratingSubmitting ? 'Submitting...' : 'Submit Rating'}
            </button>
          </div>
        )}
        {ratingSuccess && <p className="rl-success-msg">Rating submitted. Thank you!</p>}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Upload Resource Form Modal
// ---------------------------------------------------------------------------

function UploadResourceModal({
  onClose,
  onSave,
}: {
  onClose: () => void;
  onSave: (resource: TeacherResource) => void;
}) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [resourceType, setResourceType] = useState<ResourceType>('other');
  const [subject, setSubject] = useState('');
  const [gradeLevel, setGradeLevel] = useState('');
  const [tagsInput, setTagsInput] = useState('');
  const [isPublic, setIsPublic] = useState(false);
  const [externalUrl, setExternalUrl] = useState('');
  const [curriculumExpectation, setCurriculumExpectation] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) { setError('Title is required'); return; }
    setSubmitting(true);
    setError('');
    try {
      const tags = tagsInput
        ? tagsInput.split(',').map((t) => t.trim()).filter(Boolean)
        : undefined;
      const created = await resourceLibraryApi.createResource({
        title: title.trim(),
        description: description.trim() || undefined,
        resource_type: resourceType,
        subject: subject.trim() || undefined,
        grade_level: gradeLevel || undefined,
        tags,
        is_public: isPublic,
        external_url: externalUrl.trim() || undefined,
        curriculum_expectation: curriculumExpectation.trim() || undefined,
      });
      // Upload file if selected
      let finalResource = created;
      if (file) {
        finalResource = await resourceLibraryApi.uploadFile(created.id, file);
      }
      onSave(finalResource);
      onClose();
    } catch {
      setError('Failed to create resource. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="rl-modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div className="rl-modal rl-modal-form" onClick={(e) => e.stopPropagation()}>
        <button className="rl-modal-close" onClick={onClose} aria-label="Close">&#x2715;</button>
        <h2>Upload Resource</h2>
        <form onSubmit={handleSubmit} className="rl-form">
          <label className="rl-form-label">
            Title <span className="rl-required">*</span>
            <input className="rl-input" value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={500} />
          </label>

          <label className="rl-form-label">
            Description
            <textarea className="rl-input" value={description} onChange={(e) => setDescription(e.target.value)} rows={3} />
          </label>

          <div className="rl-form-row">
            <label className="rl-form-label">
              Type <span className="rl-required">*</span>
              <select className="rl-input" value={resourceType} onChange={(e) => setResourceType(e.target.value as ResourceType)}>
                {RESOURCE_TYPES.map((t) => (
                  <option key={t} value={t}>{RESOURCE_TYPE_LABELS[t]}</option>
                ))}
              </select>
            </label>

            <label className="rl-form-label">
              Grade Level
              <select className="rl-input" value={gradeLevel} onChange={(e) => setGradeLevel(e.target.value)}>
                <option value="">Any</option>
                {GRADE_LEVELS.map((g) => <option key={g} value={g}>{g}</option>)}
              </select>
            </label>
          </div>

          <label className="rl-form-label">
            Subject
            <input className="rl-input" value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="e.g. Mathematics, English" maxLength={255} />
          </label>

          <label className="rl-form-label">
            Tags (comma-separated)
            <input className="rl-input" value={tagsInput} onChange={(e) => setTagsInput(e.target.value)} placeholder="e.g. fractions, problem-solving" />
          </label>

          <label className="rl-form-label">
            Curriculum Expectation
            <input className="rl-input" value={curriculumExpectation} onChange={(e) => setCurriculumExpectation(e.target.value)} placeholder="e.g. B1.2 — Reading Strategies" maxLength={500} />
          </label>

          <label className="rl-form-label">
            External URL (YouTube, Google Drive, etc.)
            <input className="rl-input" type="url" value={externalUrl} onChange={(e) => setExternalUrl(e.target.value)} placeholder="https://" />
          </label>

          <label className="rl-form-label">
            Upload File
            <input className="rl-input" type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} />
          </label>

          <label className="rl-form-label rl-checkbox-label">
            <input type="checkbox" checked={isPublic} onChange={(e) => setIsPublic(e.target.checked)} />
            Make this resource public (visible to all teachers)
          </label>

          {error && <p className="rl-error-msg">{error}</p>}

          <div className="rl-form-actions">
            <button type="button" className="rl-btn rl-btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="rl-btn rl-btn-primary" disabled={submitting}>
              {submitting ? 'Saving...' : 'Save Resource'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Edit Resource Modal
// ---------------------------------------------------------------------------

function EditResourceModal({
  resource,
  onClose,
  onSave,
}: {
  resource: TeacherResource;
  onClose: () => void;
  onSave: (updated: TeacherResource) => void;
}) {
  const [title, setTitle] = useState(resource.title);
  const [description, setDescription] = useState(resource.description || '');
  const [resourceType, setResourceType] = useState<ResourceType>(resource.resource_type);
  const [subject, setSubject] = useState(resource.subject || '');
  const [gradeLevel, setGradeLevel] = useState(resource.grade_level || '');
  const [tagsInput, setTagsInput] = useState((resource.tags || []).join(', '));
  const [isPublic, setIsPublic] = useState(resource.is_public);
  const [externalUrl, setExternalUrl] = useState(resource.external_url || '');
  const [curriculumExpectation, setCurriculumExpectation] = useState(resource.curriculum_expectation || '');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) { setError('Title is required'); return; }
    setSubmitting(true);
    setError('');
    try {
      const tags = tagsInput
        ? tagsInput.split(',').map((t) => t.trim()).filter(Boolean)
        : [];
      const updated = await resourceLibraryApi.updateResource(resource.id, {
        title: title.trim(),
        description: description.trim() || undefined,
        resource_type: resourceType,
        subject: subject.trim() || undefined,
        grade_level: gradeLevel || undefined,
        tags,
        is_public: isPublic,
        external_url: externalUrl.trim() || undefined,
        curriculum_expectation: curriculumExpectation.trim() || undefined,
      });
      onSave(updated);
      onClose();
    } catch {
      setError('Failed to update resource. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="rl-modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div className="rl-modal rl-modal-form" onClick={(e) => e.stopPropagation()}>
        <button className="rl-modal-close" onClick={onClose} aria-label="Close">&#x2715;</button>
        <h2>Edit Resource</h2>
        <form onSubmit={handleSubmit} className="rl-form">
          <label className="rl-form-label">
            Title <span className="rl-required">*</span>
            <input className="rl-input" value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={500} />
          </label>
          <label className="rl-form-label">
            Description
            <textarea className="rl-input" value={description} onChange={(e) => setDescription(e.target.value)} rows={3} />
          </label>
          <div className="rl-form-row">
            <label className="rl-form-label">
              Type
              <select className="rl-input" value={resourceType} onChange={(e) => setResourceType(e.target.value as ResourceType)}>
                {RESOURCE_TYPES.map((t) => (
                  <option key={t} value={t}>{RESOURCE_TYPE_LABELS[t]}</option>
                ))}
              </select>
            </label>
            <label className="rl-form-label">
              Grade Level
              <select className="rl-input" value={gradeLevel} onChange={(e) => setGradeLevel(e.target.value)}>
                <option value="">Any</option>
                {GRADE_LEVELS.map((g) => <option key={g} value={g}>{g}</option>)}
              </select>
            </label>
          </div>
          <label className="rl-form-label">
            Subject
            <input className="rl-input" value={subject} onChange={(e) => setSubject(e.target.value)} maxLength={255} />
          </label>
          <label className="rl-form-label">
            Tags (comma-separated)
            <input className="rl-input" value={tagsInput} onChange={(e) => setTagsInput(e.target.value)} />
          </label>
          <label className="rl-form-label">
            Curriculum Expectation
            <input className="rl-input" value={curriculumExpectation} onChange={(e) => setCurriculumExpectation(e.target.value)} maxLength={500} />
          </label>
          <label className="rl-form-label">
            External URL
            <input className="rl-input" type="url" value={externalUrl} onChange={(e) => setExternalUrl(e.target.value)} />
          </label>
          <label className="rl-form-label rl-checkbox-label">
            <input type="checkbox" checked={isPublic} onChange={(e) => setIsPublic(e.target.checked)} />
            Make public
          </label>
          {error && <p className="rl-error-msg">{error}</p>}
          <div className="rl-form-actions">
            <button type="button" className="rl-btn rl-btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="rl-btn rl-btn-primary" disabled={submitting}>
              {submitting ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Collections Sidebar
// ---------------------------------------------------------------------------

function CollectionsSidebar({
  collections,
  onCreateCollection,
  onAddToCollection,
  selectedResourceId,
}: {
  collections: ResourceCollection[];
  onCreateCollection: (name: string) => Promise<void>;
  onAddToCollection: (collectionId: number, resourceId: number) => Promise<void>;
  selectedResourceId: number | null;
}) {
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [addingToId, setAddingToId] = useState<number | null>(null);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    await onCreateCollection(newName.trim());
    setNewName('');
    setCreating(false);
  };

  const handleAdd = async (collectionId: number) => {
    if (!selectedResourceId) return;
    setAddingToId(collectionId);
    try {
      await onAddToCollection(collectionId, selectedResourceId);
    } finally {
      setAddingToId(null);
    }
  };

  return (
    <aside className="rl-collections-sidebar">
      <div className="rl-collections-header">
        <h3>My Collections</h3>
        <button className="rl-btn-icon" onClick={() => setCreating(!creating)} title="Create collection">+</button>
      </div>
      {creating && (
        <div className="rl-collection-create">
          <input
            className="rl-input"
            placeholder="Collection name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
          />
          <button className="rl-btn rl-btn-primary rl-btn-sm" onClick={handleCreate}>Create</button>
        </div>
      )}
      {collections.length === 0 && !creating && (
        <p className="rl-empty-msg">No collections yet. Create one to organise resources.</p>
      )}
      <ul className="rl-collection-list">
        {collections.map((c) => (
          <li key={c.id} className="rl-collection-item">
            <span className="rl-collection-name">{c.name}</span>
            <span className="rl-collection-count">{c.resource_ids.length}</span>
            {selectedResourceId && (
              <button
                className="rl-btn-icon rl-btn-add"
                onClick={() => handleAdd(c.id)}
                disabled={addingToId === c.id}
                title={`Add selected resource to "${c.name}"`}
              >
                {addingToId === c.id ? '...' : '+'}
              </button>
            )}
          </li>
        ))}
      </ul>
      {selectedResourceId && (
        <p className="rl-collections-hint">Click + next to a collection to add the selected resource.</p>
      )}
    </aside>
  );
}

// ---------------------------------------------------------------------------
// Main page component
// ---------------------------------------------------------------------------

export function ResourceLibraryPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<'discover' | 'mine'>('discover');

  // --- Discover tab state ---
  const [searchQ, setSearchQ] = useState('');
  const [filterSubject, setFilterSubject] = useState('');
  const [filterGrade, setFilterGrade] = useState('');
  const [filterType, setFilterType] = useState('');
  const [subjects, setSubjects] = useState<string[]>([]);
  const [page, setPage] = useState(1);
  const [discoverResults, setDiscoverResults] = useState<PaginatedResourceResponse | null>(null);
  const [discoverLoading, setDiscoverLoading] = useState(false);

  // --- My Resources tab state ---
  const [myResources, setMyResources] = useState<TeacherResource[]>([]);
  const [myLoading, setMyLoading] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [editingResource, setEditingResource] = useState<TeacherResource | null>(null);

  // --- Detail modal ---
  const [detailResource, setDetailResource] = useState<TeacherResource | null>(null);
  const [currentUserId, setCurrentUserId] = useState<number | null>(null);

  // --- Collections ---
  const [collections, setCollections] = useState<ResourceCollection[]>([]);
  const [selectedResourceId, setSelectedResourceId] = useState<number | null>(null);

  // Fetch subjects on mount
  useEffect(() => {
    resourceLibraryApi.getSubjects().then(setSubjects).catch(() => {});
  }, []);

  // Fetch collections on mount
  useEffect(() => {
    resourceLibraryApi.getCollections().then(setCollections).catch(() => {});
  }, []);

  // Get current user id from local storage (JWT)
  useEffect(() => {
    try {
      const token = localStorage.getItem('token');
      if (token) {
        const payload = JSON.parse(atob(token.split('.')[1]));
        setCurrentUserId(parseInt(payload.sub, 10));
      }
    } catch {
      // ignore
    }
  }, []);

  // Fetch discover results
  const fetchDiscover = useCallback(async () => {
    setDiscoverLoading(true);
    try {
      const params: SearchParams = {
        q: searchQ || undefined,
        subject: filterSubject || undefined,
        grade_level: filterGrade || undefined,
        resource_type: filterType as ResourceType || undefined,
        page,
        limit: 20,
      };
      const result = await resourceLibraryApi.searchResources(params);
      setDiscoverResults(result);
    } catch {
      // ignore
    } finally {
      setDiscoverLoading(false);
    }
  }, [searchQ, filterSubject, filterGrade, filterType, page]);

  useEffect(() => {
    if (activeTab === 'discover') fetchDiscover();
  }, [activeTab, fetchDiscover]);

  // Fetch my resources
  const fetchMyResources = useCallback(async () => {
    setMyLoading(true);
    try {
      const rs = await resourceLibraryApi.getMyResources();
      setMyResources(rs);
    } catch {
      // ignore
    } finally {
      setMyLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === 'mine') fetchMyResources();
  }, [activeTab, fetchMyResources]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchDiscover();
  };

  const handleDeleteResource = async (id: number) => {
    if (!confirm('Delete this resource?')) return;
    try {
      await resourceLibraryApi.deleteResource(id);
      setMyResources((prev) => prev.filter((r) => r.id !== id));
    } catch {
      alert('Failed to delete resource.');
    }
  };

  const handleTogglePublic = async (resource: TeacherResource) => {
    try {
      const updated = await resourceLibraryApi.updateResource(resource.id, { is_public: !resource.is_public });
      setMyResources((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
    } catch {
      alert('Failed to update resource.');
    }
  };

  const handleRate = async (resourceId: number, rating: number, comment: string) => {
    await resourceLibraryApi.rateResource(resourceId, rating, comment);
  };

  const handleRemix = async (resourceId: number) => {
    const result = await resourceLibraryApi.remixResource(resourceId);
    // Optionally navigate to lesson planner
    navigate(`/teacher/lesson-plans?highlight=${result.lesson_plan_id}`);
  };

  const handleCreateCollection = async (name: string) => {
    const c = await resourceLibraryApi.createCollection({ name });
    setCollections((prev) => [c, ...prev]);
  };

  const handleAddToCollection = async (collectionId: number, resourceId: number) => {
    const updated = await resourceLibraryApi.addToCollection(collectionId, resourceId);
    setCollections((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
  };

  const handleOpenDetail = (resource: TeacherResource) => {
    setDetailResource(resource);
    setSelectedResourceId(resource.id);
  };

  return (
    <DashboardLayout welcomeSubtitle="Browse, share, and reuse teaching resources">
      <div className="rl-page">
        <div className="rl-page-header">
          <h1 className="rl-page-title">Resource Library</h1>
          <div className="rl-tabs">
            <button
              className={`rl-tab${activeTab === 'discover' ? ' active' : ''}`}
              onClick={() => setActiveTab('discover')}
            >
              Discover
            </button>
            <button
              className={`rl-tab${activeTab === 'mine' ? ' active' : ''}`}
              onClick={() => setActiveTab('mine')}
            >
              My Resources
            </button>
          </div>
        </div>

        {/* ---- DISCOVER TAB ---- */}
        {activeTab === 'discover' && (
          <div className="rl-discover-layout">
            <div className="rl-discover-main">
              <form className="rl-filter-bar" onSubmit={handleSearch}>
                <input
                  className="rl-search-input"
                  type="search"
                  placeholder="Search resources..."
                  value={searchQ}
                  onChange={(e) => setSearchQ(e.target.value)}
                />
                <select className="rl-select" value={filterSubject} onChange={(e) => setFilterSubject(e.target.value)}>
                  <option value="">All Subjects</option>
                  {subjects.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
                <select className="rl-select" value={filterGrade} onChange={(e) => setFilterGrade(e.target.value)}>
                  <option value="">All Grades</option>
                  {GRADE_LEVELS.map((g) => <option key={g} value={g}>{g}</option>)}
                </select>
                <select className="rl-select" value={filterType} onChange={(e) => setFilterType(e.target.value)}>
                  <option value="">All Types</option>
                  {RESOURCE_TYPES.map((t) => <option key={t} value={t}>{RESOURCE_TYPE_LABELS[t]}</option>)}
                </select>
                <button type="submit" className="rl-btn rl-btn-primary">Search</button>
              </form>

              {discoverLoading && <p className="rl-loading">Loading resources...</p>}

              {!discoverLoading && discoverResults && (
                <>
                  <p className="rl-result-count">{discoverResults.total} resource{discoverResults.total !== 1 ? 's' : ''} found</p>
                  {discoverResults.items.length === 0 ? (
                    <p className="rl-empty-msg">No resources found. Try different filters or be the first to share!</p>
                  ) : (
                    <div className="rl-grid">
                      {discoverResults.items.map((r) => (
                        <ResourceCard key={r.id} resource={r} onOpen={handleOpenDetail} />
                      ))}
                    </div>
                  )}
                  {discoverResults.pages > 1 && (
                    <div className="rl-pagination">
                      <button className="rl-btn rl-btn-secondary" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}>
                        Previous
                      </button>
                      <span>Page {page} of {discoverResults.pages}</span>
                      <button className="rl-btn rl-btn-secondary" onClick={() => setPage((p) => Math.min(discoverResults.pages, p + 1))} disabled={page === discoverResults.pages}>
                        Next
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>

            <CollectionsSidebar
              collections={collections}
              onCreateCollection={handleCreateCollection}
              onAddToCollection={handleAddToCollection}
              selectedResourceId={selectedResourceId}
            />
          </div>
        )}

        {/* ---- MY RESOURCES TAB ---- */}
        {activeTab === 'mine' && (
          <div className="rl-mine-layout">
            <div className="rl-mine-actions">
              <button className="rl-btn rl-btn-primary" onClick={() => setShowUploadModal(true)}>
                + Upload Resource
              </button>
            </div>

            {myLoading && <p className="rl-loading">Loading your resources...</p>}

            {!myLoading && myResources.length === 0 && (
              <p className="rl-empty-msg">You have not uploaded any resources yet. Share something!</p>
            )}

            {!myLoading && myResources.length > 0 && (
              <div className="rl-mine-list">
                {myResources.map((r) => (
                  <div key={r.id} className="rl-mine-item">
                    <div className="rl-mine-item-info">
                      <span className={`rl-type-badge rl-type-${r.resource_type}`}>{RESOURCE_TYPE_LABELS[r.resource_type]}</span>
                      <span className={`rl-visibility-badge${r.is_public ? ' public' : ' private'}`}>
                        {r.is_public ? 'Public' : 'Private'}
                      </span>
                      <strong className="rl-mine-title">{r.title}</strong>
                      {r.subject && <span className="rl-tag">{r.subject}</span>}
                      {r.grade_level && <span className="rl-tag">{r.grade_level}</span>}
                      <StarRating rating={r.avg_rating} count={r.rating_count} />
                      <span className="rl-downloads">{r.download_count} views</span>
                    </div>
                    <div className="rl-mine-item-actions">
                      <button
                        className="rl-btn rl-btn-secondary rl-btn-sm"
                        onClick={() => handleTogglePublic(r)}
                        title={r.is_public ? 'Make private' : 'Make public'}
                      >
                        {r.is_public ? 'Make Private' : 'Make Public'}
                      </button>
                      <button
                        className="rl-btn rl-btn-secondary rl-btn-sm"
                        onClick={() => setEditingResource(r)}
                      >
                        Edit
                      </button>
                      <button
                        className="rl-btn rl-btn-danger rl-btn-sm"
                        onClick={() => handleDeleteResource(r.id)}
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Modals */}
        {detailResource && (
          <ResourceDetailModal
            resource={detailResource}
            onClose={() => setDetailResource(null)}
            isOwner={currentUserId === detailResource.teacher_id}
            onRate={(rating, comment) => handleRate(detailResource.id, rating, comment)}
            onRemix={() => handleRemix(detailResource.id)}
          />
        )}

        {showUploadModal && (
          <UploadResourceModal
            onClose={() => setShowUploadModal(false)}
            onSave={(resource) => setMyResources((prev) => [resource, ...prev])}
          />
        )}

        {editingResource && (
          <EditResourceModal
            resource={editingResource}
            onClose={() => setEditingResource(null)}
            onSave={(updated) => {
              setMyResources((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
              setEditingResource(null);
            }}
          />
        )}
      </div>
    </DashboardLayout>
  );
}
