'use client';

/**
 * RoleResultCard - Common result card layout for all AI Roles
 *
 * Provides a consistent card structure with:
 * - Collapsible header with status badge
 * - Tab navigation
 * - Content area for role-specific content
 *
 * Used as a base by RunResultCard, ReviewResultCard, etc.
 */

import { useState, type ReactNode } from 'react';
import { ChevronDownIcon, ChevronUpIcon } from '@heroicons/react/24/outline';
import { cn } from '@/lib/utils';
import type { RoleExecutionStatus, RoleTab } from '@/types/role';
import { RoleStatusBadge } from './RoleStatusBadge';

interface RoleResultCardProps<T extends string = string> {
  /** Card title/role name */
  title: string;
  /** Optional subtitle (e.g., model name, executor name) */
  subtitle?: string;
  /** Current execution status */
  status: RoleExecutionStatus;
  /** Icon to display in header */
  icon?: ReactNode;
  /** Available tabs */
  tabs: RoleTab[];
  /** Currently active tab ID */
  activeTab: T;
  /** Tab change handler */
  onTabChange: (tab: T) => void;
  /** Whether to show the card content */
  defaultExpanded?: boolean;
  /** Content to render for the active tab */
  children: ReactNode;
  /** Additional CSS classes */
  className?: string;
  /** Header action buttons */
  headerActions?: ReactNode;
}

export function RoleResultCard<T extends string = string>({
  title,
  subtitle,
  status,
  icon,
  tabs,
  activeTab,
  onTabChange,
  defaultExpanded = true,
  children,
  className,
  headerActions,
}: RoleResultCardProps<T>) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  return (
    <div
      className={cn(
        'border border-gray-700 rounded-lg bg-gray-800 overflow-hidden',
        className
      )}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-gray-750 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3 min-w-0">
          {icon && (
            <div className="flex-shrink-0 text-gray-400">{icon}</div>
          )}
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-medium text-gray-200 truncate">
                {title}
              </span>
              <RoleStatusBadge status={status} size="sm" />
            </div>
            {subtitle && (
              <span className="text-xs text-gray-500 truncate block">
                {subtitle}
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {headerActions}
          <button
            type="button"
            className="p-1 text-gray-400 hover:text-gray-200 transition-colors"
            onClick={(e) => {
              e.stopPropagation();
              setIsExpanded(!isExpanded);
            }}
          >
            {isExpanded ? (
              <ChevronUpIcon className="w-5 h-5" />
            ) : (
              <ChevronDownIcon className="w-5 h-5" />
            )}
          </button>
        </div>
      </div>

      {/* Content */}
      {isExpanded && (
        <div className="border-t border-gray-700">
          {/* Tabs */}
          {tabs.length > 0 && (
            <div className="flex border-b border-gray-700 bg-gray-850">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  className={cn(
                    'flex items-center gap-2 px-4 py-2 text-sm font-medium transition-colors',
                    activeTab === tab.id
                      ? 'text-blue-400 border-b-2 border-blue-400 -mb-px'
                      : 'text-gray-400 hover:text-gray-200'
                  )}
                  onClick={(e) => {
                    e.stopPropagation();
                    onTabChange(tab.id as T);
                  }}
                >
                  {tab.icon && (
                    <tab.icon className="w-4 h-4" />
                  )}
                  {tab.label}
                </button>
              ))}
            </div>
          )}

          {/* Tab Content */}
          <div className="p-4">{children}</div>
        </div>
      )}
    </div>
  );
}

export default RoleResultCard;
