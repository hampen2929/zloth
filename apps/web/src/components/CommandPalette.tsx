'use client';

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import {
  MagnifyingGlassIcon,
  PlusIcon,
  Cog6ToothIcon,
  ViewColumnsIcon,
  ChartBarIcon,
  ClipboardDocumentListIcon,
  FolderIcon,
} from '@heroicons/react/24/outline';
import { Modal } from './ui/Modal';

interface Command {
  id: string;
  name: string;
  description?: string;
  shortcut?: string;
  icon: React.ReactNode;
  action: () => void;
  category: 'navigation' | 'action' | 'settings';
}

interface CommandPaletteProps {
  onOpenSettings?: () => void;
}

export function CommandPalette({ onOpenSettings }: CommandPaletteProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  const handleClose = useCallback(() => {
    setIsOpen(false);
    setQuery('');
    setSelectedIndex(0);
  }, []);

  const commands: Command[] = useMemo(
    () => [
      {
        id: 'new-task',
        name: 'New Task',
        description: 'Create a new task',
        shortcut: 'N',
        icon: <PlusIcon className="w-5 h-5" />,
        action: () => router.push('/'),
        category: 'navigation',
      },
      {
        id: 'kanban',
        name: 'Kanban Board',
        description: 'View task workflow',
        shortcut: 'K',
        icon: <ViewColumnsIcon className="w-5 h-5" />,
        action: () => router.push('/kanban'),
        category: 'navigation',
      },
      {
        id: 'metrics',
        name: 'Metrics',
        description: 'View development metrics',
        shortcut: 'M',
        icon: <ChartBarIcon className="w-5 h-5" />,
        action: () => router.push('/metrics'),
        category: 'navigation',
      },
      {
        id: 'backlog',
        name: 'Backlog & Archived',
        description: 'View backlog and archived tasks',
        shortcut: 'B',
        icon: <ClipboardDocumentListIcon className="w-5 h-5" />,
        action: () => router.push('/backlog'),
        category: 'navigation',
      },
      {
        id: 'repos',
        name: 'Repositories',
        description: 'Manage repositories',
        shortcut: 'R',
        icon: <FolderIcon className="w-5 h-5" />,
        action: () => router.push('/repos'),
        category: 'navigation',
      },
      {
        id: 'settings',
        name: 'Settings',
        description: 'Open settings',
        shortcut: ',',
        icon: <Cog6ToothIcon className="w-5 h-5" />,
        action: () => {
          onOpenSettings?.();
          handleClose();
        },
        category: 'settings',
      },
    ],
    [router, onOpenSettings, handleClose]
  );

  const filteredCommands = useMemo(() => {
    if (!query) return commands;
    const lowerQuery = query.toLowerCase();
    return commands.filter(
      (cmd) =>
        cmd.name.toLowerCase().includes(lowerQuery) ||
        cmd.description?.toLowerCase().includes(lowerQuery)
    );
  }, [commands, query]);

  // Reset selection when query changes - handled in onChange handler

  // Global keyboard shortcut to open
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Cmd/Ctrl + K to open
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsOpen(true);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [isOpen]);

  const executeCommand = useCallback(
    (command: Command) => {
      command.action();
      handleClose();
    },
    [handleClose]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          setSelectedIndex((prev) => (prev + 1) % filteredCommands.length);
          break;
        case 'ArrowUp':
          e.preventDefault();
          setSelectedIndex((prev) => (prev - 1 + filteredCommands.length) % filteredCommands.length);
          break;
        case 'Enter':
          e.preventDefault();
          if (filteredCommands[selectedIndex]) {
            executeCommand(filteredCommands[selectedIndex]);
          }
          break;
        case 'Escape':
          e.preventDefault();
          handleClose();
          break;
      }
    },
    [filteredCommands, selectedIndex, executeCommand, handleClose]
  );

  const isMac = typeof navigator !== 'undefined' && navigator.platform.includes('Mac');
  const modKey = isMac ? '⌘' : 'Ctrl';

  return (
    <Modal isOpen={isOpen} onClose={handleClose}>
      <div className="w-full max-w-lg mx-auto">
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-700">
          <MagnifyingGlassIcon className="w-5 h-5 text-gray-500" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            onKeyDown={handleKeyDown}
            placeholder="Type a command or search..."
            className="flex-1 bg-transparent text-gray-100 placeholder-gray-500 focus:outline-none"
          />
          <kbd className="px-2 py-1 text-xs text-gray-500 bg-gray-800 rounded">esc</kbd>
        </div>

        {/* Results */}
        <div className="max-h-80 overflow-y-auto py-2">
          {filteredCommands.length === 0 ? (
            <div className="px-4 py-8 text-center text-gray-500">No commands found</div>
          ) : (
            filteredCommands.map((command, index) => (
              <button
                key={command.id}
                onClick={() => executeCommand(command)}
                className={`w-full px-4 py-3 flex items-center gap-3 text-left transition-colors ${
                  index === selectedIndex
                    ? 'bg-gray-700 text-gray-100'
                    : 'text-gray-300 hover:bg-gray-800'
                }`}
              >
                <span className="flex-shrink-0 text-gray-400">{command.icon}</span>
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate">{command.name}</p>
                  {command.description && (
                    <p className="text-sm text-gray-500 truncate">{command.description}</p>
                  )}
                </div>
                {command.shortcut && (
                  <kbd className="flex-shrink-0 px-2 py-1 text-xs text-gray-500 bg-gray-800 rounded">
                    {modKey}+{command.shortcut}
                  </kbd>
                )}
              </button>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-2 border-t border-gray-700 flex items-center justify-between text-xs text-gray-500">
          <div className="flex items-center gap-4">
            <span>
              <kbd className="px-1.5 py-0.5 bg-gray-800 rounded">↑</kbd>{' '}
              <kbd className="px-1.5 py-0.5 bg-gray-800 rounded">↓</kbd> to navigate
            </span>
            <span>
              <kbd className="px-1.5 py-0.5 bg-gray-800 rounded">↵</kbd> to select
            </span>
          </div>
          <span>
            <kbd className="px-1.5 py-0.5 bg-gray-800 rounded">{modKey}+K</kbd> to open
          </span>
        </div>
      </div>
    </Modal>
  );
}
