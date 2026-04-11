import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { DashboardLayout } from '../components/DashboardLayout';
import { ListSkeleton } from '../components/Skeleton';
import { adminContactsApi } from '../api/adminContacts';
import type { ParentContact, ContactNote, OutreachLogEntry, ContactStats } from '../api/adminContacts';
import { useDebounce } from '../utils/useDebounce';
import { useToast } from '../components/Toast';
import { useConfirm } from '../components/ConfirmModal';
import './AdminContactsPage.css';

const PAGE_SIZE = 25;

const STATUS_OPTIONS = ['lead', 'contacted', 'interested', 'converted', 'archived', 'unresponsive'];
const SOURCE_OPTIONS = ['manual', 'waitlist', 'referral', 'event', 'website', 'other'];

export function AdminContactsPage() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { confirm, confirmModal } = useConfirm();

  // Stats
  const [stats, setStats] = useState<ContactStats | null>(null);

  // List
  const [contacts, setContacts] = useState<ParentContact[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  // Filters
  const [statusFilter, setStatusFilter] = useState('');
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebounce(search, 400);
  const [page, setPage] = useState(0);

  // Bulk selection
  const [selected, setSelected] = useState<Set<number>>(new Set());

  // Detail panel
  const [detailContact, setDetailContact] = useState<ParentContact | null>(null);
  const [detailNotes, setDetailNotes] = useState<ContactNote[]>([]);
  const [detailOutreach, setDetailOutreach] = useState<OutreachLogEntry[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [newNote, setNewNote] = useState('');

  // Add/Edit modal
  const [modalOpen, setModalOpen] = useState(false);
  const [editingContact, setEditingContact] = useState<ParentContact | null>(null);
  const [formData, setFormData] = useState({
    full_name: '',
    email: '',
    phone: '',
    school_name: '',
    child_name: '',
    child_grade: '',
    source: 'manual',
    tags: '',
    consent_given: false,
  });
  const [formSaving, setFormSaving] = useState(false);

  // Bulk status change
  const [bulkStatusValue, setBulkStatusValue] = useState('');

  const loadStats = useCallback(async () => {
    try {
      const data = await adminContactsApi.stats();
      setStats(data);
    } catch {
      // Failed to load stats
    }
  }, []);

  const loadContacts = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminContactsApi.list({
        status: statusFilter || undefined,
        search: debouncedSearch || undefined,
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      });
      setContacts(data.items);
      setTotal(data.total);
    } catch {
      // Failed to load contacts
    } finally {
      setLoading(false);
    }
  }, [statusFilter, debouncedSearch, page]);

  useEffect(() => { loadStats(); }, [loadStats]);
  useEffect(() => { loadContacts(); }, [loadContacts]);

  // Clear selection on filter/page change
  useEffect(() => { setSelected(new Set()); }, [statusFilter, debouncedSearch, page]);

  // Open detail panel
  const openDetail = async (contact: ParentContact) => {
    setDetailContact(contact);
    setDetailLoading(true);
    setDetailNotes([]);
    setDetailOutreach([]);
    try {
      const [notes, outreach] = await Promise.all([
        adminContactsApi.getNotes(contact.id),
        adminContactsApi.getOutreachHistory(contact.id),
      ]);
      setDetailNotes(notes);
      setDetailOutreach(outreach);
    } catch {
      // Failed to load detail
    } finally {
      setDetailLoading(false);
    }
  };

  const closeDetail = () => {
    setDetailContact(null);
    setNewNote('');
  };

  // Add note
  const handleAddNote = async () => {
    if (!detailContact || !newNote.trim()) return;
    try {
      const note = await adminContactsApi.addNote(detailContact.id, newNote.trim());
      setDetailNotes(prev => [note, ...prev]);
      setNewNote('');
      toast('Note added', 'success');
    } catch {
      toast('Failed to add note', 'error');
    }
  };

  // Delete note
  const handleDeleteNote = async (noteId: number) => {
    if (!detailContact) return;
    const ok = await confirm({ title: 'Delete Note', message: 'Are you sure?', variant: 'danger', confirmLabel: 'Delete' });
    if (!ok) return;
    try {
      await adminContactsApi.deleteNote(detailContact.id, noteId);
      setDetailNotes(prev => prev.filter(n => n.id !== noteId));
      toast('Note deleted', 'success');
    } catch {
      toast('Failed to delete note', 'error');
    }
  };

  // Open add modal
  const openAddModal = () => {
    setEditingContact(null);
    setFormData({ full_name: '', email: '', phone: '', school_name: '', child_name: '', child_grade: '', source: 'manual', tags: '', consent_given: false });
    setModalOpen(true);
  };

  // Open edit modal
  const openEditModal = (contact: ParentContact) => {
    setEditingContact(contact);
    setFormData({
      full_name: contact.full_name,
      email: contact.email || '',
      phone: contact.phone || '',
      school_name: contact.school_name || '',
      child_name: contact.child_name || '',
      child_grade: contact.child_grade || '',
      source: contact.source || 'manual',
      tags: (contact.tags || []).join(', '),
      consent_given: contact.consent_given,
    });
    setModalOpen(true);
  };

  // Save contact
  const handleSaveContact = async () => {
    if (!formData.full_name.trim()) {
      toast('Full name is required', 'error');
      return;
    }
    setFormSaving(true);
    const payload: Record<string, unknown> = {
      full_name: formData.full_name.trim(),
      email: formData.email.trim() || null,
      phone: formData.phone.trim() || null,
      school_name: formData.school_name.trim() || null,
      child_name: formData.child_name.trim() || null,
      child_grade: formData.child_grade.trim() || null,
      source: formData.source,
      tags: formData.tags.split(',').map(t => t.trim()).filter(Boolean),
      consent_given: formData.consent_given,
    };
    try {
      if (editingContact) {
        await adminContactsApi.update(editingContact.id, payload);
        toast('Contact updated', 'success');
      } else {
        await adminContactsApi.create(payload);
        toast('Contact created', 'success');
      }
      setModalOpen(false);
      loadContacts();
      loadStats();
    } catch {
      toast('Failed to save contact', 'error');
    } finally {
      setFormSaving(false);
    }
  };

  // Delete contact
  const handleDelete = async (contact: ParentContact) => {
    const ok = await confirm({ title: 'Delete Contact', message: `Delete "${contact.full_name}"? This cannot be undone.`, variant: 'danger', confirmLabel: 'Delete' });
    if (!ok) return;
    try {
      await adminContactsApi.remove(contact.id);
      toast('Contact deleted', 'success');
      if (detailContact?.id === contact.id) closeDetail();
      loadContacts();
      loadStats();
    } catch {
      toast('Failed to delete contact', 'error');
    }
  };

  // CSV export
  const handleExport = async () => {
    try {
      const response = await adminContactsApi.exportCsv({
        status: statusFilter || undefined,
        search: debouncedSearch || undefined,
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = 'contacts_export.csv';
      a.click();
      window.URL.revokeObjectURL(url);
      toast('CSV exported', 'success');
    } catch {
      toast('Failed to export CSV', 'error');
    }
  };

  // Bulk delete
  const handleBulkDelete = async () => {
    const ids = Array.from(selected);
    const ok = await confirm({ title: 'Bulk Delete', message: `Delete ${ids.length} contact(s)? This cannot be undone.`, variant: 'danger', confirmLabel: 'Delete All' });
    if (!ok) return;
    try {
      await adminContactsApi.bulkDelete(ids);
      toast(`${ids.length} contact(s) deleted`, 'success');
      setSelected(new Set());
      loadContacts();
      loadStats();
    } catch {
      toast('Bulk delete failed', 'error');
    }
  };

  // Bulk status
  const handleBulkStatus = async () => {
    if (!bulkStatusValue) return;
    const ids = Array.from(selected);
    try {
      await adminContactsApi.bulkStatus(ids, bulkStatusValue);
      toast(`Status updated for ${ids.length} contact(s)`, 'success');
      setSelected(new Set());
      setBulkStatusValue('');
      loadContacts();
      loadStats();
    } catch {
      toast('Bulk status update failed', 'error');
    }
  };

  // Bulk email
  const handleBulkEmail = () => {
    const ids = Array.from(selected);
    navigate(`/admin/contacts/compose?channel=email&ids=${ids.join(',')}`);
  };

  // Toggle selection
  const toggleSelect = (id: number) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selected.size === contacts.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(contacts.map(c => c.id)));
    }
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <DashboardLayout>
      <div className="admin-contacts-page">
        {/* Header */}
        <div className="admin-contacts-header">
          <h1>Customer Database</h1>
          <div className="admin-contacts-header-actions">
            <button className="btn btn-secondary" onClick={handleExport}>Export CSV</button>
            <button className="btn btn-primary" onClick={openAddModal}>Add Contact</button>
          </div>
        </div>

        {/* Stats */}
        {stats && (
          <div className="admin-contacts-stats">
            <div className="admin-contacts-stat-card">
              <h4>Total Contacts</h4>
              <div className="stat-value">{stats.total}</div>
            </div>
            <div className="admin-contacts-stat-card lead">
              <h4>Leads</h4>
              <div className="stat-value">{stats.by_status?.lead || 0}</div>
            </div>
            <div className="admin-contacts-stat-card contacted">
              <h4>Contacted</h4>
              <div className="stat-value">{stats.by_status?.contacted || 0}</div>
            </div>
            <div className="admin-contacts-stat-card interested">
              <h4>Interested</h4>
              <div className="stat-value">{stats.by_status?.interested || 0}</div>
            </div>
            <div className="admin-contacts-stat-card converted">
              <h4>Converted</h4>
              <div className="stat-value">{stats.by_status?.converted || 0}</div>
            </div>
            <div className="admin-contacts-stat-card warning">
              <h4>Missing Consent</h4>
              <div className="stat-value">{stats.contacts_without_consent}</div>
            </div>
          </div>
        )}

        {/* Search */}
        <div className="admin-contacts-filters">
          <input
            type="text"
            placeholder="Search by name, email, phone, school..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(0); }}
          />
        </div>

        {/* Status pills */}
        <div className="admin-contacts-status-pills">
          <button
            className={`admin-contacts-status-pill ${statusFilter === '' ? 'active' : ''}`}
            onClick={() => { setStatusFilter(''); setPage(0); }}
          >All</button>
          {STATUS_OPTIONS.map(s => (
            <button
              key={s}
              className={`admin-contacts-status-pill ${statusFilter === s ? 'active' : ''}`}
              onClick={() => { setStatusFilter(s); setPage(0); }}
            >{s.charAt(0).toUpperCase() + s.slice(1)}</button>
          ))}
        </div>

        {/* Bulk bar */}
        {selected.size > 0 && (
          <div className="admin-contacts-bulk-bar">
            <span>{selected.size} selected</span>
            <button className="btn btn-sm" onClick={handleBulkEmail}>Send Email</button>
            <select value={bulkStatusValue} onChange={(e) => setBulkStatusValue(e.target.value)}>
              <option value="">Change Status...</option>
              {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
            </select>
            {bulkStatusValue && <button className="btn btn-sm" onClick={handleBulkStatus}>Apply</button>}
            <button className="btn btn-sm btn-danger" onClick={handleBulkDelete}>Delete</button>
          </div>
        )}

        {/* Table */}
        {loading ? (
          <ListSkeleton rows={8} />
        ) : contacts.length === 0 ? (
          <div className="admin-contacts-empty">No contacts found.</div>
        ) : (
          <>
            <table className="admin-contacts-table">
              <thead>
                <tr>
                  <th className="col-checkbox">
                    <input
                      type="checkbox"
                      checked={selected.size === contacts.length && contacts.length > 0}
                      onChange={toggleSelectAll}
                    />
                  </th>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Phone</th>
                  <th>School</th>
                  <th>Child</th>
                  <th>Status</th>
                  <th>Tags</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {contacts.map(c => (
                  <tr key={c.id}>
                    <td className="col-checkbox">
                      <input
                        type="checkbox"
                        checked={selected.has(c.id)}
                        onChange={() => toggleSelect(c.id)}
                      />
                    </td>
                    <td>
                      <span className="admin-contacts-name-cell" onClick={() => openDetail(c)}>
                        {c.full_name}
                      </span>
                      {!c.consent_given && <span title="No PIPEDA consent" style={{ marginLeft: 4, color: '#d97706' }}>*</span>}
                    </td>
                    <td>{c.email || '-'}</td>
                    <td>{c.phone || '-'}</td>
                    <td>{c.school_name || '-'}</td>
                    <td>{c.child_name ? `${c.child_name}${c.child_grade ? ` (${c.child_grade})` : ''}` : '-'}</td>
                    <td><span className={`contact-status-badge ${c.status}`}>{c.status}</span></td>
                    <td>
                      <div className="admin-contacts-tags">
                        {(c.tags || []).map(t => <span key={t} className="admin-contacts-tag">{t}</span>)}
                      </div>
                    </td>
                    <td>
                      <div className="admin-contacts-row-actions">
                        <button className="btn btn-xs" onClick={() => openEditModal(c)}>Edit</button>
                        <button className="btn btn-xs btn-danger" onClick={() => handleDelete(c)}>Del</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Pagination */}
            <div className="admin-contacts-pagination">
              <span>Showing {page * PAGE_SIZE + 1}-{Math.min((page + 1) * PAGE_SIZE, total)} of {total}</span>
              <div style={{ display: 'flex', gap: 8 }}>
                <button disabled={page === 0} onClick={() => setPage(p => p - 1)}>Prev</button>
                <button disabled={page >= totalPages - 1} onClick={() => setPage(p => p + 1)}>Next</button>
              </div>
            </div>
          </>
        )}

        {/* Detail slide-out panel */}
        <div className={`admin-contacts-detail-overlay ${detailContact ? 'open' : ''}`} onClick={closeDetail} />
        <div className={`admin-contacts-detail-panel ${detailContact ? 'open' : ''}`}>
          {detailContact && (
            <>
              <button className="admin-contacts-detail-close" onClick={closeDetail}>&times;</button>
              <h2>{detailContact.full_name}</h2>

              {!detailContact.consent_given && (
                <div className="admin-contacts-consent-warning">
                  PIPEDA consent not given. Outreach may be restricted.
                </div>
              )}

              <div className="admin-contacts-detail-section">
                <h3>Contact Info</h3>
                <div className="admin-contacts-detail-field"><span className="label">Email</span><span className="value">{detailContact.email || '-'}</span></div>
                <div className="admin-contacts-detail-field"><span className="label">Phone</span><span className="value">{detailContact.phone || '-'}</span></div>
                <div className="admin-contacts-detail-field"><span className="label">School</span><span className="value">{detailContact.school_name || '-'}</span></div>
                <div className="admin-contacts-detail-field"><span className="label">Child</span><span className="value">{detailContact.child_name || '-'}{detailContact.child_grade ? ` (Grade ${detailContact.child_grade})` : ''}</span></div>
                <div className="admin-contacts-detail-field"><span className="label">Status</span><span className="value"><span className={`contact-status-badge ${detailContact.status}`}>{detailContact.status}</span></span></div>
                <div className="admin-contacts-detail-field"><span className="label">Source</span><span className="value">{detailContact.source}</span></div>
                <div className="admin-contacts-detail-field"><span className="label">Tags</span><span className="value">{(detailContact.tags || []).join(', ') || '-'}</span></div>
                <div className="admin-contacts-detail-field"><span className="label">Created</span><span className="value">{new Date(detailContact.created_at).toLocaleDateString()}</span></div>
              </div>

              <div className="admin-contacts-detail-section">
                <h3>Notes</h3>
                <div className="admin-contacts-note-form">
                  <input
                    type="text"
                    placeholder="Add a note..."
                    value={newNote}
                    onChange={(e) => setNewNote(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') handleAddNote(); }}
                  />
                  <button className="btn btn-sm" onClick={handleAddNote} disabled={!newNote.trim()}>Add</button>
                </div>
                {detailLoading ? <p style={{ fontSize: 13, color: 'var(--color-ink-muted)' }}>Loading...</p> : (
                  detailNotes.length === 0 ? <p style={{ fontSize: 13, color: 'var(--color-ink-muted)', marginTop: 8 }}>No notes yet.</p> : (
                    detailNotes.map(n => (
                      <div key={n.id} className="admin-contacts-note-item">
                        <div className="admin-contacts-note-text">{n.note_text}</div>
                        <div className="admin-contacts-note-meta">
                          {new Date(n.created_at).toLocaleString()}
                          <button className="btn btn-xs" style={{ marginLeft: 8 }} onClick={() => handleDeleteNote(n.id)}>x</button>
                        </div>
                      </div>
                    ))
                  )
                )}
              </div>

              <div className="admin-contacts-detail-section">
                <h3>Outreach History</h3>
                {detailLoading ? <p style={{ fontSize: 13, color: 'var(--color-ink-muted)' }}>Loading...</p> : (
                  detailOutreach.length === 0 ? <p style={{ fontSize: 13, color: 'var(--color-ink-muted)' }}>No outreach history.</p> : (
                    detailOutreach.map(o => (
                      <div key={o.id} className="admin-contacts-outreach-item">
                        <span className="admin-contacts-outreach-channel">{o.channel}</span>
                        {o.template_name && <span> - {o.template_name}</span>}
                        <span className={`contact-status-badge ${o.status}`} style={{ marginLeft: 8 }}>{o.status}</span>
                        <div className="admin-contacts-outreach-meta">
                          {o.recipient_detail && <span>{o.recipient_detail} | </span>}
                          {new Date(o.created_at).toLocaleString()}
                        </div>
                      </div>
                    ))
                  )
                )}
              </div>
            </>
          )}
        </div>

        {/* Add/Edit Modal */}
        {modalOpen && (
          <div className="admin-contacts-modal-overlay" onClick={() => setModalOpen(false)}>
            <div className="admin-contacts-modal" onClick={(e) => e.stopPropagation()}>
              <h2>{editingContact ? 'Edit Contact' : 'Add Contact'}</h2>
              <div className="admin-contacts-modal-field">
                <label>Full Name *</label>
                <input type="text" value={formData.full_name} onChange={(e) => setFormData(d => ({ ...d, full_name: e.target.value }))} />
              </div>
              <div className="admin-contacts-modal-field">
                <label>Email</label>
                <input type="email" value={formData.email} onChange={(e) => setFormData(d => ({ ...d, email: e.target.value }))} />
              </div>
              <div className="admin-contacts-modal-field">
                <label>Phone</label>
                <input type="tel" value={formData.phone} onChange={(e) => setFormData(d => ({ ...d, phone: e.target.value }))} placeholder="+1..." />
                <div className="hint">Include country code (e.g. +1 for Canada/US)</div>
              </div>
              <div className="admin-contacts-modal-field">
                <label>School</label>
                <input type="text" value={formData.school_name} onChange={(e) => setFormData(d => ({ ...d, school_name: e.target.value }))} />
              </div>
              <div className="admin-contacts-modal-field">
                <label>Child Name</label>
                <input type="text" value={formData.child_name} onChange={(e) => setFormData(d => ({ ...d, child_name: e.target.value }))} />
              </div>
              <div className="admin-contacts-modal-field">
                <label>Child Grade</label>
                <input type="text" value={formData.child_grade} onChange={(e) => setFormData(d => ({ ...d, child_grade: e.target.value }))} />
              </div>
              <div className="admin-contacts-modal-field">
                <label>Source</label>
                <select value={formData.source} onChange={(e) => setFormData(d => ({ ...d, source: e.target.value }))}>
                  {SOURCE_OPTIONS.map(s => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
                </select>
              </div>
              <div className="admin-contacts-modal-field">
                <label>Tags (comma-separated)</label>
                <input type="text" value={formData.tags} onChange={(e) => setFormData(d => ({ ...d, tags: e.target.value }))} placeholder="vip, pilot-school" />
              </div>
              <div className="admin-contacts-modal-field checkbox-field">
                <input type="checkbox" id="consent-checkbox" checked={formData.consent_given} onChange={(e) => setFormData(d => ({ ...d, consent_given: e.target.checked }))} />
                <label htmlFor="consent-checkbox">PIPEDA Consent Given</label>
              </div>
              <div className="admin-contacts-modal-actions">
                <button className="btn btn-secondary" onClick={() => setModalOpen(false)}>Cancel</button>
                <button className="btn btn-primary" onClick={handleSaveContact} disabled={formSaving}>
                  {formSaving ? 'Saving...' : (editingContact ? 'Update' : 'Create')}
                </button>
              </div>
            </div>
          </div>
        )}

        {confirmModal}
      </div>
    </DashboardLayout>
  );
}
