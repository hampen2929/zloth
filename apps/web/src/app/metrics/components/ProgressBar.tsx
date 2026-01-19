'use client';

interface ProgressBarProps {
  label: string;
  value: number;
  total: number;
  color?: 'green' | 'blue' | 'yellow' | 'red' | 'purple';
}

export function ProgressBar({
  label,
  value,
  total,
  color = 'blue',
}: ProgressBarProps) {
  const percentage = total > 0 ? (value / total) * 100 : 0;

  const colorClasses = {
    green: 'bg-green-500',
    blue: 'bg-blue-500',
    yellow: 'bg-yellow-500',
    red: 'bg-red-500',
    purple: 'bg-purple-500',
  };

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span className="text-gray-400">{label}</span>
        <span className="text-gray-300">
          {value} / {total} ({percentage.toFixed(1)}%)
        </span>
      </div>
      <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
        <div
          className={`h-full ${colorClasses[color]} transition-all duration-300`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
