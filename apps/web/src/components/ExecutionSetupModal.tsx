'use client';

import { useState } from 'react';
import { Modal, ModalBody, ModalFooter } from './ui/Modal';
import { Button } from './ui/Button';
import { cn } from '@/lib/utils';
import type { BacklogItem, ExecutorType, ModelProfile } from '@/types';
import { getExecutorDisplayName } from '@/hooks';
import {
  CheckIcon,
  CommandLineIcon,
  CpuChipIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline';

interface ExecutionSetupModalProps {
  isOpen: boolean;
  onClose: () => void;
  backlogItem: BacklogItem;
  models: ModelProfile[];
  onExecute: (instruction: string, executorType: ExecutorType, modelIds?: string[]) => void;
  isExecuting?: boolean;
}

const EXECUTOR_OPTIONS: { type: ExecutorType; description: string; icon: React.ReactNode }[] = [
  {
    type: 'claude_code',
    description: 'Use Claude Code CLI for comprehensive coding assistance',
    icon: <CommandLineIcon className="w-5 h-5" />,
  },
  {
    type: 'codex_cli',
    description: 'Use OpenAI Codex CLI for code generation',
    icon: <CommandLineIcon className="w-5 h-5" />,
  },
  {
    type: 'gemini_cli',
    description: 'Use Gemini CLI for AI-powered coding',
    icon: <CommandLineIcon className="w-5 h-5" />,
  },
  {
    type: 'patch_agent',
    description: 'Generate patches using selected LLM models',
    icon: <CpuChipIcon className="w-5 h-5" />,
  },
];

function formatInstructionFromBacklog(item: BacklogItem): string {
  const parts: string[] = [];

  // Title as the main task
  parts.push(`## Task: ${item.title}`);

  // Description
  if (item.description) {
    parts.push(`\n### Description\n${item.description}`);
  }

  // Target files
  if (item.target_files.length > 0) {
    parts.push(`\n### Target Files\n${item.target_files.map((f) => `- ${f}`).join('\n')}`);
  }

  // Subtasks
  const pendingSubtasks = item.subtasks.filter((st) => !st.completed);
  if (pendingSubtasks.length > 0) {
    parts.push(
      `\n### Subtasks\n${pendingSubtasks.map((st) => `- [ ] ${st.title}`).join('\n')}`
    );
  }

  // Implementation hint
  if (item.implementation_hint) {
    parts.push(`\n### Implementation Hint\n${item.implementation_hint}`);
  }

  return parts.join('\n');
}

export function ExecutionSetupModal({
  isOpen,
  onClose,
  backlogItem,
  models,
  onExecute,
  isExecuting = false,
}: ExecutionSetupModalProps) {
  const [selectedExecutor, setSelectedExecutor] = useState<ExecutorType>('claude_code');
  const [selectedModels, setSelectedModels] = useState<string[]>([]);
  const [instruction, setInstruction] = useState(() =>
    formatInstructionFromBacklog(backlogItem)
  );

  const isPatchAgent = selectedExecutor === 'patch_agent';
  const canExecute =
    instruction.trim() && (isPatchAgent ? selectedModels.length > 0 : true);

  // Handle executor selection - auto-select all models when switching to patch_agent
  const handleExecutorSelect = (executorType: ExecutorType) => {
    setSelectedExecutor(executorType);
    // Auto-select all models when switching to patch_agent and none are selected
    if (executorType === 'patch_agent' && selectedModels.length === 0 && models.length > 0) {
      setSelectedModels(models.map((m) => m.id));
    }
  };

  const handleExecute = () => {
    if (!canExecute) return;
    onExecute(
      instruction.trim(),
      selectedExecutor,
      isPatchAgent ? selectedModels : undefined
    );
  };

  const toggleModel = (modelId: string) => {
    setSelectedModels((prev) =>
      prev.includes(modelId)
        ? prev.filter((id) => id !== modelId)
        : [...prev, modelId]
    );
  };

  const selectAllModels = () => {
    if (selectedModels.length === models.length) {
      setSelectedModels([]);
    } else {
      setSelectedModels(models.map((m) => m.id));
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Start Execution"
      description={`Configure execution for: ${backlogItem.title}`}
      size="xl"
    >
      <ModalBody className="space-y-6">
        {/* Executor Selection */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-3">
            Select Executor
          </label>
          <div className="grid grid-cols-2 gap-3">
            {EXECUTOR_OPTIONS.map((option) => (
              <button
                key={option.type}
                onClick={() => handleExecutorSelect(option.type)}
                className={cn(
                  'flex items-start gap-3 p-3 rounded-lg border text-left transition-all',
                  selectedExecutor === option.type
                    ? 'bg-purple-900/30 border-purple-500'
                    : 'bg-gray-800/50 border-gray-700 hover:border-gray-600'
                )}
              >
                <div
                  className={cn(
                    'p-2 rounded-lg',
                    selectedExecutor === option.type
                      ? 'bg-purple-600 text-white'
                      : 'bg-gray-700 text-gray-400'
                  )}
                >
                  {option.icon}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-100">
                      {getExecutorDisplayName(option.type)}
                    </span>
                    {selectedExecutor === option.type && (
                      <CheckIcon className="w-4 h-4 text-purple-400" />
                    )}
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5">{option.description}</p>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Model Selection (only for patch_agent) */}
        {isPatchAgent && (
          <div>
            <div className="flex items-center justify-between mb-3">
              <label className="block text-sm font-medium text-gray-300">
                Select Models
              </label>
              {models.length > 1 && (
                <button
                  onClick={selectAllModels}
                  className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
                >
                  {selectedModels.length === models.length
                    ? 'Deselect all'
                    : 'Select all'}
                </button>
              )}
            </div>
            {models.length === 0 ? (
              <p className="text-sm text-gray-500 p-3 bg-gray-800/50 rounded-lg border border-gray-700">
                No models configured. Add models in Settings to use Patch Agent.
              </p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {models.map((model) => {
                  const isSelected = selectedModels.includes(model.id);
                  return (
                    <button
                      key={model.id}
                      onClick={() => toggleModel(model.id)}
                      className={cn(
                        'flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-all',
                        isSelected
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-300'
                      )}
                    >
                      {isSelected && <CheckIcon className="w-4 h-4" />}
                      {model.display_name || model.model_name}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Instruction */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Instruction
          </label>
          <div className="relative">
            <textarea
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              rows={12}
              className={cn(
                'w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg',
                'text-sm text-gray-100 font-mono',
                'focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent',
                'resize-none'
              )}
              placeholder="Enter your instruction..."
            />
            <button
              onClick={() => setInstruction(formatInstructionFromBacklog(backlogItem))}
              className="absolute top-2 right-2 px-2 py-1 text-xs text-gray-400 hover:text-gray-300 bg-gray-700 hover:bg-gray-600 rounded transition-colors"
            >
              Reset
            </button>
          </div>
          <p className="mt-1 text-xs text-gray-500">
            This instruction was auto-generated from the backlog item. Feel free to modify it.
          </p>
        </div>
      </ModalBody>

      <ModalFooter>
        <Button variant="ghost" onClick={onClose} disabled={isExecuting}>
          Cancel
        </Button>
        <Button
          variant="primary"
          onClick={handleExecute}
          disabled={!canExecute || isExecuting}
          isLoading={isExecuting}
          className="gap-2"
        >
          <SparklesIcon className="w-4 h-4" />
          {isExecuting ? 'Executing...' : 'Execute'}
        </Button>
      </ModalFooter>
    </Modal>
  );
}
