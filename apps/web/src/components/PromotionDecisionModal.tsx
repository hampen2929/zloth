'use client';

import React, { useState, useMemo } from 'react';
import { Modal, ModalBody, ModalFooter } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import type { Run, DecisionCreate, ExcludedPathReason } from '@/types';
import { decisionsApi } from '@/lib/api';
import { DocumentPlusIcon, XMarkIcon } from '@heroicons/react/24/outline';

interface PromotionDecisionModalProps {
  isOpen: boolean;
  onClose: () => void;
  taskId: string;
  run: Run;
  prId?: string;
  onSuccess?: () => void;
}

export function PromotionDecisionModal({
  isOpen,
  onClose,
  taskId,
  run,
  prId,
  onSuccess,
}: PromotionDecisionModalProps) {
  const [reason, setReason] = useState('');
  const [excludedPaths, setExcludedPaths] = useState<ExcludedPathReason[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const allPaths = useMemo(() => {
    return run.files_changed.map((f) => f.path);
  }, [run.files_changed]);

  const includedPaths = useMemo(() => {
    const excludedSet = new Set(excludedPaths.map((e) => e.path));
    return allPaths.filter((p) => !excludedSet.has(p));
  }, [allPaths, excludedPaths]);

  const handleSubmit = async () => {
    if (!reason.trim()) {
      setError('Promotion reason is required');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const data: DecisionCreate = {
        decision_type: 'promotion',
        reason: reason.trim(),
        run_id: run.id,
        pr_id: prId,
        included_paths: includedPaths,
        excluded_paths: excludedPaths.map((e) => e.path),
        excluded_reasons: excludedPaths,
      };

      await decisionsApi.create(taskId, data);
      onSuccess?.();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to record decision');
    } finally {
      setIsSubmitting(false);
    }
  };

  const togglePathExclusion = (path: string) => {
    const existing = excludedPaths.find((e) => e.path === path);
    if (existing) {
      setExcludedPaths((prev) => prev.filter((e) => e.path !== path));
    } else {
      setExcludedPaths((prev) => [...prev, { path, reason: '' }]);
    }
  };

  const updateExclusionReason = (path: string, reason: string) => {
    setExcludedPaths((prev) =>
      prev.map((e) => (e.path === path ? { ...e, reason } : e))
    );
  };

  const getFileMetrics = (path: string) => {
    const file = run.files_changed.find((f) => f.path === path);
    if (!file) return null;
    return { added: file.added_lines, removed: file.removed_lines };
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Record PR Promotion Decision"
      description="Document the scope and reason for creating this PR"
      size="xl"
    >
      <ModalBody className="space-y-6">
        {/* Run Summary */}
        <div className="bg-blue-900/20 border border-blue-800/50 rounded-lg p-4">
          <div className="flex items-center gap-2 text-blue-400 mb-2">
            <DocumentPlusIcon className="h-5 w-5" />
            <span className="font-medium">Promoting to PR</span>
          </div>
          <p className="text-gray-200">
            {run.model_name || run.executor_type || 'Run'}
          </p>
          <p className="text-sm text-gray-400 mt-1">
            {run.files_changed.length} files changed
          </p>
        </div>

        {/* Promotion Reason */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Promotion Reason <span className="text-red-400">*</span>
          </label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Why are you promoting this run to a PR? (e.g., Implements the feature correctly, ready for review)"
            rows={3}
            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-200 placeholder-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        {/* File Selection */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Files to Include ({includedPaths.length} of {allPaths.length})
          </label>
          <div className="bg-gray-800/50 rounded-lg border border-gray-700 max-h-64 overflow-y-auto">
            {allPaths.map((path) => {
              const isExcluded = excludedPaths.some((e) => e.path === path);
              const metrics = getFileMetrics(path);
              const exclusion = excludedPaths.find((e) => e.path === path);

              return (
                <div
                  key={path}
                  className={`border-b border-gray-700 last:border-b-0 ${
                    isExcluded ? 'bg-red-900/20' : ''
                  }`}
                >
                  <div className="flex items-center gap-3 px-4 py-2">
                    <input
                      type="checkbox"
                      checked={!isExcluded}
                      onChange={() => togglePathExclusion(path)}
                      className="h-4 w-4 rounded border-gray-600 bg-gray-700 text-blue-600 focus:ring-blue-500"
                    />
                    <span
                      className={`flex-1 text-sm font-mono ${
                        isExcluded ? 'text-gray-500 line-through' : 'text-gray-200'
                      }`}
                    >
                      {path}
                    </span>
                    {metrics && (
                      <span className="text-xs">
                        <span className="text-green-400">+{metrics.added}</span>
                        <span className="text-gray-500 mx-1">/</span>
                        <span className="text-red-400">-{metrics.removed}</span>
                      </span>
                    )}
                  </div>
                  {isExcluded && (
                    <div className="px-4 pb-2 pl-11">
                      <input
                        type="text"
                        value={exclusion?.reason || ''}
                        onChange={(e) => updateExclusionReason(path, e.target.value)}
                        placeholder="Reason for exclusion"
                        className="w-full px-2 py-1 text-sm bg-gray-700 border border-gray-600 rounded text-gray-200 placeholder-gray-500"
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Excluded Summary */}
        {excludedPaths.length > 0 && (
          <div className="bg-yellow-900/20 border border-yellow-800/50 rounded-lg p-3">
            <p className="text-yellow-400 text-sm">
              {excludedPaths.length} file(s) will be excluded from this PR
            </p>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="bg-red-900/20 border border-red-800/50 rounded-lg p-3 text-red-400 text-sm">
            {error}
          </div>
        )}
      </ModalBody>

      <ModalFooter>
        <Button variant="ghost" onClick={onClose} disabled={isSubmitting}>
          Cancel
        </Button>
        <Button onClick={handleSubmit} disabled={isSubmitting}>
          {isSubmitting ? 'Recording...' : 'Record & Promote'}
        </Button>
      </ModalFooter>
    </Modal>
  );
}
