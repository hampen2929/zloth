'use client';

import { useState, useRef, useEffect } from 'react';
import { tasksApi, runsApi } from '@/lib/api';
import type { Message, ModelProfile, ExecutorType } from '@/types';
import { Button } from './ui/Button';
import { useToast } from './ui/Toast';
import { getShortcutText, isModifierPressed } from '@/lib/platform';
import { cn } from '@/lib/utils';
import {
  UserIcon,
  CpuChipIcon,
  ChatBubbleLeftIcon,
  CheckIcon,
  CommandLineIcon,
} from '@heroicons/react/24/outline';

interface ChatPanelProps {
  taskId: string;
  messages: Message[];
  models: ModelProfile[];
  executorType?: ExecutorType;
  initialModelIds?: string[];
  onRunsCreated: () => void;
}

export function ChatPanel({
  taskId,
  messages,
  models,
  executorType = 'patch_agent',
  initialModelIds,
  onRunsCreated,
}: ChatPanelProps) {
  const [input, setInput] = useState('');
  const [selectedModels, setSelectedModels] = useState<string[]>(initialModelIds || []);
  const [currentExecutor, setCurrentExecutor] = useState<ExecutorType>(executorType);
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { success, error } = useToast();

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Select all models by default if none specified
  useEffect(() => {
    if (models.length > 0 && selectedModels.length === 0 && !initialModelIds) {
      setSelectedModels(models.map((m) => m.id));
    }
  }, [models, selectedModels.length, initialModelIds]);

  // Update executor type from props
  useEffect(() => {
    setCurrentExecutor(executorType);
  }, [executorType]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    if (currentExecutor === 'patch_agent' && selectedModels.length === 0) return;

    setLoading(true);

    try {
      // Add user message
      await tasksApi.addMessage(taskId, {
        role: 'user',
        content: input.trim(),
      });

      // Create runs based on executor type
      if (currentExecutor === 'claude_code') {
        await runsApi.create(taskId, {
          instruction: input.trim(),
          executor_type: 'claude_code',
        });
        success('Started Claude Code run');
      } else {
        await runsApi.create(taskId, {
          instruction: input.trim(),
          model_ids: selectedModels,
          executor_type: 'patch_agent',
        });
        success(`Started ${selectedModels.length} run${selectedModels.length > 1 ? 's' : ''}`);
      }

      setInput('');
      onRunsCreated();
    } catch (err) {
      console.error('Failed to create runs:', err);
      error('Failed to create runs. Please try again.');
    } finally {
      setLoading(false);
    }
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
    <div className="flex flex-col h-full bg-gray-900 rounded-lg border border-gray-800">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center py-8">
            <ChatBubbleLeftIcon className="w-12 h-12 text-gray-700 mb-3" />
            <p className="text-gray-500 text-sm">
              Start by entering your instructions below.
            </p>
            <p className="text-gray-600 text-xs mt-1">
              Your messages and model responses will appear here.
            </p>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={cn(
                'p-3 rounded-lg animate-in fade-in duration-200',
                msg.role === 'user'
                  ? 'bg-blue-900/30 border border-blue-800'
                  : 'bg-gray-800'
              )}
            >
              <div className="flex items-center gap-2 text-xs text-gray-500 mb-2">
                {msg.role === 'user' ? (
                  <UserIcon className="w-4 h-4" />
                ) : (
                  <CpuChipIcon className="w-4 h-4" />
                )}
                <span className="capitalize font-medium">{msg.role}</span>
              </div>
              <div className="text-sm whitespace-pre-wrap text-gray-200">
                {msg.content}
              </div>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Executor Type & Model Selection */}
      <div className="border-t border-gray-800 p-3 space-y-3">
        {/* Executor Type Toggle */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">Executor:</span>
          <div className="flex items-center bg-gray-800 rounded-lg p-0.5">
            <button
              type="button"
              onClick={() => setCurrentExecutor('patch_agent')}
              className={cn(
                'flex items-center gap-1.5 px-2.5 py-1 rounded text-xs transition-colors',
                currentExecutor === 'patch_agent'
                  ? 'bg-gray-700 text-white'
                  : 'text-gray-400 hover:text-white'
              )}
            >
              <CpuChipIcon className="w-3.5 h-3.5" />
              <span>Models</span>
            </button>
            <button
              type="button"
              onClick={() => setCurrentExecutor('claude_code')}
              className={cn(
                'flex items-center gap-1.5 px-2.5 py-1 rounded text-xs transition-colors',
                currentExecutor === 'claude_code'
                  ? 'bg-gray-700 text-white'
                  : 'text-gray-400 hover:text-white'
              )}
            >
              <CommandLineIcon className="w-3.5 h-3.5" />
              <span>Claude Code</span>
            </button>
          </div>
        </div>

        {/* Model Selection (only for patch_agent) */}
        {currentExecutor === 'patch_agent' && (
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-gray-500">Select models to run:</span>
              {models.length > 1 && (
                <button
                  type="button"
                  onClick={selectAllModels}
                  className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
                >
                  {selectedModels.length === models.length ? 'Deselect all' : 'Select all'}
                </button>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              {models.length === 0 ? (
                <p className="text-gray-600 text-xs">
                  No models configured. Add models in Settings.
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
          </div>
        )}

        {/* Claude Code info */}
        {currentExecutor === 'claude_code' && (
          <div className="flex items-center gap-2 p-2 bg-purple-900/20 rounded-lg border border-purple-800/30">
            <CommandLineIcon className="w-4 h-4 text-purple-400" />
            <span className="text-xs text-purple-300">
              Claude Code will execute in an isolated worktree
            </span>
          </div>
        )}
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="border-t border-gray-800 p-3">
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Enter your instructions..."
            rows={3}
            className={cn(
              'flex-1 px-3 py-2 bg-gray-800 border border-gray-700 rounded resize-none',
              'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
              'text-sm text-gray-100 placeholder:text-gray-500',
              'disabled:opacity-50 disabled:cursor-not-allowed',
              'transition-colors'
            )}
            disabled={loading}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && isModifierPressed(e)) {
                handleSubmit(e);
              }
            }}
            aria-label="Instructions input"
          />
          <Button
            type="submit"
            disabled={loading || !input.trim() || (currentExecutor === 'patch_agent' && selectedModels.length === 0)}
            isLoading={loading}
            className="self-end"
          >
            Run
          </Button>
        </div>
        <div className="flex items-center justify-between mt-2">
          <span className="text-xs text-gray-500">
            {getShortcutText('Enter')} to submit
          </span>
          {currentExecutor === 'patch_agent' && selectedModels.length > 0 && (
            <span className="text-xs text-gray-500">
              {selectedModels.length} model{selectedModels.length > 1 ? 's' : ''} selected
            </span>
          )}
          {currentExecutor === 'claude_code' && (
            <span className="text-xs text-purple-400">
              Claude Code CLI
            </span>
          )}
        </div>
      </form>
    </div>
  );
}
