'use client';

import { WifiIcon, ExclamationTriangleIcon } from '@heroicons/react/24/outline';
import { useNetworkStatus } from '@/hooks/useNetworkStatus';

export function NetworkStatusIndicator() {
  const { isOnline, isApiReachable } = useNetworkStatus();

  // Only show when there's a problem
  if (isOnline && isApiReachable) {
    return null;
  }

  return (
    <div
      className="fixed bottom-4 right-4 z-50 animate-in fade-in slide-in-from-bottom-2 duration-300"
      role="alert"
      aria-live="polite"
    >
      <div
        className={`flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg ${
          !isOnline
            ? 'bg-red-900/95 text-red-100 border border-red-800'
            : 'bg-amber-900/95 text-amber-100 border border-amber-800'
        }`}
      >
        {!isOnline ? (
          <>
            <WifiIcon className="w-5 h-5 flex-shrink-0" />
            <div>
              <p className="font-medium text-sm">You are offline</p>
              <p className="text-xs opacity-80">Check your internet connection</p>
            </div>
          </>
        ) : (
          <>
            <ExclamationTriangleIcon className="w-5 h-5 flex-shrink-0" />
            <div>
              <p className="font-medium text-sm">Connection issue</p>
              <p className="text-xs opacity-80">Unable to reach the server</p>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
