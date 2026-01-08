'use client';

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import useSWR from 'swr';
import { tasksApi } from '@/lib/api';
import { cn } from '@/lib/utils';
import { formatRelativeTime } from '@/lib/utils';
import { TaskListSkeleton } from './ui/Skeleton';
import {
  PlusIcon,
  UserCircleIcon,
  Cog6ToothIcon,
  ChevronUpIcon,
  ChatBubbleLeftRightIcon,
} from '@heroicons/react/24/outline';

interface SidebarProps {
  onSettingsClick: () => void;
}

export default function Sidebar({ onSettingsClick }: SidebarProps) {
  const pathname = usePathname();
  const { data: tasks, isLoading } = useSWR('tasks', () => tasksApi.list(), {
    refreshInterval: 5000,
  });
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const currentTaskId = pathname?.match(/\/tasks\/(.+)/)?.[1];

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setAccountMenuOpen(false);
      }
    };

    if (accountMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [accountMenuOpen]);

  return (
    <aside className="w-64 h-screen flex flex-col bg-gray-900 border-r border-gray-800">
      {/* Logo - hidden on mobile since we have mobile header */}
      <div className="hidden lg:block p-4 border-b border-gray-800">
        <Link
          href="/"
          className="text-xl font-bold text-white hover:text-gray-300 transition-colors inline-flex items-center gap-2"
        >
          <span className="text-blue-500">d</span>ursor
        </Link>
      </div>
      {/* Mobile spacing to account for mobile header */}
      <div className="lg:hidden h-14" />

      {/* New Task Button */}
      <div className="p-3">
        <Link
          href="/"
          className={cn(
            'flex items-center justify-center gap-2 w-full py-2.5 px-3',
            'bg-blue-600 hover:bg-blue-700 rounded-lg',
            'text-sm font-medium transition-colors',
            'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-gray-900'
          )}
        >
          <PlusIcon className="w-4 h-4" />
          New Task
        </Link>
      </div>

      {/* Task History */}
      <div className="flex-1 overflow-y-auto">
        <div className="px-3 py-2">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
              Recent Tasks
            </h2>
            {tasks && tasks.length > 0 && (
              <span className="text-xs text-gray-600 bg-gray-800 px-1.5 py-0.5 rounded">
                {tasks.length}
              </span>
            )}
          </div>

          {isLoading ? (
            <TaskListSkeleton count={5} />
          ) : !tasks || tasks.length === 0 ? (
            <div className="flex flex-col items-center py-6 text-center">
              <ChatBubbleLeftRightIcon className="w-8 h-8 text-gray-700 mb-2" />
              <p className="text-gray-500 text-sm">No tasks yet</p>
              <p className="text-gray-600 text-xs mt-1">Create your first task above</p>
            </div>
          ) : (
            <div className="space-y-1">
              {tasks.slice(0, 20).map((task) => (
                <Link
                  key={task.id}
                  href={`/tasks/${task.id}`}
                  className={cn(
                    'block px-2 py-2 rounded-lg text-sm transition-all duration-150',
                    'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-inset',
                    currentTaskId === task.id
                      ? 'bg-blue-900/40 text-white border border-blue-800'
                      : 'text-gray-400 hover:bg-gray-800 hover:text-white border border-transparent'
                  )}
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
      <div ref={menuRef} className="relative border-t border-gray-800 p-3">
        <button
          onClick={() => setAccountMenuOpen(!accountMenuOpen)}
          className={cn(
            'flex items-center gap-3 w-full px-2 py-2 rounded-lg transition-colors text-left',
            'hover:bg-gray-800',
            'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-inset',
            accountMenuOpen && 'bg-gray-800'
          )}
          aria-expanded={accountMenuOpen}
          aria-haspopup="true"
        >
          <div className="w-8 h-8 bg-gray-700 rounded-full flex items-center justify-center">
            <UserCircleIcon className="w-5 h-5 text-gray-400" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium text-white">Account</div>
            <div className="text-xs text-gray-500">Settings & Preferences</div>
          </div>
          <ChevronUpIcon
            className={cn(
              'w-4 h-4 text-gray-500 transition-transform duration-200',
              accountMenuOpen ? 'rotate-0' : 'rotate-180'
            )}
          />
        </button>

        {/* Account Menu Popup */}
        {accountMenuOpen && (
          <div
            className="absolute bottom-full left-3 right-3 mb-2 bg-gray-800 border border-gray-700 rounded-lg shadow-xl overflow-hidden animate-in fade-in slide-in-from-bottom-2 duration-200"
            role="menu"
          >
            <button
              onClick={() => {
                onSettingsClick();
                setAccountMenuOpen(false);
              }}
              className={cn(
                'flex items-center gap-3 w-full px-4 py-3 text-sm text-gray-300',
                'hover:bg-gray-700 transition-colors',
                'focus:outline-none focus:bg-gray-700'
              )}
              role="menuitem"
            >
              <Cog6ToothIcon className="w-4 h-4" />
              Settings
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}
