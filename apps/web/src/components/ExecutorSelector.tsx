'use client';

import { useRef, useState, useCallback } from 'react';
import type { ExecutorType, ModelProfile } from '@/types';
import { cn } from '@/lib/utils';
import { useClickOutside, getExecutorDisplayName } from '@/hooks';
import {
  ChevronDownIcon,
  CheckIcon,
  CpuChipIcon,
  CommandLineIcon,
} from '@heroicons/react/24/outline';

interface ExecutorSelectorProps {
  selectedCLIs: ExecutorType[];  // Selected CLI executor types
  selectedModels: string[];
  models: ModelProfile[];
  onCLIToggle: (cli: ExecutorType) => void;
  onCLIsChange: (clis: ExecutorType[]) => void;
  onModelToggle: (modelId: string) => void;
  onModelsChange: (modelIds: string[]) => void;
}

const CLI_OPTIONS: { type: ExecutorType; description: string }[] = [
  { type: 'claude_code', description: 'Use Claude Code CLI' },
  { type: 'codex_cli', description: 'Use OpenAI Codex CLI' },
  { type: 'gemini_cli', description: 'Use Google Gemini CLI' },
];

export function ExecutorSelector({
  selectedCLIs,
  selectedModels,
  models,
  onCLIToggle,
  // onCLIsChange and onModelsChange available for batch operations
  onModelToggle,
}: ExecutorSelectorProps) {
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useClickOutside(dropdownRef, () => setShowDropdown(false), showDropdown);

  const handleCLIToggle = useCallback(
    (type: ExecutorType) => {
      onCLIToggle(type);
    },
    [onCLIToggle]
  );

  const handleModelSelect = useCallback(
    (modelId: string) => {
      onModelToggle(modelId);
    },
    [onModelToggle]
  );

  const getButtonLabel = () => {
    const cliCount = selectedCLIs.length;
    const modelCount = selectedModels.length;

    if (cliCount === 0 && modelCount === 0) {
      return 'Select executors';
    }

    const parts: string[] = [];

    // CLI labels
    if (cliCount === 1) {
      parts.push(getExecutorDisplayName(selectedCLIs[0]));
    } else if (cliCount > 1) {
      parts.push(`${cliCount} CLIs`);
    }

    // Model labels
    if (modelCount === 1) {
      const model = models.find((m) => m.id === selectedModels[0]);
      parts.push(model?.display_name || model?.model_name || '1 model');
    } else if (modelCount > 1) {
      parts.push(`${modelCount} models`);
    }

    return parts.join(' + ');
  };

  const hasCLI = selectedCLIs.length > 0;
  const hasModel = selectedModels.length > 0;

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
        {hasCLI && hasModel ? (
          <div className="flex items-center gap-1">
            <CommandLineIcon className="w-4 h-4" />
            <span className="text-gray-600">+</span>
            <CpuChipIcon className="w-4 h-4" />
          </div>
        ) : hasCLI ? (
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
        <div className="absolute top-full left-0 mt-2 w-72 bg-gray-800 border border-gray-700 rounded-lg shadow-xl overflow-hidden z-10 animate-in fade-in slide-in-from-top-2 duration-200 flex flex-col max-h-80">
          {/* CLI Options (at top) - checkboxes for multi-select */}
          <div className="flex-shrink-0">
            <div className="p-3 border-b border-gray-700">
              <span className="text-xs text-gray-500 uppercase tracking-wider font-medium">
                CLI Agents
              </span>
            </div>
            {CLI_OPTIONS.map((option) => {
              const isSelected = selectedCLIs.includes(option.type);
              return (
                <button
                  key={option.type}
                  onClick={() => handleCLIToggle(option.type)}
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
              );
            })}
          </div>

          {/* Models Section (scrollable, at bottom) */}
          <div className="flex-1 overflow-y-auto min-h-0 border-t border-gray-700">
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
        </div>
      )}
    </div>
  );
}
