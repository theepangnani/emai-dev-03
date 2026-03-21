import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { studyApi } from '../api/client';
import type { StudyGuideTreeResponse } from '../api/client';
import './Breadcrumb.css';

interface StudyGuideBreadcrumbProps {
  guideId: number;
}

/**
 * Breadcrumb navigation for multi-level sub-guide hierarchies.
 * Fetches the tree from GET /api/study/guides/{id}/tree and uses
 * current_path to render clickable breadcrumb segments.
 *
 * Only renders when the guide has a parent (is a sub-guide).
 */
export function StudyGuideBreadcrumb({ guideId }: StudyGuideBreadcrumbProps) {
  const [tree, setTree] = useState<StudyGuideTreeResponse | null>(null);

  useEffect(() => {
    studyApi.getGuideTree(guideId)
      .then(setTree)
      .catch(() => setTree(null));
  }, [guideId]);

  // Don't render if no tree data or only one node in path (root-level guide)
  if (!tree || tree.current_path.length <= 1) return null;

  // Build lookup from tree for titles
  const titleMap = new Map<number, string>();
  const typeMap = new Map<number, string>();

  function walkTree(node: StudyGuideTreeResponse['root']) {
    titleMap.set(node.id, node.title);
    typeMap.set(node.id, node.guide_type);
    for (const child of node.children) {
      walkTree(child);
    }
  }
  walkTree(tree.root);

  const pathIds = tree.current_path;
  const items = pathIds.map((id, i) => ({
    id,
    label: titleMap.get(id) || `Guide ${id}`,
    isLast: i === pathIds.length - 1,
  }));

  // Find the back item for mobile
  const backItem = items.length >= 2 ? items[items.length - 2] : null;

  return (
    <nav className="breadcrumb" aria-label="Study guide hierarchy" data-testid="study-guide-breadcrumb">
      {/* Desktop: full trail */}
      <div className="breadcrumb-full">
        {items.map((item, i) => (
          <span key={item.id}>
            {i > 0 && <span className="breadcrumb-separator">&rsaquo;</span>}
            {item.isLast ? (
              <span className="breadcrumb-current">{item.label}</span>
            ) : (
              <Link to={`/study/guide/${item.id}`} className="breadcrumb-link">
                {item.label}
              </Link>
            )}
          </span>
        ))}
      </div>

      {/* Mobile: back link only */}
      {backItem && (
        <Link to={`/study/guide/${backItem.id}`} className="breadcrumb-back">
          &lsaquo; Back to {backItem.label}
        </Link>
      )}
    </nav>
  );
}
