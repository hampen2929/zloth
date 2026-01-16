'use client';

import React, { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react';

interface LiveAnnouncerContextType {
  announce: (message: string, politeness?: 'polite' | 'assertive') => void;
}

const LiveAnnouncerContext = createContext<LiveAnnouncerContextType | null>(null);

export function useLiveAnnouncer() {
  const context = useContext(LiveAnnouncerContext);
  if (!context) {
    throw new Error('useLiveAnnouncer must be used within a LiveAnnouncerProvider');
  }
  return context;
}

interface LiveAnnouncerProviderProps {
  children: React.ReactNode;
}

export function LiveAnnouncerProvider({ children }: LiveAnnouncerProviderProps) {
  const [politeMessage, setPoliteMessage] = useState('');
  const [assertiveMessage, setAssertiveMessage] = useState('');
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  const announce = useCallback((message: string, politeness: 'polite' | 'assertive' = 'polite') => {
    // Clear any pending timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    if (politeness === 'assertive') {
      setAssertiveMessage(message);
      // Clear after announcement
      timeoutRef.current = setTimeout(() => setAssertiveMessage(''), 1000);
    } else {
      setPoliteMessage(message);
      // Clear after announcement
      timeoutRef.current = setTimeout(() => setPoliteMessage(''), 1000);
    }
  }, []);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return (
    <LiveAnnouncerContext.Provider value={{ announce }}>
      {children}
      {/* Screen reader only announcer regions */}
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {politeMessage}
      </div>
      <div
        role="alert"
        aria-live="assertive"
        aria-atomic="true"
        className="sr-only"
      >
        {assertiveMessage}
      </div>
    </LiveAnnouncerContext.Provider>
  );
}

/**
 * Hook to announce run status changes
 */
export function useRunStatusAnnouncer() {
  const { announce } = useLiveAnnouncer();

  const announceRunStatus = useCallback(
    (modelName: string, status: 'running' | 'succeeded' | 'failed' | 'cancelled') => {
      const statusMessages = {
        running: `${modelName} の実行を開始しました`,
        succeeded: `${modelName} の実行が完了しました`,
        failed: `${modelName} の実行が失敗しました`,
        cancelled: `${modelName} の実行がキャンセルされました`,
      };
      announce(statusMessages[status], status === 'failed' ? 'assertive' : 'polite');
    },
    [announce]
  );

  return { announceRunStatus };
}
