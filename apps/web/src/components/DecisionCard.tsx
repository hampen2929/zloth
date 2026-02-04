'use client';

import React, { useState } from 'react';
import type { Decision, Alternative, PromotionScope, OutcomeStatus } from '@/types';
import { EvidenceDisplay } from './EvidenceDisplay';
import { Button } from '@/components/ui/Button';
import { decisionsApi } from '@/lib/api';
import {
  CheckCircleIcon,
  XCircleIcon,
  QuestionMarkCircleIcon,
  UserIcon,
  CpuChipIcon,
  ShieldCheckIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  DocumentPlusIcon,
  ArrowsRightLeftIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline';

interface DecisionCardProps {
  decision: Decision;
  onOutcomeUpdate?: () => void;
}

const DECISION_TYPE_CONFIG = {
  selection: {
    icon: ArrowsRightLeftIcon,
    label: 'Run Selection',
    color: 'blue',
  },
  promotion: {
    icon: DocumentPlusIcon,
    label: 'PR Promotion',
    color: 'green',
  },
  merge: {
    icon: ArrowPathIcon,
    label: 'Merge',
    color: 'purple',
  },
};

const DECIDER_TYPE_CONFIG = {
  human: { icon: UserIcon, label: 'Human' },
  policy: { icon: ShieldCheckIcon, label: 'Policy' },
  ai: { icon: CpuChipIcon, label: 'AI' },
};

const RISK_LEVEL_CONFIG = {
  low: { color: 'green', label: 'Low Risk' },
  medium: { color: 'yellow', label: 'Medium Risk' },
  high: { color: 'red', label: 'High Risk' },
};

const OUTCOME_CONFIG = {
  good: { icon: CheckCircleIcon, color: 'green', label: 'Good Decision' },
  bad: { icon: XCircleIcon, color: 'red', label: 'Bad Decision' },
  unknown: { icon: QuestionMarkCircleIcon, color: 'gray', label: 'Not Evaluated' },
};

function AlternativesDisplay({ alternatives }: { alternatives: Alternative }) {
  if (alternatives.rejected_runs.length === 0) {
    return null;
  }

  return (
    <div className="mt-4">
      <h5 className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2">
        Rejected Alternatives
      </h5>
      <div className="space-y-2">
        {alternatives.rejected_runs.map((rejected) => (
          <div
            key={rejected.run_id}
            className="bg-red-900/20 border border-red-800/30 rounded p-2"
          >
            <div className="flex items-center gap-2">
              <XCircleIcon className="h-4 w-4 text-red-400" />
              <span className="text-sm text-gray-300 font-mono">
                {rejected.run_id.slice(0, 8)}
              </span>
            </div>
            {rejected.reason && (
              <p className="text-xs text-gray-400 mt-1 pl-6">{rejected.reason}</p>
            )}
          </div>
        ))}
      </div>

      {alternatives.comparison_axes.length > 0 && (
        <div className="mt-3">
          <span className="text-xs text-gray-500">Comparison axes: </span>
          <span className="text-xs text-gray-400">
            {alternatives.comparison_axes.join(', ')}
          </span>
        </div>
      )}
    </div>
  );
}

function ScopeDisplay({ scope }: { scope: PromotionScope }) {
  return (
    <div className="mt-4">
      <h5 className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2">
        Promotion Scope
      </h5>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <span className="text-xs text-green-400">
            {scope.included_paths.length} included
          </span>
          <div className="mt-1 max-h-20 overflow-y-auto">
            {scope.included_paths.slice(0, 5).map((path) => (
              <div key={path} className="text-xs text-gray-400 font-mono truncate">
                {path}
              </div>
            ))}
            {scope.included_paths.length > 5 && (
              <div className="text-xs text-gray-500">
                +{scope.included_paths.length - 5} more
              </div>
            )}
          </div>
        </div>
        {scope.excluded_paths.length > 0 && (
          <div>
            <span className="text-xs text-red-400">
              {scope.excluded_paths.length} excluded
            </span>
            <div className="mt-1 max-h-20 overflow-y-auto">
              {scope.excluded_reasons.slice(0, 3).map((item) => (
                <div key={item.path} className="text-xs">
                  <span className="text-gray-400 font-mono truncate block">
                    {item.path}
                  </span>
                  {item.reason && (
                    <span className="text-gray-500 italic">- {item.reason}</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export function DecisionCard({ decision, onOutcomeUpdate }: DecisionCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isUpdatingOutcome, setIsUpdatingOutcome] = useState(false);

  const typeConfig = DECISION_TYPE_CONFIG[decision.decision_type];
  const deciderConfig = DECIDER_TYPE_CONFIG[decision.decider_type];
  const riskConfig = decision.risk_level ? RISK_LEVEL_CONFIG[decision.risk_level] : null;
  const outcomeConfig = decision.outcome ? OUTCOME_CONFIG[decision.outcome] : null;

  const TypeIcon = typeConfig.icon;
  const DeciderIcon = deciderConfig.icon;

  const handleOutcomeUpdate = async (outcome: OutcomeStatus) => {
    setIsUpdatingOutcome(true);
    try {
      await decisionsApi.updateOutcome(decision.id, {
        outcome,
        reason: '',
        refs: [],
      });
      onOutcomeUpdate?.();
    } catch (err) {
      console.error('Failed to update outcome:', err);
    } finally {
      setIsUpdatingOutcome(false);
    }
  };

  const createdAt = new Date(decision.created_at);
  const formattedDate = createdAt.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });

  return (
    <div className="border border-gray-700 rounded-lg bg-gray-800/30 overflow-hidden">
      {/* Header */}
      <div
        className="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-800/50"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3">
          <div
            className={`p-2 rounded-lg ${
              typeConfig.color === 'blue'
                ? 'bg-blue-900/50'
                : typeConfig.color === 'green'
                ? 'bg-green-900/50'
                : 'bg-purple-900/50'
            }`}
          >
            <TypeIcon
              className={`h-5 w-5 ${
                typeConfig.color === 'blue'
                  ? 'text-blue-400'
                  : typeConfig.color === 'green'
                  ? 'text-green-400'
                  : 'text-purple-400'
              }`}
            />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-medium text-gray-200">{typeConfig.label}</span>
              <span className="text-xs text-gray-500">by</span>
              <div className="flex items-center gap-1 text-gray-400">
                <DeciderIcon className="h-3 w-3" />
                <span className="text-xs">{deciderConfig.label}</span>
              </div>
            </div>
            <p className="text-sm text-gray-400 line-clamp-1">{decision.reason}</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Risk Level */}
          {riskConfig && (
            <span
              className={`px-2 py-0.5 text-xs rounded-full ${
                riskConfig.color === 'green'
                  ? 'bg-green-900/50 text-green-400'
                  : riskConfig.color === 'red'
                  ? 'bg-red-900/50 text-red-400'
                  : 'bg-yellow-900/50 text-yellow-400'
              }`}
            >
              {riskConfig.label}
            </span>
          )}

          {/* Outcome */}
          {outcomeConfig && (
            <outcomeConfig.icon
              className={`h-5 w-5 ${
                outcomeConfig.color === 'green'
                  ? 'text-green-400'
                  : outcomeConfig.color === 'red'
                  ? 'text-red-400'
                  : 'text-gray-400'
              }`}
            />
          )}

          {/* Expand Icon */}
          {isExpanded ? (
            <ChevronUpIcon className="h-5 w-5 text-gray-400" />
          ) : (
            <ChevronDownIcon className="h-5 w-5 text-gray-400" />
          )}
        </div>
      </div>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="px-4 pb-4 border-t border-gray-700 pt-4 space-y-4">
          {/* Timestamp */}
          <div className="text-xs text-gray-500">{formattedDate}</div>

          {/* Full Reason */}
          <div>
            <h5 className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-1">
              Reason
            </h5>
            <p className="text-sm text-gray-300">{decision.reason}</p>
          </div>

          {/* Risk Level Reason */}
          {decision.risk_level_reason && (
            <div>
              <h5 className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-1">
                Risk Assessment
              </h5>
              <p className="text-sm text-gray-400">{decision.risk_level_reason}</p>
            </div>
          )}

          {/* Evidence */}
          <div>
            <h5 className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2">
              Evidence
            </h5>
            <EvidenceDisplay evidence={decision.evidence} />
          </div>

          {/* Alternatives (for selection) */}
          {decision.alternatives && (
            <AlternativesDisplay alternatives={decision.alternatives as Alternative} />
          )}

          {/* Scope (for promotion) */}
          {decision.scope && (
            <ScopeDisplay scope={decision.scope as PromotionScope} />
          )}

          {/* Outcome Update */}
          {!decision.outcome && (
            <div className="flex items-center gap-2 pt-4 border-t border-gray-700">
              <span className="text-sm text-gray-400">Rate this decision:</span>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => handleOutcomeUpdate('good')}
                disabled={isUpdatingOutcome}
                className="text-green-400 hover:bg-green-900/30"
              >
                Good
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => handleOutcomeUpdate('bad')}
                disabled={isUpdatingOutcome}
                className="text-red-400 hover:bg-red-900/30"
              >
                Bad
              </Button>
            </div>
          )}

          {/* Outcome Display */}
          {decision.outcome && (
            <div className="pt-4 border-t border-gray-700">
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-400">Outcome:</span>
                {outcomeConfig && (
                  <span
                    className={`flex items-center gap-1 ${
                      outcomeConfig.color === 'green'
                        ? 'text-green-400'
                        : outcomeConfig.color === 'red'
                        ? 'text-red-400'
                        : 'text-gray-400'
                    }`}
                  >
                    <outcomeConfig.icon className="h-4 w-4" />
                    {outcomeConfig.label}
                  </span>
                )}
              </div>
              {decision.outcome_reason && (
                <p className="text-sm text-gray-500 mt-1">{decision.outcome_reason}</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
