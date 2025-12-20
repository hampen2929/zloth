'use client';

import { useState } from 'react';
import Sidebar from './Sidebar';
import SettingsModal from './SettingsModal';

interface ClientLayoutProps {
  children: React.ReactNode;
}

export default function ClientLayout({ children }: ClientLayoutProps) {
  const [settingsOpen, setSettingsOpen] = useState(false);

  return (
    <div className="flex h-screen">
      <Sidebar onSettingsClick={() => setSettingsOpen(true)} />
      <main className="flex-1 overflow-y-auto">
        <div className="p-6">{children}</div>
      </main>
      <SettingsModal isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
}
