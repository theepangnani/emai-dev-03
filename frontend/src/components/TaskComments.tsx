import { useState, useEffect, useRef } from 'react';
import { tasksApi } from '../api/client';
import type { TaskComment } from '../api/client';
import { useAuth } from '../context/AuthContext';
import './TaskComments.css';

interface TaskCommentsProps {
  taskId: number;
  /** If true, the comment section is expanded */
  expanded: boolean;
  onToggle: () => void;
  /** Comment count from parent (used for badge before first load) */
  commentCount?: number;
}

export function TaskComments({ taskId, expanded, onToggle, commentCount = 0 }: TaskCommentsProps) {
  const { user } = useAuth();
  const [comments, setComments] = useState<TaskComment[]>([]);
  const [loading, setLoading] = useState(false);
  const [newComment, setNewComment] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [loaded, setLoaded] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (expanded && !loaded) {
      loadComments();
    }
  }, [expanded]);

  useEffect(() => {
    if (expanded && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [expanded]);

  const loadComments = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await tasksApi.listComments(taskId);
      setComments(data);
      setLoaded(true);
    } catch {
      setError('Failed to load comments');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!newComment.trim() || submitting) return;
    setSubmitting(true);
    setError('');
    try {
      const comment = await tasksApi.createComment(taskId, newComment.trim());
      setComments(prev => [...prev, comment]);
      setNewComment('');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to add comment');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (commentId: number) => {
    try {
      await tasksApi.deleteComment(taskId, commentId);
      setComments(prev => prev.filter(c => c.id !== commentId));
    } catch {
      setError('Failed to delete comment');
    }
  };

  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  };

  const displayCount = loaded ? comments.length : commentCount;

  return (
    <div className="task-comments">
      <button
        className={`task-comments-toggle${expanded ? ' expanded' : ''}`}
        onClick={(e) => { e.stopPropagation(); onToggle(); }}
      >
        <span className="task-comments-icon">&#128172;</span>
        <span className="task-comments-label">
          {displayCount > 0 ? `${displayCount} comment${displayCount !== 1 ? 's' : ''}` : 'Add comment'}
        </span>
      </button>

      {expanded && (
        <div className="task-comments-panel" onClick={(e) => e.stopPropagation()}>
          {loading ? (
            <div className="task-comments-loading">Loading comments...</div>
          ) : error ? (
            <div className="task-comments-error">{error}</div>
          ) : (
            <>
              {comments.length > 0 && (
                <div className="task-comments-thread">
                  {comments.map(comment => (
                    <div key={comment.id} className="task-comment">
                      <div className="task-comment-avatar">
                        {comment.user_name.charAt(0).toUpperCase()}
                      </div>
                      <div className="task-comment-body">
                        <div className="task-comment-header">
                          <span className="task-comment-author">{comment.user_name}</span>
                          <span className="task-comment-time">{formatTime(comment.created_at)}</span>
                          {comment.user_id === user?.id && (
                            <button
                              className="task-comment-delete"
                              onClick={() => handleDelete(comment.id)}
                              title="Delete comment"
                              aria-label="Delete this comment"
                            >
                              &times;
                            </button>
                          )}
                        </div>
                        <div className="task-comment-content">{comment.content}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              <div className="task-comment-form">
                <textarea
                  ref={textareaRef}
                  className="task-comment-input"
                  placeholder="Add a comment..."
                  value={newComment}
                  onChange={(e) => setNewComment(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSubmit();
                    }
                  }}
                  rows={2}
                  maxLength={2000}
                  disabled={submitting}
                />
                <button
                  className="task-comment-submit"
                  onClick={handleSubmit}
                  disabled={!newComment.trim() || submitting}
                >
                  {submitting ? 'Sending...' : 'Send'}
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
