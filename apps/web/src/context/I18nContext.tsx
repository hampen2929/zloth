'use client';

import { createContext, useContext, type ReactNode } from 'react';
import messages from '../../messages/en.json';

type MessageKey = keyof typeof messages;
type NestedMessages = typeof messages;

interface I18nContextValue {
  t: (key: string, params?: Record<string, string | number>) => string;
  locale: string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

function getNestedValue(obj: NestedMessages, path: string): string {
  const keys = path.split('.');
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let result: any = obj;

  for (const key of keys) {
    if (result && typeof result === 'object' && key in result) {
      result = result[key];
    } else {
      return path; // Return the key if not found
    }
  }

  return typeof result === 'string' ? result : path;
}

function interpolate(template: string, params: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_, key) => {
    return key in params ? String(params[key]) : `{${key}}`;
  });
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const t = (key: string, params?: Record<string, string | number>): string => {
    const value = getNestedValue(messages, key);
    return params ? interpolate(value, params) : value;
  };

  return (
    <I18nContext.Provider value={{ t, locale: 'en' }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useTranslations(namespace?: MessageKey) {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error('useTranslations must be used within an I18nProvider');
  }

  return (key: string, params?: Record<string, string | number>) => {
    const fullKey = namespace ? `${namespace}.${key}` : key;
    return context.t(fullKey, params);
  };
}

export function useI18n() {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error('useI18n must be used within an I18nProvider');
  }
  return context;
}
