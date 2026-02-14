import { useState, useEffect } from 'react';
import { inspirationApi } from '../api/client';
import type { InspirationMessageFull } from '../api/client';
import { DashboardLayout } from '../components/DashboardLayout';
import { ListSkeleton } from '../components/Skeleton';
import './AdminInspirationPage.css';

const ROLES = ['parent', 'teacher', 'student'] as const;

export function AdminInspirationPage() {
  const [messages, setMessages] = useState<InspirationMessageFull[]>([]);
  const [loading, setLoading] = useState(true);
  const [roleFilter, setRoleFilter] = useState('');
  const [showAdd, setShowAdd] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);

  // Form state
  const [formRole, setFormRole] = useState('parent');
  const [formText, setFormText] = useState('');
  const [formAuthor, setFormAuthor] = useState('');
  const [formError, setFormError] = useState('');
  const [saving, setSaving] = useState(false);

  const loadMessages = async () => {
    setLoading(true);
    try {
      const data = await inspirationApi.list(roleFilter ? { role: roleFilter } : undefined);
      setMessages(data);
    } catch { /* */ }
    finally { setLoading(false); }
  };

  useEffect(() => { loadMessages(); }, [roleFilter]);

  const resetForm = () => {
    setFormRole('parent');
    setFormText('');
    setFormAuthor('');
    setFormError('');
    setEditId(null);
    setShowAdd(false);
  };

  const handleSave = async () => {
    if (!formText.trim()) {
      setFormError('Message text is required');
      return;
    }
    setSaving(true);
    setFormError('');
    try {
      if (editId) {
        const updated = await inspirationApi.update(editId, {
          text: formText.trim(),
          author: formAuthor.trim() || undefined,
        });
        setMessages(prev => prev.map(m => m.id === editId ? updated : m));
      } else {
        const created = await inspirationApi.create({
          role: formRole,
          text: formText.trim(),
          author: formAuthor.trim() || undefined,
        });
        setMessages(prev => [...prev, created]);
      }
      resetForm();
    } catch (err: any) {
      setFormError(err?.response?.data?.detail || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (msg: InspirationMessageFull) => {
    setEditId(msg.id);
    setFormRole(msg.role);
    setFormText(msg.text);
    setFormAuthor(msg.author || '');
    setFormError('');
    setShowAdd(true);
  };

  const handleToggleActive = async (msg: InspirationMessageFull) => {
    try {
      const updated = await inspirationApi.update(msg.id, { is_active: !msg.is_active });
      setMessages(prev => prev.map(m => m.id === msg.id ? updated : m));
    } catch { /* */ }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this message permanently?')) return;
    try {
      await inspirationApi.delete(id);
      setMessages(prev => prev.filter(m => m.id !== id));
    } catch { /* */ }
  };

  const grouped = ROLES.reduce((acc, role) => {
    acc[role] = messages.filter(m => m.role === role);
    return acc;
  }, {} as Record<string, InspirationMessageFull[]>);

  return (
    <DashboardLayout welcomeSubtitle="Manage inspirational messages">
      <div className="admin-insp-header">
        <h3>Inspirational Messages</h3>
        <div className="admin-insp-actions">
          <select value={roleFilter} onChange={e => setRoleFilter(e.target.value)}>
            <option value="">All Roles</option>
            {ROLES.map(r => <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>)}
          </select>
          <button className="admin-insp-add-btn" onClick={() => { resetForm(); setShowAdd(true); }}>
            + Add Message
          </button>
        </div>
      </div>

      {/* Add / Edit form */}
      {showAdd && (
        <div className="admin-insp-form">
          <h4>{editId ? 'Edit Message' : 'New Message'}</h4>
          {formError && <div className="admin-insp-error">{formError}</div>}
          <div className="admin-insp-form-row">
            <label>Role</label>
            <select value={formRole} onChange={e => setFormRole(e.target.value)} disabled={!!editId}>
              {ROLES.map(r => <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>)}
            </select>
          </div>
          <div className="admin-insp-form-row">
            <label>Message *</label>
            <textarea
              value={formText}
              onChange={e => setFormText(e.target.value)}
              placeholder="Enter an inspirational message..."
              rows={3}
            />
          </div>
          <div className="admin-insp-form-row">
            <label>Author (optional)</label>
            <input
              type="text"
              value={formAuthor}
              onChange={e => setFormAuthor(e.target.value)}
              placeholder="e.g. Nelson Mandela"
            />
          </div>
          <div className="admin-insp-form-actions">
            <button onClick={resetForm}>Cancel</button>
            <button className="admin-insp-save-btn" onClick={handleSave} disabled={saving}>
              {saving ? 'Saving...' : editId ? 'Update' : 'Add'}
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <ListSkeleton rows={5} />
      ) : (
        <div className="admin-insp-list">
          {(roleFilter ? [roleFilter] : ROLES as unknown as string[]).map(role => {
            const msgs = grouped[role] || [];
            if (msgs.length === 0 && roleFilter) {
              return (
                <div key={role} className="admin-insp-empty">
                  No messages for {role} role.
                </div>
              );
            }
            if (msgs.length === 0) return null;
            return (
              <div key={role} className="admin-insp-group">
                <h4 className="admin-insp-group-title">
                  {role.charAt(0).toUpperCase() + role.slice(1)} ({msgs.length})
                </h4>
                {msgs.map(msg => (
                  <div key={msg.id} className={`admin-insp-row${!msg.is_active ? ' inactive' : ''}`}>
                    <div className="admin-insp-content">
                      <span className="admin-insp-text">"{msg.text}"</span>
                      {msg.author && <span className="admin-insp-author">— {msg.author}</span>}
                    </div>
                    <div className="admin-insp-row-actions">
                      <button
                        className={`admin-insp-toggle ${msg.is_active ? 'active' : ''}`}
                        onClick={() => handleToggleActive(msg)}
                        title={msg.is_active ? 'Deactivate' : 'Activate'}
                      >
                        {msg.is_active ? 'Active' : 'Inactive'}
                      </button>
                      <button className="admin-insp-edit" onClick={() => handleEdit(msg)}>Edit</button>
                      <button className="admin-insp-delete" onClick={() => handleDelete(msg.id)}>Delete</button>
                    </div>
                  </div>
                ))}
              </div>
            );
          })}
          {messages.length === 0 && !roleFilter && (
            <div className="admin-insp-empty">
              No messages yet. Add one or use the seed button to import defaults.
            </div>
          )}
        </div>
      )}

      <div className="admin-insp-footer">
        <span className="admin-insp-count">{messages.length} total messages</span>
      </div>
    </DashboardLayout>
  );
}
