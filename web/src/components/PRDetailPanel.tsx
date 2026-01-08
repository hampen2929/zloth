'use client';

import { useState } from 'react';
import { prsApi } from '@/lib/api';
import type { PR } from '@/types';
import { Button } from './ui/Button';
import { useToast } from './ui/Toast';
import { cn } from '@/lib/utils';
import {
  DocumentTextIcon,
  ArrowTopRightOnSquareIcon,
  ArrowPathIcon,
  ClipboardDocumentIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
} from '@heroicons/react/24/outline';

interface PRDetailPanelProps {
  pr: PR;
  taskId: string;
  onUpdate?: () => void;
}

export function PRDetailPanel({
  pr,
  taskId,
  onUpdate,
}: PRDetailPanelProps) {
  const [regenerating, setRegenerating] = useState(false);
  const [currentPR, setCurrentPR] = useState(pr);
  const { success, error } = useToast();

  const handleRegenerateDescription = async () => {
    setRegenerating(true);
    try {
      const updatedPR = await prsApi.regenerateDescription(taskId, pr.id);
      setCurrentPR(updatedPR);
      success('PR description regenerated successfully!');
      onUpdate?.();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to regenerate description';
      error(message);
    } finally {
      setRegenerating(false);
    }
  };

  const getStatusBadge = () => {
    switch (currentPR.status) {
      case 'open':
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium bg-green-500/20 text-green-400">
            <CheckCircleIcon className="w-3.5 h-3.5" />
            Open
          </span>
        );
      case 'merged':
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium bg-purple-500/20 text-purple-400">
            <CheckCircleIcon className="w-3.5 h-3.5" />
            Merged
          </span>
        );
      case 'closed':
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium bg-red-500/20 text-red-400">
            <XCircleIcon className="w-3.5 h-3.5" />
            Closed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium bg-gray-500/20 text-gray-400">
            <ClockIcon className="w-3.5 h-3.5" />
            {currentPR.status}
          </span>
        );
    }
  };

  const copyToClipboard = async (text: string, label: string) => {
    try {
      if (navigator.clipboard) {
        await navigator.clipboard.writeText(text);
      } else {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
      }
      success(`${label} copied!`);
    } catch {
      error('Failed to copy to clipboard');
    }
  };

  return (
    <div className="flex flex-col h-full bg-gray-900 rounded-lg border border-gray-800">
      {/* Header */}
      <div className="p-4 border-b border-gray-800">
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0">
            <h2 className="font-semibold text-gray-100 flex items-center gap-2">
              <DocumentTextIcon className="w-5 h-5 text-blue-400 flex-shrink-0" />
              <span className="truncate">#{currentPR.number} {currentPR.title}</span>
            </h2>
            <div className="flex items-center gap-2 mt-2 flex-wrap">
              {getStatusBadge()}
              <button
                onClick={() => copyToClipboard(currentPR.branch, 'Branch name')}
                className="flex items-center gap-1 text-xs font-mono text-purple-400 hover:text-purple-300 transition-colors"
                title="Click to copy branch name"
              >
                <span>{currentPR.branch}</span>
                <ClipboardDocumentIcon className="w-3 h-3" />
              </button>
            </div>
          </div>
          <a
            href={currentPR.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-blue-400 hover:text-blue-300 hover:bg-blue-500/10 rounded-md transition-colors ml-2"
          >
            View on GitHub
            <ArrowTopRightOnSquareIcon className="w-4 h-4" />
          </a>
        </div>
      </div>

      {/* Description Section */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="mb-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-medium text-gray-200">Description</h3>
            <Button
              variant="secondary"
              size="sm"
              onClick={handleRegenerateDescription}
              disabled={regenerating}
              className="flex items-center gap-1.5"
            >
              <ArrowPathIcon className={cn('w-4 h-4', regenerating && 'animate-spin')} />
              {regenerating ? 'Regenerating...' : 'Regenerate Description'}
            </Button>
          </div>

          {currentPR.body ? (
            <div className="prose prose-sm prose-invert max-w-none">
              <div className="p-4 bg-gray-800/50 rounded-lg text-gray-300 text-sm leading-relaxed whitespace-pre-wrap">
                {currentPR.body}
              </div>
            </div>
          ) : (
            <div className="p-4 bg-gray-800/30 rounded-lg text-gray-500 text-sm text-center">
              No description provided. Click &quot;Regenerate Description&quot; to generate one automatically.
            </div>
          )}
        </div>

        {/* PR Info */}
        <div className="border-t border-gray-800 pt-4">
          <h3 className="font-medium text-gray-200 mb-3">Details</h3>
          <div className="space-y-2 text-sm">
            <div className="flex items-center justify-between py-2 border-b border-gray-800/50">
              <span className="text-gray-400">Branch</span>
              <button
                onClick={() => copyToClipboard(currentPR.branch, 'Branch name')}
                className="font-mono text-gray-300 hover:text-gray-100 flex items-center gap-1.5"
              >
                {currentPR.branch}
                <ClipboardDocumentIcon className="w-3.5 h-3.5 text-gray-500" />
              </button>
            </div>
            <div className="flex items-center justify-between py-2 border-b border-gray-800/50">
              <span className="text-gray-400">Latest Commit</span>
              <button
                onClick={() => copyToClipboard(currentPR.latest_commit, 'Commit SHA')}
                className="font-mono text-gray-300 hover:text-gray-100 flex items-center gap-1.5"
              >
                {currentPR.latest_commit.slice(0, 7)}
                <ClipboardDocumentIcon className="w-3.5 h-3.5 text-gray-500" />
              </button>
            </div>
            <div className="flex items-center justify-between py-2 border-b border-gray-800/50">
              <span className="text-gray-400">Created</span>
              <span className="text-gray-300">
                {new Date(currentPR.created_at).toLocaleString()}
              </span>
            </div>
            <div className="flex items-center justify-between py-2">
              <span className="text-gray-400">Updated</span>
              <span className="text-gray-300">
                {new Date(currentPR.updated_at).toLocaleString()}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
