import { type ComponentType, type ReactNode } from 'react';
import { Button } from './Button';

interface EmptyStateAction {
  label: string;
  onClick: () => void;
  variant?: 'primary' | 'secondary' | 'ghost';
  icon?: ReactNode;
}

interface EmptyStateProps {
  icon: ComponentType<{ className?: string }>;
  title: string;
  description?: string;
  actions?: EmptyStateAction[];
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const sizeStyles = {
  sm: {
    container: 'py-6',
    icon: 'w-8 h-8',
    title: 'text-base',
    description: 'text-sm',
    gap: 'gap-2',
  },
  md: {
    container: 'py-12',
    icon: 'w-12 h-12',
    title: 'text-lg',
    description: 'text-sm',
    gap: 'gap-3',
  },
  lg: {
    container: 'py-16',
    icon: 'w-16 h-16',
    title: 'text-xl',
    description: 'text-base',
    gap: 'gap-4',
  },
};

export function EmptyState({
  icon: Icon,
  title,
  description,
  actions,
  size = 'md',
  className = '',
}: EmptyStateProps) {
  const styles = sizeStyles[size];

  return (
    <div
      className={`${styles.container} flex flex-col items-center justify-center text-center ${className}`}
      role="status"
      aria-label={title}
    >
      <Icon className={`${styles.icon} text-gray-600 mb-4`} aria-hidden="true" />
      <h3 className={`${styles.title} font-medium text-gray-300 mb-2`}>{title}</h3>
      {description && (
        <p className={`${styles.description} text-gray-500 max-w-sm mb-4`}>{description}</p>
      )}
      {actions && actions.length > 0 && (
        <div className={`flex ${styles.gap} flex-wrap justify-center`}>
          {actions.map((action, i) => (
            <Button
              key={i}
              variant={action.variant ?? (i === 0 ? 'primary' : 'secondary')}
              onClick={action.onClick}
              size="sm"
            >
              {action.icon}
              {action.label}
            </Button>
          ))}
        </div>
      )}
    </div>
  );
}

// Preset empty states for common scenarios
export function NoTasksEmptyState({ onCreateTask }: { onCreateTask: () => void }) {
  return (
    <EmptyState
      icon={({ className }) => (
        <svg
          className={className}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
          />
        </svg>
      )}
      title="No tasks yet"
      description="Create your first task to get started with zloth"
      actions={[{ label: 'New Task', onClick: onCreateTask }]}
    />
  );
}

export function NoRunsEmptyState() {
  return (
    <EmptyState
      icon={({ className }) => (
        <svg
          className={className}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"
          />
        </svg>
      )}
      title="No runs yet"
      description="Enter instructions to start a new run"
      size="sm"
    />
  );
}

export function NoResultsEmptyState({
  searchQuery,
  onClearSearch,
}: {
  searchQuery: string;
  onClearSearch: () => void;
}) {
  return (
    <EmptyState
      icon={({ className }) => (
        <svg
          className={className}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>
      )}
      title={`No results for "${searchQuery}"`}
      description="Try adjusting your search or filters"
      actions={[{ label: 'Clear search', onClick: onClearSearch, variant: 'secondary' }]}
      size="sm"
    />
  );
}

export function NoModelsEmptyState({ onAddModel }: { onAddModel: () => void }) {
  return (
    <EmptyState
      icon={({ className }) => (
        <svg
          className={className}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
          />
        </svg>
      )}
      title="No models configured"
      description="Add an API key to start using AI models"
      actions={[{ label: 'Add Model', onClick: onAddModel }]}
    />
  );
}

export function ErrorEmptyState({
  title = 'Something went wrong',
  description,
  onRetry,
}: {
  title?: string;
  description?: string;
  onRetry?: () => void;
}) {
  return (
    <EmptyState
      icon={({ className }) => (
        <svg
          className={className}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
          />
        </svg>
      )}
      title={title}
      description={description}
      actions={onRetry ? [{ label: 'Try again', onClick: onRetry, variant: 'secondary' }] : undefined}
    />
  );
}
