'use client';

import { useRouter } from 'next/navigation';
import { CheckCircleIcon, ArrowRightIcon } from '@heroicons/react/24/outline';
import { useSetupStatus } from '@/hooks/useSetupStatus';
import { Button } from './ui/Button';

export function WelcomeCard() {
  const router = useRouter();
  const { isComplete, isLoading, steps, nextStep, completedCount, totalCount } = useSetupStatus();

  // Don't show if setup is complete or still loading
  if (isComplete || isLoading) {
    return null;
  }

  const handleNavigate = (href: string | undefined) => {
    if (href) {
      router.push(href);
    }
  };

  return (
    <div className="mb-6 p-6 bg-gradient-to-r from-blue-950/30 to-violet-950/30 border border-blue-800/50 rounded-xl">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h2 className="text-xl font-semibold text-gray-100">Welcome to zloth!</h2>
          <p className="text-gray-400 mt-1">
            Complete the setup to start creating tasks
          </p>
        </div>
        <div className="text-sm text-gray-500">
          {completedCount} / {totalCount} complete
        </div>
      </div>

      <div className="space-y-3">
        {steps.map((step, index) => (
          <div
            key={step.id}
            className={`flex items-center gap-4 p-4 rounded-lg transition-colors ${
              step.complete
                ? 'bg-green-950/20 border border-green-800/30'
                : step.id === nextStep?.id
                  ? 'bg-gray-800/50 border border-gray-700'
                  : 'bg-gray-900/50 border border-gray-800/50'
            }`}
          >
            <div className="flex-shrink-0">
              {step.complete ? (
                <CheckCircleIcon className="w-6 h-6 text-green-500" />
              ) : (
                <div className="w-6 h-6 rounded-full border-2 border-gray-600 flex items-center justify-center text-xs text-gray-500">
                  {index + 1}
                </div>
              )}
            </div>

            <div className="flex-1 min-w-0">
              <p
                className={`font-medium ${
                  step.complete ? 'text-gray-400 line-through' : 'text-gray-200'
                }`}
              >
                {step.label}
              </p>
              <p className="text-sm text-gray-500 truncate">{step.description}</p>
            </div>

            {!step.complete && step.id === nextStep?.id && (
              <Button
                size="sm"
                variant="primary"
                onClick={() => handleNavigate(step.href)}
              >
                Configure
                <ArrowRightIcon className="w-4 h-4 ml-1" />
              </Button>
            )}
          </div>
        ))}
      </div>

      <div className="mt-4 pt-4 border-t border-gray-800/50">
        <p className="text-xs text-gray-500">
          You can always access these settings from the Settings menu.
        </p>
      </div>
    </div>
  );
}
