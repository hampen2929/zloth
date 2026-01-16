import { useCallback } from 'react';
import { useToast } from '@/components/ui/Toast';

export interface UseClipboardOptions {
  /** Success message to display (default: '{label} copied!') */
  successMessage?: string;
  /** Error message to display (default: 'Failed to copy to clipboard') */
  errorMessage?: string;
}

export interface UseClipboardResult {
  /** Copy text to clipboard */
  copy: (text: string, label?: string) => Promise<boolean>;
}

/**
 * Hook for copying text to clipboard with toast notifications
 *
 * @example
 * ```tsx
 * const { copy } = useClipboard();
 *
 * const handleCopy = () => {
 *   copy(branchName, 'Branch name');
 * };
 * ```
 */
export function useClipboard(options?: UseClipboardOptions): UseClipboardResult {
  const { success, error } = useToast();

  const copy = useCallback(
    async (text: string, label?: string): Promise<boolean> => {
      try {
        if (navigator.clipboard) {
          await navigator.clipboard.writeText(text);
        } else {
          // Fallback for non-HTTPS contexts or older browsers
          const textarea = document.createElement('textarea');
          textarea.value = text;
          textarea.style.position = 'fixed';
          textarea.style.opacity = '0';
          document.body.appendChild(textarea);
          textarea.select();
          document.execCommand('copy');
          document.body.removeChild(textarea);
        }

        const successMsg =
          options?.successMessage ?? (label ? `${label} copied!` : 'Copied to clipboard!');
        success(successMsg);
        return true;
      } catch {
        const errorMsg = options?.errorMessage ?? 'Failed to copy to clipboard';
        error(errorMsg);
        return false;
      }
    },
    [success, error, options]
  );

  return { copy };
}
