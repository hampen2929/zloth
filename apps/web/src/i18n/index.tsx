'use client';

import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import en from './translations/en.json';
import ja from './translations/ja.json';

export type Locale = 'en' | 'ja';

const translations: Record<Locale, typeof en> = {
  en,
  ja,
};

export const localeNames: Record<Locale, string> = {
  en: 'English',
  ja: '日本語',
};

const STORAGE_KEY = 'dursor-locale';

/**
 * Get the browser's preferred language or default to 'en'.
 */
function getDefaultLocale(): Locale {
  if (typeof window === 'undefined') return 'en';

  // Check localStorage first
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === 'en' || stored === 'ja') {
    return stored;
  }

  // Check browser language
  const browserLang = navigator.language.split('-')[0];
  if (browserLang === 'ja') return 'ja';
  return 'en';
}

interface I18nContextType {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: string, params?: Record<string, string>) => string;
}

const I18nContext = createContext<I18nContextType | null>(null);

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>('en');
  const [mounted, setMounted] = useState(false);

  // Initialize locale from localStorage on mount
  // This is intentional: we need to read from localStorage which is only available on client
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLocaleState(getDefaultLocale());
    setMounted(true);
  }, []);

  const setLocale = useCallback((newLocale: Locale) => {
    setLocaleState(newLocale);
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, newLocale);
    }
  }, []);

  const t = useCallback((key: string, params?: Record<string, string>): string => {
    const keys = key.split('.');
    let value: unknown = translations[locale];

    for (const k of keys) {
      if (value && typeof value === 'object' && k in value) {
        value = (value as Record<string, unknown>)[k];
      } else {
        // Fallback to English
        value = translations.en;
        for (const fallbackKey of keys) {
          if (value && typeof value === 'object' && fallbackKey in value) {
            value = (value as Record<string, unknown>)[fallbackKey];
          } else {
            return key; // Return the key if not found
          }
        }
        break;
      }
    }

    if (typeof value !== 'string') {
      return key;
    }

    // Replace params like {name} with actual values
    if (params) {
      return Object.entries(params).reduce(
        (str, [paramKey, paramValue]) => str.replace(new RegExp(`\\{${paramKey}\\}`, 'g'), paramValue),
        value
      );
    }

    return value;
  }, [locale]);

  // Prevent hydration mismatch by rendering with default locale on server
  if (!mounted) {
    return (
      <I18nContext.Provider value={{ locale: 'en', setLocale, t }}>
        {children}
      </I18nContext.Provider>
    );
  }

  return (
    <I18nContext.Provider value={{ locale, setLocale, t }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useTranslation() {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error('useTranslation must be used within an I18nProvider');
  }
  return context;
}

export function useLocale() {
  const { locale, setLocale } = useTranslation();
  return { locale, setLocale };
}
