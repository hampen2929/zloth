'use client';

import { cn } from '@/lib/utils';
import type { RunStatus } from '@/types';
import {
  CheckCircleIcon,
  ExclamationTriangleIcon,
  ArrowPathIcon,
  ClockIcon,
  XCircleIcon,
} from '@heroicons/react/24/outline';

export interface StatusBadgeProps {
  status: RunStatus;
  className?: string;
  showLabel?: boolean;
}

interface StatusConfig {
  icon: React.ReactNode;
  label: string;
  className: string;
}

const STATUS_CONFIGS: Record<RunStatus, StatusConfig> = {
  succeeded: {
    icon: <CheckCircleIcon className="w-3 h-3" />,
    label: 'Completed',
    className: 'bg-green-500/20 text-green-400',
  },
  failed: {
    icon: <ExclamationTriangleIcon className="w-3 h-3" />,
    label: 'Failed',
    className: 'bg-red-500/20 text-red-400',
  },
  running: {
    icon: <ArrowPathIcon className="w-3 h-3 animate-spin" />,
    label: 'Running',
    className: 'bg-yellow-500/20 text-yellow-400',
  },
  queued: {
    icon: <ClockIcon className="w-3 h-3" />,
    label: 'Queued',
    className: 'bg-gray-500/20 text-gray-400',
  },
  canceled: {
    icon: <XCircleIcon className="w-3 h-3" />,
    label: 'Canceled',
    className: 'bg-gray-500/20 text-gray-400',
  },
};

/**
 * Status badge component for displaying run status
 */
export function StatusBadge({ status, className, showLabel = true }: StatusBadgeProps) {
  const config = STATUS_CONFIGS[status];
  if (!config) return null;

  return (
    <span
      role="status"
      aria-label={`Status: ${config.label}`}
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium',
        config.className,
        className
      )}
    >
      {config.icon}
      {showLabel && config.label}
    </span>
  );
}

/**
 * Get the border color class for a run status
 */
export function getStatusBorderColor(status: RunStatus, isCLI: boolean = false): string {
  if (isCLI) {
    return 'border-purple-800/50';
  }

  switch (status) {
    case 'succeeded':
      return 'border-green-800/50';
    case 'failed':
      return 'border-red-800/50';
    case 'running':
      return 'border-yellow-800/50';
    default:
      return 'border-gray-700';
  }
}

/**
 * Get the background color class for a run status
 */
export function getStatusBackgroundColor(status: RunStatus, isCLI: boolean = false): string {
  if (isCLI) {
    return 'bg-purple-900/10';
  }

  return 'bg-gray-800/50';
}
