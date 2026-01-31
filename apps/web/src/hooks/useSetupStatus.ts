import useSWR from 'swr';
import { modelsApi, githubApi } from '@/lib/api';

interface SetupStep {
  id: string;
  label: string;
  description: string;
  complete: boolean;
  href?: string;
}

interface SetupStatus {
  isComplete: boolean;
  isLoading: boolean;
  steps: SetupStep[];
  nextStep: SetupStep | null;
  completedCount: number;
  totalCount: number;
}

export function useSetupStatus(): SetupStatus {
  const { data: models, isLoading: modelsLoading } = useSWR('models', modelsApi.list, {
    revalidateOnFocus: false,
  });
  const { data: github, isLoading: githubLoading } = useSWR('github-config', githubApi.getConfig, {
    revalidateOnFocus: false,
  });

  const isLoading = modelsLoading || githubLoading;

  const githubComplete = github?.is_configured ?? false;
  const modelsComplete = (models?.length ?? 0) > 0;

  const steps: SetupStep[] = [
    {
      id: 'github',
      label: 'Connect GitHub App',
      description: 'Connect your GitHub App to access repositories',
      complete: githubComplete,
      href: '/settings?tab=github',
    },
    {
      id: 'models',
      label: 'Add a model',
      description: 'Add an OpenAI, Anthropic, or Google API key',
      complete: modelsComplete,
      href: '/settings?tab=models',
    },
  ];

  const completedCount = steps.filter((s) => s.complete).length;
  const isComplete = steps.every((s) => s.complete);
  const nextStep = steps.find((s) => !s.complete) ?? null;

  return {
    isComplete,
    isLoading,
    steps,
    nextStep,
    completedCount,
    totalCount: steps.length,
  };
}
