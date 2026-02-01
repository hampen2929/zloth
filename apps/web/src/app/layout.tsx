import type { Metadata } from 'next';
import './globals.css';
import ClientLayout from '@/components/ClientLayout';

export const metadata: Metadata = {
  title: 'zloth - Multi-model Coding Agent',
  description: 'BYO API Key / Multi-model parallel execution / Conversation-driven PR development',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="bg-background text-foreground min-h-screen">
        <ClientLayout>{children}</ClientLayout>
      </body>
    </html>
  );
}
