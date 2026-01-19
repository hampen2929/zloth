'use client';

import { ArrowUpIcon, ArrowDownIcon, MinusIcon } from '@heroicons/react/24/solid';

interface MetricCardProps {
  title: string;
  value: string | number;
  unit?: string;
  change?: number | null;
  description?: string;
  loading?: boolean;
}

export function MetricCard({
  title,
  value,
  unit,
  change,
  description,
  loading,
}: MetricCardProps) {
  const formatChange = (val: number) => {
    const sign = val > 0 ? '+' : '';
    return `${sign}${val.toFixed(1)}`;
  };

  const getTrendIcon = (val: number) => {
    if (val > 1) return <ArrowUpIcon className="h-4 w-4" />;
    if (val < -1) return <ArrowDownIcon className="h-4 w-4" />;
    return <MinusIcon className="h-4 w-4" />;
  };

  const getTrendColor = (val: number) => {
    if (val > 1) return 'text-green-400';
    if (val < -1) return 'text-red-400';
    return 'text-gray-400';
  };

  if (loading) {
    return (
      <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
        <div className="animate-pulse">
          <div className="h-4 w-24 bg-gray-700 rounded mb-2"></div>
          <div className="h-8 w-16 bg-gray-700 rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
      <div className="text-sm text-gray-400 mb-1">{title}</div>
      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-bold text-white">{value}</span>
        {unit && <span className="text-sm text-gray-400">{unit}</span>}
      </div>
      {change !== undefined && change !== null && (
        <div className={`flex items-center gap-1 mt-1 text-sm ${getTrendColor(change)}`}>
          {getTrendIcon(change)}
          <span>{formatChange(change)}</span>
          <span className="text-gray-500">vs prev</span>
        </div>
      )}
      {description && (
        <div className="text-xs text-gray-500 mt-2">{description}</div>
      )}
    </div>
  );
}
