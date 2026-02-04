'use client';

import React, { useState } from 'react';
import { Modal, ModalBody, ModalFooter } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import type { PR, DecisionCreate, RiskLevel } from '@/types';
import { decisionsApi } from '@/lib/api';
import {
  CheckCircleIcon,
  ExclamationTriangleIcon,
  ShieldExclamationIcon,
} from '@heroicons/react/24/outline';

interface MergeDecisionModalProps {
  isOpen: boolean;
  onClose: () => void;
  taskId: string;
  pr: PR;
  riskLevel?: RiskLevel;
  riskReason?: string;
  onSuccess?: () => void;
}

const RISK_CONFIG: Record<RiskLevel, { icon: React.ElementType; color: string; label: string }> = {
  low: { icon: CheckCircleIcon, color: 'green', label: 'Low Risk' },
  medium: { icon: ExclamationTriangleIcon, color: 'yellow', label: 'Medium Risk' },
  high: { icon: ShieldExclamationIcon, color: 'red', label: 'High Risk' },
};

export function MergeDecisionModal({
  isOpen,
  onClose,
  taskId,
  pr,
  riskLevel = 'medium',
  riskReason,
  onSuccess,
}: MergeDecisionModalProps) {
  const [reason, setReason] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const risk = RISK_CONFIG[riskLevel];
  const RiskIcon = risk.icon;

  const handleSubmit = async () => {
    if (!reason.trim()) {
      setError('Merge reason is required');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const data: DecisionCreate = {
        decision_type: 'merge',
        reason: reason.trim(),
        pr_id: pr.id,
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

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Record Merge Decision"
      description="Document the reason for merging this PR"
      size="md"
    >
      <ModalBody className="space-y-6">
        {/* PR Info */}
        <div className="bg-purple-900/20 border border-purple-800/50 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-purple-400 font-medium">PR #{pr.number}</p>
              <p className="text-gray-200 mt-1">{pr.title}</p>
            </div>
            <a
              href={pr.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-400 hover:text-blue-300 text-sm"
            >
              View on GitHub
            </a>
          </div>
        </div>

        {/* Risk Level */}
        <div
          className={`bg-${risk.color}-900/20 border border-${risk.color}-800/50 rounded-lg p-4`}
          style={{
            backgroundColor:
              riskLevel === 'low'
                ? 'rgba(34, 197, 94, 0.1)'
                : riskLevel === 'high'
                ? 'rgba(239, 68, 68, 0.1)'
                : 'rgba(234, 179, 8, 0.1)',
            borderColor:
              riskLevel === 'low'
                ? 'rgba(34, 197, 94, 0.3)'
                : riskLevel === 'high'
                ? 'rgba(239, 68, 68, 0.3)'
                : 'rgba(234, 179, 8, 0.3)',
          }}
        >
          <div className="flex items-center gap-2">
            <RiskIcon
              className={`h-5 w-5 ${
                riskLevel === 'low'
                  ? 'text-green-400'
                  : riskLevel === 'high'
                  ? 'text-red-400'
                  : 'text-yellow-400'
              }`}
            />
            <span
              className={`font-medium ${
                riskLevel === 'low'
                  ? 'text-green-400'
                  : riskLevel === 'high'
                  ? 'text-red-400'
                  : 'text-yellow-400'
              }`}
            >
              {risk.label}
            </span>
          </div>
          {riskReason && <p className="text-gray-400 text-sm mt-2">{riskReason}</p>}
        </div>

        {/* High Risk Warning */}
        {riskLevel === 'high' && (
          <div className="bg-red-900/30 border border-red-700 rounded-lg p-4">
            <p className="text-red-300 font-medium">
              This is a high-risk merge. Please ensure:
            </p>
            <ul className="text-red-400 text-sm mt-2 list-disc list-inside space-y-1">
              <li>All CI checks have passed</li>
              <li>Code has been reviewed by a team member</li>
              <li>No security vulnerabilities have been introduced</li>
              <li>Changes have been tested in a staging environment</li>
            </ul>
          </div>
        )}

        {/* Merge Reason */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Merge Reason <span className="text-red-400">*</span>
          </label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Why are you approving this merge? (e.g., All checks passed, code reviewed and approved)"
            rows={3}
            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-200 placeholder-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

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
        <Button
          onClick={handleSubmit}
          disabled={isSubmitting}
          className={riskLevel === 'high' ? 'bg-red-600 hover:bg-red-700' : ''}
        >
          {isSubmitting ? 'Recording...' : 'Approve & Merge'}
        </Button>
      </ModalFooter>
    </Modal>
  );
}
