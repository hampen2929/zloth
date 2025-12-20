'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

/**
 * Settings page - redirects to home with settings modal
 * Settings are now accessed via the Account menu in the sidebar
 */
export default function SettingsPage() {
  const router = useRouter();

  useEffect(() => {
    // Redirect to home - settings are now in the sidebar modal
    router.replace('/');
  }, [router]);

  return (
    <div className="max-w-2xl mx-auto py-8">
      <p className="text-gray-400">Redirecting to home...</p>
    </div>
  );
}
