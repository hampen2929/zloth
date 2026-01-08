'use client';

import { useRef, useState, useCallback } from 'react';
import type { ExecutorType, ModelProfile } from '@/types';
import { cn } from '@/lib/utils';
import { useClickOutside, getExecutorDisplayName, isCLIExecutor } from '@/hooks';
import {
  ChevronDownIcon,
  CheckIcon,
  CpuChipIcon,
  CommandLineIcon,
} from '@heroicons/react/24/outline';

interface ExecutorSelectorProps {
  executorType: ExecutorType;
  selectedModels: string[];
  models: ModelProfile[];
  onExecutorChange: (executor: ExecutorType) => void;
  onModelToggle: (modelId: string) => void;
  onModelsChange: (modelIds: string[]) => void;
}

const CLI_OPTIONS: { type: ExecutorType; description: string }[] = [
  { type: 'claude_code', description: 'Use Claude Code CLI' },
  { type: 'codex_cli', description: 'Use OpenAI Codex CLI' },
  { type: 'gemini_cli', description: 'Use Google Gemini CLI' },
];

export function ExecutorSelector({
  executorType,
  selectedModels,
  models,
  onExecutorChange,
  onModelToggle,
  onModelsChange,
}: ExecutorSelectorProps) {
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useClickOutside(dropdownRef, () => setShowDropdown(false), showDropdown);

  const handleCLISelect = useCallback(
    (type: ExecutorType) => {
      onExecutorChange(type);
      onModelsChange([]);
      setShowDropdown(false);
    },
    [onExecutorChange, onModelsChange]
  );

  const handleModelSelect = useCallback(
    (modelId: string) => {
      onExecutorChange('patch_agent');
      onModelToggle(modelId);
    },
    [onExecutorChange, onModelToggle]
  );

  const getButtonLabel = () => {
    if (isCLIExecutor(executorType)) {
      return getExecutorDisplayName(executorType);
    }
    if (selectedModels.length === 0) return 'Select models';
    if (selectedModels.length === 1) {
      const model = models.find((m) => m.id === selectedModels[0]);
      return model?.display_name || model?.model_name || 'Select models';
    }
    return `${selectedModels.length} models selected`;
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setShowDropdown(!showDropdown)}
        className={cn(
          'flex items-center gap-2 text-sm transition-colors',
          'text-gray-400 hover:text-white',
          'focus:outline-none focus:ring-2 focus:ring-blue-500 rounded px-2 py-1'
        )}
      >
        {isCLIExecutor(executorType) ? (
          <CommandLineIcon className="w-4 h-4" />
        ) : (
          <CpuChipIcon className="w-4 h-4" />
        )}
        <span>{getButtonLabel()}</span>
        <ChevronDownIcon
          className={cn('w-4 h-4 transition-transform', showDropdown && 'rotate-180')}
        />
      </button>

      {showDropdown && (
        <div className="absolute bottom-full left-0 mb-2 w-72 bg-gray-800 border border-gray-700 rounded-lg shadow-xl overflow-hidden z-10 animate-in fade-in slide-in-from-bottom-2 duration-200 flex flex-col max-h-80">
          {/* Models Section (scrollable) */}
          <div className="flex-1 overflow-y-auto min-h-0">
            <div className="p-3 border-b border-gray-700 sticky top-0 bg-gray-800">
              <span className="text-xs text-gray-500 uppercase tracking-wider font-medium">
                Models
              </span>
            </div>
            {!models || models.length === 0 ? (
              <div className="p-4 text-center">
                <CpuChipIcon className="w-8 h-8 text-gray-600 mx-auto mb-2" />
                <p className="text-gray-500 text-sm">No models configured</p>
                <p className="text-gray-600 text-xs mt-1">Add models in Settings</p>
              </div>
            ) : (
              models.map((model) => {
                const isSelected = selectedModels.includes(model.id);
                return (
                  <button
                    key={model.id}
                    onClick={() => handleModelSelect(model.id)}
                    className={cn(
                      'w-full px-3 py-2.5 text-left flex items-center gap-3',
                      'hover:bg-gray-700 transition-colors',
                      'focus:outline-none focus:bg-gray-700'
                    )}
                  >
                    <div
                      className={cn(
                        'w-4 h-4 rounded border flex items-center justify-center flex-shrink-0',
                        isSelected ? 'bg-blue-600 border-blue-600' : 'border-gray-600'
                      )}
                    >
                      {isSelected && <CheckIcon className="w-3 h-3 text-white" />}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-gray-100 text-sm font-medium truncate">
                        {model.display_name || model.model_name}
                      </div>
                      <div className="text-gray-500 text-xs">{model.provider}</div>
                    </div>
                  </button>
                );
              })
            )}
          </div>

          {/* CLI Options (fixed at bottom) */}
          <div className="border-t border-gray-700 flex-shrink-0">
            <div className="p-3 border-b border-gray-700">
              <span className="text-xs text-gray-500 uppercase tracking-wider font-medium">
                CLI Agents
              </span>
            </div>
            {CLI_OPTIONS.map((option) => (
              <button
                key={option.type}
                onClick={() => handleCLISelect(option.type)}
                className={cn(
                  'w-full px-3 py-2.5 text-left flex items-center gap-3',
                  'hover:bg-gray-700 transition-colors',
                  'focus:outline-none focus:bg-gray-700'
                )}
              >
                <div
                  className={cn(
                    'w-4 h-4 rounded-full border flex items-center justify-center flex-shrink-0',
                    executorType === option.type
                      ? 'bg-blue-600 border-blue-600'
                      : 'border-gray-600'
                  )}
                >
                  {executorType === option.type && <CheckIcon className="w-3 h-3 text-white" />}
                </div>
                <div className="min-w-0 flex-1 flex items-center gap-2">
                  <CommandLineIcon className="w-4 h-4 text-gray-400" />
                  <div>
                    <div className="text-gray-100 text-sm font-medium">
                      {getExecutorDisplayName(option.type)}
                    </div>
                    <div className="text-gray-500 text-xs">{option.description}</div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
