'use client';

import { Modal, ModalBody } from './ui/Modal';
import { getShortcutsList } from '@/hooks/useKeyboardShortcuts';
import { CommandLineIcon } from '@heroicons/react/24/outline';

interface KeyboardShortcutsHelpProps {
  isOpen: boolean;
  onClose: () => void;
}

export function KeyboardShortcutsHelp({ isOpen, onClose }: KeyboardShortcutsHelpProps) {
  const shortcuts = getShortcutsList();

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="キーボードショートカット" size="sm">
      <ModalBody>
        <div className="space-y-1">
          {shortcuts.map((shortcut, idx) => (
            <div
              key={idx}
              className="flex items-center justify-between py-2 px-1 rounded hover:bg-gray-800/50"
            >
              <span className="text-gray-300 text-sm">{shortcut.description}</span>
              <kbd className="px-2 py-1 bg-gray-800 border border-gray-700 rounded text-xs text-gray-400 font-mono">
                {shortcut.key}
              </kbd>
            </div>
          ))}
        </div>

        <div className="mt-6 pt-4 border-t border-gray-800">
          <div className="flex items-center gap-2 text-gray-500 text-xs">
            <CommandLineIcon className="w-4 h-4" />
            <span>ヒント: ほとんどのショートカットはどこからでも使えます</span>
          </div>
        </div>
      </ModalBody>
    </Modal>
  );
}
