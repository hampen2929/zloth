'use client';

import { useState } from 'react';
import useSWR from 'swr';
import { executorsApi } from '@/lib/api';
import type { CLIStatus } from '@/types';
import { Button } from './ui/Button';
import { cn } from '@/lib/utils';
import {
  CheckCircleIcon,
  XCircleIcon,
  ArrowPathIcon,
  CommandLineIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';

function CLIStatusCard({ status }: { status: CLIStatus }) {
  return (
    <div
      className={cn(
        'p-4 rounded-lg border transition-colors',
        status.available
          ? 'bg-green-900/10 border-green-800/50 hover:border-green-700/50'
          : 'bg-red-900/10 border-red-800/50 hover:border-red-700/50'
      )}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          {status.available ? (
            <CheckCircleIcon className="w-6 h-6 text-green-400 flex-shrink-0" />
          ) : (
            <XCircleIcon className="w-6 h-6 text-red-400 flex-shrink-0" />
          )}
          <div>
            <h4 className="font-medium text-gray-100">{status.display_name}</h4>
            <span
              className={cn(
                'text-xs font-medium px-2 py-0.5 rounded',
                status.available
                  ? 'bg-green-900/30 text-green-400'
                  : 'bg-red-900/30 text-red-400'
              )}
            >
              {status.available ? 'Available' : 'Unavailable'}
            </span>
          </div>
        </div>
      </div>

      <div className="mt-3 space-y-2 text-sm">
        <div className="flex items-start gap-2">
          <span className="text-gray-500 w-24 flex-shrink-0">Config Path:</span>
          <code className="text-gray-300 bg-gray-800/50 px-2 py-0.5 rounded text-xs font-mono break-all">
            {status.configured_path}
          </code>
        </div>

        {status.resolved_path && (
          <div className="flex items-start gap-2">
            <span className="text-gray-500 w-24 flex-shrink-0">Resolved:</span>
            <code className="text-gray-300 bg-gray-800/50 px-2 py-0.5 rounded text-xs font-mono break-all">
              {status.resolved_path}
            </code>
          </div>
        )}

        {status.version && (
          <div className="flex items-start gap-2">
            <span className="text-gray-500 w-24 flex-shrink-0">Version:</span>
            <span className="text-gray-300 text-xs">{status.version}</span>
          </div>
        )}

        {status.error && (
          <div className="flex items-start gap-2 mt-2">
            <ExclamationTriangleIcon className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
            <span className="text-red-400 text-xs">{status.error}</span>
          </div>
        )}
      </div>
    </div>
  );
}

export default function ExecutorsTab() {
  const { data, error, isLoading, mutate } = useSWR(
    'executors-status',
    executorsApi.getStatus
  );
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await mutate();
    } finally {
      setRefreshing(false);
    }
  };

  const availableCount = data?.executors.filter((e) => e.available).length ?? 0;
  const totalCount = data?.executors.length ?? 0;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-100">CLI Executors</h3>
          <p className="text-sm text-gray-400 mt-1">
            Status of CLI tools available for code execution
          </p>
        </div>
        <Button
          onClick={handleRefresh}
          variant="secondary"
          size="sm"
          isLoading={refreshing}
          leftIcon={<ArrowPathIcon className="w-4 h-4" />}
        >
          Refresh
        </Button>
      </div>

      {/* Summary */}
      {data && (
        <div className="mb-4 p-3 bg-gray-800/30 border border-gray-700 rounded-lg">
          <div className="flex items-center gap-2">
            <CommandLineIcon className="w-5 h-5 text-gray-400" />
            <span className="text-sm text-gray-300">
              <span className="font-medium text-green-400">{availableCount}</span>
              <span className="text-gray-500"> / {totalCount}</span>
              {' '}executors available
            </span>
          </div>
        </div>
      )}

      {/* Loading state */}
      {isLoading && (
        <div className="flex items-center justify-center py-8">
          <ArrowPathIcon className="w-6 h-6 text-gray-400 animate-spin" />
          <span className="ml-2 text-gray-400">Checking CLI status...</span>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="flex items-center gap-2 p-3 bg-red-900/20 border border-red-800/50 rounded-lg text-red-400 text-sm">
          <ExclamationTriangleIcon className="w-4 h-4 flex-shrink-0" />
          Failed to check CLI status. Please try again.
        </div>
      )}

      {/* CLI status cards */}
      {data && (
        <div className="space-y-3">
          {data.executors.map((status) => (
            <CLIStatusCard key={status.name} status={status} />
          ))}
        </div>
      )}

      {/* Help text */}
      <div className="mt-6 p-4 bg-gray-800/20 border border-gray-700 rounded-lg">
        <h4 className="text-sm font-medium text-gray-300 mb-2">Configuration</h4>
        <p className="text-xs text-gray-500 mb-3">
          CLI paths can be configured via environment variables:
        </p>
        <div className="font-mono text-xs text-gray-400 space-y-1 bg-gray-800/50 p-3 rounded">
          <div>ZLOTH_CLAUDE_CLI_PATH=&lt;path_or_command&gt;</div>
          <div>ZLOTH_CODEX_CLI_PATH=&lt;path_or_command&gt;</div>
          <div>ZLOTH_GEMINI_CLI_PATH=&lt;path_or_command&gt;</div>
        </div>
        <p className="text-xs text-gray-500 mt-3">
          If not set, the default command names (claude, codex, gemini) are used and searched in PATH.
        </p>
      </div>
    </div>
  );
}
