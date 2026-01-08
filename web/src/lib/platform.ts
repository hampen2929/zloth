import { useState, useEffect } from 'react';

/**
 * Platform detection utilities
 */

/**
 * Detect if the user is on macOS (client-side only)
 */
export function isMac(): boolean {
  if (typeof navigator === 'undefined') return false;
  return navigator.platform.toUpperCase().includes('MAC');
}

/**
 * Get the platform-specific modifier key name
 * Returns 'Cmd' for macOS, 'Ctrl' for other platforms
 */
export function getPlatformModifier(): string {
  return isMac() ? 'Cmd' : 'Ctrl';
}

/**
 * Get platform-specific keyboard shortcut display text
 */
export function getShortcutText(key: string, modifier: boolean = true): string {
  if (!modifier) return key;
  return `${getPlatformModifier()}+${key}`;
}

/**
 * Hook to get platform-specific shortcut text without hydration mismatch
 * Returns a consistent default during SSR, then updates after mount
 */
export function useShortcutText(key: string, modifier: boolean = true): string {
  const [shortcutText, setShortcutText] = useState(() => {
    if (!modifier) return key;
    return `Ctrl+${key}`; // Default for SSR
  });

  useEffect(() => {
    setShortcutText(getShortcutText(key, modifier));
  }, [key, modifier]);

  return shortcutText;
}

/**
 * Check if the modifier key is pressed based on platform
 */
export function isModifierPressed(event: KeyboardEvent | React.KeyboardEvent): boolean {
  return isMac() ? event.metaKey : event.ctrlKey;
}
