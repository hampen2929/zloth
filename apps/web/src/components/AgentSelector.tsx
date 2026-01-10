'use client';

import { useState, useRef, useCallback } from 'react';
import type { ExecutorType } from '@/types';
import { cn } from '@/lib/utils';
import { useClickOutside } from '@/hooks';
import {
  ChevronDownIcon,
  CheckIcon,
  CommandLineIcon,
} from '@heroicons/react/24/outline';

interface AgentSelectorProps {
  selectedAgents: ExecutorType[];
  onAgentsChange: (agents: ExecutorType[]) => void;
  useMultipleAgents: boolean;
  onUseMultipleAgentsChange: (value: boolean) => void;
  disabled?: boolean;
}

const AGENT_OPTIONS: {
  type: ExecutorType;
  name: string;
  description: string;
  color: string;
}[] = [
  {
    type: 'claude_code',
    name: 'Claude Code',
    description: 'Anthropic Claude CLI',
    color: 'text-purple-400',
  },
  {
    type: 'codex_cli',
    name: 'Codex',
    description: 'OpenAI Codex CLI',
    color: 'text-green-400',
  },
  {
    type: 'gemini_cli',
    name: 'Gemini CLI',
    description: 'Google Gemini CLI',
    color: 'text-blue-400',
  },
];

export function AgentSelector({
  selectedAgents,
  onAgentsChange,
  useMultipleAgents,
  onUseMultipleAgentsChange,
  disabled = false,
}: AgentSelectorProps) {
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useClickOutside(dropdownRef, () => setShowDropdown(false), showDropdown);

  const toggleAgent = useCallback(
    (type: ExecutorType) => {
      if (useMultipleAgents) {
        // Multi-mode: toggle
        if (selectedAgents.includes(type)) {
          // Don't allow deselecting if it's the only one
          if (selectedAgents.length > 1) {
            onAgentsChange(selectedAgents.filter((a) => a !== type));
          }
        } else {
          onAgentsChange([...selectedAgents, type]);
        }
      } else {
        // Single mode: replace
        onAgentsChange([type]);
        setShowDropdown(false);
      }
    },
    [selectedAgents, onAgentsChange, useMultipleAgents]
  );

  const getDisplayText = () => {
    if (selectedAgents.length === 0) return 'Select agent';
    if (selectedAgents.length === 1) {
      return AGENT_OPTIONS.find((a) => a.type === selectedAgents[0])?.name || 'Select agent';
    }
    return `${selectedAgents.length} agents`;
  };

  return (
    <div className="flex items-center gap-3">
      {/* Agent Dropdown */}
      <div className="relative" ref={dropdownRef}>
        <button
          onClick={() => setShowDropdown(!showDropdown)}
          disabled={disabled}
          className={cn(
            'flex items-center gap-2 px-3 py-2 rounded-lg',
            'bg-gray-800 border border-gray-700',
            'text-sm text-gray-300 hover:text-white',
            'transition-colors',
            disabled && 'opacity-50 cursor-not-allowed'
          )}
        >
          <CommandLineIcon className="w-4 h-4" />
          <span className="truncate max-w-[150px]">{getDisplayText()}</span>
          <ChevronDownIcon
            className={cn('w-4 h-4 transition-transform', showDropdown && 'rotate-180')}
          />
        </button>

        {/* Dropdown */}
        {showDropdown && (
          <div className="absolute bottom-full left-0 mb-2 w-72 bg-gray-800 border border-gray-700 rounded-lg shadow-xl overflow-hidden z-20 animate-in fade-in slide-in-from-bottom-2 duration-200">
            {/* Agent List */}
            <div className="max-h-60 overflow-y-auto">
              {AGENT_OPTIONS.map((agent) => {
                const isSelected = selectedAgents.includes(agent.type);
                return (
                  <button
                    key={agent.type}
                    onClick={() => toggleAgent(agent.type)}
                    className={cn(
                      'w-full px-3 py-3 text-left flex items-center gap-3',
                      'hover:bg-gray-700 transition-colors',
                      'focus:outline-none focus:bg-gray-700'
                    )}
                  >
                    {/* Checkbox/Radio */}
                    <div
                      className={cn(
                        'w-5 h-5 flex items-center justify-center flex-shrink-0',
                        useMultipleAgents ? 'rounded border' : 'rounded-full border',
                        isSelected ? 'bg-blue-600 border-blue-600' : 'border-gray-600'
                      )}
                    >
                      {isSelected && <CheckIcon className="w-3 h-3 text-white" />}
                    </div>

                    {/* Agent Info */}
                    <div className="flex-1 min-w-0">
                      <div className={cn('text-sm font-medium', agent.color)}>{agent.name}</div>
                      <div className="text-xs text-gray-500">{agent.description}</div>
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Select all button (multi-mode only) */}
            {useMultipleAgents && (
              <div className="p-2 border-t border-gray-700 flex justify-between items-center">
                <span className="text-xs text-gray-500">
                  {selectedAgents.length} agent{selectedAgents.length !== 1 ? 's' : ''} selected
                </span>
                <button
                  onClick={() => {
                    if (selectedAgents.length === AGENT_OPTIONS.length) {
                      onAgentsChange([AGENT_OPTIONS[0].type]);
                    } else {
                      onAgentsChange(AGENT_OPTIONS.map((a) => a.type));
                    }
                  }}
                  className="text-xs text-blue-400 hover:text-blue-300"
                >
                  {selectedAgents.length === AGENT_OPTIONS.length ? 'Keep one' : 'Select all'}
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Multi-agent Toggle - always visible outside dropdown */}
      <label className="flex items-center gap-2 cursor-pointer">
        <span className="text-xs text-gray-400">Multi</span>
        <button
          type="button"
          disabled={disabled}
          onClick={() => {
            const newValue = !useMultipleAgents;
            onUseMultipleAgentsChange(newValue);
            // If switching to single mode and multiple agents selected, keep first
            if (!newValue && selectedAgents.length > 1) {
              onAgentsChange([selectedAgents[0]]);
            }
          }}
          className={cn(
            'w-9 h-5 rounded-full transition-colors relative',
            useMultipleAgents ? 'bg-green-600' : 'bg-gray-600',
            disabled && 'opacity-50 cursor-not-allowed'
          )}
        >
          <div
            className={cn(
              'w-3.5 h-3.5 bg-white rounded-full absolute top-0.5 transition-transform',
              useMultipleAgents ? 'translate-x-[18px]' : 'translate-x-1'
            )}
          />
        </button>
      </label>
    </div>
  );
}
