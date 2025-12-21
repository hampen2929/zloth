'use client';

import { useState, useEffect } from 'react';
import useSWR, { mutate } from 'swr';
import { tasksApi, runsApi, prsApi, modelsApi } from '@/lib/api';
import type { Run, RunStatus, ModelProfile } from '@/types';
import { ChatPanel } from '@/components/ChatPanel';
import { RunDetailPanel } from '@/components/RunDetailPanel';

interface PageProps {
  params: { taskId: string };
}

export default function TaskPage({ params }: PageProps) {
  const { taskId } = params;
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  const { data: task, error: taskError } = useSWR(
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

  // Auto-select first run when runs load
  useEffect(() => {
    if (runs && runs.length > 0 && !selectedRunId) {
      setSelectedRunId(runs[0].id);
    }
  }, [runs, selectedRunId]);

  if (taskError) {
    return (
      <div className="text-center py-12">
        <p className="text-red-400">Failed to load task.</p>
      </div>
    );
  }

  if (!task) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-400">Loading...</p>
      </div>
    );
  }

  const selectedRun = runs?.find((r) => r.id === selectedRunId);

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-4">
      {/* Left Panel: Chat + Model Selection */}
      <div className="w-1/2 flex flex-col">
        <ChatPanel
          taskId={taskId}
          messages={task.messages}
          models={models || []}
          onRunsCreated={() => mutate(`runs-${taskId}`)}
        />
      </div>

      {/* Right Panel: Run Details */}
      <div className="w-1/2 flex flex-col">
        {selectedRun ? (
          <RunDetailPanel
            run={selectedRun}
            taskId={taskId}
            onPRCreated={() => mutate(`task-${taskId}`)}
          />
        ) : (
          <div className="flex-1 flex items-center justify-center bg-gray-900 rounded-lg border border-gray-800">
            <p className="text-gray-500">Select a run to view details</p>
          </div>
        )}
      </div>
    </div>
  );
}
