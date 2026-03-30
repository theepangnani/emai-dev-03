import { useState } from 'react';
import type { StudyGuide } from '../../api/client';
import type { MindMapData, MindMapBranchGroup } from '../../api/study';
import type { TaskItem } from '../../api/tasks';
import { GenerationSpinner } from '../../components/GenerationSpinner';
import { LinkedTasksBanner } from './LinkedTasksBanner';
import { ContentMetaBar } from './ContentMetaBar';
import './MindMapTab.css';

interface MindMapTabProps {
  mindMap: StudyGuide | undefined;
  generating: string | null;
  focusPrompt: string;
  onFocusPromptChange: (value: string) => void;
  onGenerate: () => void;
  onDelete: (guide: StudyGuide) => void;
  hasSourceContent: boolean;
  linkedTasks?: TaskItem[];
  atLimit?: boolean;
  courseName?: string | null;
  createdAt?: string | null;
  courseId?: number;
}

function FocusIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.3"/>
      <circle cx="8" cy="8" r="2.5" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M8 1v2M8 13v2M1 8h2M13 8h2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
    </svg>
  );
}

function EmptyMindMapIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="1.5"/>
      <circle cx="4" cy="6" r="2" stroke="currentColor" strokeWidth="1.3"/>
      <circle cx="20" cy="6" r="2" stroke="currentColor" strokeWidth="1.3"/>
      <circle cx="4" cy="18" r="2" stroke="currentColor" strokeWidth="1.3"/>
      <circle cx="20" cy="18" r="2" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M9.2 9.2L5.5 7M14.8 9.2L18.5 7M9.2 14.8L5.5 17M14.8 14.8L18.5 17" stroke="currentColor" strokeWidth="1.2"/>
    </svg>
  );
}

const BRANCH_COLORS = [
  'var(--mm-color-1, #2a9fa8)',
  'var(--mm-color-2, #e67e22)',
  'var(--mm-color-3, #9b59b6)',
  'var(--mm-color-4, #27ae60)',
  'var(--mm-color-5, #e74c3c)',
  'var(--mm-color-6, #3498db)',
];

interface BranchNodeProps {
  branch: MindMapBranchGroup;
  index: number;
  total: number;
  side: 'left' | 'right';
}

function BranchNode({ branch, index, side }: BranchNodeProps) {
  const [expanded, setExpanded] = useState(true);
  const color = BRANCH_COLORS[index % BRANCH_COLORS.length];

  return (
    <div
      className={`mm-branch mm-branch-${side}`}
      style={{ '--branch-color': color } as React.CSSProperties}
    >
      <div className="mm-branch-connector" style={{ background: color }} />
      <button
        className={`mm-branch-label${expanded ? ' expanded' : ''}`}
        onClick={() => setExpanded(!expanded)}
        style={{ borderColor: color, color }}
        aria-expanded={expanded}
      >
        {branch.label}
        {branch.children.length > 0 && (
          <span className="mm-expand-icon">{expanded ? '\u25BC' : '\u25B6'}</span>
        )}
      </button>

      {expanded && branch.children.length > 0 && (
        <ul className="mm-children">
          {branch.children.map((child, ci) => (
            <li key={ci} className="mm-child" style={{ borderLeftColor: color }}>
              <span className="mm-child-label">{child.label}</span>
              {child.detail && (
                <span className="mm-child-detail">{child.detail}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function MindMapTab({
  mindMap,
  generating,
  focusPrompt,
  onFocusPromptChange,
  onGenerate,
  onDelete,
  hasSourceContent,
  linkedTasks = [],
  atLimit = false,
  courseName,
  createdAt,
  courseId,
}: MindMapTabProps) {
  const parsedMindMap: MindMapData | null = mindMap ? (() => {
    try { return JSON.parse(mindMap.content) as MindMapData; } catch { return null; }
  })() : null;

  // Split branches into left and right halves
  const leftBranches: { branch: MindMapBranchGroup; index: number }[] = [];
  const rightBranches: { branch: MindMapBranchGroup; index: number }[] = [];
  if (parsedMindMap) {
    parsedMindMap.branches.forEach((branch, i) => {
      if (i % 2 === 0) {
        rightBranches.push({ branch, index: i });
      } else {
        leftBranches.push({ branch, index: i });
      }
    });
  }

  return (
    <div className="cm-mindmap-tab">
      <div className="cm-focus-prompt">
        <div className="cm-focus-prompt-inner">
          <span className="cm-focus-prompt-icon"><FocusIcon /></span>
          <input
            type="text"
            value={focusPrompt}
            onChange={(e) => onFocusPromptChange(e.target.value)}
            placeholder="Focus on a specific topic (e.g., photosynthesis, the Calvin cycle)"
            disabled={generating !== null}
          />
        </div>
      </div>
      {mindMap && parsedMindMap ? (
        <div className="cm-tab-card">
          <div className="cm-guide-actions">
            <span className={atLimit ? 'ai-btn-disabled-wrapper' : ''}>
              <button className="cm-action-btn" onClick={onGenerate} disabled={generating !== null || atLimit}>
                {generating === 'mind_map' ? <><GenerationSpinner size="sm" /> Regenerating...</> : <>{'\u2728'} Regenerate</>}
              </button>
              {atLimit && <span className="ai-limit-tooltip">AI limit reached</span>}
            </span>
            <button className="cm-action-btn danger" onClick={() => onDelete(mindMap)}>{'\u{1F5D1}\uFE0F'} Delete</button>
          </div>
          <ContentMetaBar courseName={courseName} createdAt={createdAt || mindMap.created_at} linkedTasks={linkedTasks} courseId={courseId} />
          <LinkedTasksBanner tasks={linkedTasks} />
          {generating === 'mind_map' && (
            <div className="cm-regen-status">
              <GenerationSpinner size="md" />
              <span>Regenerating mind map...</span>
            </div>
          )}
          <div className="mm-container">
            <div className="mm-canvas">
              <div className="mm-side mm-side-left">
                {leftBranches.map(({ branch, index }) => (
                  <BranchNode
                    key={index}
                    branch={branch}
                    index={index}
                    total={parsedMindMap.branches.length}
                    side="left"
                  />
                ))}
              </div>
              <div className="mm-center-node">
                {parsedMindMap.central_topic}
              </div>
              <div className="mm-side mm-side-right">
                {rightBranches.map(({ branch, index }) => (
                  <BranchNode
                    key={index}
                    branch={branch}
                    index={index}
                    total={parsedMindMap.branches.length}
                    side="right"
                  />
                ))}
              </div>
            </div>
          </div>
        </div>
      ) : generating === 'mind_map' ? (
        <div className="cm-inline-generating">
          <GenerationSpinner size="lg" />
          <p>Generating mind map... This may take a moment.</p>
        </div>
      ) : (
        <div className="cm-empty-tab">
          <div className="cm-empty-tab-icon"><EmptyMindMapIcon /></div>
          <h3>Visualize the key concepts</h3>
          <p>Generate a mind map to see how the key concepts and relationships in this material connect.</p>
          <span className={atLimit ? 'ai-btn-disabled-wrapper' : ''}>
            <button
              className="cm-empty-generate-btn"
              onClick={onGenerate}
              disabled={generating !== null || !hasSourceContent || atLimit}
            >
              {'\u2728'} Generate Mind Map
            </button>
            {atLimit && <span className="ai-limit-tooltip">AI limit reached</span>}
          </span>
          {!hasSourceContent && (
            <p className="cm-hint">Add content or upload a document first to generate a mind map.</p>
          )}
        </div>
      )}
    </div>
  );
}
