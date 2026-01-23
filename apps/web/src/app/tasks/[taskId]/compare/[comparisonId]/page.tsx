'use client';

import useSWR from 'swr';
import Link from 'next/link';
import { use } from 'react';
import { comparisonsApi, runsApi } from '@/lib/api';
import type { Comparison, Run } from '@/types';

interface PageProps {
  params: Promise<{ taskId: string; comparisonId: string }>;
}

export default function ComparePage({ params }: PageProps) {
  const { taskId, comparisonId } = use(params);
  const { data: comparison } = useSWR<Comparison>(`cmp-${comparisonId}`, () => comparisonsApi.get(comparisonId), {
    refreshInterval: 2000,
  });
  const { data: runs } = useSWR<Run[]>(`runs-${taskId}`, () => runsApi.list(taskId));

  if (!comparison) return <div className="p-6 text-gray-400">Loading comparison...</div>;

  const runsById = new Map((runs || []).map((r) => [r.id, r] as const));

  return (
    <div className="max-w-6xl mx-auto p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-white">Comparison</h1>
        <Link href={`/tasks/${taskId}`} className="text-sm text-blue-400 hover:underline">
          Back to Task
        </Link>
      </div>

      <div className="rounded-lg border border-gray-800 p-4 bg-gray-900">
        <div className="text-sm text-gray-400 mb-1">Status: {comparison.status}</div>
        {comparison.overall_summary && (
          <p className="text-gray-200 whitespace-pre-wrap">{comparison.overall_summary}</p>
        )}
        {comparison.overall_winner_run_id && (
          <div className="mt-2 text-sm">
            <span className="text-gray-400">Winner: </span>
            <span className="text-green-400 font-medium">{comparison.overall_winner_run_id.slice(0,8)}</span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {comparison.scores.map((s) => {
          const run = runsById.get(s.run_id);
          return (
            <div key={s.run_id} className="rounded-lg border border-gray-800 p-4 bg-gray-900">
              <div className="flex items-center justify-between mb-2">
                <div className="text-sm text-gray-400">{s.executor_type}</div>
                <div className="text-sm font-semibold text-blue-400">{Math.round(s.score * 100)}%</div>
              </div>
              {run?.summary && (
                <div className="text-xs text-gray-300 whitespace-pre-wrap mb-2">{run.summary}</div>
              )}
              {s.pros.length > 0 && (
                <div className="mt-2">
                  <div className="text-xs text-green-400 font-medium">Pros</div>
                  <ul className="list-disc pl-4 text-xs text-gray-300 space-y-1">
                    {s.pros.map((p, i) => <li key={i}>{p}</li>)}
                  </ul>
                </div>
              )}
              {s.cons.length > 0 && (
                <div className="mt-2">
                  <div className="text-xs text-red-400 font-medium">Cons</div>
                  <ul className="list-disc pl-4 text-xs text-gray-300 space-y-1">
                    {s.cons.map((c, i) => <li key={i}>{c}</li>)}
                  </ul>
                </div>
              )}
              {s.rationale && (
                <div className="mt-2 text-xs text-gray-400 whitespace-pre-wrap">{s.rationale}</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

