'use client';

import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';
import useSWR from 'swr';
import { preferencesApi } from '@/lib/api';
import type { UserPreferences, UserPreferencesSave } from '@/types';

interface PreferencesContextValue {
  preferences: UserPreferences | null;
  isLoading: boolean;
  error: Error | null;
  updatePreference: <K extends keyof UserPreferencesSave>(
    key: K,
    value: UserPreferencesSave[K]
  ) => Promise<void>;
  updatePreferences: (updates: UserPreferencesSave) => Promise<void>;
  refresh: () => Promise<void>;
}

const PreferencesContext = createContext<PreferencesContextValue | null>(null);

const STORAGE_KEY = 'zloth-preferences';

function loadCachedPreferences(): UserPreferences | null {
  if (typeof window === 'undefined') return null;
  try {
    const cached = localStorage.getItem(STORAGE_KEY);
    if (cached) {
      return JSON.parse(cached);
    }
  } catch {
    // Ignore parse errors
  }
  return null;
}

export function PreferencesProvider({ children }: { children: ReactNode }) {
  const [localCache, setLocalCache] = useState<UserPreferences | null>(loadCachedPreferences);

  const { data, error, isLoading, mutate } = useSWR<UserPreferences>(
    'preferences',
    preferencesApi.get,
    {
      revalidateOnFocus: false,
      dedupingInterval: 5000,
      onSuccess: (fetchedData) => {
        setLocalCache(fetchedData);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(fetchedData));
      },
    }
  );

  const updatePreference = useCallback(
    async <K extends keyof UserPreferencesSave>(key: K, value: UserPreferencesSave[K]) => {
      const currentPrefs = localCache ?? data;
      if (!currentPrefs) return;

      // Only update if value is not undefined
      const updated: UserPreferences = value !== undefined
        ? { ...currentPrefs, [key]: value } as UserPreferences
        : currentPrefs;

      // Optimistic update
      setLocalCache(updated);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));

      try {
        await preferencesApi.save({ [key]: value });
        await mutate(updated, false);
      } catch (err) {
        // Rollback on error
        setLocalCache(currentPrefs);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(currentPrefs));
        throw err;
      }
    },
    [localCache, data, mutate]
  );

  const updatePreferences = useCallback(
    async (updates: UserPreferencesSave) => {
      const currentPrefs = localCache ?? data;
      if (!currentPrefs) return;

      // Merge updates, keeping non-null values from currentPrefs for required fields
      const updated: UserPreferences = {
        ...currentPrefs,
        ...Object.fromEntries(
          Object.entries(updates).filter(([, v]) => v !== undefined)
        ),
      } as UserPreferences;

      // Optimistic update
      setLocalCache(updated);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));

      try {
        await preferencesApi.save(updates);
        await mutate(updated, false);
      } catch (err) {
        // Rollback on error
        setLocalCache(currentPrefs);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(currentPrefs));
        throw err;
      }
    },
    [localCache, data, mutate]
  );

  const refresh = useCallback(async () => {
    await mutate();
  }, [mutate]);

  const preferences = localCache ?? data ?? null;

  return (
    <PreferencesContext.Provider
      value={{
        preferences,
        isLoading,
        error: error ?? null,
        updatePreference,
        updatePreferences,
        refresh,
      }}
    >
      {children}
    </PreferencesContext.Provider>
  );
}

export function usePreferences() {
  const context = useContext(PreferencesContext);
  if (!context) {
    throw new Error('usePreferences must be used within a PreferencesProvider');
  }
  return context;
}
