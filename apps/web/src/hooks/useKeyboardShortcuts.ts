import { useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { isMac } from '@/lib/platform';
import { keyboardShortcuts, keyboardShortcutsJa } from '@/lib/terminology';
import type { Language } from '@/types';

export interface KeyboardShortcut {
  key: string;
  modifiers?: ('ctrl' | 'meta' | 'shift' | 'alt')[];
  description: string;
  action: () => void;
  global?: boolean; // If true, works even when input is focused
}

interface UseKeyboardShortcutsOptions {
  onOpenSettings?: () => void;
  onShowHelp?: () => void;
  onFocusInput?: () => void;
}

/**
 * Hook to register global keyboard shortcuts
 */
export function useKeyboardShortcuts({
  onOpenSettings,
  onShowHelp,
  onFocusInput,
}: UseKeyboardShortcutsOptions = {}) {
  const router = useRouter();

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      const isMacOS = isMac();
      const modifierPressed = isMacOS ? e.metaKey : e.ctrlKey;
      const isInputFocused =
        document.activeElement instanceof HTMLInputElement ||
        document.activeElement instanceof HTMLTextAreaElement ||
        document.activeElement instanceof HTMLSelectElement;

      // Cmd/Ctrl + , : Open settings
      if (modifierPressed && e.key === ',') {
        e.preventDefault();
        onOpenSettings?.();
        return;
      }

      // Cmd/Ctrl + / : Show shortcuts help
      if (modifierPressed && e.key === '/') {
        e.preventDefault();
        onShowHelp?.();
        return;
      }

      // Cmd/Ctrl + N : New task (go to home)
      if (modifierPressed && e.key === 'n' && !e.shiftKey) {
        e.preventDefault();
        router.push('/');
        return;
      }

      // Only trigger these if not in an input
      if (!isInputFocused) {
        // / : Focus input
        if (e.key === '/' && !modifierPressed) {
          e.preventDefault();
          onFocusInput?.();
          return;
        }
      }
    },
    [router, onOpenSettings, onShowHelp, onFocusInput]
  );

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);
}

/**
 * Get list of all available shortcuts for display
 */
export function getShortcutsList(language: Language = 'en'): { key: string; description: string }[] {
  const mod = isMac() ? '⌘' : 'Ctrl';
  const labels = language === 'ja' ? keyboardShortcutsJa : keyboardShortcuts;

  return [
    { key: `${mod} + ,`, description: labels.openSettings },
    { key: `${mod} + /`, description: labels.showShortcuts },
    { key: `${mod} + N`, description: labels.newTask },
    { key: `${mod} + Enter`, description: labels.submitTask },
    { key: '/', description: labels.focusInput },
    { key: 'Escape', description: labels.closeModal },
  ];
}
