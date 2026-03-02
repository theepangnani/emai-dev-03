/**
 * LessonPlannerPage — TeachAssist-compatible lesson planning tool for Ontario teachers.
 *
 * Features:
 *   - List/filter lesson plans by type, course, grade
 *   - Create / edit / duplicate / delete plans
 *   - Plan editor modal with tabs: Overview, Curriculum, Learning, 3-Part Lesson, Assessment, Differentiation
 *   - Import from TeachAssist XML or CSV
 *   - AI-generate learning goals + 3-part lesson
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { DashboardLayout } from '../components/DashboardLayout';
import { lessonPlanApi } from '../api/lessonPlans';
import type { LessonPlanItem, LessonPlanCreate, LessonPlanType, ThreePartLesson, DifferentiationPlan } from '../api/lessonPlans';
import { coursesApi } from '../api/client';
import './LessonPlannerPage.css';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const PLAN_TYPE_LABELS: Record<LessonPlanType, string> = {
  long_range: 'Long-Range Plan',
  unit: 'Unit Plan',
  daily: 'Daily Lesson',
};

const PLAN_TYPE_ABBR: Record<LessonPlanType, string> = {
  long_range: 'LRP',
  unit: 'Unit',
  daily: 'Daily',
};

const GRADE_OPTIONS = ['9', '10', '11', '12', 'K', '1', '2', '3', '4', '5', '6', '7', '8'];

interface Course {
  id: number;
  name: string;
}

type EditorTab = 'overview' | 'curriculum' | 'learning' | 'three_part' | 'assessment' | 'differentiation';

const EDITOR_TABS: { id: EditorTab; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'curriculum', label: 'Curriculum' },
  { id: 'learning', label: 'Learning' },
  { id: 'three_part', label: '3-Part Lesson' },
  { id: 'assessment', label: 'Assessment' },
  { id: 'differentiation', label: 'Differentiation' },
];

// ---------------------------------------------------------------------------
// Editable list component
// ---------------------------------------------------------------------------

interface EditableListProps {
  label: string;
  items: string[];
  onChange: (items: string[]) => void;
  placeholder?: string;
}

function EditableList({ label, items, onChange, placeholder }: EditableListProps) {
  const [newItem, setNewItem] = useState('');

  const addItem = () => {
    const trimmed = newItem.trim();
    if (!trimmed) return;
    onChange([...items, trimmed]);
    setNewItem('');
  };

  const removeItem = (idx: number) => {
    onChange(items.filter((_, i) => i !== idx));
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      addItem();
    }
  };

  return (
    <div className="lp-editable-list">
      <label className="lp-field-label">{label}</label>
      <ul className="lp-list-items">
        {items.map((item, idx) => (
          <li key={idx} className="lp-list-item">
            <span className="lp-list-item-text">{item}</span>
            <button
              type="button"
              className="lp-list-item-remove"
              onClick={() => removeItem(idx)}
              aria-label="Remove item"
            >
              &times;
            </button>
          </li>
        ))}
      </ul>
      <div className="lp-list-add-row">
        <input
          type="text"
          className="lp-input lp-list-add-input"
          value={newItem}
          onChange={e => setNewItem(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder || `Add ${label.toLowerCase()}…`}
        />
        <button type="button" className="lp-btn-add-item" onClick={addItem}>
          + Add
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Import Modal
// ---------------------------------------------------------------------------

interface ImportModalProps {
  onClose: () => void;
  onImported: (plans: LessonPlanItem[]) => void;
}

function ImportModal({ onClose, onImported }: ImportModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [preview, setPreview] = useState<LessonPlanItem[] | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = (f: File) => {
    setFile(f);
    setError('');
    setPreview(null);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) handleFile(dropped);
  };

  const handleImport = async () => {
    if (!file) return;
    setLoading(true);
    setError('');
    try {
      const result = await lessonPlanApi.import(file);
      setPreview(result.plans);
      if (result.plans.length > 0) {
        onImported(result.plans);
      }
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e?.response?.data?.detail || 'Import failed. Please check the file format.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="lp-modal-overlay" onClick={onClose}>
      <div className="lp-modal lp-import-modal" onClick={e => e.stopPropagation()}>
        <div className="lp-modal-header">
          <h2 className="lp-modal-title">Import from TeachAssist</h2>
          <button type="button" className="lp-modal-close" onClick={onClose}>&times;</button>
        </div>

        {preview ? (
          <div className="lp-import-success">
            <div className="lp-import-success-icon">&#10003;</div>
            <h3>Successfully imported {preview.length} plan{preview.length !== 1 ? 's' : ''}!</h3>
            <ul className="lp-import-preview-list">
              {preview.slice(0, 10).map((p, i) => (
                <li key={i}>
                  <span className={`lp-type-badge lp-type-${p.plan_type}`}>
                    {PLAN_TYPE_ABBR[p.plan_type]}
                  </span>
                  {p.title}
                </li>
              ))}
              {preview.length > 10 && <li>…and {preview.length - 10} more</li>}
            </ul>
            <button type="button" className="lp-btn-primary" onClick={onClose}>
              Done
            </button>
          </div>
        ) : (
          <>
            <p className="lp-import-hint">
              Upload a TeachAssist XML export (<code>.xml</code>) or CSV file (<code>.csv</code>).
            </p>

            <div
              className={`lp-dropzone${dragging ? ' lp-dropzone-active' : ''}`}
              onDragOver={e => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
              onClick={() => inputRef.current?.click()}
              role="button"
              tabIndex={0}
              onKeyDown={e => e.key === 'Enter' && inputRef.current?.click()}
            >
              <div className="lp-dropzone-icon">&#128196;</div>
              {file ? (
                <p className="lp-dropzone-filename">{file.name}</p>
              ) : (
                <p>Drag &amp; drop XML or CSV file here, or click to browse</p>
              )}
              <input
                ref={inputRef}
                type="file"
                accept=".xml,.csv,application/xml,text/xml,text/csv"
                style={{ display: 'none' }}
                onChange={e => {
                  const f = e.target.files?.[0];
                  if (f) handleFile(f);
                }}
              />
            </div>

            {error && <p className="lp-error-msg">{error}</p>}

            <div className="lp-modal-footer">
              <button type="button" className="lp-btn-secondary" onClick={onClose}>
                Cancel
              </button>
              <button
                type="button"
                className="lp-btn-primary"
                disabled={!file || loading}
                onClick={handleImport}
              >
                {loading ? 'Importing…' : 'Import'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Plan Editor Modal
// ---------------------------------------------------------------------------

const EMPTY_PLAN: LessonPlanCreate = {
  plan_type: 'unit',
  title: '',
  course_id: null,
  strand: '',
  unit_number: undefined,
  grade_level: '',
  subject_code: '',
  big_ideas: [],
  curriculum_expectations: [],
  overall_expectations: [],
  specific_expectations: [],
  learning_goals: [],
  success_criteria: [],
  three_part_lesson: null,
  assessment_for_learning: '',
  assessment_of_learning: '',
  differentiation: null,
  materials_resources: [],
  cross_curricular: [],
  duration_minutes: undefined,
  start_date: '',
  end_date: '',
  is_template: false,
};

interface PlanEditorProps {
  initial: LessonPlanItem | null;  // null = create new
  courses: Course[];
  onClose: () => void;
  onSaved: (plan: LessonPlanItem) => void;
}

function PlanEditor({ initial, courses, onClose, onSaved }: PlanEditorProps) {
  const [tab, setTab] = useState<EditorTab>('overview');
  const [form, setForm] = useState<LessonPlanCreate>(() => {
    if (!initial) return { ...EMPTY_PLAN };
    return {
      plan_type: initial.plan_type,
      title: initial.title,
      course_id: initial.course_id,
      strand: initial.strand || '',
      unit_number: initial.unit_number || undefined,
      grade_level: initial.grade_level || '',
      subject_code: initial.subject_code || '',
      big_ideas: initial.big_ideas || [],
      curriculum_expectations: initial.curriculum_expectations || [],
      overall_expectations: initial.overall_expectations || [],
      specific_expectations: initial.specific_expectations || [],
      learning_goals: initial.learning_goals || [],
      success_criteria: initial.success_criteria || [],
      three_part_lesson: initial.three_part_lesson || null,
      assessment_for_learning: initial.assessment_for_learning || '',
      assessment_of_learning: initial.assessment_of_learning || '',
      differentiation: initial.differentiation || null,
      materials_resources: initial.materials_resources || [],
      cross_curricular: initial.cross_curricular || [],
      duration_minutes: initial.duration_minutes || undefined,
      start_date: initial.start_date || '',
      end_date: initial.end_date || '',
      is_template: initial.is_template || false,
    };
  });

  const [saving, setSaving] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [error, setError] = useState('');

  const set = <K extends keyof LessonPlanCreate>(key: K, value: LessonPlanCreate[K]) => {
    setForm(prev => ({ ...prev, [key]: value }));
  };

  const setThreePart = (key: keyof ThreePartLesson, value: string) => {
    setForm(prev => ({
      ...prev,
      three_part_lesson: { ...(prev.three_part_lesson || {}), [key]: value },
    }));
  };

  const setDiff = (key: keyof DifferentiationPlan, value: string) => {
    setForm(prev => ({
      ...prev,
      differentiation: { ...(prev.differentiation || {}), [key]: value },
    }));
  };

  const handleSave = async () => {
    if (!form.title.trim()) {
      setError('Title is required.');
      setTab('overview');
      return;
    }
    setSaving(true);
    setError('');
    try {
      let saved: LessonPlanItem;
      if (initial) {
        saved = await lessonPlanApi.update(initial.id, form);
      } else {
        saved = await lessonPlanApi.create(form);
      }
      onSaved(saved);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e?.response?.data?.detail || 'Save failed. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const handleAiGenerate = async () => {
    if (!initial) {
      setError('Save the plan first before generating AI content.');
      return;
    }
    setAiLoading(true);
    setError('');
    try {
      const updated = await lessonPlanApi.aiGenerate(initial.id);
      // Merge AI-generated fields into form
      setForm(prev => ({
        ...prev,
        learning_goals: updated.learning_goals || prev.learning_goals,
        success_criteria: updated.success_criteria || prev.success_criteria,
        three_part_lesson: updated.three_part_lesson || prev.three_part_lesson,
      }));
      onSaved(updated);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e?.response?.data?.detail || 'AI generation failed. Please try again.');
    } finally {
      setAiLoading(false);
    }
  };

  return (
    <div className="lp-modal-overlay" onClick={onClose}>
      <div className="lp-modal lp-editor-modal" onClick={e => e.stopPropagation()}>
        <div className="lp-modal-header">
          <h2 className="lp-modal-title">
            {initial ? 'Edit Plan' : 'New Lesson Plan'}
          </h2>
          <button type="button" className="lp-modal-close" onClick={onClose}>&times;</button>
        </div>

        {/* Tab bar */}
        <div className="lp-editor-tabs">
          {EDITOR_TABS.map(t => (
            <button
              key={t.id}
              type="button"
              className={`lp-editor-tab${tab === t.id ? ' lp-editor-tab-active' : ''}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="lp-editor-body">
          {/* ---- Overview ---- */}
          {tab === 'overview' && (
            <div className="lp-tab-content">
              <div className="lp-field-row">
                <div className="lp-field">
                  <label className="lp-field-label">Title *</label>
                  <input
                    type="text"
                    className="lp-input"
                    value={form.title}
                    onChange={e => set('title', e.target.value)}
                    placeholder="e.g. Quadratic Relations Unit"
                  />
                </div>
              </div>

              <div className="lp-field-row lp-field-row-3">
                <div className="lp-field">
                  <label className="lp-field-label">Plan Type</label>
                  <select
                    className="lp-select"
                    value={form.plan_type}
                    onChange={e => set('plan_type', e.target.value as LessonPlanType)}
                  >
                    <option value="unit">Unit Plan</option>
                    <option value="long_range">Long-Range Plan</option>
                    <option value="daily">Daily Lesson</option>
                  </select>
                </div>
                <div className="lp-field">
                  <label className="lp-field-label">Grade Level</label>
                  <select
                    className="lp-select"
                    value={form.grade_level || ''}
                    onChange={e => set('grade_level', e.target.value)}
                  >
                    <option value="">— Select —</option>
                    {GRADE_OPTIONS.map(g => (
                      <option key={g} value={g}>{g}</option>
                    ))}
                  </select>
                </div>
                <div className="lp-field">
                  <label className="lp-field-label">Course Code</label>
                  <input
                    type="text"
                    className="lp-input"
                    value={form.subject_code || ''}
                    onChange={e => set('subject_code', e.target.value)}
                    placeholder="e.g. MPM2D"
                    maxLength={20}
                  />
                </div>
              </div>

              <div className="lp-field-row lp-field-row-2">
                <div className="lp-field">
                  <label className="lp-field-label">Linked Course</label>
                  <select
                    className="lp-select"
                    value={form.course_id ?? ''}
                    onChange={e => set('course_id', e.target.value ? Number(e.target.value) : null)}
                  >
                    <option value="">— None —</option>
                    {courses.map(c => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                </div>
                <div className="lp-field">
                  <label className="lp-field-label">Strand</label>
                  <input
                    type="text"
                    className="lp-input"
                    value={form.strand || ''}
                    onChange={e => set('strand', e.target.value)}
                    placeholder="e.g. Number Sense and Algebra"
                  />
                </div>
              </div>

              <div className="lp-field-row lp-field-row-3">
                <div className="lp-field">
                  <label className="lp-field-label">Unit #</label>
                  <input
                    type="number"
                    className="lp-input"
                    value={form.unit_number ?? ''}
                    onChange={e => set('unit_number', e.target.value ? Number(e.target.value) : undefined)}
                    min={1}
                  />
                </div>
                <div className="lp-field">
                  <label className="lp-field-label">Duration (min)</label>
                  <input
                    type="number"
                    className="lp-input"
                    value={form.duration_minutes ?? ''}
                    onChange={e => set('duration_minutes', e.target.value ? Number(e.target.value) : undefined)}
                    min={1}
                  />
                </div>
                <div className="lp-field lp-field-checkbox">
                  <label className="lp-checkbox-label">
                    <input
                      type="checkbox"
                      checked={form.is_template}
                      onChange={e => set('is_template', e.target.checked)}
                    />
                    Share as Template
                  </label>
                </div>
              </div>

              <div className="lp-field-row lp-field-row-2">
                <div className="lp-field">
                  <label className="lp-field-label">Start Date</label>
                  <input
                    type="date"
                    className="lp-input"
                    value={form.start_date || ''}
                    onChange={e => set('start_date', e.target.value)}
                  />
                </div>
                <div className="lp-field">
                  <label className="lp-field-label">End Date</label>
                  <input
                    type="date"
                    className="lp-input"
                    value={form.end_date || ''}
                    onChange={e => set('end_date', e.target.value)}
                  />
                </div>
              </div>
            </div>
          )}

          {/* ---- Curriculum ---- */}
          {tab === 'curriculum' && (
            <div className="lp-tab-content">
              <EditableList
                label="Big Ideas"
                items={form.big_ideas || []}
                onChange={v => set('big_ideas', v)}
                placeholder="e.g. Algebra models real-world relationships"
              />
              <EditableList
                label="Overall Expectations"
                items={form.overall_expectations || []}
                onChange={v => set('overall_expectations', v)}
                placeholder="e.g. QR1 — expand and simplify polynomial expressions"
              />
              <EditableList
                label="Specific Expectations"
                items={form.specific_expectations || []}
                onChange={v => set('specific_expectations', v)}
                placeholder="e.g. QR1.1"
              />
              <EditableList
                label="Curriculum Expectation Codes"
                items={form.curriculum_expectations || []}
                onChange={v => set('curriculum_expectations', v)}
                placeholder="e.g. B1.1, B1.2"
              />
              <EditableList
                label="Materials & Resources"
                items={form.materials_resources || []}
                onChange={v => set('materials_resources', v)}
                placeholder="e.g. graphing calculators, textbook p.45"
              />
              <EditableList
                label="Cross-Curricular Connections"
                items={form.cross_curricular || []}
                onChange={v => set('cross_curricular', v)}
                placeholder="e.g. Science — parabolic motion"
              />
            </div>
          )}

          {/* ---- Learning ---- */}
          {tab === 'learning' && (
            <div className="lp-tab-content">
              <div className="lp-ai-generate-bar">
                <span className="lp-ai-hint">
                  Let AI generate learning goals, success criteria, and the 3-part lesson from your curriculum expectations.
                </span>
                <button
                  type="button"
                  className={`lp-btn-ai${aiLoading ? ' lp-btn-ai-loading' : ''}`}
                  onClick={handleAiGenerate}
                  disabled={aiLoading}
                >
                  {aiLoading ? 'Generating…' : '&#10024; AI Generate'}
                </button>
              </div>

              <EditableList
                label="Learning Goals"
                items={form.learning_goals || []}
                onChange={v => set('learning_goals', v)}
                placeholder="Students will be able to…"
              />
              <EditableList
                label="Success Criteria"
                items={form.success_criteria || []}
                onChange={v => set('success_criteria', v)}
                placeholder="I can…"
              />
            </div>
          )}

          {/* ---- 3-Part Lesson ---- */}
          {tab === 'three_part' && (
            <div className="lp-tab-content">
              <div className="lp-ai-generate-bar">
                <span className="lp-ai-hint">
                  AI can generate the complete 3-part lesson structure from your plan details.
                </span>
                <button
                  type="button"
                  className={`lp-btn-ai${aiLoading ? ' lp-btn-ai-loading' : ''}`}
                  onClick={handleAiGenerate}
                  disabled={aiLoading}
                >
                  {aiLoading ? 'Generating…' : '&#10024; AI Generate'}
                </button>
              </div>

              <div className="lp-three-part-section">
                <div className="lp-three-part-badge lp-badge-mindson">Minds On</div>
                <p className="lp-three-part-hint">
                  Hook activity or warm-up to activate prior knowledge (5–10 min)
                </p>
                <textarea
                  className="lp-textarea"
                  rows={5}
                  value={form.three_part_lesson?.minds_on || ''}
                  onChange={e => setThreePart('minds_on', e.target.value)}
                  placeholder="Describe the opening hook, warm-up, or activating strategy…"
                />
              </div>

              <div className="lp-three-part-section">
                <div className="lp-three-part-badge lp-badge-action">Action</div>
                <p className="lp-three-part-hint">
                  Main instructional activity / working time (40–50 min)
                </p>
                <textarea
                  className="lp-textarea"
                  rows={7}
                  value={form.three_part_lesson?.action || ''}
                  onChange={e => setThreePart('action', e.target.value)}
                  placeholder="Describe the main lesson activity, investigations, or direct instruction…"
                />
              </div>

              <div className="lp-three-part-section">
                <div className="lp-three-part-badge lp-badge-consolidation">Consolidation</div>
                <p className="lp-three-part-hint">
                  Exit ticket, debrief, or consolidation activity (10–15 min)
                </p>
                <textarea
                  className="lp-textarea"
                  rows={5}
                  value={form.three_part_lesson?.consolidation || ''}
                  onChange={e => setThreePart('consolidation', e.target.value)}
                  placeholder="Describe how students consolidate and share their learning…"
                />
              </div>
            </div>
          )}

          {/* ---- Assessment ---- */}
          {tab === 'assessment' && (
            <div className="lp-tab-content">
              <div className="lp-field">
                <label className="lp-field-label">Assessment FOR Learning (Formative)</label>
                <p className="lp-field-hint">
                  Ongoing checks during learning: observations, exit tickets, discussions
                </p>
                <textarea
                  className="lp-textarea"
                  rows={5}
                  value={form.assessment_for_learning || ''}
                  onChange={e => set('assessment_for_learning', e.target.value)}
                  placeholder="e.g. Exit ticket: solve one quadratic equation; observation checklist during group work…"
                />
              </div>
              <div className="lp-field">
                <label className="lp-field-label">Assessment OF Learning (Summative)</label>
                <p className="lp-field-hint">
                  Final evaluation: tests, assignments, projects, culminating tasks
                </p>
                <textarea
                  className="lp-textarea"
                  rows={5}
                  value={form.assessment_of_learning || ''}
                  onChange={e => set('assessment_of_learning', e.target.value)}
                  placeholder="e.g. Unit test on quadratic relations (MPM2D Unit 3); performance task…"
                />
              </div>
            </div>
          )}

          {/* ---- Differentiation ---- */}
          {tab === 'differentiation' && (
            <div className="lp-tab-content">
              <div className="lp-field">
                <label className="lp-field-label">Enrichment</label>
                <p className="lp-field-hint">Extensions for students who are ready to go deeper</p>
                <textarea
                  className="lp-textarea"
                  rows={4}
                  value={form.differentiation?.enrichment || ''}
                  onChange={e => setDiff('enrichment', e.target.value)}
                  placeholder="e.g. Investigate vertex form; extension problems from textbook p.52…"
                />
              </div>
              <div className="lp-field">
                <label className="lp-field-label">Support / Accommodation</label>
                <p className="lp-field-hint">Modifications for students who need additional scaffolding</p>
                <textarea
                  className="lp-textarea"
                  rows={4}
                  value={form.differentiation?.support || ''}
                  onChange={e => setDiff('support', e.target.value)}
                  placeholder="e.g. Graphic organiser, peer pairing, reduced question set, manipulatives…"
                />
              </div>
              <div className="lp-field">
                <label className="lp-field-label">English Language Learners (ELL)</label>
                <p className="lp-field-hint">Language and vocabulary supports</p>
                <textarea
                  className="lp-textarea"
                  rows={4}
                  value={form.differentiation?.ell || ''}
                  onChange={e => setDiff('ell', e.target.value)}
                  placeholder="e.g. Pre-teach key vocabulary (vertex, parabola); bilingual glossary; visual models…"
                />
              </div>
            </div>
          )}
        </div>

        {error && <p className="lp-error-msg lp-editor-error">{error}</p>}

        <div className="lp-modal-footer">
          <button type="button" className="lp-btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="lp-btn-primary"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? 'Saving…' : (initial ? 'Save Changes' : 'Create Plan')}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Plan Card
// ---------------------------------------------------------------------------

interface PlanCardProps {
  plan: LessonPlanItem;
  onEdit: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
  deleting: boolean;
}

function PlanCard({ plan, onEdit, onDuplicate, onDelete, deleting }: PlanCardProps) {
  const expectationCount = plan.curriculum_expectations?.length || 0;
  const hasAI = Boolean(plan.three_part_lesson);

  return (
    <div className="lp-plan-card">
      <div className="lp-plan-card-header">
        <span className={`lp-type-badge lp-type-${plan.plan_type}`}>
          {PLAN_TYPE_ABBR[plan.plan_type]}
        </span>
        {plan.is_template && (
          <span className="lp-template-badge">Template</span>
        )}
        {hasAI && (
          <span className="lp-ai-badge" title="Has AI-generated content">&#10024; AI</span>
        )}
      </div>

      <h3 className="lp-plan-card-title">{plan.title}</h3>

      <div className="lp-plan-card-meta">
        {plan.grade_level && (
          <span className="lp-meta-chip">Grade {plan.grade_level}</span>
        )}
        {plan.subject_code && (
          <span className="lp-meta-chip">{plan.subject_code}</span>
        )}
        {plan.strand && (
          <span className="lp-meta-chip lp-meta-strand" title={plan.strand}>
            {plan.strand.length > 28 ? plan.strand.slice(0, 26) + '…' : plan.strand}
          </span>
        )}
        {plan.duration_minutes && (
          <span className="lp-meta-chip">{plan.duration_minutes} min</span>
        )}
        {expectationCount > 0 && (
          <span className="lp-meta-chip">{expectationCount} expectations</span>
        )}
      </div>

      <div className="lp-plan-card-actions">
        <button type="button" className="lp-card-btn lp-card-btn-edit" onClick={onEdit}>
          Edit
        </button>
        <button type="button" className="lp-card-btn lp-card-btn-dup" onClick={onDuplicate}>
          Duplicate
        </button>
        <button
          type="button"
          className="lp-card-btn lp-card-btn-delete"
          onClick={onDelete}
          disabled={deleting}
        >
          {deleting ? '…' : 'Delete'}
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export function LessonPlannerPage() {
  const [plans, setPlans] = useState<LessonPlanItem[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Filters
  const [filterType, setFilterType] = useState<LessonPlanType | ''>('');
  const [filterCourse, setFilterCourse] = useState<number | ''>('');
  const [filterGrade, setFilterGrade] = useState('');

  // Modals
  const [showEditor, setShowEditor] = useState(false);
  const [editingPlan, setEditingPlan] = useState<LessonPlanItem | null>(null);
  const [showImport, setShowImport] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const loadPlans = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params: Record<string, string | number> = {};
      if (filterType) params.plan_type = filterType;
      if (filterCourse) params.course_id = filterCourse;
      if (filterGrade) params.grade_level = filterGrade;
      const data = await lessonPlanApi.list(params as Parameters<typeof lessonPlanApi.list>[0]);
      setPlans(data);
    } catch {
      setError('Failed to load lesson plans. Please refresh.');
    } finally {
      setLoading(false);
    }
  }, [filterType, filterCourse, filterGrade]);

  useEffect(() => {
    Promise.all([
      loadPlans(),
      coursesApi.teachingList()
        .then((data: Course[]) => setCourses(data))
        .catch(() => setCourses([])),
    ]);
  }, [loadPlans]);

  const handleNewPlan = () => {
    setEditingPlan(null);
    setShowEditor(true);
  };

  const handleEdit = (plan: LessonPlanItem) => {
    setEditingPlan(plan);
    setShowEditor(true);
  };

  const handleEditorSaved = (plan: LessonPlanItem) => {
    setPlans(prev => {
      const idx = prev.findIndex(p => p.id === plan.id);
      if (idx >= 0) {
        const updated = [...prev];
        updated[idx] = plan;
        return updated;
      }
      return [plan, ...prev];
    });
    setShowEditor(false);
  };

  const handleDuplicate = async (plan: LessonPlanItem) => {
    try {
      const copy = await lessonPlanApi.duplicate(plan.id);
      setPlans(prev => [copy, ...prev]);
    } catch {
      setError('Failed to duplicate plan.');
    }
  };

  const handleDelete = async (plan: LessonPlanItem) => {
    if (!window.confirm(`Delete "${plan.title}"? This cannot be undone.`)) return;
    setDeletingId(plan.id);
    try {
      await lessonPlanApi.delete(plan.id);
      setPlans(prev => prev.filter(p => p.id !== plan.id));
    } catch {
      setError('Failed to delete plan.');
    } finally {
      setDeletingId(null);
    }
  };

  const handleImported = (imported: LessonPlanItem[]) => {
    setPlans(prev => [...imported, ...prev]);
  };

  return (
    <DashboardLayout>
      <div className="lp-page">
        {/* Page Header */}
        <div className="lp-header">
          <div>
            <h1 className="lp-title">Lesson Planner</h1>
            <p className="lp-subtitle">
              TeachAssist-compatible Ontario lesson planning — LRPs, unit plans, and daily lessons.
            </p>
          </div>
          <div className="lp-header-actions">
            <button type="button" className="lp-btn-secondary" onClick={() => setShowImport(true)}>
              Import
            </button>
            <button type="button" className="lp-btn-primary" onClick={handleNewPlan}>
              + New Plan
            </button>
          </div>
        </div>

        {/* Filters */}
        <div className="lp-filters">
          <select
            className="lp-select lp-filter-select"
            value={filterType}
            onChange={e => setFilterType(e.target.value as LessonPlanType | '')}
          >
            <option value="">All Types</option>
            <option value="long_range">Long-Range Plans</option>
            <option value="unit">Unit Plans</option>
            <option value="daily">Daily Lessons</option>
          </select>

          <select
            className="lp-select lp-filter-select"
            value={filterCourse}
            onChange={e => setFilterCourse(e.target.value ? Number(e.target.value) : '')}
          >
            <option value="">All Courses</option>
            {courses.map(c => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>

          <select
            className="lp-select lp-filter-select"
            value={filterGrade}
            onChange={e => setFilterGrade(e.target.value)}
          >
            <option value="">All Grades</option>
            {GRADE_OPTIONS.map(g => (
              <option key={g} value={g}>Grade {g}</option>
            ))}
          </select>
        </div>

        {/* Error */}
        {error && <p className="lp-error-msg">{error}</p>}

        {/* Content */}
        {loading ? (
          <div className="lp-loading">Loading lesson plans…</div>
        ) : plans.length === 0 ? (
          <div className="lp-empty">
            <div className="lp-empty-icon">&#128221;</div>
            <h3>No lesson plans yet</h3>
            <p>
              Create your first lesson plan or import an existing plan from TeachAssist.
            </p>
            <div className="lp-empty-actions">
              <button type="button" className="lp-btn-secondary" onClick={() => setShowImport(true)}>
                Import from TeachAssist
              </button>
              <button type="button" className="lp-btn-primary" onClick={handleNewPlan}>
                + New Plan
              </button>
            </div>
          </div>
        ) : (
          <div className="lp-plans-grid">
            {plans.map(plan => (
              <PlanCard
                key={plan.id}
                plan={plan}
                onEdit={() => handleEdit(plan)}
                onDuplicate={() => handleDuplicate(plan)}
                onDelete={() => handleDelete(plan)}
                deleting={deletingId === plan.id}
              />
            ))}
          </div>
        )}
      </div>

      {/* Plan Editor Modal */}
      {showEditor && (
        <PlanEditor
          initial={editingPlan}
          courses={courses}
          onClose={() => setShowEditor(false)}
          onSaved={handleEditorSaved}
        />
      )}

      {/* Import Modal */}
      {showImport && (
        <ImportModal
          onClose={() => setShowImport(false)}
          onImported={handleImported}
        />
      )}
    </DashboardLayout>
  );
}
