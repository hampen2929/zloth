'use client';

import { useState, useEffect } from 'react';
import { usePathname } from 'next/navigation';
import Sidebar from './Sidebar';
import SettingsModal from './SettingsModal';
import BreakdownModal from './BreakdownModal';
import { KeyboardShortcutsHelp } from './KeyboardShortcutsHelp';
import { ToastProvider } from './ui/Toast';
import { Bars3Icon, XMarkIcon } from '@heroicons/react/24/outline';
import { cn } from '@/lib/utils';
import { useKeyboardShortcuts } from '@/hooks';

interface ClientLayoutProps {
  children: React.ReactNode;
}

export default function ClientLayout({ children }: ClientLayoutProps) {
  const pathname = usePathname();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [shortcutsHelpOpen, setShortcutsHelpOpen] = useState(false);
  const [breakdownOpen, setBreakdownOpen] = useState(false);
  const [settingsDefaultTab, setSettingsDefaultTab] = useState<'models' | 'github' | 'defaults' | undefined>(undefined);

  // Register keyboard shortcuts
  useKeyboardShortcuts({
    onOpenSettings: () => setSettingsOpen(true),
    onShowHelp: () => setShortcutsHelpOpen(true),
  });

  // Close sidebar when navigating on mobile
  // This is intentional: we want to close the sidebar when route changes
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSidebarOpen(false);
  }, [pathname]);

  // Close sidebar on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && sidebarOpen) {
        setSidebarOpen(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [sidebarOpen]);

  // Prevent body scroll when sidebar is open on mobile
  useEffect(() => {
    if (sidebarOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [sidebarOpen]);

  // Handle hash-based settings navigation
  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash;
      if (hash === '#settings-models') {
        setSettingsDefaultTab('models');
        setSettingsOpen(true);
        window.history.replaceState(null, '', window.location.pathname);
      } else if (hash === '#settings-github') {
        setSettingsDefaultTab('github');
        setSettingsOpen(true);
        window.history.replaceState(null, '', window.location.pathname);
      } else if (hash === '#settings-defaults') {
        setSettingsDefaultTab('defaults');
        setSettingsOpen(true);
        window.history.replaceState(null, '', window.location.pathname);
      }
    };

    // Check on mount
    handleHashChange();

    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const handleSettingsClose = () => {
    setSettingsOpen(false);
    setSettingsDefaultTab(undefined);
  };

  return (
    <ToastProvider>
      <div className="flex h-screen bg-gray-950">
        {/* Mobile header bar */}
        <div className="lg:hidden fixed top-0 left-0 right-0 z-50 h-14 bg-gray-900 border-b border-gray-800 flex items-center px-4">
          <button
            className="p-2 -ml-2 rounded-lg hover:bg-gray-800 transition-colors"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            aria-label={sidebarOpen ? 'メニューを閉じる' : 'メニューを開く'}
            aria-expanded={sidebarOpen}
          >
            {sidebarOpen ? (
              <XMarkIcon className="w-6 h-6 text-gray-300" />
            ) : (
              <Bars3Icon className="w-6 h-6 text-gray-300" />
            )}
          </button>
          <span className="ml-3 text-lg font-bold text-white">
            <span className="text-blue-500">d</span>ursor
          </span>
        </div>

        {/* Mobile sidebar overlay */}
        <div
          className={cn(
            'lg:hidden fixed inset-0 bg-black/60 z-30 transition-opacity duration-300',
            sidebarOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
          )}
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />

        {/* Sidebar - hidden on mobile, shown on desktop */}
        <div
          className={cn(
            'fixed lg:relative z-40 h-full',
            'transform transition-transform duration-300 ease-out',
            sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
          )}
        >
          <Sidebar
            onSettingsClick={() => {
              setSettingsOpen(true);
              setSidebarOpen(false);
            }}
            onBreakdownClick={() => {
              setBreakdownOpen(true);
              setSidebarOpen(false);
            }}
          />
        </div>

        {/* Main content */}
        <main className="flex-1 overflow-y-auto">
          <div className="p-4 lg:p-6 pt-16 lg:pt-6">{children}</div>
        </main>

        <SettingsModal
          isOpen={settingsOpen}
          onClose={handleSettingsClose}
          defaultTab={settingsDefaultTab}
        />

        <KeyboardShortcutsHelp
          isOpen={shortcutsHelpOpen}
          onClose={() => setShortcutsHelpOpen(false)}
        />

        <BreakdownModal
          isOpen={breakdownOpen}
          onClose={() => setBreakdownOpen(false)}
        />
      </div>
    </ToastProvider>
  );
}
