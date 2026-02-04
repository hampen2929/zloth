'use client';

import React from 'react';
import type { Evidence, CIEvidence, MetricsEvidence, ReviewEvidence, RefsEvidence } from '@/types';
import {
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  CodeBracketIcon,
  DocumentCheckIcon,
  LinkIcon,
} from '@heroicons/react/24/outline';

interface EvidenceDisplayProps {
  evidence: Evidence | Record<string, unknown>;
  compact?: boolean;
}

function CIEvidenceCard({ ci }: { ci: CIEvidence }) {
  const statusConfig = {
    passed: { icon: CheckCircleIcon, color: 'green', label: 'Passed' },
    failed: { icon: XCircleIcon, color: 'red', label: 'Failed' },
    pending: { icon: ClockIcon, color: 'yellow', label: 'Pending' },
  };

  const config = statusConfig[ci.status as keyof typeof statusConfig] || statusConfig.pending;
  const StatusIcon = config.icon;

  return (
    <div className="bg-gray-800/50 rounded-lg p-3 border border-gray-700">
      <div className="flex items-center gap-2 mb-2">
        <StatusIcon
          className={`h-4 w-4 ${
            config.color === 'green'
              ? 'text-green-400'
              : config.color === 'red'
              ? 'text-red-400'
              : 'text-yellow-400'
          }`}
        />
        <span className="text-sm font-medium text-gray-300">CI Status</span>
        <span
          className={`ml-auto px-2 py-0.5 text-xs rounded-full ${
            config.color === 'green'
              ? 'bg-green-900/50 text-green-400'
              : config.color === 'red'
              ? 'bg-red-900/50 text-red-400'
              : 'bg-yellow-900/50 text-yellow-400'
          }`}
        >
          {config.label}
        </span>
      </div>

      {ci.check_names.length > 0 && (
        <div className="text-xs text-gray-500">
          {ci.check_names.length} check(s): {ci.check_names.slice(0, 3).join(', ')}
          {ci.check_names.length > 3 && ` +${ci.check_names.length - 3} more`}
        </div>
      )}

      {ci.failed_checks.length > 0 && (
        <div className="mt-2 space-y-1">
          {ci.failed_checks.map((check, i) => (
            <div key={i} className="text-xs text-red-400">
              <span className="font-medium">{check.name}:</span>{' '}
              <span className="text-red-300">{check.reason}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function MetricsEvidenceCard({ metrics }: { metrics: MetricsEvidence }) {
  return (
    <div className="bg-gray-800/50 rounded-lg p-3 border border-gray-700">
      <div className="flex items-center gap-2 mb-2">
        <CodeBracketIcon className="h-4 w-4 text-blue-400" />
        <span className="text-sm font-medium text-gray-300">Code Metrics</span>
      </div>
      <div className="flex gap-4">
        <div>
          <span className="text-lg font-semibold text-gray-200">
            {metrics.files_changed}
          </span>
          <span className="text-xs text-gray-500 ml-1">files</span>
        </div>
        <div>
          <span className="text-lg font-semibold text-green-400">
            +{metrics.lines_changed}
          </span>
          <span className="text-xs text-gray-500 ml-1">lines</span>
        </div>
      </div>
    </div>
  );
}

function ReviewEvidenceCard({ review }: { review: ReviewEvidence }) {
  return (
    <div className="bg-gray-800/50 rounded-lg p-3 border border-gray-700">
      <div className="flex items-center gap-2 mb-2">
        <DocumentCheckIcon className="h-4 w-4 text-purple-400" />
        <span className="text-sm font-medium text-gray-300">Review Status</span>
      </div>
      <div className="flex gap-4">
        <div>
          <span className="text-lg font-semibold text-green-400">
            {review.approvals}
          </span>
          <span className="text-xs text-gray-500 ml-1">approvals</span>
        </div>
        <div>
          <span className="text-lg font-semibold text-orange-400">
            {review.change_requests}
          </span>
          <span className="text-xs text-gray-500 ml-1">changes requested</span>
        </div>
      </div>
    </div>
  );
}

function RefsEvidenceCard({ refs }: { refs: RefsEvidence }) {
  return (
    <div className="bg-gray-800/50 rounded-lg p-3 border border-gray-700">
      <div className="flex items-center gap-2 mb-2">
        <LinkIcon className="h-4 w-4 text-cyan-400" />
        <span className="text-sm font-medium text-gray-300">References</span>
      </div>
      <div className="space-y-1">
        {refs.pr_url && (
          <a
            href={refs.pr_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-blue-400 hover:text-blue-300 block truncate"
          >
            Pull Request
          </a>
        )}
        {refs.ci_url && (
          <a
            href={refs.ci_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-blue-400 hover:text-blue-300 block truncate"
          >
            CI Workflow
          </a>
        )}
      </div>
    </div>
  );
}

export function EvidenceDisplay({ evidence, compact = false }: EvidenceDisplayProps) {
  // Parse evidence if it's a plain object
  const parsed = evidence as Evidence;

  const hasAnyEvidence =
    parsed.ci_results || parsed.metrics || parsed.review_summary || parsed.refs;

  if (!hasAnyEvidence) {
    return (
      <div className="text-sm text-gray-500 italic">
        No evidence collected
      </div>
    );
  }

  if (compact) {
    // Compact inline display
    return (
      <div className="flex flex-wrap gap-2">
        {parsed.ci_results && (
          <span
            className={`px-2 py-0.5 text-xs rounded-full ${
              parsed.ci_results.status === 'passed'
                ? 'bg-green-900/50 text-green-400'
                : parsed.ci_results.status === 'failed'
                ? 'bg-red-900/50 text-red-400'
                : 'bg-yellow-900/50 text-yellow-400'
            }`}
          >
            CI: {parsed.ci_results.status}
          </span>
        )}
        {parsed.metrics && (
          <span className="px-2 py-0.5 text-xs bg-blue-900/50 text-blue-400 rounded-full">
            {parsed.metrics.files_changed} files
          </span>
        )}
        {parsed.review_summary && (
          <span className="px-2 py-0.5 text-xs bg-purple-900/50 text-purple-400 rounded-full">
            {parsed.review_summary.approvals} approvals
          </span>
        )}
      </div>
    );
  }

  // Full display
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {parsed.ci_results && <CIEvidenceCard ci={parsed.ci_results} />}
      {parsed.metrics && <MetricsEvidenceCard metrics={parsed.metrics} />}
      {parsed.review_summary && <ReviewEvidenceCard review={parsed.review_summary} />}
      {parsed.refs && (parsed.refs.pr_url || parsed.refs.ci_url) && (
        <RefsEvidenceCard refs={parsed.refs} />
      )}
    </div>
  );
}
