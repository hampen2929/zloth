'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { tasksApi, runsApi } from '@/lib/api';
import type { Message, ModelProfile, ExecutorType, ImageAttachment } from '@/types';
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
  PhotoIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';

interface PendingMessage {
  id: string;
  content: string;
  status: 'pending' | 'error';
  errorMessage?: string;
}

interface AttachedImage {
  id: string;
  file: File;
  preview: string;  // Data URL for preview
}

// Image upload constants
const MAX_IMAGES = 10;
const MAX_IMAGE_SIZE = 10 * 1024 * 1024; // 10MB
const ALLOWED_TYPES = ['image/png', 'image/jpeg', 'image/gif', 'image/webp'];

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
  // Support multiple CLI selection
  const [selectedCLIs, setSelectedCLIs] = useState<ExecutorType[]>(
    executorType !== 'patch_agent' ? [executorType] : []
  );
  const [usePatchAgent, setUsePatchAgent] = useState(executorType === 'patch_agent');
  const [loading, setLoading] = useState(false);
  const [pendingMessages, setPendingMessages] = useState<PendingMessage[]>([]);
  const [attachedImages, setAttachedImages] = useState<AttachedImage[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { success, error } = useToast();

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, pendingMessages]);

  // Remove pending message when real message arrives
  useEffect(() => {
    if (pendingMessages.length > 0 && messages.length > 0) {
      const lastPending = pendingMessages[pendingMessages.length - 1];
      const matchingMessage = messages.find(
        (m) => m.role === 'user' && m.content === lastPending.content
      );
      if (matchingMessage) {
        setPendingMessages((prev) => prev.filter((p) => p.id !== lastPending.id));
      }
    }
  }, [messages, pendingMessages]);

  // Select all models by default if none specified
  useEffect(() => {
    if (models.length > 0 && selectedModels.length === 0 && !initialModelIds) {
      setSelectedModels(models.map((m) => m.id));
    }
  }, [models, selectedModels.length, initialModelIds]);

  // Update executor type from props
  useEffect(() => {
    if (executorType === 'patch_agent') {
      setUsePatchAgent(true);
    } else {
      setSelectedCLIs((prev) => (prev.includes(executorType) ? prev : [executorType]));
    }
  }, [executorType]);

  // Auto-resize textarea based on content
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      const newHeight = Math.min(textarea.scrollHeight, 200); // Max height of 200px
      textarea.style.height = `${newHeight}px`;
    }
  }, [input]);

  // Process image files and add to attachments
  const processImageFiles = useCallback((files: FileList | File[]) => {
    const fileArray = Array.from(files);
    const validFiles: File[] = [];

    for (const file of fileArray) {
      // Check type
      if (!ALLOWED_TYPES.includes(file.type)) {
        error(`Unsupported image type: ${file.type}. Allowed: PNG, JPEG, GIF, WebP`);
        continue;
      }
      // Check size
      if (file.size > MAX_IMAGE_SIZE) {
        error(`Image too large: ${file.name}. Maximum size is 10MB.`);
        continue;
      }
      validFiles.push(file);
    }

    // Check total count
    const totalImages = attachedImages.length + validFiles.length;
    if (totalImages > MAX_IMAGES) {
      error(`Maximum ${MAX_IMAGES} images allowed per message.`);
      const allowedCount = MAX_IMAGES - attachedImages.length;
      validFiles.splice(allowedCount);
    }

    // Create preview URLs and add to state
    for (const file of validFiles) {
      const reader = new FileReader();
      reader.onload = (e) => {
        const preview = e.target?.result as string;
        const newImage: AttachedImage = {
          id: `img-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
          file,
          preview,
        };
        setAttachedImages((prev) => [...prev, newImage]);
      };
      reader.readAsDataURL(file);
    }
  }, [attachedImages.length, error]);

  // Handle file input change
  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      processImageFiles(e.target.files);
      // Reset input to allow selecting the same file again
      e.target.value = '';
    }
  }, [processImageFiles]);

  // Handle paste event for clipboard images
  const handlePaste = useCallback((e: React.ClipboardEvent) => {
    const items = e.clipboardData.items;
    const imageFiles: File[] = [];

    for (const item of Array.from(items)) {
      if (item.type.startsWith('image/')) {
        const file = item.getAsFile();
        if (file) {
          imageFiles.push(file);
        }
      }
    }

    if (imageFiles.length > 0) {
      e.preventDefault(); // Prevent pasting as text
      processImageFiles(imageFiles);
    }
  }, [processImageFiles]);

  // Remove attached image
  const removeImage = useCallback((imageId: string) => {
    setAttachedImages((prev) => prev.filter((img) => img.id !== imageId));
  }, []);

  // Convert attached images to ImageAttachment format for API
  const convertImagesToAttachments = async (): Promise<ImageAttachment[]> => {
    const attachments: ImageAttachment[] = [];

    for (const img of attachedImages) {
      // Read file as base64
      const base64 = await new Promise<string>((resolve) => {
        const reader = new FileReader();
        reader.onload = () => {
          const result = reader.result as string;
          // Remove data URL prefix (e.g., "data:image/png;base64,")
          const base64Data = result.split(',')[1];
          resolve(base64Data);
        };
        reader.readAsDataURL(img.file);
      });

      attachments.push({
        id: img.id,
        filename: img.file.name || 'pasted-image',
        content_type: img.file.type,
        size_bytes: img.file.size,
        data: base64,
      });
    }

    return attachments;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    // Validate: need at least CLIs or models selected
    const hasExecutors = selectedCLIs.length > 0 || (usePatchAgent && selectedModels.length > 0);
    if (!hasExecutors) return;

    // Optimistic UI: Clear input and show pending message immediately
    const pendingId = `pending-${Date.now()}`;
    const messageContent = input.trim();
    const currentImages = [...attachedImages]; // Save current images before clearing

    setPendingMessages((prev) => [
      ...prev,
      { id: pendingId, content: messageContent, status: 'pending' },
    ]);
    setInput('');
    setAttachedImages([]); // Clear images
    setLoading(true);

    try {
      // Convert images to API format
      const imageAttachments = currentImages.length > 0
        ? await convertImagesToAttachments()
        : undefined;

      // Add user message and get the message ID
      const message = await tasksApi.addMessage(taskId, {
        role: 'user',
        content: messageContent,
        images: imageAttachments,
      });

      // Build executor_types array
      const executorTypesToRun: ExecutorType[] = [...selectedCLIs];
      if (usePatchAgent && selectedModels.length > 0) {
        executorTypesToRun.push('patch_agent');
      }

      // Create runs with executor_types for parallel execution
      await runsApi.create(taskId, {
        instruction: messageContent,
        executor_types: executorTypesToRun,
        model_ids: usePatchAgent && selectedModels.length > 0 ? selectedModels : undefined,
        message_id: message.id,
        images: imageAttachments,
      });

      // Show success message
      const parts: string[] = [];
      if (selectedCLIs.length === 1) {
        const cliNames: Record<string, string> = {
          claude_code: 'Claude Code',
          codex_cli: 'Codex',
          gemini_cli: 'Gemini CLI',
        };
        parts.push(cliNames[selectedCLIs[0]] || selectedCLIs[0]);
      } else if (selectedCLIs.length > 1) {
        parts.push(`${selectedCLIs.length} CLIs`);
      }
      if (usePatchAgent && selectedModels.length > 0) {
        parts.push(`${selectedModels.length} model${selectedModels.length > 1 ? 's' : ''}`);
      }
      success(`Started ${parts.join(' + ')} run${executorTypesToRun.length > 1 ? 's' : ''}`);

      onRunsCreated();
    } catch (err) {
      console.error('Failed to create runs:', err);
      // Mark pending message as error and restore input
      setPendingMessages((prev) =>
        prev.map((p) =>
          p.id === pendingId
            ? { ...p, status: 'error', errorMessage: 'Failed to send. Click to retry.' }
            : p
        )
      );
      error('Failed to create runs. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const retryPendingMessage = (pendingId: string, content: string) => {
    // Remove the failed message and restore the content to input
    setPendingMessages((prev) => prev.filter((p) => p.id !== pendingId));
    setInput(content);
  };

  const dismissPendingMessage = (pendingId: string) => {
    setPendingMessages((prev) => prev.filter((p) => p.id !== pendingId));
  };

  const toggleModel = (modelId: string) => {
    setSelectedModels((prev) =>
      prev.includes(modelId)
        ? prev.filter((id) => id !== modelId)
        : [...prev, modelId]
    );
  };

  const toggleCLI = (cli: ExecutorType) => {
    setSelectedCLIs((prev) =>
      prev.includes(cli)
        ? prev.filter((c) => c !== cli)
        : [...prev, cli]
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
          <>
            {messages.map((msg) => (
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
                  {msg.images && msg.images.length > 0 && (
                    <span className="flex items-center gap-1 text-gray-600">
                      <PhotoIcon className="w-3 h-3" />
                      {msg.images.length} image{msg.images.length > 1 ? 's' : ''}
                    </span>
                  )}
                </div>
                {/* Image attachments */}
                {msg.images && msg.images.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-2">
                    {msg.images.map((img) => (
                      <a
                        key={img.id}
                        href={`data:${img.content_type};base64,${img.data}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block"
                      >
                        <img
                          src={`data:${img.content_type};base64,${img.data}`}
                          alt={img.filename}
                          className="max-w-[200px] max-h-[150px] object-contain rounded border border-gray-600 hover:border-blue-500 transition-colors cursor-pointer"
                        />
                      </a>
                    ))}
                  </div>
                )}
                <div className="text-sm whitespace-pre-wrap text-gray-200">
                  {msg.content}
                </div>
              </div>
            ))}
            {/* Pending messages (optimistic UI) */}
            {pendingMessages.map((pending) => (
              <div
                key={pending.id}
                className={cn(
                  'p-3 rounded-lg animate-in fade-in duration-200',
                  pending.status === 'pending'
                    ? 'bg-blue-900/20 border border-blue-800/50'
                    : 'bg-red-900/20 border border-red-800/50'
                )}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2 text-xs text-gray-500">
                    <UserIcon className="w-4 h-4" />
                    <span className="font-medium">User</span>
                    {pending.status === 'pending' && (
                      <span className="text-blue-400 animate-pulse">Sending...</span>
                    )}
                  </div>
                  {pending.status === 'error' && (
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => retryPendingMessage(pending.id, pending.content)}
                        className="text-xs text-blue-400 hover:text-blue-300 underline"
                      >
                        Retry
                      </button>
                      <button
                        onClick={() => dismissPendingMessage(pending.id)}
                        className="text-xs text-gray-500 hover:text-gray-400"
                      >
                        Dismiss
                      </button>
                    </div>
                  )}
                </div>
                <div className="text-sm whitespace-pre-wrap text-gray-200">
                  {pending.content}
                </div>
                {pending.status === 'error' && pending.errorMessage && (
                  <div className="mt-2 text-xs text-red-400">
                    {pending.errorMessage}
                  </div>
                )}
              </div>
            ))}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Executor Type & Model Selection */}
      <div className="border-t border-gray-800 p-3 space-y-3">
        {/* CLI Agents Selection (checkboxes for multi-select) */}
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

        {/* Models Toggle & Selection */}
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
          )}
        </div>

        {/* Info message when CLIs are selected */}
        {selectedCLIs.length > 0 && (
          <div className="flex items-center gap-2 p-2 bg-purple-900/20 rounded-lg border border-purple-800/30">
            <CommandLineIcon className="w-4 h-4 text-purple-400" />
            <span className="text-xs text-purple-300">
              {selectedCLIs.length === 1
                ? 'CLI will execute in an isolated worktree'
                : `${selectedCLIs.length} CLIs will execute in parallel worktrees`}
            </span>
          </div>
        )}
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="border-t border-gray-800 p-3">
        {/* Image preview area */}
        {attachedImages.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-3 p-2 bg-gray-800/50 rounded-lg border border-gray-700">
            {attachedImages.map((img) => (
              <div key={img.id} className="relative group">
                <img
                  src={img.preview}
                  alt={img.file.name || 'Attached image'}
                  className="w-16 h-16 object-cover rounded border border-gray-600"
                />
                <button
                  type="button"
                  onClick={() => removeImage(img.id)}
                  className={cn(
                    'absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full',
                    'bg-red-600 hover:bg-red-500 text-white',
                    'flex items-center justify-center',
                    'opacity-0 group-hover:opacity-100 transition-opacity'
                  )}
                  aria-label={`Remove ${img.file.name || 'image'}`}
                >
                  <XMarkIcon className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="flex gap-2">
          {/* Hidden file input */}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/png,image/jpeg,image/gif,image/webp"
            multiple
            onChange={handleFileSelect}
            className="hidden"
            aria-hidden="true"
          />

          {/* Image upload button */}
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={loading || attachedImages.length >= MAX_IMAGES}
            className={cn(
              'self-end p-2 rounded transition-colors',
              'bg-gray-800 border border-gray-700',
              'hover:bg-gray-700 hover:border-gray-600',
              'disabled:opacity-50 disabled:cursor-not-allowed',
              'focus:outline-none focus:ring-2 focus:ring-blue-500'
            )}
            title={`Attach images (${attachedImages.length}/${MAX_IMAGES})`}
            aria-label="Attach images"
          >
            <PhotoIcon className="w-5 h-5 text-gray-400" />
          </button>

          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onPaste={handlePaste}
            placeholder="Enter your instructions... (paste images with Ctrl/Cmd+V)"
            rows={1}
            className={cn(
              'flex-1 px-3 py-2 bg-gray-800 border border-gray-700 rounded resize-none',
              'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
              'text-sm text-gray-100 placeholder:text-gray-500',
              'disabled:opacity-50 disabled:cursor-not-allowed',
              'transition-colors min-h-[42px] max-h-[200px] overflow-y-auto'
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
            disabled={loading || !input.trim() || (selectedCLIs.length === 0 && (!usePatchAgent || selectedModels.length === 0))}
            isLoading={loading}
            className="self-end"
          >
            Run
          </Button>
        </div>
        <div className="flex items-center justify-between mt-2">
          <span className="text-xs text-gray-500">
            {getShortcutText('Enter')} to submit
            {attachedImages.length > 0 && ` • ${attachedImages.length} image${attachedImages.length > 1 ? 's' : ''} attached`}
          </span>
          <span className="text-xs text-gray-500">
            {(() => {
              const parts: string[] = [];
              if (selectedCLIs.length > 0) {
                parts.push(`${selectedCLIs.length} CLI${selectedCLIs.length > 1 ? 's' : ''}`);
              }
              if (usePatchAgent && selectedModels.length > 0) {
                parts.push(`${selectedModels.length} model${selectedModels.length > 1 ? 's' : ''}`);
              }
              return parts.length > 0 ? parts.join(' + ') + ' selected' : 'Select executors';
            })()}
          </span>
        </div>
      </form>
    </div>
  );
}
