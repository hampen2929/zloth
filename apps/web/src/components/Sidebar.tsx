'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import useSWR from 'swr';
import { tasksApi } from '@/lib/api';

interface SidebarProps {
  onSettingsClick: () => void;
}

export default function Sidebar({ onSettingsClick }: SidebarProps) {
  const pathname = usePathname();
  const { data: tasks } = useSWR('tasks', () => tasksApi.list(), {
    refreshInterval: 5000,
  });
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);

  const currentTaskId = pathname?.match(/\/tasks\/(.+)/)?.[1];

  return (
    <aside className="w-64 h-screen flex flex-col bg-gray-900 border-r border-gray-800">
      {/* Logo */}
      <div className="p-4 border-b border-gray-800">
        <Link href="/" className="text-xl font-bold text-white hover:text-gray-300 transition-colors">
          dursor
        </Link>
      </div>

      {/* New Task Button */}
      <div className="p-3">
        <Link
          href="/"
          className="flex items-center justify-center gap-2 w-full py-2 px-3 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          New Task
        </Link>
      </div>

      {/* Task History */}
      <div className="flex-1 overflow-y-auto">
        <div className="px-3 py-2">
          <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
            Recent Tasks
          </h2>
          {!tasks || tasks.length === 0 ? (
            <p className="text-gray-500 text-sm px-2">No tasks yet</p>
          ) : (
            <div className="space-y-1">
              {tasks.slice(0, 20).map((task) => (
                <Link
                  key={task.id}
                  href={`/tasks/${task.id}`}
                  className={`block px-2 py-2 rounded-lg text-sm transition-colors ${
                    currentTaskId === task.id
                      ? 'bg-gray-800 text-white'
                      : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                  }`}
                >
                  <div className="truncate font-medium">
                    {task.title || 'Untitled Task'}
                  </div>
                  <div className="text-xs text-gray-500 mt-0.5">
                    {formatRelativeTime(task.updated_at)}
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Account Section */}
      <div className="relative border-t border-gray-800 p-3">
        <button
          onClick={() => setAccountMenuOpen(!accountMenuOpen)}
          className="flex items-center gap-3 w-full px-2 py-2 rounded-lg hover:bg-gray-800 transition-colors text-left"
        >
          <div className="w-8 h-8 bg-gray-700 rounded-full flex items-center justify-center">
            <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium text-white">Account</div>
            <div className="text-xs text-gray-500">Settings & Preferences</div>
          </div>
          <svg
            className={`w-4 h-4 text-gray-500 transition-transform ${accountMenuOpen ? 'rotate-180' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
          </svg>
        </button>

        {/* Account Menu Popup */}
        {accountMenuOpen && (
          <div className="absolute bottom-full left-3 right-3 mb-2 bg-gray-800 border border-gray-700 rounded-lg shadow-lg overflow-hidden">
            <button
              onClick={() => {
                onSettingsClick();
                setAccountMenuOpen(false);
              }}
              className="flex items-center gap-3 w-full px-4 py-3 text-sm text-gray-300 hover:bg-gray-700 transition-colors"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              Settings
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;

  return date.toLocaleDateString();
}
