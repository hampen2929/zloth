'use client';

import { useState } from 'react';
import useSWR from 'swr';
import { modelsApi, githubApi } from '@/lib/api';
import { Modal, ModalBody } from './ui/Modal';
import { Button } from './ui/Button';
import { useTranslation } from '@/i18n';
import { cn } from '@/lib/utils';
import {
  CheckCircleIcon,
  KeyIcon,
  CpuChipIcon,
  RocketLaunchIcon,
  ArrowRightIcon,
  ArrowLeftIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline';

interface OnboardingWizardProps {
  isOpen: boolean;
  onClose: () => void;
  onGoToSettings: (tab: 'models' | 'github') => void;
}

type Step = 'welcome' | 'github' | 'models' | 'ready';

interface StepConfig {
  id: Step;
  titleKey: string;
  titleFallback: string;
  icon: React.ReactNode;
}

const steps: StepConfig[] = [
  { id: 'welcome', titleKey: 'onboarding.welcome.title', titleFallback: 'Welcome', icon: <SparklesIcon className="w-6 h-6" /> },
  { id: 'github', titleKey: 'onboarding.github.title', titleFallback: 'GitHub App', icon: <KeyIcon className="w-6 h-6" /> },
  { id: 'models', titleKey: 'onboarding.models.title', titleFallback: 'Models', icon: <CpuChipIcon className="w-6 h-6" /> },
  { id: 'ready', titleKey: 'onboarding.ready.title', titleFallback: 'Ready!', icon: <RocketLaunchIcon className="w-6 h-6" /> },
];

const STORAGE_KEY = 'dursor-onboarding-completed';

export function OnboardingWizard({ isOpen, onClose, onGoToSettings }: OnboardingWizardProps) {
  const [currentStep, setCurrentStep] = useState<Step>('welcome');
  const { t } = useTranslation();

  // Fetch configuration status
  const { data: githubConfig } = useSWR(isOpen ? 'github-config' : null, githubApi.getConfig);
  const { data: models } = useSWR(isOpen ? 'models' : null, modelsApi.list);

  const isGitHubConfigured = githubConfig?.is_configured ?? false;
  const hasModels = (models?.length ?? 0) > 0;

  // Calculate current step index
  const currentIndex = steps.findIndex((s) => s.id === currentStep);

  const canGoNext = () => {
    switch (currentStep) {
      case 'welcome':
        return true;
      case 'github':
        return true; // Always allow continuing, but show warning if not configured
      case 'models':
        return true; // Always allow continuing
      case 'ready':
        return true;
      default:
        return false;
    }
  };

  const handleNext = () => {
    const nextIndex = currentIndex + 1;
    if (nextIndex < steps.length) {
      setCurrentStep(steps[nextIndex].id);
    } else {
      handleComplete();
    }
  };

  const handlePrev = () => {
    const prevIndex = currentIndex - 1;
    if (prevIndex >= 0) {
      setCurrentStep(steps[prevIndex].id);
    }
  };

  const handleComplete = () => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, 'true');
    }
    onClose();
  };

  const getStepText = (key: string, fallback: string): string => {
    try {
      const translated = t(key);
      return translated === key ? fallback : translated;
    } catch {
      return fallback;
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title=""
      size="lg"
    >
      {/* Progress indicator */}
      <div className="flex items-center justify-center gap-2 py-4 border-b border-gray-800">
        {steps.map((step, index) => {
          const isCompleted = index < currentIndex;
          const isCurrent = step.id === currentStep;
          const isCompletedStep = (step.id === 'github' && isGitHubConfigured) ||
                                  (step.id === 'models' && hasModels);

          return (
            <div key={step.id} className="flex items-center">
              <div
                className={cn(
                  'w-10 h-10 rounded-full flex items-center justify-center transition-colors',
                  isCurrent && 'bg-blue-600 text-white',
                  isCompleted && !isCurrent && 'bg-green-600 text-white',
                  !isCurrent && !isCompleted && 'bg-gray-700 text-gray-400'
                )}
              >
                {isCompleted || isCompletedStep ? (
                  <CheckCircleIcon className="w-5 h-5" />
                ) : (
                  step.icon
                )}
              </div>
              {index < steps.length - 1 && (
                <div
                  className={cn(
                    'w-12 h-0.5 mx-1',
                    index < currentIndex ? 'bg-green-600' : 'bg-gray-700'
                  )}
                />
              )}
            </div>
          );
        })}
      </div>

      <ModalBody className="py-6">
        {/* Welcome step */}
        {currentStep === 'welcome' && (
          <div className="text-center space-y-4">
            <div className="w-16 h-16 mx-auto bg-blue-600 rounded-full flex items-center justify-center">
              <SparklesIcon className="w-8 h-8 text-white" />
            </div>
            <h2 className="text-2xl font-bold text-gray-100">
              {getStepText('onboarding.welcome.heading', 'Welcome to dursor!')}
            </h2>
            <p className="text-gray-400 max-w-md mx-auto">
              {getStepText('onboarding.welcome.description', 'A self-hostable multi-model parallel coding agent. Complete the setup to get started.')}
            </p>
            <div className="pt-4 space-y-2 text-left max-w-sm mx-auto">
              <div className="flex items-center gap-3 p-3 bg-gray-800/50 rounded-lg">
                <KeyIcon className="w-5 h-5 text-blue-400 flex-shrink-0" />
                <div>
                  <div className="text-sm font-medium text-gray-200">
                    {getStepText('onboarding.welcome.step1', 'Connect GitHub App')}
                  </div>
                  <div className="text-xs text-gray-500">
                    {getStepText('onboarding.welcome.step1Desc', 'Access repositories and create PRs')}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-3 p-3 bg-gray-800/50 rounded-lg">
                <CpuChipIcon className="w-5 h-5 text-green-400 flex-shrink-0" />
                <div>
                  <div className="text-sm font-medium text-gray-200">
                    {getStepText('onboarding.welcome.step2', 'Add LLM Models')}
                  </div>
                  <div className="text-xs text-gray-500">
                    {getStepText('onboarding.welcome.step2Desc', 'OpenAI, Anthropic, or Google API keys')}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-3 p-3 bg-gray-800/50 rounded-lg">
                <RocketLaunchIcon className="w-5 h-5 text-purple-400 flex-shrink-0" />
                <div>
                  <div className="text-sm font-medium text-gray-200">
                    {getStepText('onboarding.welcome.step3', 'Create Your First Task')}
                  </div>
                  <div className="text-xs text-gray-500">
                    {getStepText('onboarding.welcome.step3Desc', 'Run parallel AI agents on your code')}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* GitHub step */}
        {currentStep === 'github' && (
          <div className="text-center space-y-4">
            <div className={cn(
              'w-16 h-16 mx-auto rounded-full flex items-center justify-center',
              isGitHubConfigured ? 'bg-green-600' : 'bg-gray-700'
            )}>
              {isGitHubConfigured ? (
                <CheckCircleIcon className="w-8 h-8 text-white" />
              ) : (
                <KeyIcon className="w-8 h-8 text-gray-400" />
              )}
            </div>
            <h2 className="text-xl font-bold text-gray-100">
              {getStepText('onboarding.github.heading', 'Connect GitHub App')}
            </h2>
            <p className="text-gray-400 max-w-md mx-auto">
              {getStepText('onboarding.github.description', 'A GitHub App is needed to access your repositories and create pull requests.')}
            </p>

            {isGitHubConfigured ? (
              <div className="flex items-center justify-center gap-2 p-3 bg-green-900/20 border border-green-800/50 rounded-lg text-green-400">
                <CheckCircleIcon className="w-5 h-5" />
                <span>{getStepText('onboarding.github.configured', 'GitHub App is configured')}</span>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="p-3 bg-yellow-900/20 border border-yellow-800/50 rounded-lg text-yellow-400 text-sm">
                  {getStepText('onboarding.github.notConfigured', 'GitHub App is not configured yet')}
                </div>
                <Button
                  onClick={() => {
                    onClose();
                    onGoToSettings('github');
                  }}
                >
                  {getStepText('onboarding.github.configure', 'Configure GitHub App')}
                </Button>
              </div>
            )}
          </div>
        )}

        {/* Models step */}
        {currentStep === 'models' && (
          <div className="text-center space-y-4">
            <div className={cn(
              'w-16 h-16 mx-auto rounded-full flex items-center justify-center',
              hasModels ? 'bg-green-600' : 'bg-gray-700'
            )}>
              {hasModels ? (
                <CheckCircleIcon className="w-8 h-8 text-white" />
              ) : (
                <CpuChipIcon className="w-8 h-8 text-gray-400" />
              )}
            </div>
            <h2 className="text-xl font-bold text-gray-100">
              {getStepText('onboarding.models.heading', 'Add LLM Models')}
            </h2>
            <p className="text-gray-400 max-w-md mx-auto">
              {getStepText('onboarding.models.description', 'Add your API keys for OpenAI, Anthropic, or Google to run AI agents.')}
            </p>

            {hasModels ? (
              <div className="space-y-3">
                <div className="flex items-center justify-center gap-2 p-3 bg-green-900/20 border border-green-800/50 rounded-lg text-green-400">
                  <CheckCircleIcon className="w-5 h-5" />
                  <span>
                    {models?.length === 1
                      ? getStepText('onboarding.models.oneConfigured', '1 model configured')
                      : getStepText('onboarding.models.multipleConfigured', `${models?.length} models configured`)}
                  </span>
                </div>
                <div className="space-y-1">
                  {models?.slice(0, 3).map((model) => (
                    <div key={model.id} className="text-sm text-gray-400">
                      {model.display_name || model.model_name}
                    </div>
                  ))}
                  {(models?.length ?? 0) > 3 && (
                    <div className="text-sm text-gray-500">
                      +{(models?.length ?? 0) - 3} more
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="p-3 bg-yellow-900/20 border border-yellow-800/50 rounded-lg text-yellow-400 text-sm">
                  {getStepText('onboarding.models.noModels', 'No models configured yet')}
                </div>
                <Button
                  onClick={() => {
                    onClose();
                    onGoToSettings('models');
                  }}
                >
                  {getStepText('onboarding.models.addModel', 'Add Model')}
                </Button>
              </div>
            )}
          </div>
        )}

        {/* Ready step */}
        {currentStep === 'ready' && (
          <div className="text-center space-y-4">
            <div className="w-16 h-16 mx-auto bg-green-600 rounded-full flex items-center justify-center">
              <RocketLaunchIcon className="w-8 h-8 text-white" />
            </div>
            <h2 className="text-2xl font-bold text-gray-100">
              {getStepText('onboarding.ready.heading', "You're All Set!")}
            </h2>
            <p className="text-gray-400 max-w-md mx-auto">
              {getStepText('onboarding.ready.description', 'Start creating tasks to run AI agents on your code.')}
            </p>

            {/* Setup summary */}
            <div className="pt-4 space-y-2 max-w-sm mx-auto">
              <div className={cn(
                'flex items-center gap-3 p-3 rounded-lg',
                isGitHubConfigured ? 'bg-green-900/20' : 'bg-yellow-900/20'
              )}>
                {isGitHubConfigured ? (
                  <CheckCircleIcon className="w-5 h-5 text-green-400 flex-shrink-0" />
                ) : (
                  <KeyIcon className="w-5 h-5 text-yellow-400 flex-shrink-0" />
                )}
                <span className={isGitHubConfigured ? 'text-green-400' : 'text-yellow-400'}>
                  {isGitHubConfigured
                    ? getStepText('onboarding.ready.githubReady', 'GitHub App connected')
                    : getStepText('onboarding.ready.githubNotReady', 'GitHub App not configured')}
                </span>
              </div>
              <div className={cn(
                'flex items-center gap-3 p-3 rounded-lg',
                hasModels ? 'bg-green-900/20' : 'bg-yellow-900/20'
              )}>
                {hasModels ? (
                  <CheckCircleIcon className="w-5 h-5 text-green-400 flex-shrink-0" />
                ) : (
                  <CpuChipIcon className="w-5 h-5 text-yellow-400 flex-shrink-0" />
                )}
                <span className={hasModels ? 'text-green-400' : 'text-yellow-400'}>
                  {hasModels
                    ? getStepText('onboarding.ready.modelsReady', `${models?.length} model(s) configured`)
                    : getStepText('onboarding.ready.modelsNotReady', 'No models configured')}
                </span>
              </div>
            </div>
          </div>
        )}
      </ModalBody>

      {/* Navigation buttons */}
      <div className="flex items-center justify-between p-4 border-t border-gray-800">
        <div>
          {currentIndex > 0 && (
            <Button
              variant="secondary"
              onClick={handlePrev}
              leftIcon={<ArrowLeftIcon className="w-4 h-4" />}
            >
              {getStepText('onboarding.nav.back', 'Back')}
            </Button>
          )}
        </div>
        <div className="flex gap-2">
          <Button
            variant="ghost"
            onClick={handleComplete}
          >
            {getStepText('onboarding.nav.skip', 'Skip')}
          </Button>
          {currentStep === 'ready' ? (
            <Button
              onClick={handleComplete}
              rightIcon={<RocketLaunchIcon className="w-4 h-4" />}
            >
              {getStepText('onboarding.nav.getStarted', 'Get Started')}
            </Button>
          ) : (
            <Button
              onClick={handleNext}
              disabled={!canGoNext()}
              rightIcon={<ArrowRightIcon className="w-4 h-4" />}
            >
              {getStepText('onboarding.nav.next', 'Next')}
            </Button>
          )}
        </div>
      </div>
    </Modal>
  );
}

// Helper function to check if onboarding is completed
export function isOnboardingCompleted(): boolean {
  if (typeof window === 'undefined') return true;
  return localStorage.getItem(STORAGE_KEY) === 'true';
}

// Helper function to reset onboarding
export function resetOnboarding(): void {
  if (typeof window !== 'undefined') {
    localStorage.removeItem(STORAGE_KEY);
  }
}
