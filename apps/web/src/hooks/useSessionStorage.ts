'use client';

import { useState, useEffect, useCallback } from 'react';

/**
 * A hook that syncs state with sessionStorage.
 * The value persists across page navigations within the same browser session.
 *
 * @param key - The sessionStorage key
 * @param initialValue - The initial value if nothing is stored
 * @returns A tuple of [value, setValue, clearValue]
 */
export function useSessionStorage<T>(
  key: string,
  initialValue: T
): [T, (value: T | ((prev: T) => T)) => void, () => void] {
  // Initialize state with value from sessionStorage or initial value
  const [storedValue, setStoredValue] = useState<T>(() => {
    if (typeof window === 'undefined') {
      return initialValue;
    }
    try {
      const item = window.sessionStorage.getItem(key);
      return item ? (JSON.parse(item) as T) : initialValue;
    } catch (error) {
      console.warn(`Error reading sessionStorage key "${key}":`, error);
      return initialValue;
    }
  });

  // Update sessionStorage when state changes
  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    try {
      window.sessionStorage.setItem(key, JSON.stringify(storedValue));
    } catch (error) {
      console.warn(`Error setting sessionStorage key "${key}":`, error);
    }
  }, [key, storedValue]);

  // Wrapped setter that supports both direct values and updater functions
  const setValue = useCallback((value: T | ((prev: T) => T)) => {
    setStoredValue((prev) => {
      const newValue = value instanceof Function ? value(prev) : value;
      return newValue;
    });
  }, []);

  // Clear the value from sessionStorage
  const clearValue = useCallback(() => {
    if (typeof window === 'undefined') {
      return;
    }
    try {
      window.sessionStorage.removeItem(key);
      setStoredValue(initialValue);
    } catch (error) {
      console.warn(`Error removing sessionStorage key "${key}":`, error);
    }
  }, [key, initialValue]);

  return [storedValue, setValue, clearValue];
}
