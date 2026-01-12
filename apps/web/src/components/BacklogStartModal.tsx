'use client';

import { useEffect, useMemo, useState } from 'react';
import useSWR from 'swr';
import { Modal, ModalBody, ModalFooter } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import { useToast } from '@/components/ui/Toast';
import { cn } from '@/lib/utils';
import { backlogApi, modelsApi, runsApi, tasksApi } from '@/lib/api';
import type { BacklogItem, ExecutorType, ModelProfile } from '@/types';
import {
  CpuChipIcon,
  CheckIcon,
  CommandLineIcon,
  PlayIcon,
} from '@heroicons/react/24/outline';

interface BacklogStartModalProps {
  isOpen: boolean;
  item: BacklogItem;
  onClose: () => void;
  onStarted?: (taskId: string) => void;
}

function buildInstructionFromBacklog(item: BacklogItem): string {
  const lines: string[] = [];
  const push = (s: string) => lines.push(s);

  push(`${item.title}`);
  push('');

  if (item.description?.trim()) {
    push('Context:');
    push(item.description.trim());
    push('');
  }

  push(
    `Type: ${item.type}  |  Size: ${item.estimated_size}${
      item.tags.length ? `  |  Tags: ${item.tags.join(', ')}` : ''
    }`
  );
  if (item.target_files?.length) {
    push(`Target files: ${item.target_files.join(', ')}`);
  }
  if (item.implementation_hint?.trim()) {
    push(`Implementation hint: ${item.implementation_hint.trim()}`);
  }
  push('');

  if (item.subtasks?.length) {
    push('Subtasks:');
    for (const st of item.subtasks) {
      push(`- ${st.title}`);
    }
    push('');
  }

  push(
    'Please implement the above in the codebase with minimal, focused changes. Avoid modifying forbidden paths (e.g., .git, .env).'
  );

  return lines.join('\n');
}

