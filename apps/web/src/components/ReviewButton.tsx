'use client';

import { useState } from 'react';
import { MagnifyingGlassIcon } from '@heroicons/react/24/outline';
import { Button } from './ui/Button';
import { reviewsApi } from '@/lib/api';
import type { ExecutorType } from '@/types';

interface ReviewButtonProps {
  taskId: string;
  runIds: string[];
  executorType: ExecutorType;
  disabled?: boolean;
  onReviewCreated: (reviewId: string) => void;
  onError: (message: string) => void;
}

export function ReviewButton({
  taskId,
  runIds,
  executorType,
  disabled = false,
  onReviewCreated,
  onError,
}: ReviewButtonProps) {
  const [loading, setLoading] = useState(false);

  const handleClick = async () => {
    if (runIds.length === 0) {
      onError('No successful runs to review');
      return;
    }

    setLoading(true);
    try {
      const result = await reviewsApi.create(taskId, {
        target_run_ids: runIds,
        executor_type: executorType,
      });
      onReviewCreated(result.review_id);
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Failed to start review');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Button
      variant="secondary"
      size="sm"
      onClick={handleClick}
      disabled={disabled || loading || runIds.length === 0}
      isLoading={loading}
      className="flex items-center gap-1.5"
    >
      <MagnifyingGlassIcon className="w-4 h-4" />
      {loading ? 'Starting Review...' : 'Review Code'}
    </Button>
  );
}
