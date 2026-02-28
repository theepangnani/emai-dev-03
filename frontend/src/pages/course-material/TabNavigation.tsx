import './TabNavigation.css';

export type TabKey = 'document' | 'guide' | 'quiz' | 'flashcards';

export interface TabDefinition {
  key: TabKey;
  label: string;
  hasContent: boolean;
}

interface TabNavigationProps {
  tabs: TabDefinition[];
  activeTab: TabKey;
  onTabChange: (tab: TabKey) => void;
}

export function TabNavigation({ tabs, activeTab, onTabChange }: TabNavigationProps) {
  return (
    <div className="cm-tabs" role="tablist">
      {tabs.map(tab => (
        <button
          key={tab.key}
          className={`cm-tab${activeTab === tab.key ? ' active' : ''}${!tab.hasContent ? ' empty' : ''}`}
          onClick={() => onTabChange(tab.key)}
          role="tab"
          aria-selected={activeTab === tab.key}
        >
          {tab.label}
          {!tab.hasContent && tab.key !== 'document' && (
            <span className="cm-tab-empty-dot" />
          )}
        </button>
      ))}
    </div>
  );
}
