import { useEffect, RefObject, useCallback } from 'react';

/**
 * Hook to detect clicks outside of a referenced element
 *
 * @param ref - React ref object pointing to the element to monitor
 * @param onClickOutside - Callback function when a click outside is detected
 * @param enabled - Optional flag to enable/disable the listener (default: true)
 *
 * @example
 * ```tsx
 * const dropdownRef = useRef<HTMLDivElement>(null);
 * const [isOpen, setIsOpen] = useState(false);
 *
 * useClickOutside(dropdownRef, () => setIsOpen(false), isOpen);
 *
 * return (
 *   <div ref={dropdownRef}>
 *     {isOpen && <DropdownContent />}
 *   </div>
 * );
 * ```
 */
export function useClickOutside<T extends HTMLElement>(
  ref: RefObject<T | null>,
  onClickOutside: () => void,
  enabled: boolean = true
): void {
  const handleClickOutside = useCallback(
    (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        onClickOutside();
      }
    },
    [ref, onClickOutside]
  );

  useEffect(() => {
    if (!enabled) return;

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [enabled, handleClickOutside]);
}

/**
 * Hook to detect clicks outside of multiple referenced elements
 * Useful when you have multiple dropdowns that should all close on outside click
 *
 * @param refs - Array of React ref objects pointing to elements to monitor
 * @param onClickOutside - Callback function when a click outside all refs is detected
 * @param enabled - Optional flag to enable/disable the listener (default: true)
 */
export function useClickOutsideMultiple<T extends HTMLElement>(
  refs: RefObject<T | null>[],
  onClickOutside: () => void,
  enabled: boolean = true
): void {
  const handleClickOutside = useCallback(
    (event: MouseEvent) => {
      const target = event.target as Node;
      const isOutsideAll = refs.every(
        (ref) => ref.current && !ref.current.contains(target)
      );

      if (isOutsideAll) {
        onClickOutside();
      }
    },
    [refs, onClickOutside]
  );

  useEffect(() => {
    if (!enabled) return;

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [enabled, handleClickOutside]);
}
