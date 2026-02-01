'use client';

import { Suspense, useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'next/navigation';
import {
  ModelsTab,
  GitHubAppTab,
  DefaultsTab,
  ExecutorsTab,
  settingsTabConfig,
  SettingsTabType,
} from '@/components/SettingsModal';
import { cn } from '@/lib/utils';

function SettingsContent() {
  const searchParams = useSearchParams();
  const tabParam = searchParams.get('tab') as SettingsTabType | null;
  const validTabs = useMemo(() => ['executors', 'models', 'github', 'defaults'], []);
  const [activeTab, setActiveTab] = useState<SettingsTabType>(
    tabParam && validTabs.includes(tabParam) ? tabParam : 'models'
  );

  // Update active tab when URL param changes
  // This is intentional: we want to switch tabs when URL param changes
  useEffect(() => {
    if (tabParam && validTabs.includes(tabParam)) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setActiveTab(tabParam);
    }
  }, [tabParam, validTabs]);

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold text-white mb-6">Settings</h1>

      {/* Tabs */}
      <div className="flex border-b border-gray-800 mb-6" role="tablist">
        {settingsTabConfig.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            role="tab"
            aria-selected={activeTab === tab.id}
            className={cn(
              'flex items-center gap-2 px-6 py-3 text-sm font-medium transition-colors',
              'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-inset',
              activeTab === tab.id
                ? 'text-blue-400 border-b-2 border-blue-500 -mb-[1px]'
                : 'text-gray-400 hover:text-gray-300'
            )}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="pb-8">
        {activeTab === 'models' && <ModelsTab />}
        {activeTab === 'github' && <GitHubAppTab />}
        {activeTab === 'defaults' && <DefaultsTab />}
        {activeTab === 'executors' && <ExecutorsTab />}
      </div>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <Suspense fallback={<div className="max-w-4xl mx-auto"><p className="text-gray-400">Loading settings...</p></div>}>
      <SettingsContent />
    </Suspense>
  );
}
