'use client';

import { useState } from 'react';
import Sidebar from './Sidebar';
import SettingsModal from './SettingsModal';
import { ToastProvider } from './ui/Toast';
import { Bars3Icon, XMarkIcon } from '@heroicons/react/24/outline';

interface ClientLayoutProps {
  children: React.ReactNode;
}

export default function ClientLayout({ children }: ClientLayoutProps) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <ToastProvider>
      <div className="flex h-screen">
        {/* Mobile menu button */}
        <button
          className="lg:hidden fixed top-4 left-4 z-50 p-2 bg-gray-800 rounded-lg"
          onClick={() => setSidebarOpen(!sidebarOpen)}
          aria-label={sidebarOpen ? 'Close menu' : 'Open menu'}
        >
          {sidebarOpen ? (
            <XMarkIcon className="w-6 h-6 text-gray-300" />
          ) : (
            <Bars3Icon className="w-6 h-6 text-gray-300" />
          )}
        </button>

        {/* Mobile sidebar overlay */}
        {sidebarOpen && (
          <div
            className="lg:hidden fixed inset-0 bg-black/50 z-30"
            onClick={() => setSidebarOpen(false)}
            aria-hidden="true"
          />
        )}

        {/* Sidebar - hidden on mobile, shown on desktop */}
        <div
          className={`
            fixed lg:relative z-40 h-full
            transform transition-transform duration-200 ease-in-out
            ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
          `}
        >
          <Sidebar
            onSettingsClick={() => {
              setSettingsOpen(true);
              setSidebarOpen(false);
            }}
          />
        </div>

        {/* Main content */}
        <main className="flex-1 overflow-y-auto">
          <div className="p-4 lg:p-6 pt-16 lg:pt-6">{children}</div>
        </main>

        <SettingsModal isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} />
      </div>
    </ToastProvider>
  );
}
