import { useState, useEffect, useCallback } from 'react';
import { DashboardLayout } from '../components/DashboardLayout';
import { useAuth } from '../context/AuthContext';
import {
  forumApi,
  type ForumCategory,
  type ForumThread,
  type ForumPost,
  type ForumListResponse,
  type ThreadDetailResponse,
} from '../api/forum';
import './ForumPage.css';

type View = 'categories' | 'threads' | 'thread-detail' | 'search';

function formatRelative(dateStr: string): string {
  const d = new Date(dateStr);
  const now = Date.now();
  const diff = Math.floor((now - d.getTime()) / 1000);
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

// ─── New Thread Modal ──────────────────────────────────────────────────────────

interface NewThreadModalProps {
  categories: ForumCategory[];
  defaultCategoryId?: number;
  onClose: () => void;
  onCreated: (thread: ForumThread) => void;
}

function NewThreadModal({ categories, defaultCategoryId, onClose, onCreated }: NewThreadModalProps) {
  const [categoryId, setCategoryId] = useState<number>(defaultCategoryId ?? categories[0]?.id ?? 0);
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async () => {
    if (!title.trim() || !body.trim()) {
      setError('Title and body are required.');
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      const thread = await forumApi.createThread({ category_id: categoryId, title: title.trim(), body: body.trim() });
      onCreated(thread);
    } catch {
      setError('Failed to create thread. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="forum-modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="forum-modal">
        <h2>New Thread</h2>
        {error && <div className="forum-error">{error}</div>}
        <label>Category</label>
        <select value={categoryId} onChange={(e) => setCategoryId(Number(e.target.value))}>
          {categories.map((cat) => (
            <option key={cat.id} value={cat.id}>{cat.name}</option>
          ))}
        </select>
        <label>Title</label>
        <input
          type="text"
          maxLength={200}
          placeholder="Thread title..."
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        <label>Body</label>
        <textarea
          placeholder="Write your post here..."
          value={body}
          onChange={(e) => setBody(e.target.value)}
        />
        <div className="forum-modal-actions">
          <button className="btn-secondary" onClick={onClose} disabled={submitting}>Cancel</button>
          <button className="btn-primary" onClick={handleSubmit} disabled={submitting}>
            {submitting ? 'Posting...' : 'Post Thread'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Post item with replies ────────────────────────────────────────────────────

interface PostItemProps {
  post: ForumPost;
  threadId: number;
  isLocked: boolean;
  likedPostIds: Set<number>;
  onLike: (postId: number) => void;
  onReply: (parentPostId: number, body: string) => Promise<void>;
}

function PostItem({ post, threadId: _threadId, isLocked, likedPostIds, onLike, onReply }: PostItemProps) {
  const [showReply, setShowReply] = useState(false);
  const [replyBody, setReplyBody] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleReply = async () => {
    if (!replyBody.trim()) return;
    setSubmitting(true);
    try {
      await onReply(post.id, replyBody.trim());
      setReplyBody('');
      setShowReply(false);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="forum-post">
      <div className="forum-post-meta">
        <span className="forum-post-author">{post.author_name}</span>
        <span>{formatRelative(post.created_at)}</span>
      </div>
      <div className="forum-post-body">{post.body}</div>
      <div className="forum-post-actions">
        <button
          className={`btn-like${likedPostIds.has(post.id) ? ' liked' : ''}`}
          onClick={() => onLike(post.id)}
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
          </svg>
          {post.like_count}
        </button>
        {!isLocked && (
          <button className="btn-reply" onClick={() => setShowReply(!showReply)}>
            Reply
          </button>
        )}
      </div>

      {/* Nested replies (1 level deep) */}
      {post.replies && post.replies.length > 0 && (
        <div className="forum-post-replies">
          {post.replies.map((reply) => (
            <div key={reply.id} className="forum-post reply">
              <div className="forum-post-meta">
                <span className="forum-post-author">{reply.author_name}</span>
                <span>{formatRelative(reply.created_at)}</span>
              </div>
              <div className="forum-post-body">{reply.body}</div>
              <div className="forum-post-actions">
                <button
                  className={`btn-like${likedPostIds.has(reply.id) ? ' liked' : ''}`}
                  onClick={() => onLike(reply.id)}
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
                  </svg>
                  {reply.like_count}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showReply && !isLocked && (
        <div className="forum-inline-reply">
          <textarea
            placeholder="Write a reply..."
            value={replyBody}
            onChange={(e) => setReplyBody(e.target.value)}
          />
          <div className="forum-inline-reply-actions">
            <button className="btn-secondary" onClick={() => setShowReply(false)} disabled={submitting}>Cancel</button>
            <button className="btn-primary" onClick={handleReply} disabled={submitting || !replyBody.trim()}>
              {submitting ? 'Posting...' : 'Post Reply'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Main ForumPage component ──────────────────────────────────────────────────

export function ForumPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';

  const [view, setView] = useState<View>('categories');
  const [categories, setCategories] = useState<ForumCategory[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<ForumCategory | null>(null);
  const [threadList, setThreadList] = useState<ForumListResponse | null>(null);
  const [threadListPage, setThreadListPage] = useState(1);
  const [selectedThread, setSelectedThread] = useState<ForumThread | null>(null);
  const [threadDetail, setThreadDetail] = useState<ThreadDetailResponse | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<ForumListResponse | null>(null);
  const [searchPage, setSearchPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showNewThread, setShowNewThread] = useState(false);
  const [replyBody, setReplyBody] = useState('');
  const [replySubmitting, setReplySubmitting] = useState(false);
  const [likedPostIds, setLikedPostIds] = useState<Set<number>>(new Set());

  // Load categories on mount
  useEffect(() => {
    setLoading(true);
    forumApi.getCategories()
      .then(setCategories)
      .catch(() => setError('Failed to load categories.'))
      .finally(() => setLoading(false));
  }, []);

  const loadThreads = useCallback(async (category: ForumCategory, page: number) => {
    setLoading(true);
    setError('');
    try {
      const data = await forumApi.getThreads(category.id, page);
      setThreadList(data);
      setThreadListPage(page);
    } catch {
      setError('Failed to load threads.');
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSelectCategory = useCallback((cat: ForumCategory) => {
    setSelectedCategory(cat);
    setView('threads');
    loadThreads(cat, 1);
  }, [loadThreads]);

  const loadThread = useCallback(async (thread: ForumThread) => {
    setLoading(true);
    setError('');
    try {
      const detail = await forumApi.getThread(thread.id);
      setSelectedThread(detail.thread);
      setThreadDetail(detail);
      setView('thread-detail');
    } catch {
      setError('Failed to load thread.');
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSearch = useCallback(async (page: number) => {
    if (!searchQuery.trim()) return;
    setLoading(true);
    setError('');
    try {
      const data = await forumApi.searchForum(searchQuery.trim(), page);
      setSearchResults(data);
      setSearchPage(page);
      setView('search');
    } catch {
      setError('Search failed.');
    } finally {
      setLoading(false);
    }
  }, [searchQuery]);

  const handleLike = useCallback(async (postId: number) => {
    try {
      const result = await forumApi.likePost(postId);
      setLikedPostIds((prev) => {
        const next = new Set(prev);
        if (result.liked) next.add(postId); else next.delete(postId);
        return next;
      });
      // Update like_count in thread detail state
      setThreadDetail((prev) => {
        if (!prev) return prev;
        const updatePost = (posts: ForumPost[]): ForumPost[] =>
          posts.map((p) => {
            if (p.id === postId) return { ...p, like_count: result.like_count };
            if (p.replies.length) return { ...p, replies: updatePost(p.replies) };
            return p;
          });
        return { ...prev, posts: updatePost(prev.posts) };
      });
    } catch {
      // silently ignore
    }
  }, []);

  const handleReply = useCallback(async (parentPostId: number, body: string) => {
    if (!selectedThread) return;
    const post = await forumApi.createPost(selectedThread.id, { body, parent_post_id: parentPostId });
    setThreadDetail((prev) => {
      if (!prev) return prev;
      const addReply = (posts: ForumPost[]): ForumPost[] =>
        posts.map((p) => {
          if (p.id === parentPostId) return { ...p, replies: [...p.replies, post] };
          if (p.replies.length) return { ...p, replies: addReply(p.replies) };
          return p;
        });
      return { ...prev, posts: addReply(prev.posts) };
    });
  }, [selectedThread]);

  const handlePostReply = async () => {
    if (!selectedThread || !replyBody.trim()) return;
    setReplySubmitting(true);
    try {
      const post = await forumApi.createPost(selectedThread.id, { body: replyBody.trim() });
      setThreadDetail((prev) => prev ? { ...prev, posts: [...prev.posts, post] } : prev);
      setReplyBody('');
      // Update reply_count on selected thread
      setSelectedThread((prev) => prev ? { ...prev, reply_count: prev.reply_count + 1 } : prev);
    } catch {
      setError('Failed to post reply.');
    } finally {
      setReplySubmitting(false);
    }
  };

  // Admin actions
  const handleAdminPin = async (threadId: number) => {
    try {
      const updated = await forumApi.pinThread(threadId);
      setSelectedThread(updated);
      if (selectedCategory) loadThreads(selectedCategory, threadListPage);
    } catch {
      setError('Action failed.');
    }
  };

  const handleAdminLock = async (threadId: number) => {
    try {
      const updated = await forumApi.lockThread(threadId);
      setSelectedThread(updated);
      if (selectedCategory) loadThreads(selectedCategory, threadListPage);
    } catch {
      setError('Action failed.');
    }
  };

  const handleAdminDelete = async (threadId: number) => {
    if (!window.confirm('Delete this thread permanently?')) return;
    try {
      await forumApi.deleteThread(threadId);
      setView('threads');
      setSelectedThread(null);
      setThreadDetail(null);
      if (selectedCategory) loadThreads(selectedCategory, threadListPage);
    } catch {
      setError('Failed to delete thread.');
    }
  };

  const handleNewThreadCreated = (thread: ForumThread) => {
    setShowNewThread(false);
    loadThread(thread);
    if (selectedCategory && thread.category_id === selectedCategory.id) {
      loadThreads(selectedCategory, 1);
    }
  };

  // ─── Views ───────────────────────────────────────────────────────────────────

  const renderBreadcrumb = () => (
    <div className="forum-breadcrumb">
      <button onClick={() => setView('categories')}>Forum</button>
      {(view === 'threads' || view === 'thread-detail') && selectedCategory && (
        <>
          <span className="forum-breadcrumb-sep">/</span>
          <button onClick={() => { setView('threads'); if (selectedCategory) loadThreads(selectedCategory, threadListPage); }}>
            {selectedCategory.name}
          </button>
        </>
      )}
      {view === 'thread-detail' && selectedThread && (
        <>
          <span className="forum-breadcrumb-sep">/</span>
          <span>{selectedThread.title.length > 40 ? selectedThread.title.slice(0, 40) + '...' : selectedThread.title}</span>
        </>
      )}
      {view === 'search' && (
        <>
          <span className="forum-breadcrumb-sep">/</span>
          <span>Search: "{searchQuery}"</span>
        </>
      )}
    </div>
  );

  const canPost = user?.role === 'parent' || user?.role === 'teacher' || user?.role === 'student';

  return (
    <DashboardLayout welcomeSubtitle="Community Discussion Forum">
      <div className="forum-page">
        <div className="forum-header">
          <h1>Community Forum</h1>
          <div className="forum-search-bar">
            <input
              type="text"
              placeholder="Search threads..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch(1)}
            />
            <button className="btn-secondary" onClick={() => handleSearch(1)}>Search</button>
          </div>
          {canPost && (
            <button className="btn-primary" onClick={() => setShowNewThread(true)}>+ New Thread</button>
          )}
        </div>

        {error && <div className="forum-error">{error}</div>}
        {loading && <div className="forum-loading">Loading...</div>}

        {!loading && view !== 'categories' && renderBreadcrumb()}

        {/* ── Categories ── */}
        {!loading && view === 'categories' && (
          <>
            {categories.length === 0 ? (
              <div className="forum-empty"><p>No categories available.</p></div>
            ) : (
              <div className="forum-categories">
                {categories.map((cat) => (
                  <div key={cat.id} className="forum-category-card" onClick={() => handleSelectCategory(cat)}>
                    <h3>{cat.name}</h3>
                    {cat.description && <p>{cat.description}</p>}
                    <span className="forum-category-meta">{cat.thread_count} thread{cat.thread_count !== 1 ? 's' : ''}</span>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {/* ── Thread list ── */}
        {!loading && view === 'threads' && threadList && (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
              <h2 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700 }}>{selectedCategory?.name}</h2>
              {canPost && (
                <button className="btn-primary" onClick={() => setShowNewThread(true)} style={{ fontSize: '0.85rem' }}>
                  + New Thread
                </button>
              )}
            </div>

            {threadList.items.length === 0 ? (
              <div className="forum-empty"><p>No threads yet. Be the first to post!</p></div>
            ) : (
              <div className="forum-thread-list">
                {threadList.items.map((thread) => (
                  <div key={thread.id} className="forum-thread-row" onClick={() => loadThread(thread)}>
                    <div className="forum-thread-row-header">
                      <span className="forum-thread-title">{thread.title}</span>
                      {thread.is_pinned && <span className="forum-pin-badge">Pinned</span>}
                      {thread.is_locked && <span className="forum-lock-badge">Locked</span>}
                    </div>
                    <div className="forum-thread-meta">
                      <span>by {thread.author_name}</span>
                      <span>{thread.reply_count} repl{thread.reply_count !== 1 ? 'ies' : 'y'}</span>
                      <span>{thread.view_count} view{thread.view_count !== 1 ? 's' : ''}</span>
                      <span>{formatRelative(thread.created_at)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {threadList.pages > 1 && (
              <div className="forum-pagination">
                <button disabled={threadListPage === 1} onClick={() => selectedCategory && loadThreads(selectedCategory, threadListPage - 1)}>Prev</button>
                {Array.from({ length: threadList.pages }, (_, i) => i + 1).map((p) => (
                  <button
                    key={p}
                    className={p === threadListPage ? 'active' : ''}
                    onClick={() => selectedCategory && loadThreads(selectedCategory, p)}
                  >{p}</button>
                ))}
                <button disabled={threadListPage === threadList.pages} onClick={() => selectedCategory && loadThreads(selectedCategory, threadListPage + 1)}>Next</button>
              </div>
            )}
          </>
        )}

        {/* ── Thread detail ── */}
        {!loading && view === 'thread-detail' && threadDetail && selectedThread && (
          <div className="forum-thread-detail">
            <div className="forum-thread-body">
              <h2>
                {selectedThread.is_pinned && <span className="forum-pin-badge" style={{ marginRight: '0.5rem' }}>Pinned</span>}
                {selectedThread.is_locked && <span className="forum-lock-badge" style={{ marginRight: '0.5rem' }}>Locked</span>}
                {selectedThread.title}
              </h2>
              <div className="forum-thread-body-meta">
                <span>by <strong>{selectedThread.author_name}</strong></span>
                <span>{formatRelative(selectedThread.created_at)}</span>
                <span>{selectedThread.view_count} views</span>
                <span>{selectedThread.reply_count} replies</span>
              </div>
              <div className="forum-thread-body-text">{selectedThread.body}</div>
              {isAdmin && (
                <div className="forum-thread-admin-actions">
                  <button className="btn-admin pin" onClick={() => handleAdminPin(selectedThread.id)}>
                    {selectedThread.is_pinned ? 'Unpin' : 'Pin'}
                  </button>
                  <button className="btn-admin lock" onClick={() => handleAdminLock(selectedThread.id)}>
                    {selectedThread.is_locked ? 'Unlock' : 'Lock'}
                  </button>
                  <button className="btn-admin delete" onClick={() => handleAdminDelete(selectedThread.id)}>
                    Delete Thread
                  </button>
                </div>
              )}
            </div>

            {/* Posts */}
            <div className="forum-posts-section">
              <h3>Replies ({threadDetail.posts.length})</h3>
              {threadDetail.posts.length === 0 ? (
                <div className="forum-empty"><p>No replies yet.</p></div>
              ) : (
                <div className="forum-posts-list">
                  {threadDetail.posts.map((post) => (
                    <PostItem
                      key={post.id}
                      post={post}
                      threadId={selectedThread.id}
                      isLocked={selectedThread.is_locked}
                      likedPostIds={likedPostIds}
                      onLike={handleLike}
                      onReply={handleReply}
                    />
                  ))}
                </div>
              )}
            </div>

            {/* Main reply form */}
            {canPost && !selectedThread.is_locked && (
              <div className="forum-reply-form">
                <h4>Post a Reply</h4>
                <textarea
                  placeholder="Write your reply..."
                  value={replyBody}
                  onChange={(e) => setReplyBody(e.target.value)}
                />
                <div className="forum-reply-form-actions">
                  <button
                    className="btn-primary"
                    onClick={handlePostReply}
                    disabled={replySubmitting || !replyBody.trim()}
                  >
                    {replySubmitting ? 'Posting...' : 'Post Reply'}
                  </button>
                </div>
              </div>
            )}
            {selectedThread.is_locked && (
              <div className="forum-error">This thread is locked. No new replies are allowed.</div>
            )}
          </div>
        )}

        {/* ── Search results ── */}
        {!loading && view === 'search' && searchResults && (
          <>
            <p style={{ margin: '0 0 0.75rem', fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
              {searchResults.total} result{searchResults.total !== 1 ? 's' : ''} for "{searchQuery}"
            </p>
            {searchResults.items.length === 0 ? (
              <div className="forum-empty"><p>No threads found matching your search.</p></div>
            ) : (
              <div className="forum-thread-list">
                {searchResults.items.map((thread) => (
                  <div key={thread.id} className="forum-thread-row" onClick={() => loadThread(thread)}>
                    <div className="forum-thread-row-header">
                      <span className="forum-thread-title">{thread.title}</span>
                      {thread.is_pinned && <span className="forum-pin-badge">Pinned</span>}
                      {thread.is_locked && <span className="forum-lock-badge">Locked</span>}
                    </div>
                    <div className="forum-thread-meta">
                      <span>by {thread.author_name}</span>
                      <span>{thread.reply_count} replies</span>
                      <span>{formatRelative(thread.created_at)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
            {searchResults.pages > 1 && (
              <div className="forum-pagination">
                <button disabled={searchPage === 1} onClick={() => handleSearch(searchPage - 1)}>Prev</button>
                {Array.from({ length: searchResults.pages }, (_, i) => i + 1).map((p) => (
                  <button
                    key={p}
                    className={p === searchPage ? 'active' : ''}
                    onClick={() => handleSearch(p)}
                  >{p}</button>
                ))}
                <button disabled={searchPage === searchResults.pages} onClick={() => handleSearch(searchPage + 1)}>Next</button>
              </div>
            )}
          </>
        )}

        {/* ── New Thread Modal ── */}
        {showNewThread && (
          <NewThreadModal
            categories={categories}
            defaultCategoryId={selectedCategory?.id}
            onClose={() => setShowNewThread(false)}
            onCreated={handleNewThreadCreated}
          />
        )}
      </div>
    </DashboardLayout>
  );
}

export default ForumPage;
