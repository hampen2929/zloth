'use client';

import { useState } from 'react';
import {
  LightBulbIcon,
  SparklesIcon,
  ChartBarIcon,
  ChatBubbleLeftRightIcon,
  ExclamationTriangleIcon,
  ClockIcon,
  CheckCircleIcon,
  ArrowTrendingUpIcon,
} from '@heroicons/react/24/outline';

type PeriodOption = '7d' | '30d' | '90d' | 'all';

const PERIOD_OPTIONS: { value: PeriodOption; label: string }[] = [
  { value: '7d', label: '7 Days' },
  { value: '30d', label: '30 Days' },
  { value: '90d', label: '90 Days' },
  { value: 'all', label: 'All Time' },
];

// Placeholder recommendations for UI preview
const PLACEHOLDER_RECOMMENDATIONS = [
  {
    id: 'rec_001',
    priority: 'high' as const,
    category: 'prompt_quality',
    title: 'Add test requirements to prompts',
    description:
      'Including test requirements in your initial prompt reduces iterations by 2.3 on average.',
    impact: '-2.3 iterations',
    icon: ChatBubbleLeftRightIcon,
  },
  {
    id: 'rec_002',
    priority: 'high' as const,
    category: 'executor_selection',
    title: 'Use Claude Code for authentication tasks',
    description:
      'Tasks related to authentication have 25% higher success rate when using Claude Code executor.',
    impact: '+25% success rate',
    icon: SparklesIcon,
  },
  {
    id: 'rec_003',
    priority: 'medium' as const,
    category: 'error_pattern',
    title: 'Break down database migration tasks',
    description:
      'Database migration tasks have 30% failure rate. Consider breaking into smaller steps.',
    impact: '-30% failure rate',
    icon: ExclamationTriangleIcon,
  },
  {
    id: 'rec_004',
    priority: 'medium' as const,
    category: 'time_optimization',
    title: 'Submit tasks during morning hours',
    description: 'Tasks created between 9-11 AM have 25% faster completion times.',
    impact: '-25% completion time',
    icon: ClockIcon,
  },
];

function PriorityBadge({ priority }: { priority: 'high' | 'medium' | 'low' }) {
  const colors = {
    high: 'bg-red-500/20 text-red-400',
    medium: 'bg-yellow-500/20 text-yellow-400',
    low: 'bg-blue-500/20 text-blue-400',
  };
  return (
    <span className={`px-2 py-0.5 text-xs rounded ${colors[priority]}`}>
      {priority.charAt(0).toUpperCase() + priority.slice(1)}
    </span>
  );
}

