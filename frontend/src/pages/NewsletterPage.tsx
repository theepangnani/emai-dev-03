import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { DashboardLayout } from '../components/DashboardLayout';
import {
  newslettersApi,
  type Newsletter,
  type NewsletterTemplate,
  type NewsletterAudience,
  type NewsletterTone,
} from '../api/newsletters';
import './NewsletterPage.css';

type ComposerTab = 'blank' | 'template' | 'ai';

function StatusBadge({ status }: { status: Newsletter['status'] }) {
  return <span className={`nl-status-badge nl-status-badge--${status}`}>{status}</span>;
}

function AudienceLabel({ audience }: { audience: NewsletterAudience }) {
  const labels: Record<NewsletterAudience, string> = {
    all: 'All',
    parents: 'Parents',
    teachers: 'Teachers',
    students: 'Students',
  };
  return <>{labels[audience] ?? audience}</>;
}

export function NewsletterPage() {
  const queryClient = useQueryClient();

  // ── data ───────────────────────────────────────────────────────────────────
  const { data: newsletters = [], isLoading } = useQuery({
    queryKey: ['newsletters'],
    queryFn: newslettersApi.list,
  });

  const { data: templates = [] } = useQuery({
    queryKey: ['newsletter-templates'],
    queryFn: newslettersApi.getTemplates,
  });

  // ── composer state ─────────────────────────────────────────────────────────
  const [composerTab, setComposerTab] = useState<ComposerTab>('blank');
  const [showComposer, setShowComposer] = useState(false);
  const [previewNewsletter, setPreviewNewsletter] = useState<Newsletter | null>(null);
  const [sendConfirmId, setSendConfirmId] = useState<number | null>(null);
  const [scheduleId, setScheduleId] = useState<number | null>(null);
  const [scheduleDateTime, setScheduleDateTime] = useState('');

  // Blank / template form fields
  const [formTitle, setFormTitle] = useState('');
  const [formSubject, setFormSubject] = useState('');
  const [formContent, setFormContent] = useState('');
  const [formAudience, setFormAudience] = useState<NewsletterAudience>('all');

  // AI generate fields
  const [aiTopic, setAiTopic] = useState('');
  const [aiKeyPoints, setAiKeyPoints] = useState<string[]>(['']);
  const [aiAudience, setAiAudience] = useState<NewsletterAudience>('all');
  const [aiTone, setAiTone] = useState<NewsletterTone>('friendly');

  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // ── mutations ──────────────────────────────────────────────────────────────
  const createMutation = useMutation({
    mutationFn: newslettersApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['newsletters'] });
      setSuccess('Newsletter draft created!');
      resetComposer();
    },
    onError: () => setError('Failed to create newsletter'),
  });

  const generateMutation = useMutation({
    mutationFn: newslettersApi.generate,
    onSuccess: (nl) => {
      queryClient.invalidateQueries({ queryKey: ['newsletters'] });
      setSuccess('AI newsletter generated and saved as draft!');
      setPreviewNewsletter(nl);
      resetComposer();
    },
    onError: () => setError('AI generation failed — check your API key and try again'),
  });

  const sendMutation = useMutation({
    mutationFn: (id: number) => newslettersApi.send(id),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['newsletters'] });
      setSendConfirmId(null);
      setSuccess(`Sent to ${result.sent_count} recipient(s). ${result.failed_count > 0 ? `${result.failed_count} failed.` : ''}`);
    },
    onError: () => setError('Send failed'),
  });

  const scheduleMutation = useMutation({
    mutationFn: ({ id, scheduledAt }: { id: number; scheduledAt: string }) =>
      newslettersApi.schedule(id, scheduledAt),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['newsletters'] });
      setScheduleId(null);
      setScheduleDateTime('');
      setSuccess('Newsletter scheduled!');
    },
    onError: () => setError('Scheduling failed'),
  });

  const deleteMutation = useMutation({
    mutationFn: newslettersApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['newsletters'] });
      setSuccess('Newsletter deleted.');
    },
    onError: () => setError('Delete failed'),
  });

  // ── helpers ────────────────────────────────────────────────────────────────
  const resetComposer = () => {
    setShowComposer(false);
    setFormTitle('');
    setFormSubject('');
    setFormContent('');
    setFormAudience('all');
    setAiTopic('');
    setAiKeyPoints(['']);
    setAiAudience('all');
    setAiTone('friendly');
  };

  const applyTemplate = (template: NewsletterTemplate) => {
    setFormContent(template.content_template);
    setFormTitle(`[${template.name}]`);
    setComposerTab('blank');
  };

  const handleSubmitBlank = () => {
    if (!formTitle.trim() || !formSubject.trim() || !formContent.trim()) {
      setError('Title, subject, and content are required');
      return;
    }
    setError('');
    createMutation.mutate({
      title: formTitle,
      subject: formSubject,
      content: formContent,
      audience: formAudience,
    });
  };

  const handleAiGenerate = () => {
    if (!aiTopic.trim()) {
      setError('Topic is required for AI generation');
      return;
    }
    setError('');
    const filteredPoints = aiKeyPoints.filter((p) => p.trim());
    generateMutation.mutate({
      topic: aiTopic,
      key_points: filteredPoints,
      audience: aiAudience,
      tone: aiTone,
    });
  };

  const addKeyPoint = () => setAiKeyPoints((prev) => [...prev, '']);
  const removeKeyPoint = (i: number) =>
    setAiKeyPoints((prev) => prev.filter((_, idx) => idx !== i));
  const updateKeyPoint = (i: number, val: string) =>
    setAiKeyPoints((prev) => prev.map((p, idx) => (idx === i ? val : p)));

  // Auto-clear messages
  useEffect(() => {
    if (!success && !error) return;
    const t = setTimeout(() => {
      setSuccess('');
      setError('');
    }, 4000);
    return () => clearTimeout(t);
  }, [success, error]);

  // ── render ─────────────────────────────────────────────────────────────────
  return (
    <DashboardLayout welcomeSubtitle="Compose and send newsletters to your school community">
      <div className="nl-page">
        {/* Flash messages */}
        {success && <div className="nl-flash nl-flash--success">{success}</div>}
        {error && <div className="nl-flash nl-flash--error">{error}</div>}

        {/* Header */}
        <div className="nl-header">
          <h1 className="nl-title">School Newsletter</h1>
          <button
            className="nl-btn nl-btn--primary"
            onClick={() => setShowComposer(true)}
          >
            + New Newsletter
          </button>
        </div>

        {/* Composer panel */}
        {showComposer && (
          <div className="nl-composer">
            <div className="nl-composer-header">
              <h2 className="nl-composer-title">Create Newsletter</h2>
              <button className="nl-composer-close" onClick={resetComposer} aria-label="Close">
                &times;
              </button>
            </div>

            {/* Tabs */}
            <div className="nl-tabs">
              {(['blank', 'template', 'ai'] as ComposerTab[]).map((tab) => (
                <button
                  key={tab}
                  className={`nl-tab${composerTab === tab ? ' nl-tab--active' : ''}`}
                  onClick={() => setComposerTab(tab)}
                >
                  {tab === 'blank' && 'Blank'}
                  {tab === 'template' && 'From Template'}
                  {tab === 'ai' && 'AI Generate'}
                </button>
              ))}
            </div>

            {/* Blank tab */}
            {composerTab === 'blank' && (
              <div className="nl-form">
                <div className="nl-field">
                  <label className="nl-label">Title</label>
                  <input
                    className="nl-input"
                    placeholder="Newsletter title (internal)"
                    value={formTitle}
                    onChange={(e) => setFormTitle(e.target.value)}
                  />
                </div>
                <div className="nl-field">
                  <label className="nl-label">Email Subject</label>
                  <input
                    className="nl-input"
                    placeholder="Subject line recipients will see"
                    value={formSubject}
                    onChange={(e) => setFormSubject(e.target.value)}
                  />
                </div>
                <div className="nl-field">
                  <label className="nl-label">Audience</label>
                  <select
                    className="nl-select"
                    value={formAudience}
                    onChange={(e) => setFormAudience(e.target.value as NewsletterAudience)}
                  >
                    <option value="all">All</option>
                    <option value="parents">Parents Only</option>
                    <option value="teachers">Teachers Only</option>
                    <option value="students">Students Only</option>
                  </select>
                </div>
                <div className="nl-field">
                  <label className="nl-label">Content (HTML or plain text)</label>
                  <textarea
                    className="nl-textarea"
                    placeholder="Write your newsletter content here. HTML is supported."
                    value={formContent}
                    onChange={(e) => setFormContent(e.target.value)}
                    rows={12}
                  />
                </div>
                {formContent && (
                  <div className="nl-field">
                    <label className="nl-label">Preview</label>
                    <div
                      className="nl-preview"
                      dangerouslySetInnerHTML={{ __html: formContent }}
                    />
                  </div>
                )}
                <div className="nl-form-actions">
                  <button className="nl-btn nl-btn--secondary" onClick={resetComposer}>
                    Cancel
                  </button>
                  <button
                    className="nl-btn nl-btn--primary"
                    onClick={handleSubmitBlank}
                    disabled={createMutation.isPending}
                  >
                    {createMutation.isPending ? 'Saving…' : 'Save Draft'}
                  </button>
                </div>
              </div>
            )}

            {/* Template tab */}
            {composerTab === 'template' && (
              <div className="nl-template-gallery">
                {templates.length === 0 && (
                  <p className="nl-empty">No templates available.</p>
                )}
                {templates.map((t) => (
                  <div key={t.id} className="nl-template-card">
                    <h3 className="nl-template-name">{t.name}</h3>
                    <p className="nl-template-desc">{t.description}</p>
                    <div
                      className="nl-template-preview"
                      dangerouslySetInnerHTML={{ __html: t.content_template }}
                    />
                    <button
                      className="nl-btn nl-btn--secondary nl-btn--sm"
                      onClick={() => applyTemplate(t)}
                    >
                      Use Template
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* AI Generate tab */}
            {composerTab === 'ai' && (
              <div className="nl-form">
                <div className="nl-field">
                  <label className="nl-label">Topic</label>
                  <input
                    className="nl-input"
                    placeholder="e.g. End of Term Celebrations and Summer Plans"
                    value={aiTopic}
                    onChange={(e) => setAiTopic(e.target.value)}
                  />
                </div>
                <div className="nl-field">
                  <label className="nl-label">Key Points</label>
                  {aiKeyPoints.map((point, i) => (
                    <div key={i} className="nl-key-point-row">
                      <input
                        className="nl-input"
                        placeholder={`Key point ${i + 1}`}
                        value={point}
                        onChange={(e) => updateKeyPoint(i, e.target.value)}
                      />
                      {aiKeyPoints.length > 1 && (
                        <button
                          className="nl-remove-point"
                          onClick={() => removeKeyPoint(i)}
                          aria-label="Remove point"
                        >
                          &times;
                        </button>
                      )}
                    </div>
                  ))}
                  <button className="nl-btn nl-btn--ghost nl-btn--sm" onClick={addKeyPoint}>
                    + Add Key Point
                  </button>
                </div>
                <div className="nl-field nl-field--row">
                  <div className="nl-field nl-field--half">
                    <label className="nl-label">Audience</label>
                    <select
                      className="nl-select"
                      value={aiAudience}
                      onChange={(e) => setAiAudience(e.target.value as NewsletterAudience)}
                    >
                      <option value="all">All</option>
                      <option value="parents">Parents Only</option>
                      <option value="teachers">Teachers Only</option>
                      <option value="students">Students Only</option>
                    </select>
                  </div>
                  <div className="nl-field nl-field--half">
                    <label className="nl-label">Tone</label>
                    <select
                      className="nl-select"
                      value={aiTone}
                      onChange={(e) => setAiTone(e.target.value as NewsletterTone)}
                    >
                      <option value="friendly">Friendly</option>
                      <option value="formal">Formal</option>
                      <option value="informative">Informative</option>
                    </select>
                  </div>
                </div>
                <div className="nl-form-actions">
                  <button className="nl-btn nl-btn--secondary" onClick={resetComposer}>
                    Cancel
                  </button>
                  <button
                    className="nl-btn nl-btn--primary"
                    onClick={handleAiGenerate}
                    disabled={generateMutation.isPending}
                  >
                    {generateMutation.isPending ? 'Generating…' : 'Generate with AI'}
                  </button>
                </div>
                {generateMutation.isPending && (
                  <p className="nl-ai-loading">
                    AI is crafting your newsletter — this may take a few seconds…
                  </p>
                )}
              </div>
            )}
          </div>
        )}

        {/* Preview modal */}
        {previewNewsletter && (
          <div className="nl-modal-overlay" onClick={() => setPreviewNewsletter(null)}>
            <div className="nl-modal" onClick={(e) => e.stopPropagation()}>
              <div className="nl-modal-header">
                <h2 className="nl-modal-title">{previewNewsletter.title}</h2>
                <button
                  className="nl-composer-close"
                  onClick={() => setPreviewNewsletter(null)}
                  aria-label="Close preview"
                >
                  &times;
                </button>
              </div>
              <p className="nl-modal-subject">
                <strong>Subject:</strong> {previewNewsletter.subject}
              </p>
              <div
                className="nl-preview nl-preview--large"
                dangerouslySetInnerHTML={{
                  __html: previewNewsletter.html_content || previewNewsletter.content,
                }}
              />
            </div>
          </div>
        )}

        {/* Send confirmation modal */}
        {sendConfirmId !== null && (
          <div className="nl-modal-overlay" onClick={() => setSendConfirmId(null)}>
            <div className="nl-modal nl-modal--sm" onClick={(e) => e.stopPropagation()}>
              <h3 className="nl-modal-title">Send Newsletter?</h3>
              <p className="nl-modal-body">
                This will immediately email all matching recipients. This action cannot be undone.
              </p>
              <div className="nl-modal-actions">
                <button
                  className="nl-btn nl-btn--secondary"
                  onClick={() => setSendConfirmId(null)}
                >
                  Cancel
                </button>
                <button
                  className="nl-btn nl-btn--danger"
                  onClick={() => sendMutation.mutate(sendConfirmId!)}
                  disabled={sendMutation.isPending}
                >
                  {sendMutation.isPending ? 'Sending…' : 'Send Now'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Schedule modal */}
        {scheduleId !== null && (
          <div className="nl-modal-overlay" onClick={() => setScheduleId(null)}>
            <div className="nl-modal nl-modal--sm" onClick={(e) => e.stopPropagation()}>
              <h3 className="nl-modal-title">Schedule Newsletter</h3>
              <div className="nl-field">
                <label className="nl-label">Send Date &amp; Time</label>
                <input
                  type="datetime-local"
                  className="nl-input"
                  value={scheduleDateTime}
                  onChange={(e) => setScheduleDateTime(e.target.value)}
                />
              </div>
              <div className="nl-modal-actions">
                <button
                  className="nl-btn nl-btn--secondary"
                  onClick={() => setScheduleId(null)}
                >
                  Cancel
                </button>
                <button
                  className="nl-btn nl-btn--primary"
                  onClick={() => {
                    if (!scheduleDateTime) return;
                    scheduleMutation.mutate({
                      id: scheduleId!,
                      scheduledAt: new Date(scheduleDateTime).toISOString(),
                    });
                  }}
                  disabled={scheduleMutation.isPending || !scheduleDateTime}
                >
                  {scheduleMutation.isPending ? 'Scheduling…' : 'Schedule'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Newsletter history list */}
        <section className="nl-history">
          <h2 className="nl-section-title">Newsletter History</h2>
          {isLoading && <p className="nl-empty">Loading…</p>}
          {!isLoading && newsletters.length === 0 && (
            <p className="nl-empty">No newsletters yet. Create your first one!</p>
          )}
          {newsletters.map((nl) => (
            <div key={nl.id} className="nl-card">
              <div className="nl-card-top">
                <div className="nl-card-info">
                  <h3 className="nl-card-title">{nl.title}</h3>
                  <p className="nl-card-subject">{nl.subject}</p>
                  <div className="nl-card-meta">
                    <StatusBadge status={nl.status} />
                    <span className="nl-card-audience">
                      <AudienceLabel audience={nl.audience} />
                    </span>
                    {nl.sent_at && (
                      <span className="nl-card-date">
                        Sent {new Date(nl.sent_at).toLocaleDateString()}
                      </span>
                    )}
                    {nl.scheduled_at && nl.status === 'scheduled' && (
                      <span className="nl-card-date">
                        Scheduled {new Date(nl.scheduled_at).toLocaleString()}
                      </span>
                    )}
                    {nl.recipient_count > 0 && (
                      <span className="nl-card-recipients">
                        {nl.recipient_count} recipient{nl.recipient_count !== 1 ? 's' : ''}
                      </span>
                    )}
                  </div>
                </div>
                <div className="nl-card-actions">
                  <button
                    className="nl-btn nl-btn--ghost nl-btn--sm"
                    onClick={() => setPreviewNewsletter(nl)}
                  >
                    Preview
                  </button>
                  {nl.status !== 'sent' && (
                    <>
                      <button
                        className="nl-btn nl-btn--secondary nl-btn--sm"
                        onClick={() => {
                          setScheduleId(nl.id);
                        }}
                      >
                        Schedule
                      </button>
                      <button
                        className="nl-btn nl-btn--primary nl-btn--sm"
                        onClick={() => setSendConfirmId(nl.id)}
                      >
                        Send Now
                      </button>
                      <button
                        className="nl-btn nl-btn--ghost nl-btn--sm nl-btn--danger-ghost"
                        onClick={() => deleteMutation.mutate(nl.id)}
                        disabled={deleteMutation.isPending}
                      >
                        Delete
                      </button>
                    </>
                  )}
                </div>
              </div>
            </div>
          ))}
        </section>
      </div>
    </DashboardLayout>
  );
}