export default function BacklogStartModal({
  isOpen,
  item,
  onClose,
  onStarted,
}: BacklogStartModalProps) {
  const { data: models = [] } = useSWR<ModelProfile[]>(isOpen ? 'models' : null, modelsApi.list);
  const { success, error } = useToast();

  const [instruction, setInstruction] = useState(() => buildInstructionFromBacklog(item));
  const [loading, setLoading] = useState(false);

  // Executor selection state
  const [selectedCLIs, setSelectedCLIs] = useState<ExecutorType[]>([]);
  const [usePatchAgent, setUsePatchAgent] = useState(true);
  const [selectedModels, setSelectedModels] = useState<string[]>([]);

  // Reset state when opening
  useEffect(() => {
    if (!isOpen) return;
    setInstruction(buildInstructionFromBacklog(item));
    // Default selection: use patch_agent if models exist; else default to Claude CLI
    if (models.length > 0) {
      setUsePatchAgent(true);
      setSelectedModels(models.map((m) => m.id));
      setSelectedCLIs([]);
    } else {
      setUsePatchAgent(false);
      setSelectedModels([]);
      setSelectedCLIs(['claude_code']);
    }
  }, [isOpen, item, models]);

  const hasExecutors = useMemo(() => {
    return selectedCLIs.length > 0 || (usePatchAgent && selectedModels.length > 0);
  }, [selectedCLIs, usePatchAgent, selectedModels]);

  const toggleCLI = (cli: ExecutorType) => {
    setSelectedCLIs((prev) =>
      prev.includes(cli) ? prev.filter((c) => c !== cli) : [...prev, cli]
    );
  };

  const toggleModel = (modelId: string) => {
    setSelectedModels((prev) =>
      prev.includes(modelId) ? prev.filter((id) => id !== modelId) : [...prev, modelId]
    );
  };

  const selectAllModels = () => {
    if (selectedModels.length === models.length) {
      setSelectedModels([]);
    } else {
      setSelectedModels(models.map((m) => m.id));
    }
  };

  const handleStart = async () => {
    if (!instruction.trim()) {
      error('Instruction is empty');
      return;
    }
    if (!hasExecutors) {
      error('Select at least one executor');
      return;
    }
    if (usePatchAgent && selectedModels.length === 0) {
      error('Select at least one model');
      return;
    }

    setLoading(true);
    try {
      // 1) Promote backlog item to task
      const task = await backlogApi.startWork(item.id);

      // 2) Create initial user message from instruction
      const message = await tasksApi.addMessage(task.id, {
        role: 'user',
        content: instruction.trim(),
      });

      // 3) Build executor_types and create runs
      const executorTypesToRun: ExecutorType[] = [...selectedCLIs];
      if (usePatchAgent && selectedModels.length > 0) {
        executorTypesToRun.push('patch_agent');
      }

      await runsApi.create(task.id, {
        instruction: instruction.trim(),
        executor_types: executorTypesToRun,
        model_ids: usePatchAgent ? selectedModels : undefined,
        message_id: message.id,
      });

      success('Task started');
      onClose();
      onStarted?.(task.id);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to start task';
      error(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={loading ? () => {} : onClose}
      title="Start Task Execution"
      description="Choose executors and review the instruction before running."
      size="xl"
    >
      <ModalBody className="space-y-4 max-h-[calc(85vh-180px)] overflow-y-auto">
        {/* Summary */}
        <div className="p-3 rounded border border-gray-800 bg-gray-900/60">
          <div className="text-sm text-gray-400">
            <span className="text-gray-300 font-medium">Backlog:</span> {item.title}
          </div>
        </div>

        {/* Executor selection */}
        <div className="space-y-3">
          <div>
            <span className="text-xs text-gray-500 block mb-2">CLI Agents:</span>
            <div className="flex items-center gap-2 flex-wrap">
              {(['claude_code', 'codex_cli', 'gemini_cli'] as const).map((cli) => {
                const isSelected = selectedCLIs.includes(cli);
                const labels: Record<string, string> = {
                  claude_code: 'Claude',
                  codex_cli: 'Codex',
                  gemini_cli: 'Gemini',
                };
                return (
                  <button
                    key={cli}
                    type="button"
                    onClick={() => toggleCLI(cli)}
                    className={cn(
                      'flex items-center gap-1.5 px-2.5 py-1.5 rounded text-xs font-medium transition-all',
                      'focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-1 focus:ring-offset-gray-900',
                      isSelected
                        ? 'bg-purple-600 text-white shadow-sm'
                        : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-300'
                    )}
                    aria-pressed={isSelected}
                  >
                    {isSelected && <CheckIcon className="w-3 h-3" />}
                    <CommandLineIcon className="w-3.5 h-3.5" />
                    <span>{labels[cli]}</span>
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <button
                type="button"
                onClick={() => setUsePatchAgent(!usePatchAgent)}
                className={cn(
                  'flex items-center gap-1.5 text-xs transition-colors',
                  usePatchAgent ? 'text-blue-400' : 'text-gray-500 hover:text-gray-300'
                )}
              >
                <div
                  className={cn(
                    'w-4 h-4 rounded border flex items-center justify-center flex-shrink-0',
                    usePatchAgent ? 'bg-blue-600 border-blue-600' : 'border-gray-600'
                  )}
                >
                  {usePatchAgent && <CheckIcon className="w-3 h-3 text-white" />}
                </div>
                <CpuChipIcon className="w-3.5 h-3.5" />
                <span>Models</span>
              </button>
              {usePatchAgent && models.length > 1 && (
                <button
                  type="button"
                  onClick={selectAllModels}
                  className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
                >
                  {selectedModels.length === models.length ? 'Deselect all' : 'Select all'}
                </button>
              )}
            </div>
            {usePatchAgent && (
              <div className="flex flex-wrap gap-2 ml-6">
                {models.length === 0 ? (
                  <p className="text-gray-600 text-xs">
                    No models configured. Add models in Settings or choose a CLI agent.
                  </p>
                ) : (
                  models.map((model) => {
                    const isSelected = selectedModels.includes(model.id);
                    return (
                      <button
                        key={model.id}
                        type="button"
                        onClick={() => toggleModel(model.id)}
                        className={cn(
                          'flex items-center gap-1.5 px-2.5 py-1.5 rounded text-xs font-medium transition-all',
                          'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 focus:ring-offset-gray-900',
                          isSelected
                            ? 'bg-blue-600 text-white shadow-sm'
                            : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-300'
                        )}
                        aria-pressed={isSelected}
                      >
                        {isSelected && <CheckIcon className="w-3 h-3" />}
                        {model.display_name || model.model_name}
                      </button>
                    );
                  })
                )}
              </div>
            )}
          </div>
        </div>

        {/* Instruction */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-xs text-gray-500">Instruction</label>
            <span className="text-[11px] text-gray-500">
              {instruction.length} chars
            </span>
          </div>
          <textarea
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            rows={10}
            className={cn(
              'w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded',
              'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
              'text-sm text-gray-100 placeholder:text-gray-500'
            )}
          />
        </div>
      </ModalBody>
      <ModalFooter>
        <Button variant="secondary" onClick={onClose} disabled={loading}>
          Cancel
        </Button>
        <Button
          variant="primary"
          onClick={handleStart}
          isLoading={loading}
          leftIcon={<PlayIcon className="w-4 h-4" />}
          disabled={!hasExecutors || !instruction.trim()}
        >
          Start & Open Task
        </Button>
      </ModalFooter>
    </Modal>
  );
}

