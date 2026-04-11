import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { DashboardLayout } from '../components/DashboardLayout';
import { useToast } from '../components/Toast';
import { api } from '../api/client';
import { adminOutreachApi } from '../api/adminOutreach';
import type { OutreachTemplate, OutreachSendResult } from '../api/adminOutreach';
import './AdminOutreachComposer.css';

interface Contact {
  id: number;
  full_name: string;
  email: string | null;
  phone: string | null;
  status: string;
}

type Channel = 'email' | 'whatsapp' | 'sms';

const CHANNELS: { key: Channel; label: string }[] = [
  { key: 'email', label: 'Email' },
  { key: 'whatsapp', label: 'WhatsApp' },
  { key: 'sms', label: 'SMS' },
];

const VARIABLES = ['{{full_name}}', '{{child_name}}', '{{school_name}}', '{{classbridge_url}}'];

export function AdminOutreachComposer() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { toast } = useToast();

  const channel = (searchParams.get('channel') as Channel) || 'email';
  const idsParam = searchParams.get('ids') || '';

  // State
  const [step, setStep] = useState(1);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loadingContacts, setLoadingContacts] = useState(true);
  const [templates, setTemplates] = useState<OutreachTemplate[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null);
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [sending, setSending] = useState(false);
  const [results, setResults] = useState<OutreachSendResult | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);
  const [showPreviewModal, setShowPreviewModal] = useState(false);
  const [previewHtml, setPreviewHtml] = useState('');
  const [twilioError, setTwilioError] = useState(false);

  const bodyRef = useRef<HTMLTextAreaElement>(null);

  // Load contacts from IDs
  const loadContacts = useCallback(async () => {
    if (!idsParam) {
      setLoadingContacts(false);
      return;
    }
    setLoadingContacts(true);
    try {
      const ids = idsParam.split(',').map(Number).filter(Boolean);
      const results: Contact[] = [];
      for (const id of ids) {
        try {
          const res = await api.get(`/api/admin/contacts/${id}`);
          results.push(res.data);
        } catch {
          // skip invalid IDs
        }
      }
      setContacts(results);
    } catch {
      toast('Failed to load contacts', 'error');
    } finally {
      setLoadingContacts(false);
    }
  }, [idsParam, toast]);

  // Load templates for channel
  const loadTemplates = useCallback(async () => {
    try {
      const templateType = channel === 'whatsapp' ? 'whatsapp' : channel;
      const data = await adminOutreachApi.listTemplates({ template_type: templateType, is_active: true });
      setTemplates(Array.isArray(data) ? data : data.items || []);
    } catch {
      // Templates may not be available
      setTemplates([]);
    }
  }, [channel]);

  useEffect(() => {
    loadContacts();
  }, [loadContacts]);

  useEffect(() => {
    loadTemplates();
    // Reset message fields on channel change
    setSelectedTemplateId(null);
    setSubject('');
    setBody('');
    setTwilioError(false);
  }, [loadTemplates]);

  const setChannel = (ch: Channel) => {
    setSearchParams((prev) => {
      prev.set('channel', ch);
      return prev;
    });
    setStep(1);
    setResults(null);
  };

  // Determine valid recipients for channel
  const getValidContacts = useCallback(() => {
    if (channel === 'email') {
      return contacts.filter(c => !!c.email);
    }
    return contacts.filter(c => !!c.phone);
  }, [contacts, channel]);

  const validContacts = getValidContacts();

  const isContactValid = (c: Contact) => {
    if (channel === 'email') return !!c.email;
    return !!c.phone;
  };

  // Template selection
  const handleTemplateSelect = (templateId: number | null) => {
    setSelectedTemplateId(templateId);
    if (templateId) {
      const tmpl = templates.find(t => t.id === templateId);
      if (tmpl) {
        setSubject(tmpl.subject || '');
        setBody(tmpl.body_text || '');
      }
    }
  };

  // Insert variable at cursor position
  const insertVariable = (variable: string) => {
    const textarea = bodyRef.current;
    if (!textarea) {
      setBody(prev => prev + variable);
      return;
    }
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const newBody = body.substring(0, start) + variable + body.substring(end);
    setBody(newBody);
    // Set cursor after inserted variable
    setTimeout(() => {
      textarea.selectionStart = textarea.selectionEnd = start + variable.length;
      textarea.focus();
    }, 0);
  };

  // Preview
  const handlePreview = async () => {
    if (selectedTemplateId) {
      try {
        const data = await adminOutreachApi.previewTemplate(selectedTemplateId, {
          variable_values: {
            full_name: validContacts[0]?.full_name || 'Parent Name',
            child_name: 'Student Name',
            school_name: 'School Name',
            classbridge_url: 'https://www.classbridge.ca',
          },
        });
        setPreviewHtml(data.rendered_html || data.rendered_text || body);
      } catch {
        setPreviewHtml(body);
      }
    } else {
      setPreviewHtml(body);
    }
    setShowPreviewModal(true);
  };

  // Send
  const handleSend = async () => {
    setShowConfirm(false);
    setSending(true);
    setTwilioError(false);
    try {
      const payload: Parameters<typeof adminOutreachApi.send>[0] = {
        parent_contact_ids: validContacts.map(c => c.id),
        channel,
        ...(selectedTemplateId ? { template_id: selectedTemplateId } : {}),
        ...(subject ? { custom_subject: subject } : {}),
        ...(body ? { custom_body: body } : {}),
      };
      const result = await adminOutreachApi.send(payload);
      setResults(result);
      toast(`Sent to ${result.sent_count} recipient(s)`, 'success');
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 503 && channel !== 'email') {
        setTwilioError(true);
        toast('Twilio is not configured for this channel', 'error');
      } else {
        toast('Failed to send outreach', 'error');
      }
    } finally {
      setSending(false);
    }
  };

  // SMS segment count
  const smsSegments = Math.max(1, Math.ceil(body.length / 160));

  const canProceedToStep2 = validContacts.length > 0;
  const canProceedToStep3 = body.trim().length > 0 || selectedTemplateId !== null;

  return (
    <DashboardLayout>
      <div className="outreach-composer">
        {/* Header */}
        <div className="outreach-composer-header">
          <button className="outreach-composer-back-btn" onClick={() => navigate('/admin/contacts')}>
            &larr; Back
          </button>
          <h1>Compose Outreach</h1>
        </div>

        {/* Channel Tabs */}
        <div className="outreach-composer-tabs">
          {CHANNELS.map(ch => (
            <button
              key={ch.key}
              className={`outreach-composer-tab${channel === ch.key ? ' outreach-composer-tab--active' : ''}`}
              onClick={() => setChannel(ch.key)}
            >
              {ch.label}
            </button>
          ))}
        </div>

        {/* Twilio not configured banner */}
        {twilioError && (
          <div className="outreach-composer-info-banner">
            Twilio is not configured for {channel === 'whatsapp' ? 'WhatsApp' : 'SMS'} messaging.
            Please configure Twilio credentials in the backend to enable this channel.
          </div>
        )}

        {/* Step Indicators */}
        <div className="outreach-composer-steps">
          {[
            { num: 1, label: 'Recipients' },
            { num: 2, label: 'Message' },
            { num: 3, label: 'Send' },
          ].map((s, i) => (
            <span key={s.num}>
              {i > 0 && <span className="outreach-composer-step-separator" />}
              <span className={`outreach-composer-step${step === s.num ? ' outreach-composer-step--active' : ''}${step > s.num ? ' outreach-composer-step--done' : ''}`}>
                <span className="outreach-composer-step-number">{step > s.num ? '\u2713' : s.num}</span>
                {s.label}
              </span>
            </span>
          ))}
        </div>

        {/* Results state */}
        {results && (
          <div className="outreach-composer-results">
            <h3>Outreach Complete</h3>
            <div className="outreach-composer-results-stats">
              <div className="outreach-composer-results-stat">
                <div className="outreach-composer-results-stat-value outreach-composer-results-stat-value--success">
                  {results.sent_count}
                </div>
                <div className="outreach-composer-results-stat-label">Sent</div>
              </div>
              <div className="outreach-composer-results-stat">
                <div className="outreach-composer-results-stat-value outreach-composer-results-stat-value--error">
                  {results.failed_count}
                </div>
                <div className="outreach-composer-results-stat-label">Failed</div>
              </div>
            </div>
            {results.errors.length > 0 && (
              <div className="outreach-composer-errors">
                <strong>Errors:</strong>
                <ul>
                  {results.errors.map((e, i) => (
                    <li key={i}>{e.contact_name}: {e.error}</li>
                  ))}
                </ul>
              </div>
            )}
            <div className="outreach-composer-actions">
              <button className="outreach-composer-btn outreach-composer-btn--secondary" onClick={() => navigate('/admin/contacts')}>
                Back to Contacts
              </button>
            </div>
          </div>
        )}

        {/* Step 1: Recipients */}
        {!results && step === 1 && (
          <div className="outreach-composer-recipients">
            <h3>Recipients ({validContacts.length} valid of {contacts.length})</h3>
            {loadingContacts ? (
              <p>Loading contacts...</p>
            ) : contacts.length === 0 ? (
              <p>No contacts selected. Go back and select contacts first.</p>
            ) : (
              <>
                <div className="outreach-composer-recipient-list">
                  {contacts.map(c => (
                    <div key={c.id} className={`outreach-composer-recipient${!isContactValid(c) ? ' outreach-composer-recipient--disabled' : ''}`}>
                      <span className="outreach-composer-recipient-name">{c.full_name}</span>
                      <span className="outreach-composer-recipient-contact">
                        {channel === 'email' ? (c.email || 'No email') : (c.phone || 'No phone')}
                      </span>
                      {!isContactValid(c) && (
                        <span className="outreach-composer-recipient-badge">
                          {channel === 'email' ? 'No email' : 'No phone'}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
                <div className="outreach-composer-valid-count">
                  {validContacts.length} valid recipient(s) for {channel}
                </div>
              </>
            )}
            <div className="outreach-composer-actions">
              <span />
              <button
                className="outreach-composer-btn outreach-composer-btn--primary"
                disabled={!canProceedToStep2}
                onClick={() => setStep(2)}
              >
                Next: Compose Message
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Template & Message */}
        {!results && step === 2 && (
          <div className="outreach-composer-message">
            {/* WhatsApp warning */}
            {channel === 'whatsapp' && (
              <div className="outreach-composer-warning">
                WhatsApp messages require pre-approved templates. Free-form only within 24-hour window.
              </div>
            )}

            {/* Template dropdown */}
            <div className="outreach-composer-field">
              <label>Template</label>
              <select
                value={selectedTemplateId ?? ''}
                onChange={e => handleTemplateSelect(e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">-- No template (custom message) --</option>
                {templates.map(t => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </div>

            {/* Subject (email only) */}
            {channel === 'email' && (
              <div className="outreach-composer-field">
                <label>Subject</label>
                <input
                  type="text"
                  value={subject}
                  onChange={e => setSubject(e.target.value)}
                  placeholder="Email subject line"
                />
              </div>
            )}

            {/* Body */}
            <div className="outreach-composer-field">
              <label>Message Body</label>
              <textarea
                ref={bodyRef}
                value={body}
                onChange={e => setBody(e.target.value)}
                placeholder={channel === 'email' ? 'Compose your email...' : 'Type your message...'}
              />
              {channel === 'sms' && (
                <div className="outreach-composer-char-count">
                  {body.length}/160 ({smsSegments} segment{smsSegments !== 1 ? 's' : ''})
                </div>
              )}
              {channel === 'whatsapp' && (
                <div className="outreach-composer-char-count">
                  {body.length}/4096
                </div>
              )}
            </div>

            {/* Variable chips */}
            <div className="outreach-composer-field">
              <label>Insert Variable</label>
              <div className="outreach-composer-variables">
                {VARIABLES.map(v => (
                  <button
                    key={v}
                    type="button"
                    className="outreach-composer-variable-chip"
                    onClick={() => insertVariable(v)}
                  >
                    {v}
                  </button>
                ))}
              </div>
            </div>

            {/* Actions */}
            <div className="outreach-composer-actions">
              <button className="outreach-composer-btn outreach-composer-btn--secondary" onClick={() => setStep(1)}>
                Back
              </button>
              <div style={{ display: 'flex', gap: '10px' }}>
                {channel === 'email' && (
                  <button className="outreach-composer-btn outreach-composer-btn--secondary" onClick={handlePreview}>
                    Preview
                  </button>
                )}
                <button
                  className="outreach-composer-btn outreach-composer-btn--primary"
                  disabled={!canProceedToStep3}
                  onClick={() => setStep(3)}
                >
                  Next: Review &amp; Send
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Step 3: Preview & Send */}
        {!results && step === 3 && (
          <div className="outreach-composer-preview">
            <h3>Review &amp; Send</h3>
            <div className="outreach-composer-preview-summary">
              <span><strong>Recipients:</strong> {validContacts.length}</span>
              <span><strong>Channel:</strong> {channel}</span>
              {selectedTemplateId && (
                <span><strong>Template:</strong> {templates.find(t => t.id === selectedTemplateId)?.name}</span>
              )}
              {channel === 'email' && subject && (
                <span><strong>Subject:</strong> {subject}</span>
              )}
            </div>
            <div className="outreach-composer-preview-body">
              {body || '(Template content will be used)'}
            </div>
            <div className="outreach-composer-actions">
              <button className="outreach-composer-btn outreach-composer-btn--secondary" onClick={() => setStep(2)}>
                Back
              </button>
              <button
                className="outreach-composer-btn outreach-composer-btn--primary"
                disabled={sending}
                onClick={() => setShowConfirm(true)}
              >
                {sending ? 'Sending...' : 'Send Outreach'}
              </button>
            </div>
          </div>
        )}

        {/* Confirm Modal */}
        {showConfirm && (
          <div className="outreach-composer-modal-overlay" onClick={() => setShowConfirm(false)}>
            <div className="outreach-composer-modal" onClick={e => e.stopPropagation()}>
              <h3>Confirm Send</h3>
              <p>
                Send {channel} message to {validContacts.length} recipient(s)?
                This action cannot be undone.
              </p>
              <div className="outreach-composer-modal-actions">
                <button className="outreach-composer-btn outreach-composer-btn--secondary" onClick={() => setShowConfirm(false)}>
                  Cancel
                </button>
                <button className="outreach-composer-btn outreach-composer-btn--primary" onClick={handleSend}>
                  Confirm Send
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Preview Modal (email) */}
        {showPreviewModal && (
          <div className="outreach-composer-preview-modal-overlay" onClick={() => setShowPreviewModal(false)}>
            <div className="outreach-composer-preview-modal" onClick={e => e.stopPropagation()}>
              <h3>Email Preview</h3>
              <div
                className="outreach-composer-preview-modal-body"
                dangerouslySetInnerHTML={{ __html: previewHtml }}
              />
              <div className="outreach-composer-modal-actions">
                <button className="outreach-composer-btn outreach-composer-btn--secondary" onClick={() => setShowPreviewModal(false)}>
                  Close
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
