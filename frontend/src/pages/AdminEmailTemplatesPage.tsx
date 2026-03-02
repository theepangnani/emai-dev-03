import { useState, useEffect, useCallback } from 'react';
import { DashboardLayout } from '../components/DashboardLayout';
import { ListSkeleton } from '../components/Skeleton';
import { useConfirm } from '../components/ConfirmModal';
import { adminApi, type EmailTemplateItem, type EmailTemplateDetail } from '../api/client';
import './AdminEmailTemplatesPage.css';

export function AdminEmailTemplatesPage() {
  const [templates, setTemplates] = useState<EmailTemplateItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Edit modal state
  const [editTemplate, setEditTemplate] = useState<EmailTemplateDetail | null>(null);
  const [editSubject, setEditSubject] = useState('');
  const [editHtmlBody, setEditHtmlBody] = useState('');
  const [editTextBody, setEditTextBody] = useState('');
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState('');

  // Preview state
  const [previewLoading, setPreviewLoading] = useState<string | null>(null);

  // Reset state
  const [resetLoading, setResetLoading] = useState<string | null>(null);

  const { confirm, confirmModal } = useConfirm();

  const loadTemplates = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await adminApi.listEmailTemplates();
      setTemplates(data);
    } catch {
      setError('Failed to load email templates.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  const handleOpenEdit = async (name: string) => {
    try {
      const detail = await adminApi.getEmailTemplate(name);
      setEditTemplate(detail);
      setEditSubject(detail.subject);
      setEditHtmlBody(detail.html_body);
      setEditTextBody(detail.text_body ?? '');
      setEditError('');
    } catch {
      setError(`Failed to load template '${name}'.`);
    }
  };

  const handleSaveEdit = async () => {
    if (!editTemplate) return;
    if (!editSubject.trim() || !editHtmlBody.trim()) {
      setEditError('Subject and HTML body are required.');
      return;
    }
    setEditSaving(true);
    setEditError('');
    try {
      const updated = await adminApi.updateEmailTemplate(editTemplate.name, {
        subject: editSubject.trim(),
        html_body: editHtmlBody,
        text_body: editTextBody || undefined,
      });
      setTemplates(prev => prev.map(t => t.name === updated.name ? { ...t, subject: updated.subject, is_customized: updated.is_customized, updated_at: updated.updated_at } : t));
      setEditTemplate(null);
    } catch (err: any) {
      setEditError(err?.response?.data?.detail || 'Failed to save template.');
    } finally {
      setEditSaving(false);
    }
  };

  const handlePreview = async (name: string) => {
    setPreviewLoading(name);
    try {
      const result = await adminApi.previewEmailTemplate(name);
      // Open rendered HTML in a new tab
      const win = window.open('', '_blank');
      if (win) {
        win.document.write(result.html);
        win.document.close();
      }
    } catch {
      setError(`Failed to preview template '${name}'.`);
    } finally {
      setPreviewLoading(null);
    }
  };

  const handlePreviewFromEdit = async () => {
    if (!editTemplate) return;
    setPreviewLoading(editTemplate.name + '_edit');
    try {
      // Build a temporary preview from current edit state by rendering dummy vars client-side
      const dummyVars: Record<string, string> = {
        user_name: 'Jane Smith',
        recipient_name: 'Jane Smith',
        sender_name: 'John Teacher',
        parent_name: 'Jane Parent',
        child_name: 'Alex Student',
        inviter_name: 'Jane Parent',
        course_name: 'Grade 10 Math',
        app_url: window.location.origin,
        task_url: `${window.location.origin}/tasks/1`,
        invite_link: `${window.location.origin}/accept-invite?token=PREVIEW`,
        reset_url: `${window.location.origin}/reset-password?token=PREVIEW`,
        verify_url: `${window.location.origin}/verify-email?token=PREVIEW`,
        task_title: 'Chapter 5 Review',
        due_date: 'March 10, 2026',
        days_remaining: '2',
        message_preview: 'Hi, just wanted to check in about the upcoming test...',
        subject: editSubject,
        body: '(Preview body content)',
      };
      let html = editHtmlBody;
      for (const [key, value] of Object.entries(dummyVars)) {
        html = html.replaceAll(`{{${key}}}`, value);
      }
      const win = window.open('', '_blank');
      if (win) {
        win.document.write(html);
        win.document.close();
      }
    } finally {
      setPreviewLoading(null);
    }
  };

  const handleReset = async (name: string) => {
    const confirmed = await confirm({
      title: 'Reset Template',
      message: `Reset "${name}" to the system default? Your customizations will be lost.`,
      confirmLabel: 'Reset',
      variant: 'danger',
    });
    if (!confirmed) return;

    setResetLoading(name);
    try {
      const updated = await adminApi.resetEmailTemplate(name);
      setTemplates(prev => prev.map(t => t.name === updated.name ? { ...t, subject: updated.subject, is_customized: updated.is_customized, updated_at: updated.updated_at } : t));
      // Close edit modal if it was open for this template
      if (editTemplate?.name === name) setEditTemplate(null);
    } catch (err: any) {
      setError(err?.response?.data?.detail || `Failed to reset template '${name}'.`);
    } finally {
      setResetLoading(null);
    }
  };

  return (
    <DashboardLayout welcomeSubtitle="Manage email templates">
      <div className="admin-et-page">
        {confirmModal}

        <div className="admin-et-header">
          <h2>Email Templates</h2>
          <p className="admin-et-subtitle">
            Customize the emails sent by ClassBridge. Click Edit to modify subject and body.
            Reset restores the system default.
          </p>
        </div>

        {error && <p className="admin-et-error">{error}</p>}

        {loading ? (
          <ListSkeleton rows={6} />
        ) : (
          <div className="admin-et-list">
            {templates.length === 0 ? (
              <p className="admin-et-empty">No email templates found.</p>
            ) : (
              templates.map(tpl => (
                <div key={tpl.name} className="admin-et-row">
                  <div className="admin-et-row-info">
                    <div className="admin-et-name-line">
                      <span className="admin-et-name">{tpl.name}</span>
                      {tpl.is_customized && (
                        <span className="admin-et-customized-badge">Customized</span>
                      )}
                    </div>
                    <div className="admin-et-subject">{tpl.subject}</div>
                    {tpl.description && (
                      <div className="admin-et-description">{tpl.description}</div>
                    )}
                    {tpl.updated_at && (
                      <div className="admin-et-updated">
                        Last updated: {new Date(tpl.updated_at).toLocaleString()}
                      </div>
                    )}
                  </div>
                  <div className="admin-et-row-actions">
                    <button
                      className="admin-et-btn admin-et-btn-preview"
                      onClick={() => handlePreview(tpl.name)}
                      disabled={previewLoading === tpl.name}
                    >
                      {previewLoading === tpl.name ? 'Loading...' : 'Preview'}
                    </button>
                    <button
                      className="admin-et-btn admin-et-btn-edit"
                      onClick={() => handleOpenEdit(tpl.name)}
                    >
                      Edit
                    </button>
                    {tpl.is_customized && (
                      <button
                        className="admin-et-btn admin-et-btn-reset"
                        onClick={() => handleReset(tpl.name)}
                        disabled={resetLoading === tpl.name}
                      >
                        {resetLoading === tpl.name ? 'Resetting...' : 'Reset'}
                      </button>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* Edit Modal */}
      {editTemplate && (
        <div className="modal-overlay" onClick={() => { if (!editSaving) setEditTemplate(null); }}>
          <div
            className="modal admin-et-modal"
            role="dialog"
            aria-modal="true"
            aria-label={`Edit template: ${editTemplate.name}`}
            onClick={e => e.stopPropagation()}
          >
            <div className="admin-et-modal-header">
              <h2>Edit Template: <span className="admin-et-modal-name">{editTemplate.name}</span></h2>
              {editTemplate.description && (
                <p className="admin-et-modal-desc">{editTemplate.description}</p>
              )}
            </div>

            <div className="admin-et-modal-body">
              <div className="admin-et-field">
                <label htmlFor="et-subject">Subject</label>
                <input
                  id="et-subject"
                  type="text"
                  value={editSubject}
                  onChange={e => setEditSubject(e.target.value)}
                  disabled={editSaving}
                  placeholder="Email subject line"
                />
              </div>

              <div className="admin-et-field">
                <label htmlFor="et-html-body">
                  HTML Body
                  <span className="admin-et-hint"> — Use {'{{variable}}'} for dynamic values</span>
                </label>
                <textarea
                  id="et-html-body"
                  value={editHtmlBody}
                  onChange={e => setEditHtmlBody(e.target.value)}
                  disabled={editSaving}
                  rows={18}
                  spellCheck={false}
                  className="admin-et-textarea-mono"
                  placeholder="HTML email body..."
                />
              </div>

              <div className="admin-et-field">
                <label htmlFor="et-text-body">
                  Plain Text Body <span className="admin-et-hint">(optional)</span>
                </label>
                <textarea
                  id="et-text-body"
                  value={editTextBody}
                  onChange={e => setEditTextBody(e.target.value)}
                  disabled={editSaving}
                  rows={5}
                  placeholder="Plain text fallback (optional)..."
                />
              </div>

              {editError && <p className="admin-et-error">{editError}</p>}
            </div>

            <div className="modal-actions">
              <button
                className="cancel-btn"
                onClick={() => setEditTemplate(null)}
                disabled={editSaving}
              >
                Cancel
              </button>
              <button
                className="admin-et-btn admin-et-btn-preview"
                onClick={handlePreviewFromEdit}
                disabled={editSaving || previewLoading === editTemplate.name + '_edit'}
              >
                {previewLoading === editTemplate.name + '_edit' ? 'Opening...' : 'Preview'}
              </button>
              <button
                className="admin-et-btn admin-et-btn-reset"
                onClick={() => { setEditTemplate(null); handleReset(editTemplate.name); }}
                disabled={editSaving || !editTemplate.is_customized}
                title={editTemplate.is_customized ? 'Reset to system default' : 'Already at default'}
              >
                Reset to Default
              </button>
              <button
                className="submit-btn"
                onClick={handleSaveEdit}
                disabled={editSaving || !editSubject.trim() || !editHtmlBody.trim()}
              >
                {editSaving ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