export default function AnalysisPage() {
  const [period, setPeriod] = useState<PeriodOption>('30d');

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <div className="border-b border-gray-700 bg-gray-800/50">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <LightBulbIcon className="h-6 w-6 text-yellow-400" />
              <h1 className="text-xl font-semibold">Prompt Analysis</h1>
              <span className="px-2 py-0.5 text-xs bg-blue-500/20 text-blue-400 rounded">
                Preview
              </span>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-400">Period:</span>
                <select
                  value={period}
                  onChange={(e) => setPeriod(e.target.value as PeriodOption)}
                  className="bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {PERIOD_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          <div className="bg-gradient-to-r from-purple-900/40 to-blue-900/40 border border-purple-700/50 rounded-xl p-6">
            <div className="flex items-center gap-2 mb-2">
              <ChatBubbleLeftRightIcon className="h-5 w-5 text-purple-400" />
              <span className="text-sm text-gray-400">Prompt Quality Score</span>
            </div>
            <div className="text-4xl font-bold text-white">72%</div>
            <div className="text-sm text-gray-400 mt-1">Based on 156 tasks analyzed</div>
          </div>

          <div className="bg-gradient-to-r from-green-900/40 to-teal-900/40 border border-green-700/50 rounded-xl p-6">
            <div className="flex items-center gap-2 mb-2">
              <CheckCircleIcon className="h-5 w-5 text-green-400" />
              <span className="text-sm text-gray-400">Success Rate</span>
            </div>
            <div className="text-4xl font-bold text-white">85%</div>
            <div className="text-sm text-green-400 mt-1">+5% from last period</div>
          </div>

          <div className="bg-gradient-to-r from-blue-900/40 to-cyan-900/40 border border-blue-700/50 rounded-xl p-6">
            <div className="flex items-center gap-2 mb-2">
              <ArrowTrendingUpIcon className="h-5 w-5 text-blue-400" />
              <span className="text-sm text-gray-400">Avg Iterations</span>
            </div>
            <div className="text-4xl font-bold text-white">3.2</div>
            <div className="text-sm text-blue-400 mt-1">-0.8 from last period</div>
          </div>
        </div>

        {/* Top Recommendations */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-4">
            <SparklesIcon className="h-5 w-5 text-yellow-400" />
            <h2 className="text-lg font-semibold">Top Recommendations</h2>
          </div>
          <div className="space-y-3">
            {PLACEHOLDER_RECOMMENDATIONS.map((rec) => (
              <div
                key={rec.id}
                className="bg-gray-800 border border-gray-700 rounded-lg p-4 hover:border-gray-600 transition-colors"
              >
                <div className="flex items-start gap-4">
                  <div className="p-2 bg-gray-700 rounded-lg">
                    <rec.icon className="h-5 w-5 text-gray-300" />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="font-medium text-white">{rec.title}</h3>
                      <PriorityBadge priority={rec.priority} />
                    </div>
                    <p className="text-sm text-gray-400 mb-2">{rec.description}</p>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-500">Impact:</span>
                      <span className="text-xs text-green-400 font-medium">{rec.impact}</span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Analysis Categories */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Prompt Quality Analysis */}
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-6">
            <div className="flex items-center gap-2 mb-4">
              <ChatBubbleLeftRightIcon className="h-5 w-5 text-blue-400" />
              <h3 className="font-semibold">Prompt Quality Analysis</h3>
            </div>
            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-400">Average Length</span>
                  <span className="text-white">45 words</span>
                </div>
                <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                  <div className="h-full bg-blue-500 w-[45%]" />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-400">Specificity Score</span>
                  <span className="text-white">68%</span>
                </div>
                <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                  <div className="h-full bg-purple-500 w-[68%]" />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-400">Context Score</span>
                  <span className="text-white">72%</span>
                </div>
                <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                  <div className="h-full bg-green-500 w-[72%]" />
                </div>
              </div>
            </div>
            <div className="mt-4 pt-4 border-t border-gray-700">
              <div className="text-xs text-gray-500 mb-2">Common Missing Elements:</div>
              <div className="flex flex-wrap gap-2">
                <span className="px-2 py-1 text-xs bg-gray-700 text-gray-300 rounded">
                  Acceptance Criteria
                </span>
                <span className="px-2 py-1 text-xs bg-gray-700 text-gray-300 rounded">
                  Affected Files
                </span>
                <span className="px-2 py-1 text-xs bg-gray-700 text-gray-300 rounded">
                  Test Requirements
                </span>
              </div>
            </div>
          </div>

          {/* Error Pattern Analysis */}
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-6">
            <div className="flex items-center gap-2 mb-4">
              <ExclamationTriangleIcon className="h-5 w-5 text-red-400" />
              <h3 className="font-semibold">Error Pattern Analysis</h3>
            </div>
            <div className="space-y-3">
              <div className="flex items-center justify-between p-3 bg-red-900/20 border border-red-700/50 rounded-lg">
                <span className="text-sm text-gray-300">Database Migrations</span>
                <span className="text-sm text-red-400">30% failure rate</span>
              </div>
              <div className="flex items-center justify-between p-3 bg-orange-900/20 border border-orange-700/50 rounded-lg">
                <span className="text-sm text-gray-300">Authentication Changes</span>
                <span className="text-sm text-orange-400">22% failure rate</span>
              </div>
              <div className="flex items-center justify-between p-3 bg-yellow-900/20 border border-yellow-700/50 rounded-lg">
                <span className="text-sm text-gray-300">API Endpoint Changes</span>
                <span className="text-sm text-yellow-400">15% failure rate</span>
              </div>
            </div>
            <div className="mt-4 pt-4 border-t border-gray-700">
              <div className="text-xs text-gray-500">
                Tip: Break complex database migrations into smaller steps to reduce failures.
              </div>
            </div>
          </div>

          {/* Model Comparison */}
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-6">
            <div className="flex items-center gap-2 mb-4">
              <ChartBarIcon className="h-5 w-5 text-green-400" />
              <h3 className="font-semibold">Executor Comparison</h3>
            </div>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-300">Claude Code</span>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-green-400">92% success</span>
                  <span className="text-xs text-gray-500">avg 4.2min</span>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-300">Codex CLI</span>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-blue-400">78% success</span>
                  <span className="text-xs text-gray-500">avg 1.5min</span>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-300">Gemini CLI</span>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-purple-400">85% success</span>
                  <span className="text-xs text-gray-500">avg 2.8min</span>
                </div>
              </div>
            </div>
            <div className="mt-4 pt-4 border-t border-gray-700">
              <div className="text-xs text-gray-500">
                Claude Code shows highest success rate for complex refactoring tasks.
              </div>
            </div>
          </div>

          {/* Time Analysis */}
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-6">
            <div className="flex items-center gap-2 mb-4">
              <ClockIcon className="h-5 w-5 text-yellow-400" />
              <h3 className="font-semibold">Time-to-Completion Analysis</h3>
            </div>
            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-400">Avg Task Duration</span>
                  <span className="text-white">2.4 hours</span>
                </div>
              </div>
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-400">Time in Gating</span>
                  <span className="text-yellow-400">45%</span>
                </div>
                <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                  <div className="h-full bg-yellow-500 w-[45%]" />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-400">Best Submission Time</span>
                  <span className="text-green-400">9-11 AM</span>
                </div>
              </div>
            </div>
            <div className="mt-4 pt-4 border-t border-gray-700">
              <div className="text-xs text-gray-500">
                Consider enabling auto-merge for low-risk changes to reduce gating time.
              </div>
            </div>
          </div>
        </div>

        {/* Coming Soon Notice */}
        <div className="mt-8 p-6 bg-gray-800/50 border border-gray-700 rounded-lg text-center">
          <SparklesIcon className="h-8 w-8 text-yellow-400 mx-auto mb-3" />
          <h3 className="text-lg font-semibold mb-2">AI-Powered Analysis Coming Soon</h3>
          <p className="text-gray-400 text-sm max-w-xl mx-auto">
            This is a preview of the Analysis feature. Full AI-powered prompt analysis,
            personalized recommendations, and predictive insights will be available in a future
            release.
          </p>
        </div>
      </div>
    </div>
  );
}
