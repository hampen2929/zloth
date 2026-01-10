'use client';

/**
 * RoleStatusBadge - Common status badge for all AI Roles
 *
 * Displays execution status with appropriate colors and icons.
 * Used by RunResultCard, ReviewResultCard, etc.
 */

import { cn } from '@/lib/utils';
import type { RoleExecutionStatus } from '@/types/role';
import { STATUS_CONFIGS } from '@/types/role';

interface RoleStatusBadgeProps {
  status: RoleExecutionStatus;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export function RoleStatusBadge({
  status,
  size = 'md',
  className,
}: RoleStatusBadgeProps) {
  const config = STATUS_CONFIGS[status];

  const colorClasses: Record<typeof config.color, string> = {
    gray: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
    yellow: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    green: 'bg-green-500/20 text-green-400 border-green-500/30',
    red: 'bg-red-500/20 text-red-400 border-red-500/30',
  };

  const sizeClasses: Record<typeof size, string> = {
    sm: 'text-xs px-1.5 py-0.5',
    md: 'text-xs px-2 py-1',
    lg: 'text-sm px-2.5 py-1',
  };

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded border font-medium',
        colorClasses[config.color],
        sizeClasses[size],
        className
      )}
    >
      {config.animate && (
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-current opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-current" />
        </span>
      )}
      {config.label}
    </span>
  );
}

export default RoleStatusBadge;
