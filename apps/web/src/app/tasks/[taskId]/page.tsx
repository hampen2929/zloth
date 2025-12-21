'use client';

import { useState, useEffect } from 'react';
import useSWR, { mutate } from 'swr';
import { tasksApi, runsApi, modelsApi } from '@/lib/api';
import { ChatPanel } from '@/components/ChatPanel';
import { RunDetailPanel } from '@/components/RunDetailPanel';
import { MessageSkeleton, RunListSkeleton } from '@/components/ui/Skeleton';
import { ExclamationCircleIcon, InboxIcon } from '@heroicons/react/24/outline';

interface PageProps {
  params: { taskId: string };
}

export default function TaskPage({ params }: PageProps) {
  const { taskId } = params;
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [activePanel, setActivePanel] = useState<'chat' | 'runs'>('chat');

  const { data: task, error: taskError, isLoading: taskLoading } = useSWR(
    `task-${taskId}`,
    () => tasksApi.get(taskId),
    { refreshInterval: 2000 }
  );

  const { data: runs, isLoading: runsLoading } = useSWR(
    `runs-${taskId}`,
    () => runsApi.list(taskId),
    { refreshInterval: 2000 }
  );

  const { data: models } = useSWR('models', modelsApi.list);

  // Auto-select first run when runs load
  useEffect(() => {
    if (runs && runs.length > 0 && !selectedRunId) {
      setSelectedRunId(runs[0].id);
    }
  }, [runs, selectedRunId]);

  // Error state
  if (taskError) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <ExclamationCircleIcon className="w-12 h-12 text-red-400 mb-4" />
        <p className="text-red-400 text-lg font-medium">Failed to load task</p>
        <p className="text-gray-500 text-sm mt-1">Please try refreshing the page</p>
      </div>
    );
  }

  // Loading state with skeleton
  if (taskLoading || !task) {
    return (
      <div className="flex flex-col lg:flex-row h-[calc(100vh-8rem)] gap-4">
        <div className="w-full lg:w-1/2 flex flex-col bg-gray-900 rounded-lg border border-gray-800">
          <MessageSkeleton />
          <MessageSkeleton />
          <MessageSkeleton />
        </div>
        <div className="w-full lg:w-1/2 flex flex-col bg-gray-900 rounded-lg border border-gray-800">
          <RunListSkeleton count={3} />
        </div>
      </div>
    );
  }

  const selectedRun = runs?.find((r) => r.id === selectedRunId);

  return (
    <div className="flex flex-col lg:flex-row h-[calc(100vh-8rem)] gap-4">
      {/* Mobile tab switcher */}
      <div className="lg:hidden flex border-b border-gray-800 mb-2">
        <button
          onClick={() => setActivePanel('chat')}
          className={`flex-1 py-2 text-sm font-medium transition-colors ${
            activePanel === 'chat'
              ? 'text-blue-400 border-b-2 border-blue-400'
              : 'text-gray-500 hover:text-gray-300'
          }`}
        >
          Chat
        </button>
        <button
          onClick={() => setActivePanel('runs')}
          className={`flex-1 py-2 text-sm font-medium transition-colors ${
            activePanel === 'runs'
              ? 'text-blue-400 border-b-2 border-blue-400'
              : 'text-gray-500 hover:text-gray-300'
          }`}
        >
          Runs {runs && runs.length > 0 && `(${runs.length})`}
        </button>
      </div>

      {/* Left Panel: Chat + Model Selection */}
      <div
        className={`w-full lg:w-1/2 flex flex-col ${
          activePanel === 'chat' ? 'flex' : 'hidden lg:flex'
        }`}
      >
        <ChatPanel
          taskId={taskId}
          messages={task.messages}
          models={models || []}
          onRunsCreated={() => {
            mutate(`runs-${taskId}`);
            setActivePanel('runs'); // Switch to runs panel on mobile after creating runs
          }}
        />
      </div>

      {/* Right Panel: Run Details */}
      <div
        className={`w-full lg:w-1/2 flex flex-col ${
          activePanel === 'runs' ? 'flex' : 'hidden lg:flex'
        }`}
      >
        {runsLoading ? (
          <div className="flex-1 bg-gray-900 rounded-lg border border-gray-800">
            <RunListSkeleton count={3} />
          </div>
        ) : selectedRun ? (
          <RunDetailPanel
            run={selectedRun}
            taskId={taskId}
            onPRCreated={() => mutate(`task-${taskId}`)}
          />
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center bg-gray-900 rounded-lg border border-gray-800">
            <InboxIcon className="w-12 h-12 text-gray-600 mb-3" />
            <p className="text-gray-500 text-sm">No runs yet</p>
            <p className="text-gray-600 text-xs mt-1">Send a message to create runs</p>
          </div>
        )}
      </div>
    </div>
  );
}
