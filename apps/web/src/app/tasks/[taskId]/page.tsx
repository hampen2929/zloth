'use client';

import { use, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import useSWR, { mutate } from 'swr';
import { tasksApi, runsApi, modelsApi } from '@/lib/api';
import { ChatCodeView } from '@/components/ChatCodeView';
import { MessageSkeleton } from '@/components/ui/Skeleton';
import { ExclamationCircleIcon } from '@heroicons/react/24/outline';
import type { ExecutorType } from '@/types';

interface PageProps {
  params: Promise<{ taskId: string }>;
}

function TaskPageContent({ taskId }: { taskId: string }) {
  const searchParams = useSearchParams();

  // Parse query params for executor type and model IDs
  const executorType = (searchParams.get('executor') || 'patch_agent') as ExecutorType;
  const initialModelIds = searchParams.get('models')?.split(',').filter(Boolean);

  const { data: task, error: taskError, isLoading: taskLoading } = useSWR(
    `task-${taskId}`,
    () => tasksApi.get(taskId),
    { refreshInterval: 2000 }
  );

  const { data: runs } = useSWR(
    `runs-${taskId}`,
    () => runsApi.list(taskId),
    { refreshInterval: 2000 }
  );

  const { data: models } = useSWR('models', modelsApi.list);

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
      <div className="max-w-4xl mx-auto h-[calc(100vh-8rem)]">
        <div className="h-full flex flex-col bg-gray-900 rounded-lg border border-gray-800 p-4">
          <MessageSkeleton />
          <MessageSkeleton />
          <MessageSkeleton />
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto h-[calc(100vh-8rem)]">
      <ChatCodeView
        taskId={taskId}
        messages={task.messages}
        runs={runs || []}
        models={models || []}
        executorType={executorType}
        initialModelIds={initialModelIds}
        onRunsCreated={() => {
          mutate(`runs-${taskId}`);
        }}
        onPRCreated={() => mutate(`task-${taskId}`)}
      />
    </div>
  );
}

export default function TaskPage({ params }: PageProps) {
  const { taskId } = use(params);

  return (
    <Suspense fallback={
      <div className="max-w-4xl mx-auto h-[calc(100vh-8rem)]">
        <div className="h-full flex flex-col bg-gray-900 rounded-lg border border-gray-800 p-4">
          <MessageSkeleton />
          <MessageSkeleton />
          <MessageSkeleton />
        </div>
      </div>
    }>
      <TaskPageContent taskId={taskId} />
    </Suspense>
  );
}
