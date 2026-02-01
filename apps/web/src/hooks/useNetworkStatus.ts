'use client';

import { useState, useEffect, useCallback } from 'react';

interface NetworkStatus {
  isOnline: boolean;
  isApiReachable: boolean;
  latency: number | null;
  lastChecked: Date | null;
}

const API_HEALTH_ENDPOINT = '/api/health';
const CHECK_INTERVAL = 30000; // 30 seconds

export function useNetworkStatus(): NetworkStatus {
  const [status, setStatus] = useState<NetworkStatus>({
    isOnline: typeof navigator !== 'undefined' ? navigator.onLine : true,
    isApiReachable: true,
    latency: null,
    lastChecked: null,
  });

  const checkApiHealth = useCallback(async () => {
    const start = Date.now();

    try {
      const response = await fetch(API_HEALTH_ENDPOINT, {
        method: 'HEAD',
        cache: 'no-store',
      });

      const latency = Date.now() - start;

      setStatus((prev) => ({
        ...prev,
        isApiReachable: response.ok,
        latency,
        lastChecked: new Date(),
      }));
    } catch {
      setStatus((prev) => ({
        ...prev,
        isApiReachable: false,
        latency: null,
        lastChecked: new Date(),
      }));
    }
  }, []);

  useEffect(() => {
    // Handle online/offline events
    const handleOnline = () => {
      setStatus((prev) => ({ ...prev, isOnline: true }));
      // Check API when coming back online
      checkApiHealth();
    };

    const handleOffline = () => {
      setStatus((prev) => ({
        ...prev,
        isOnline: false,
        isApiReachable: false,
      }));
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    // Initial check - this is intentional for startup health verification
    // eslint-disable-next-line react-hooks/set-state-in-effect
    checkApiHealth();

    // Periodic checks
    const interval = setInterval(checkApiHealth, CHECK_INTERVAL);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
      clearInterval(interval);
    };
  }, [checkApiHealth]);

  return status;
}
