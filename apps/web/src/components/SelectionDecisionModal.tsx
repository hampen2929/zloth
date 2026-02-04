'use client';

import React, { useState } from 'react';
import { Modal, ModalBody, ModalFooter } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import type { Run, DecisionCreate } from '@/types';
import { decisionsApi } from '@/lib/api';
import { CheckCircleIcon, XCircleIcon } from '@heroicons/react/24/outline';

interface SelectionDecisionModalProps {
  isOpen: boolean;
  onClose: () => void;
  taskId: string;
  selectedRun: Run;
  rejectedRuns: Run[];
  onSuccess?: () => void;
}

const COMPARISON_AXES = [
  { id: 'ci_status', label: 'CI Status' },
  { id: 'metrics', label: 'Code Metrics' },
  { id: 'review', label: 'Review Score' },
  { id: 'file_scope', label: 'File Scope' },
  { id: 'implementation', label: 'Implementation Quality' },
];

export function SelectionDecisionModal({
  isOpen,
  onClose,
  taskId,
  selectedRun,
  rejectedRuns,
  onSuccess,
}: SelectionDecisionModalProps) {
  const [reason, setReason] = useState('');
  const [rejectionReasons, setRejectionReasons] = useState<Record<string, string>>({});
  const [selectedAxes, setSelectedAxes] = useState<string[]>(['metrics']);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!reason.trim()) {
      setError('Selection reason is required');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const data: DecisionCreate = {
        decision_type: 'selection',
        reason: reason.trim(),
        selected_run_id: selectedRun.id,
        rejected_run_ids: rejectedRuns.map((r) => r.id),
        rejection_reasons: rejectionReasons,
        comparison_axes: selectedAxes,
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

  const toggleAxis = (axisId: string) => {
    setSelectedAxes((prev) =>
      prev.includes(axisId) ? prev.filter((a) => a !== axisId) : [...prev, axisId]
    );
  };

  const getRunLabel = (run: Run) => {
    return run.model_name || run.executor_type || 'Run';
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Record Selection Decision"
      description="Document why this run was selected and others rejected"
      size="lg"
    >
      <ModalBody className="space-y-6">
        {/* Selected Run */}
        <div className="bg-green-900/20 border border-green-800/50 rounded-lg p-4">
          <div className="flex items-center gap-2 text-green-400 mb-2">
            <CheckCircleIcon className="h-5 w-5" />
            <span className="font-medium">Selected Run</span>
          </div>
          <p className="text-gray-200">{getRunLabel(selectedRun)}</p>
          <p className="text-sm text-gray-400 mt-1 line-clamp-2">
            {selectedRun.instruction}
          </p>
        </div>

        {/* Selection Reason */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Selection Reason <span className="text-red-400">*</span>
          </label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Why did you select this run? (e.g., Better implementation, cleaner code, passes all tests)"
            rows={3}
            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-200 placeholder-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        {/* Comparison Axes */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Comparison Criteria Used
          </label>
          <div className="flex flex-wrap gap-2">
            {COMPARISON_AXES.map((axis) => (
              <button
                key={axis.id}
                onClick={() => toggleAxis(axis.id)}
                className={`px-3 py-1.5 rounded-full text-sm transition-colors ${
                  selectedAxes.includes(axis.id)
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                }`}
              >
                {axis.label}
              </button>
            ))}
          </div>
        </div>

        {/* Rejected Runs */}
        {rejectedRuns.length > 0 && (
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Rejected Runs
            </label>
            <div className="space-y-3">
              {rejectedRuns.map((run) => (
                <div
                  key={run.id}
                  className="bg-red-900/20 border border-red-800/50 rounded-lg p-4"
                >
                  <div className="flex items-center gap-2 text-red-400 mb-2">
                    <XCircleIcon className="h-5 w-5" />
                    <span className="font-medium">{getRunLabel(run)}</span>
                  </div>
                  <Input
                    value={rejectionReasons[run.id] || ''}
                    onChange={(e) =>
                      setRejectionReasons((prev) => ({
                        ...prev,
                        [run.id]: e.target.value,
                      }))
                    }
                    placeholder="Reason for rejection (optional)"
                    className="bg-gray-800 border-gray-700"
                  />
                </div>
              ))}
            </div>
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
          {isSubmitting ? 'Recording...' : 'Record Decision'}
        </Button>
      </ModalFooter>
    </Modal>
  );
}
