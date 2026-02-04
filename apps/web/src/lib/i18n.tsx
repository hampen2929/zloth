'use client';

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import type { Language } from '@/types';
import {
  settingsLabels,
  settingsLabelsJa,
  terms,
  termsJa,
  actionLabels,
  actionLabelsJa,
  runStatusLabels,
  runStatusLabelsJa,
  emptyStates,
  emptyStatesJa,
  successMessages,
  successMessagesJa,
  runDetailTabs,
  runDetailTabsJa,
  filterLabels,
  filterLabelsJa,
  executorTypeLabels,
  executorTypeLabelsJa,
  ariaLabels,
  ariaLabelsJa,
  keyboardShortcuts,
  keyboardShortcutsJa,
  homeLabels,
  homeLabelsJa,
  metricsLabels,
  metricsLabelsJa,
  runDetailLabels,
  runDetailLabelsJa,
  runsPanelLabels,
  runsPanelLabelsJa,
  announcements,
  announcementsJa,
  errorMessages,
  errorMessagesJa,
} from './terminology';

/**
 * Type for translations object structure
 * Using generic string types to allow different translated values
 */
export interface Translations {
  settings: typeof settingsLabels;
  terms: typeof terms;
  actions: typeof actionLabels;
  runStatus: typeof runStatusLabels;
  emptyStates: typeof emptyStates;
  success: typeof successMessages;
  runDetailTabs: typeof runDetailTabs;
  filters: typeof filterLabels;
  executorTypes: typeof executorTypeLabels;
  aria: typeof ariaLabels;
  keyboard: typeof keyboardShortcuts;
  home: typeof homeLabels;
  metrics: typeof metricsLabels;
  runDetail: typeof runDetailLabels;
  runsPanel: typeof runsPanelLabels;
  announcements: typeof announcements;
  errors: typeof errorMessages;
}

/**
 * Get translations for a given language
 */
function getTranslations(lang: Language): Translations {
  if (lang === 'ja') {
    return {
      // Using unknown as intermediate cast to satisfy TypeScript's strict literal types
      settings: settingsLabelsJa as unknown as typeof settingsLabels,
      terms: termsJa as unknown as typeof terms,
      actions: actionLabelsJa as unknown as typeof actionLabels,
      runStatus: runStatusLabelsJa as unknown as typeof runStatusLabels,
      emptyStates: emptyStatesJa as unknown as typeof emptyStates,
      success: successMessagesJa as unknown as typeof successMessages,
      runDetailTabs: runDetailTabsJa as unknown as typeof runDetailTabs,
      filters: filterLabelsJa as unknown as typeof filterLabels,
      executorTypes: executorTypeLabelsJa as unknown as typeof executorTypeLabels,
      aria: ariaLabelsJa as unknown as typeof ariaLabels,
      keyboard: keyboardShortcutsJa as unknown as typeof keyboardShortcuts,
      home: homeLabelsJa as unknown as typeof homeLabels,
      metrics: metricsLabelsJa as unknown as typeof metricsLabels,
      runDetail: runDetailLabelsJa as unknown as typeof runDetailLabels,
      runsPanel: runsPanelLabelsJa as unknown as typeof runsPanelLabels,
      announcements: announcementsJa as unknown as typeof announcements,
      errors: errorMessagesJa as unknown as typeof errorMessages,
    };
  }
  return {
    settings: settingsLabels,
    terms,
    actions: actionLabels,
    runStatus: runStatusLabels,
    emptyStates,
    success: successMessages,
    runDetailTabs,
    filters: filterLabels,
    executorTypes: executorTypeLabels,
    aria: ariaLabels,
    keyboard: keyboardShortcuts,
    home: homeLabels,
    metrics: metricsLabels,
    runDetail: runDetailLabels,
    runsPanel: runsPanelLabels,
    announcements,
    errors: errorMessages,
  };
}

interface LanguageContextValue {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: Translations;
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

interface LanguageProviderProps {
  children: React.ReactNode;
  initialLanguage?: Language;
}

/**
 * Language Provider Component
 * Provides language context to the entire application
 */
export function LanguageProvider({ children, initialLanguage = 'en' }: LanguageProviderProps) {
  const [language, setLanguageState] = useState<Language>(initialLanguage);

  // Update language state and document lang attribute
  const setLanguage = useCallback((lang: Language) => {
    setLanguageState(lang);
    // Update HTML lang attribute for accessibility
    if (typeof document !== 'undefined') {
      document.documentElement.lang = lang;
    }
  }, []);

  // Set initial language on mount
  useEffect(() => {
    if (typeof document !== 'undefined') {
      document.documentElement.lang = language;
    }
  }, [language]);

  // Update language when initialLanguage changes (e.g., from preferences API)
  useEffect(() => {
    if (initialLanguage && initialLanguage !== language) {
      setLanguage(initialLanguage);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialLanguage]);

  const t = getTranslations(language);

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  );
}

/**
 * Hook to access language context
 * @returns Language context value with language, setLanguage, and translations
 */
export function useLanguage(): LanguageContextValue {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
}

/**
 * Hook to get translations only
 * Shorthand for useLanguage().t
 */
export function useTranslations(): Translations {
  return useLanguage().t;
}
