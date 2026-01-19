'use client';

interface MetricsSectionProps {
  title: string;
  children: React.ReactNode;
}

export function MetricsSection({ title, children }: MetricsSectionProps) {
  return (
    <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
      <h3 className="text-lg font-semibold text-white mb-4">{title}</h3>
      {children}
    </div>
  );
}
