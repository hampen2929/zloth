'use client';

import { use, Suspense, useState, useEffect, useCallback } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import useSWR, { mutate } from 'swr';
import { tasksApi, runsApi, modelsApi, backlogApi } from '@/lib/api';
import { ChatCodeView } from '@/components/ChatCodeView';
import { ExecutionSetupModal } from '@/components/ExecutionSetupModal';
import { MessageSkeleton } from '@/components/ui/Skeleton';
import { useToast } from '@/components/ui/Toast';
import { ExclamationCircleIcon } from '@heroicons/react/24/outline';
import type { ExecutorType, BacklogItem } from '@/types';

interface PageProps {
  params: Promise<{ taskId: string }>;
}

function TaskPageContent({ taskId }: { taskId: string }) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { success, error: showError } = useToast();

  // Parse query params for executor type and model IDs
  const executorType = (searchParams.get('executor') || 'patch_agent') as ExecutorType;
  const initialModelIds = searchParams.get('models')?.split(',').filter(Boolean);
  const fromBacklogId = searchParams.get('fromBacklog');

  // State for execution setup modal
  const [showExecutionModal, setShowExecutionModal] = useState(false);
  const [backlogItem, setBacklogItem] = useState<BacklogItem | null>(null);
  const [isExecuting, setIsExecuting] = useState(false);

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

  // Fetch backlog item if fromBacklog param is present
  useEffect(() => {
    if (fromBacklogId && !backlogItem) {
      backlogApi.get(fromBacklogId).then((item) => {
        setBacklogItem(item);
        setShowExecutionModal(true);
      }).catch((err) => {
        console.error('Failed to fetch backlog item:', err);
      });
    }
  }, [fromBacklogId, backlogItem]);

  // Handle execution from modal
  const handleExecute = useCallback(
    async (
      instruction: string,
      selectedExecutor: ExecutorType,
      modelIds?: string[]
    ) => {
      setIsExecuting(true);
      try {
        // Create message
        const message = await tasksApi.addMessage(taskId, {
          role: 'user',
          content: instruction,
        });

        // Determine executor types to run
        const executorTypes: ExecutorType[] = [];
        const isCLI =
          selectedExecutor === 'claude_code' ||
          selectedExecutor === 'codex_cli' ||
          selectedExecutor === 'gemini_cli';

        if (isCLI) {
          executorTypes.push(selectedExecutor);
        } else if (selectedExecutor === 'patch_agent') {
          executorTypes.push('patch_agent');
        }

        // Create run
        await runsApi.create(taskId, {
          instruction,
          executor_types: executorTypes,
          model_ids:
            selectedExecutor === 'patch_agent' && modelIds
              ? modelIds
              : undefined,
          message_id: message.id,
        });

        success('Execution started');
        setShowExecutionModal(false);

        // Remove fromBacklog param from URL
        router.replace(`/tasks/${taskId}`);

        // Refresh data
        mutate(`runs-${taskId}`);
        mutate(`task-${taskId}`);
      } catch (err) {
        console.error('Failed to start execution:', err);
        showError('Failed to start execution. Please try again.');
      } finally {
        setIsExecuting(false);
      }
    },
    [taskId, router, success, showError]
  );

  // Handle modal close
  const handleModalClose = useCallback(() => {
    setShowExecutionModal(false);
    // Remove fromBacklog param from URL
    router.replace(`/tasks/${taskId}`);
  }, [taskId, router]);

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

      {/* Execution Setup Modal for Backlog Items */}
      {backlogItem && (
        <ExecutionSetupModal
          isOpen={showExecutionModal}
          onClose={handleModalClose}
          backlogItem={backlogItem}
          models={models || []}
          onExecute={handleExecute}
          isExecuting={isExecuting}
        />
      )}
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
