'use client';

import { useState, useEffect, useRef, useMemo } from 'react';
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
  ChatBubbleLeftRightIcon,
  MagnifyingGlassIcon,
  XMarkIcon,
  ArrowsUpDownIcon,
  ClipboardDocumentListIcon,
  ViewColumnsIcon,
  FolderIcon,
  CogIcon,
  EyeIcon,
  ClockIcon,
  ChartBarIcon,
} from '@heroicons/react/24/outline';

type SortOption = 'newest' | 'oldest' | 'alphabetical';

export default function Sidebar() {
  const pathname = usePathname();
  const { data: tasks, isLoading } = useSWR('tasks', () => tasksApi.list(), {
    refreshInterval: 5000,
  });
  const [searchQuery, setSearchQuery] = useState('');
  const [sortOption, setSortOption] = useState<SortOption>('newest');
  const [showSortMenu, setShowSortMenu] = useState(false);
  const sortMenuRef = useRef<HTMLDivElement>(null);

  const currentTaskId = pathname?.match(/\/tasks\/(.+)/)?.[1];

  // Filter and sort tasks - only show in_progress, gating, and in_review tasks
  const filteredTasks = useMemo(() => {
    if (!tasks) return [];

    let result = [...tasks];

    // Filter by kanban status - only show in_progress, gating, and in_review tasks
    result = result.filter(
      (task) => task.kanban_status === 'in_progress' || task.kanban_status === 'gating' || task.kanban_status === 'in_review'
    );

    // Filter by search query
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      result = result.filter((task) =>
        (task.title || 'Untitled Task').toLowerCase().includes(query)
      );
    }

    // Sort
    switch (sortOption) {
      case 'newest':
        result.sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());
        break;
      case 'oldest':
        result.sort((a, b) => new Date(a.updated_at).getTime() - new Date(b.updated_at).getTime());
        break;
      case 'alphabetical':
        result.sort((a, b) =>
          (a.title || 'Untitled Task').localeCompare(b.title || 'Untitled Task')
        );
        break;
    }

    return result;
  }, [tasks, searchQuery, sortOption]);

  // Close sort menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (sortMenuRef.current && !sortMenuRef.current.contains(event.target as Node)) {
        setShowSortMenu(false);
      }
    };

    if (showSortMenu) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showSortMenu]);

  return (
    <aside className="w-64 h-screen flex flex-col bg-gray-900 border-r border-gray-800">
      {/* Logo - hidden on mobile since we have mobile header */}
      <div className="hidden lg:block p-4 border-b border-gray-800">
        <Link
          href="/"
          className="text-xl font-bold text-white hover:text-gray-300 transition-colors inline-flex items-center gap-2"
        >
          <span className="text-blue-500">t</span>azuna
        </Link>
      </div>
      {/* Mobile spacing to account for mobile header */}
      <div className="lg:hidden h-14" />

      {/* New Task & Navigation Buttons */}
      <div className="p-3 space-y-2">
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
        <Link
          href="/backlog"
          className={cn(
            'flex items-center justify-center gap-2 w-full py-2.5 px-3',
            'bg-purple-600 hover:bg-purple-700 rounded-lg',
            'text-sm font-medium transition-colors',
            'focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 focus:ring-offset-gray-900',
            pathname === '/backlog' && 'ring-2 ring-purple-400'
          )}
        >
          <ClipboardDocumentListIcon className="w-4 h-4" />
          Backlog & Archived
        </Link>
        <Link
          href="/kanban"
          className={cn(
            'flex items-center justify-center gap-2 w-full py-2.5 px-3',
            'bg-gray-800 hover:bg-gray-700 rounded-lg',
            'text-sm font-medium transition-colors',
            'focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 focus:ring-offset-gray-900',
            pathname === '/kanban' && 'bg-gray-700 ring-2 ring-gray-500'
          )}
        >
          <ViewColumnsIcon className="w-4 h-4" />
          Kanban Board
        </Link>
        <Link
          href="/repos"
          className={cn(
            'flex items-center justify-center gap-2 w-full py-2.5 px-3',
            'bg-gray-800 hover:bg-gray-700 rounded-lg',
            'text-sm font-medium transition-colors',
            'focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 focus:ring-offset-gray-900',
            pathname === '/repos' && 'bg-gray-700 ring-2 ring-gray-500'
          )}
        >
          <FolderIcon className="w-4 h-4" />
          Repositories
        </Link>
        <Link
          href="/metrics"
          className={cn(
            'flex items-center justify-center gap-2 w-full py-2.5 px-3',
            'bg-gray-800 hover:bg-gray-700 rounded-lg',
            'text-sm font-medium transition-colors',
            'focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 focus:ring-offset-gray-900',
            pathname === '/metrics' && 'bg-gray-700 ring-2 ring-gray-500'
          )}
        >
          <ChartBarIcon className="w-4 h-4" />
          Metrics
        </Link>
      </div>

      {/* Search and Filter */}
      <div className="px-3 py-2 border-b border-gray-800">
        <div className="relative">
          <MagnifyingGlassIcon className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search tasks..."
            className={cn(
              'w-full pl-8 pr-8 py-1.5 bg-gray-800 border border-gray-700 rounded-lg',
              'text-sm text-gray-100 placeholder:text-gray-500',
              'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
              'transition-colors'
            )}
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
            >
              <XMarkIcon className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Sort Options */}
        <div className="flex items-center justify-between mt-2" ref={sortMenuRef}>
          <span className="text-xs text-gray-500">
            {filteredTasks.length} task{filteredTasks.length !== 1 ? 's' : ''}
          </span>
          <div className="relative">
            <button
              onClick={() => setShowSortMenu(!showSortMenu)}
              className={cn(
                'flex items-center gap-1 text-xs text-gray-500 hover:text-gray-300 transition-colors',
                showSortMenu && 'text-gray-300'
              )}
            >
              <ArrowsUpDownIcon className="w-3.5 h-3.5" />
              <span>
                {sortOption === 'newest' && 'Newest'}
                {sortOption === 'oldest' && 'Oldest'}
                {sortOption === 'alphabetical' && 'A-Z'}
              </span>
            </button>
            {showSortMenu && (
              <div className="absolute right-0 top-full mt-1 bg-gray-800 border border-gray-700 rounded-lg shadow-xl overflow-hidden z-10 min-w-[120px] animate-in fade-in slide-in-from-top-2 duration-150">
                <button
                  onClick={() => {
                    setSortOption('newest');
                    setShowSortMenu(false);
                  }}
                  className={cn(
                    'w-full px-3 py-2 text-xs text-left transition-colors',
                    sortOption === 'newest'
                      ? 'bg-blue-900/40 text-blue-400'
                      : 'text-gray-300 hover:bg-gray-700'
                  )}
                >
                  Newest first
                </button>
                <button
                  onClick={() => {
                    setSortOption('oldest');
                    setShowSortMenu(false);
                  }}
                  className={cn(
                    'w-full px-3 py-2 text-xs text-left transition-colors',
                    sortOption === 'oldest'
                      ? 'bg-blue-900/40 text-blue-400'
                      : 'text-gray-300 hover:bg-gray-700'
                  )}
                >
                  Oldest first
                </button>
                <button
                  onClick={() => {
                    setSortOption('alphabetical');
                    setShowSortMenu(false);
                  }}
                  className={cn(
                    'w-full px-3 py-2 text-xs text-left transition-colors',
                    sortOption === 'alphabetical'
                      ? 'bg-blue-900/40 text-blue-400'
                      : 'text-gray-300 hover:bg-gray-700'
                  )}
                >
                  Alphabetical
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Task History */}
      <div className="flex-1 overflow-y-auto">
        <div className="px-3 py-2">
          {isLoading ? (
            <TaskListSkeleton count={5} />
          ) : !tasks || tasks.length === 0 ? (
            <div className="flex flex-col items-center py-6 text-center">
              <ChatBubbleLeftRightIcon className="w-8 h-8 text-gray-700 mb-2" />
              <p className="text-gray-500 text-sm">No tasks yet</p>
              <p className="text-gray-600 text-xs mt-1">Create your first task above</p>
            </div>
          ) : filteredTasks.length === 0 ? (
            <div className="flex flex-col items-center py-6 text-center">
              {searchQuery.trim() ? (
                <>
                  <MagnifyingGlassIcon className="w-8 h-8 text-gray-700 mb-2" />
                  <p className="text-gray-500 text-sm">No matching tasks</p>
                  <button
                    onClick={() => setSearchQuery('')}
                    className="text-blue-400 hover:text-blue-300 text-xs mt-1 underline"
                  >
                    Clear search
                  </button>
                </>
              ) : (
                <>
                  <CogIcon className="w-8 h-8 text-gray-700 mb-2" />
                  <p className="text-gray-500 text-sm">No active tasks</p>
                  <p className="text-gray-600 text-xs mt-1">Tasks in progress, gating, or review will appear here</p>
                </>
              )}
            </div>
          ) : (
            <div className="space-y-1">
              {filteredTasks.slice(0, 50).map((task) => (
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
                  <div className="flex items-center gap-2">
                    {/* Status indicator */}
                    {task.kanban_status === 'in_progress' ? (
                      <CogIcon className="w-3.5 h-3.5 text-yellow-400 flex-shrink-0 animate-spin" style={{ animationDuration: '3s' }} />
                    ) : task.kanban_status === 'gating' ? (
                      <ClockIcon className="w-3.5 h-3.5 text-orange-400 flex-shrink-0" />
                    ) : task.kanban_status === 'in_review' ? (
                      <EyeIcon className="w-3.5 h-3.5 text-purple-400 flex-shrink-0" />
                    ) : null}
                    <div className="truncate font-medium flex-1 min-w-0">
                      {task.title || 'Untitled Task'}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-xs text-gray-500">
                      {formatRelativeTime(task.updated_at)}
                    </span>
                    {task.kanban_status === 'in_progress' && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-yellow-900/50 text-yellow-400">
                        Running
                      </span>
                    )}
                    {task.kanban_status === 'gating' && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-orange-900/50 text-orange-400">
                        Gating
                      </span>
                    )}
                    {task.kanban_status === 'in_review' && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-900/50 text-purple-400">
                        Review
                      </span>
                    )}
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Account Section */}
      <div className="border-t border-gray-800 p-3">
        <Link
          href="/settings"
          className={cn(
            'flex items-center gap-3 w-full px-2 py-2 rounded-lg transition-colors',
            'hover:bg-gray-800',
            'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-inset',
            pathname === '/settings' && 'bg-gray-800'
          )}
        >
          <div className="w-8 h-8 bg-gray-700 rounded-full flex items-center justify-center">
            <UserCircleIcon className="w-5 h-5 text-gray-400" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium text-white">Account</div>
            <div className="text-xs text-gray-500">Settings & Preferences</div>
          </div>
        </Link>
      </div>
    </aside>
  );
}
