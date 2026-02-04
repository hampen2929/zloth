'use client';

import { useState, useEffect } from 'react';
import useSWR, { mutate } from 'swr';
import { githubApi, preferencesApi, executorsApi } from '@/lib/api';
import type {
  PRCreationMode,
  CodingMode,
  ExecutorStatus,
  Language,
} from '@/types';
import { Modal, ModalBody } from './ui/Modal';
import { Button } from './ui/Button';
import { Input, Textarea } from './ui/Input';
import { useToast } from './ui/Toast';
import { useLanguage } from '@/lib/i18n';
import { cn } from '@/lib/utils';
import {
  KeyIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  Cog6ToothIcon,
  CommandLineIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline';

export type SettingsTabType = 'github' | 'defaults' | 'executors';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  defaultTab?: SettingsTabType;
}

export const settingsTabConfig: { id: SettingsTabType; label: string; icon: React.ReactNode }[] = [
  { id: 'executors', label: 'Executors', icon: <CommandLineIcon className="w-4 h-4" /> },
  { id: 'github', label: 'GitHub App', icon: <KeyIcon className="w-4 h-4" /> },
  { id: 'defaults', label: 'Defaults', icon: <Cog6ToothIcon className="w-4 h-4" /> },
];

export default function SettingsModal({ isOpen, onClose, defaultTab }: SettingsModalProps) {
  const [activeTab, setActiveTab] = useState<SettingsTabType>(defaultTab || 'executors');

  // Update active tab when defaultTab changes
  // This is intentional: we want to switch tabs when externally triggered
  useEffect(() => {
    if (defaultTab) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setActiveTab(defaultTab);
    }
  }, [defaultTab]);

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Settings"
      size="xl"
    >
      {/* Tabs */}
      <div className="flex border-b border-gray-800" role="tablist">
        {settingsTabConfig.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            role="tab"
            aria-selected={activeTab === tab.id}
            className={cn(
              'flex items-center gap-2 px-6 py-3 text-sm font-medium transition-colors',
              'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-inset',
              activeTab === tab.id
                ? 'text-blue-400 border-b-2 border-blue-500 -mb-[1px]'
                : 'text-gray-400 hover:text-gray-300'
            )}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <ModalBody className="max-h-[calc(85vh-180px)] overflow-y-auto">
        {activeTab === 'github' && <GitHubAppTab />}
        {activeTab === 'defaults' && <DefaultsTab />}
        {activeTab === 'executors' && <ExecutorsTab />}
      </ModalBody>
    </Modal>
  );
}

export function GitHubAppTab() {
  const { data: config, isLoading } = useSWR('github-config', githubApi.getConfig);
  const [appId, setAppId] = useState('');
  const [privateKey, setPrivateKey] = useState('');
  const [installationId, setInstallationId] = useState('');
  const [loading, setLoading] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const { success } = useToast();

  // When source is 'env', the config is read-only
  const isEnvConfig = config?.source === 'env';

  useEffect(() => {
    if (config && config.source !== 'env') {
      setAppId(config.app_id || '');
      setInstallationId(config.installation_id || '');
      // Private key is not returned for security
    }
  }, [config]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setSaveError(null);

    try {
      await githubApi.saveConfig({
        app_id: appId,
        private_key: privateKey || undefined,
        installation_id: installationId || undefined,
      });
      mutate('github-config');
      success('GitHub App configuration saved successfully');
      setPrivateKey(''); // Clear private key input after save
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to save configuration');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="mb-6">
        <h3 className="text-lg font-semibold text-gray-100">GitHub App Configuration</h3>
        <p className="text-sm text-gray-400 mt-1">
          Connect a GitHub App to create pull requests and access repositories.
        </p>
      </div>

      {/* Status indicator */}
      {!isLoading && config && (
        <div className={cn(
          'mb-4 p-3 rounded-lg border flex items-center gap-2',
          config.is_configured
            ? 'bg-green-900/20 border-green-800/50 text-green-400'
            : 'bg-yellow-900/20 border-yellow-800/50 text-yellow-400'
        )}>
          {config.is_configured ? (
            <>
              <CheckCircleIcon className="w-5 h-5 flex-shrink-0" />
              <span className="text-sm font-medium">GitHub App is configured</span>
              {config.source === 'env' && (
                <span className="text-xs bg-green-800/50 px-2 py-0.5 rounded ml-auto">via .env</span>
              )}
            </>
          ) : (
            <>
              <ExclamationTriangleIcon className="w-5 h-5 flex-shrink-0" />
              <span className="text-sm font-medium">GitHub App not configured</span>
            </>
          )}
        </div>
      )}

      {/* Environment variables display (read-only) */}
      {isEnvConfig && (
        <div className="space-y-4 mb-6">
          <div className="p-4 bg-gray-800/30 border border-gray-700 rounded-lg">
            <h4 className="text-sm font-medium text-gray-300 mb-3">Configuration from Environment Variables</h4>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-400">App ID</span>
                <span className="font-mono text-sm text-gray-200 bg-gray-700 px-2 py-1 rounded">
                  {config?.app_id_masked || '***'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-400">Private Key</span>
                <span className={cn(
                  'text-sm px-2 py-1 rounded font-medium',
                  config?.has_private_key
                    ? 'text-green-400 bg-green-900/30'
                    : 'text-red-400 bg-red-900/30'
                )}>
                  {config?.has_private_key ? 'Configured' : 'Not set'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-400">Installation ID</span>
                <span className={cn(
                  'text-sm px-2 py-1 rounded',
                  config?.installation_id_masked
                    ? 'font-mono text-gray-200 bg-gray-700'
                    : 'text-blue-400 bg-blue-900/30 font-medium'
                )}>
                  {config?.installation_id_masked || 'Auto (all installations)'}
                </span>
              </div>
            </div>
            <p className="text-xs text-gray-500 mt-4">
              To modify these values, update your .env file and restart the application.
            </p>
          </div>
        </div>
      )}

      {/* Manual configuration form (only when not using env) */}
      {!isEnvConfig && (
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="App ID"
            value={appId}
            onChange={(e) => setAppId(e.target.value)}
            placeholder="123456"
            hint="Find this in your GitHub App settings page"
          />

          <Textarea
            label="Private Key"
            value={privateKey}
            onChange={(e) => setPrivateKey(e.target.value)}
            placeholder="-----BEGIN RSA PRIVATE KEY-----"
            rows={4}
            className="font-mono text-xs"
            hint={config?.is_configured
              ? 'Leave blank to keep existing key. Paste new key to update.'
              : 'Paste the private key generated from your GitHub App'}
          />

          <Input
            label="Installation ID (optional)"
            value={installationId}
            onChange={(e) => setInstallationId(e.target.value)}
            placeholder="12345678"
            hint="Optional: If not set, all installations of this GitHub App will be available. Find this in your organization's installed apps settings."
            error={saveError || undefined}
          />

          <Button
            type="submit"
            disabled={!appId}
            isLoading={loading}
            className="w-full"
          >
            Save Configuration
          </Button>
        </form>
      )}

      {/* Required permissions info */}
      <div className="mt-6 p-4 bg-blue-900/20 border border-blue-800/50 rounded-lg">
        <h4 className="text-sm font-medium text-blue-300 mb-3">Required Permissions</h4>
        <p className="text-xs text-gray-400 mb-3">
          Your GitHub App must have the following permissions:
        </p>
        <div className="space-y-2 text-xs">
          <div className="flex items-start gap-2">
            <span className="text-blue-400 font-medium w-24 flex-shrink-0">Contents</span>
            <span className="text-gray-400">Read & Write - Clone repos, push commits, create branches</span>
          </div>
          <div className="flex items-start gap-2">
            <span className="text-blue-400 font-medium w-24 flex-shrink-0">Pull requests</span>
            <span className="text-gray-400">Read & Write - Create and update pull requests</span>
          </div>
          <div className="flex items-start gap-2">
            <span className="text-blue-400 font-medium w-24 flex-shrink-0">Metadata</span>
            <span className="text-gray-400">Read-only - Access repository metadata (auto-granted)</span>
          </div>
        </div>
        <p className="text-xs text-gray-500 mt-3 pt-3 border-t border-blue-800/30">
          <span className="text-gray-400">Optional:</span> Checks (read-only) and Workflows (read & write) for CI integration
        </p>
      </div>

      {/* Environment variable info */}
      <div className="mt-4 p-4 bg-gray-800/20 border border-gray-700 rounded-lg">
        <h4 className="text-sm font-medium text-gray-300 mb-2">Environment Variables</h4>
        <p className="text-xs text-gray-500 mb-3">
          You can also configure the GitHub App via environment variables:
        </p>
        <div className="font-mono text-xs text-gray-400 space-y-1 bg-gray-800/50 p-3 rounded">
          <div>ZLOTH_GITHUB_APP_ID=&lt;app_id&gt;</div>
          <div>ZLOTH_GITHUB_APP_PRIVATE_KEY=&lt;base64_encoded_key&gt;</div>
          <div className="text-gray-500"># Optional: if not set, all installations are available</div>
          <div>ZLOTH_GITHUB_APP_INSTALLATION_ID=&lt;installation_id&gt;</div>
        </div>
      </div>
    </div>
  );
}

export function DefaultsTab() {
  const { data: preferences } = useSWR('preferences', preferencesApi.get);
  const { data: githubConfig } = useSWR('github-config', githubApi.getConfig);
  const { data: repos, isLoading: reposLoading } = useSWR(
    githubConfig?.is_configured ? 'github-repos' : null,
    githubApi.listRepos
  );

  const { t, setLanguage: setGlobalLanguage } = useLanguage();
  const labels = t.settings.defaults;

  const [selectedRepo, setSelectedRepo] = useState<string>('');
  const [selectedBranch, setSelectedBranch] = useState<string>('');
  const [branches, setBranches] = useState<string[]>([]);
  const [branchPrefix, setBranchPrefix] = useState<string>('');
  const [prCreationMode, setPrCreationMode] = useState<PRCreationMode>('link');
  const [codingMode, setCodingMode] = useState<CodingMode>('interactive');
  const [autoGeneratePrDescription, setAutoGeneratePrDescription] = useState<boolean>(false);
  const [enableGatingStatus, setEnableGatingStatus] = useState<boolean>(false);
  const [notifyOnReady, setNotifyOnReady] = useState<boolean>(true);
  const [notifyOnComplete, setNotifyOnComplete] = useState<boolean>(true);
  const [notifyOnFailure, setNotifyOnFailure] = useState<boolean>(true);
  const [notifyOnWarning, setNotifyOnWarning] = useState<boolean>(true);
  const [mergeMethod, setMergeMethod] = useState<string>('squash');
  const [reviewMinScore, setReviewMinScore] = useState<number>(0.75);
  const [languagePref, setLanguagePref] = useState<Language>('en');
  const [loading, setLoading] = useState(false);
  const [branchesLoading, setBranchesLoading] = useState(false);
  const { success, error: toastError } = useToast();

  // Initialize from saved preferences
  useEffect(() => {
    if (preferences && repos) {
      if (preferences.default_repo_owner && preferences.default_repo_name) {
        const repoFullName = `${preferences.default_repo_owner}/${preferences.default_repo_name}`;
        setSelectedRepo(repoFullName);
        // Find the repository to get its default branch
        const repoData = repos.find((r) => r.full_name === repoFullName);
        // Set selected branch to repository's default branch directly (like top page)
        setSelectedBranch(repoData?.default_branch || '');
        // Load branch list
        loadBranches(preferences.default_repo_owner, preferences.default_repo_name);
      }
    }
  }, [preferences, repos]);

  // Initialize branch prefix and other settings from preferences
  useEffect(() => {
    if (preferences) {
      setBranchPrefix(preferences.default_branch_prefix || '');
      setPrCreationMode(preferences.default_pr_creation_mode || 'link');
      setCodingMode(preferences.default_coding_mode || 'interactive');
      setAutoGeneratePrDescription(preferences.auto_generate_pr_description || false);
      setEnableGatingStatus(preferences.enable_gating_status || false);
      setNotifyOnReady(preferences.notify_on_ready ?? true);
      setNotifyOnComplete(preferences.notify_on_complete ?? true);
      setNotifyOnFailure(preferences.notify_on_failure ?? true);
      setNotifyOnWarning(preferences.notify_on_warning ?? true);
      setMergeMethod(preferences.merge_method || 'squash');
      setReviewMinScore(
        typeof preferences.review_min_score === 'number' ? preferences.review_min_score : 0.75
      );
      setLanguagePref(preferences.language || 'en');
    }
  }, [preferences]);

  const selectedRepoDefaultBranch = (() => {
    if (!repos || !selectedRepo) return null;
    return repos.find((r) => r.full_name === selectedRepo)?.default_branch ?? null;
  })();

  const branchOptions: { value: string; label: string }[] = (() => {
    const list = branches || [];
    const seen = new Set<string>();
    const opts: { value: string; label: string }[] = [];

    if (selectedRepoDefaultBranch) {
      seen.add(selectedRepoDefaultBranch);
      opts.push({
        value: selectedRepoDefaultBranch,
        label: `Default (${selectedRepoDefaultBranch})`,
      });
    }

    for (const b of list) {
      if (seen.has(b)) continue;
      seen.add(b);
      opts.push({ value: b, label: b });
    }

    return opts;
  })();

  const loadBranches = async (owner: string, repo: string) => {
    setBranchesLoading(true);
    try {
      const branchList = await githubApi.listBranches(owner, repo);
      setBranches(branchList);
    } catch (err) {
      console.error('Failed to load branches:', err);
      setBranches([]);
    } finally {
      setBranchesLoading(false);
    }
  };

  const handleRepoChange = async (fullName: string) => {
    setSelectedRepo(fullName);
    setBranches([]);

    if (fullName) {
      const [owner, repo] = fullName.split('/');
      // Find the repository to get its default branch and set it directly (like top page)
      const selectedRepoData = repos?.find((r) => r.full_name === fullName);
      setSelectedBranch(selectedRepoData?.default_branch || '');
      await loadBranches(owner, repo);
    } else {
      setSelectedBranch('');
    }
  };

  const handleSave = async () => {
    setLoading(true);
    try {
      const [owner, repo] = selectedRepo ? selectedRepo.split('/') : [null, null];
      await preferencesApi.save({
        default_repo_owner: owner,
        default_repo_name: repo,
        default_branch: selectedBranch || null,
        default_branch_prefix: branchPrefix.trim() ? branchPrefix.trim() : null,
        default_pr_creation_mode: prCreationMode,
        default_coding_mode: codingMode,
        auto_generate_pr_description: autoGeneratePrDescription,
        enable_gating_status: enableGatingStatus,
        notify_on_ready: notifyOnReady,
        notify_on_complete: notifyOnComplete,
        notify_on_failure: notifyOnFailure,
        notify_on_warning: notifyOnWarning,
        merge_method: mergeMethod,
        review_min_score: reviewMinScore,
        language: languagePref,
      });
      mutate('preferences');
      // Update global language context
      setGlobalLanguage(languagePref);
      success(labels.savedSuccess);
    } catch {
      toastError(labels.saveFailed);
    } finally {
      setLoading(false);
    }
  };

  const handleClear = async () => {
    setLoading(true);
    try {
      await preferencesApi.save({
        default_repo_owner: null,
        default_repo_name: null,
        default_branch: null,
        default_branch_prefix: null,
        default_pr_creation_mode: null,
        default_coding_mode: null,
        auto_generate_pr_description: false,
        enable_gating_status: false,
        notify_on_ready: null,
        notify_on_complete: null,
        notify_on_failure: null,
        notify_on_warning: null,
        merge_method: null,
        review_min_score: null,
        language: 'en',
      });
      setSelectedRepo('');
      setSelectedBranch('');
      setBranches([]);
      setBranchPrefix('');
      setPrCreationMode('create');
      setCodingMode('interactive');
      setAutoGeneratePrDescription(false);
      setEnableGatingStatus(false);
      setNotifyOnReady(true);
      setNotifyOnComplete(true);
      setNotifyOnFailure(true);
      setNotifyOnWarning(true);
      setMergeMethod('squash');
      setReviewMinScore(0.75);
      setLanguagePref('en');
      setGlobalLanguage('en');
      mutate('preferences');
      success(labels.clearedSuccess);
    } catch {
      toastError(labels.clearFailed);
    } finally {
      setLoading(false);
    }
  };

  if (!githubConfig?.is_configured) {
    return (
      <div>
        <div className="mb-6">
          <h3 className="text-lg font-semibold text-gray-100">{labels.title}</h3>
          <p className="text-sm text-gray-400 mt-1">
            {labels.description}
          </p>
        </div>
        <div className="flex items-center gap-2 p-3 bg-yellow-900/20 border border-yellow-800/50 rounded-lg text-yellow-400 text-sm">
          <ExclamationTriangleIcon className="w-5 h-5 flex-shrink-0" />
          <span>{labels.configureGithubFirst}</span>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6">
        <h3 className="text-lg font-semibold text-gray-100">{labels.title}</h3>
        <p className="text-sm text-gray-400 mt-1">
          {labels.description}
        </p>
      </div>

      {/* Current defaults display */}
      {preferences?.default_repo_owner && preferences?.default_repo_name && (
        <div className="mb-4 p-3 bg-green-900/20 border border-green-800/50 rounded-lg flex items-center gap-2 text-green-400">
          <CheckCircleIcon className="w-5 h-5 flex-shrink-0" />
          <span className="text-sm">
            {labels.currentDefault}: <span className="font-medium">{preferences.default_repo_owner}/{preferences.default_repo_name}</span>
            {preferences.default_branch && (
              <span className="text-green-500"> ({preferences.default_branch})</span>
            )}
          </span>
        </div>
      )}

      <div className="space-y-4">
        {/* Repository selection */}
        <div className="space-y-1">
          <label className="block text-sm font-medium text-gray-300">
            {labels.repository}
          </label>
          <select
            value={selectedRepo}
            onChange={(e) => handleRepoChange(e.target.value)}
            disabled={reposLoading}
            className={cn(
              'w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-md',
              'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
              'text-gray-100 transition-colors disabled:opacity-50'
            )}
          >
            <option value="">{labels.selectRepository}</option>
            {repos?.map((repo) => (
              <option key={repo.id} value={repo.full_name}>
                {repo.full_name}
              </option>
            ))}
          </select>
          <p className="text-xs text-gray-500">
            {labels.repositoryHint}
          </p>
        </div>

        {/* Branch selection */}
        <div className="space-y-1">
          <label className="block text-sm font-medium text-gray-300">
            {labels.branch}
          </label>
          <select
            value={selectedBranch}
            onChange={(e) => setSelectedBranch(e.target.value)}
            disabled={!selectedRepo || branchesLoading}
            className={cn(
              'w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-md',
              'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
              'text-gray-100 transition-colors disabled:opacity-50'
            )}
          >
            <option value="">
              {branchesLoading ? labels.loadingBranches : labels.selectBranch}
            </option>
            {branchOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <p className="text-xs text-gray-500">
            {labels.branchHint}
          </p>
        </div>

        {/* Branch prefix */}
        <Input
          label={labels.branchPrefix}
          value={branchPrefix}
          onChange={(e) => setBranchPrefix(e.target.value)}
          placeholder="zloth"
          hint={labels.branchPrefixHint}
        />

        {/* Default coding mode */}
        <div className="space-y-1">
          <label className="block text-sm font-medium text-gray-300">
            {labels.codingMode}
          </label>
          <select
            value={codingMode}
            onChange={(e) => setCodingMode(e.target.value as CodingMode)}
            className={cn(
              'w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-md',
              'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
              'text-gray-100 transition-colors'
            )}
          >
            <option value="interactive">{labels.codingModeOptions.interactive}</option>
            <option value="semi_auto">{labels.codingModeOptions.semiAuto}</option>
            <option value="full_auto">{labels.codingModeOptions.fullAuto}</option>
          </select>
          <p className="text-xs text-gray-500">
            {labels.codingModeHint}
          </p>
        </div>

        {/* PR creation behavior */}
        <div className="space-y-1">
          <label className="block text-sm font-medium text-gray-300">
            {labels.prCreationMode}
          </label>
          <select
            value={prCreationMode}
            onChange={(e) => setPrCreationMode(e.target.value as PRCreationMode)}
            className={cn(
              'w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-md',
              'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
              'text-gray-100 transition-colors'
            )}
          >
            <option value="create">{labels.prCreationModeOptions.create}</option>
            <option value="link">{labels.prCreationModeOptions.link}</option>
          </select>
          <p className="text-xs text-gray-500">
            {labels.prCreationModeHint}
          </p>
        </div>

        {/* Auto-generate PR description */}
        <div className="space-y-1">
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={autoGeneratePrDescription}
              onChange={(e) => setAutoGeneratePrDescription(e.target.checked)}
              className={cn(
                'w-4 h-4 rounded border-gray-600 bg-gray-800',
                'text-blue-500 focus:ring-blue-500 focus:ring-offset-0 focus:ring-offset-gray-900'
              )}
            />
            <span className="text-sm font-medium text-gray-300">
              {labels.autoGeneratePrDescription}
            </span>
          </label>
          <p className="text-xs text-gray-500 ml-7">
            {labels.autoGeneratePrDescriptionHint}
          </p>
        </div>

        {/* Enable Gating status */}
        <div className="space-y-1">
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={enableGatingStatus}
              onChange={(e) => setEnableGatingStatus(e.target.checked)}
              className={cn(
                'w-4 h-4 rounded border-gray-600 bg-gray-800',
                'text-blue-500 focus:ring-blue-500 focus:ring-offset-0 focus:ring-offset-gray-900'
              )}
            />
            <span className="text-sm font-medium text-gray-300">
              {labels.enableGating}
            </span>
          </label>
          <p className="text-xs text-gray-500 ml-7">
            {labels.enableGatingHint}
          </p>
        </div>

        {/* Merge method */}
        <div className="space-y-1">
          <label className="block text-sm font-medium text-gray-300">
            {labels.mergeMethod}
          </label>
          <select
            value={mergeMethod}
            onChange={(e) => setMergeMethod(e.target.value)}
            className={cn(
              'w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-md',
              'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
              'text-gray-100 transition-colors'
            )}
          >
            <option value="merge">{labels.mergeMethodOptions.merge}</option>
            <option value="squash">{labels.mergeMethodOptions.squash}</option>
            <option value="rebase">{labels.mergeMethodOptions.rebase}</option>
          </select>
          <p className="text-xs text-gray-500">
            {labels.mergeMethodHint}
          </p>
        </div>

        {/* Review minimum score */}
        <Input
          label={labels.reviewMinScore}
          type="number"
          min={0}
          max={1}
          step={0.05}
          value={reviewMinScore}
          onChange={(e) => setReviewMinScore(Number(e.target.value))}
          hint={labels.reviewMinScoreHint}
        />

        {/* Notification preferences */}
        <div className="space-y-2">
          <p className="text-sm font-medium text-gray-300">{labels.notifications}</p>
          <div className="space-y-2">
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={notifyOnReady}
                onChange={(e) => setNotifyOnReady(e.target.checked)}
                className={cn(
                  'w-4 h-4 rounded border-gray-600 bg-gray-800',
                  'text-blue-500 focus:ring-blue-500 focus:ring-offset-0 focus:ring-offset-gray-900'
                )}
              />
              <span className="text-sm font-medium text-gray-300">
                {labels.notifyOnReady}
              </span>
            </label>
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={notifyOnComplete}
                onChange={(e) => setNotifyOnComplete(e.target.checked)}
                className={cn(
                  'w-4 h-4 rounded border-gray-600 bg-gray-800',
                  'text-blue-500 focus:ring-blue-500 focus:ring-offset-0 focus:ring-offset-gray-900'
                )}
              />
              <span className="text-sm font-medium text-gray-300">
                {labels.notifyOnComplete}
              </span>
            </label>
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={notifyOnFailure}
                onChange={(e) => setNotifyOnFailure(e.target.checked)}
                className={cn(
                  'w-4 h-4 rounded border-gray-600 bg-gray-800',
                  'text-blue-500 focus:ring-blue-500 focus:ring-offset-0 focus:ring-offset-gray-900'
                )}
              />
              <span className="text-sm font-medium text-gray-300">
                {labels.notifyOnFailure}
              </span>
            </label>
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={notifyOnWarning}
                onChange={(e) => setNotifyOnWarning(e.target.checked)}
                className={cn(
                  'w-4 h-4 rounded border-gray-600 bg-gray-800',
                  'text-blue-500 focus:ring-blue-500 focus:ring-offset-0 focus:ring-offset-gray-900'
                )}
              />
              <span className="text-sm font-medium text-gray-300">
                {labels.notifyOnWarning}
              </span>
            </label>
          </div>
          <p className="text-xs text-gray-500">
            {labels.notificationsHint}
          </p>
        </div>

        {/* Language selection */}
        <div className="space-y-1">
          <label className="block text-sm font-medium text-gray-300">
            {labels.language}
          </label>
          <select
            value={languagePref}
            onChange={(e) => setLanguagePref(e.target.value as Language)}
            className={cn(
              'w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-md',
              'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
              'text-gray-100 transition-colors'
            )}
          >
            <option value="en">{labels.languageOptions.en}</option>
            <option value="ja">{labels.languageOptions.ja}</option>
          </select>
          <p className="text-xs text-gray-500">
            {labels.languageHint}
          </p>
        </div>

        {/* Action buttons */}
        <div className="flex gap-2 pt-2">
          <Button
            onClick={handleSave}
            disabled={!selectedRepo}
            isLoading={loading}
            className="flex-1"
          >
            {labels.saveDefaults}
          </Button>
          <Button
            onClick={handleClear}
            variant="secondary"
            disabled={!preferences?.default_repo_owner}
            isLoading={loading}
          >
            {labels.clearDefaults}
          </Button>
        </div>
      </div>
    </div>
  );
}

const EXECUTOR_INFO: {
  key: 'claude_code' | 'codex_cli' | 'gemini_cli';
  label: string;
  description: string;
  envVar: string;
}[] = [
  {
    key: 'claude_code',
    label: 'Claude Code',
    description: 'Anthropic Claude Code CLI for code generation',
    envVar: 'ZLOTH_CLAUDE_CLI_PATH',
  },
  {
    key: 'codex_cli',
    label: 'Codex CLI',
    description: 'OpenAI Codex CLI for code generation',
    envVar: 'ZLOTH_CODEX_CLI_PATH',
  },
  {
    key: 'gemini_cli',
    label: 'Gemini CLI',
    description: 'Google Gemini CLI for code generation',
    envVar: 'ZLOTH_GEMINI_CLI_PATH',
  },
];

function ExecutorStatusCard({ label, description, status }: {
  label: string;
  description: string;
  status: ExecutorStatus | undefined;
}) {
  if (!status) {
    return (
      <div className="p-4 bg-gray-800/30 rounded-lg border border-gray-700">
        <div className="flex items-center gap-3">
          <div className="w-5 h-5 rounded-full bg-gray-600 animate-pulse" />
          <div className="flex-1">
            <div className="font-medium text-gray-300">{label}</div>
            <div className="text-sm text-gray-500">{description}</div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={cn(
      'p-4 rounded-lg border',
      status.available
        ? 'bg-green-900/10 border-green-800/50'
        : 'bg-red-900/10 border-red-800/50'
    )}>
      <div className="flex items-start gap-3">
        {status.available ? (
          <CheckCircleIcon className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
        ) : (
          <ExclamationTriangleIcon className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={cn(
              'font-medium',
              status.available ? 'text-green-300' : 'text-red-300'
            )}>
              {label}
            </span>
            {status.available ? (
              <span className="text-xs bg-green-800/50 text-green-400 px-2 py-0.5 rounded">
                Available
              </span>
            ) : (
              <span className="text-xs bg-red-800/50 text-red-400 px-2 py-0.5 rounded">
                Not Available
              </span>
            )}
          </div>
          <div className="text-sm text-gray-500 mt-1">{description}</div>

          <div className="mt-3 space-y-1 text-sm">
            <div className="flex items-center gap-2">
              <span className="text-gray-500">Path:</span>
              <code className="font-mono text-gray-300 bg-gray-800/50 px-2 py-0.5 rounded text-xs">
                {status.path}
              </code>
            </div>
            {status.available && status.version && (
              <div className="flex items-center gap-2">
                <span className="text-gray-500">Version:</span>
                <span className="text-gray-300 text-xs">{status.version}</span>
              </div>
            )}
            {!status.available && status.error && (
              <div className="mt-2 p-2 bg-red-900/20 rounded text-xs text-red-400">
                {status.error}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export function ExecutorsTab() {
  const { data: status, error, isLoading, mutate: refreshStatus } = useSWR(
    'executors-status',
    executorsApi.getStatus
  );
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await refreshStatus();
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-100">CLI Executors</h3>
          <p className="text-sm text-gray-400 mt-1">
            Check availability of AI coding CLIs for parallel execution
          </p>
        </div>
        <Button
          onClick={handleRefresh}
          variant="secondary"
          size="sm"
          disabled={isLoading || refreshing}
          leftIcon={
            <ArrowPathIcon className={cn('w-4 h-4', refreshing && 'animate-spin')} />
          }
        >
          Refresh
        </Button>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 bg-red-900/20 border border-red-800/50 rounded-lg text-red-400 text-sm mb-4">
          <ExclamationTriangleIcon className="w-4 h-4 flex-shrink-0" />
          Failed to check executor status.
        </div>
      )}

      <div className="space-y-3">
        {EXECUTOR_INFO.map((executor) => (
          <ExecutorStatusCard
            key={executor.key}
            label={executor.label}
            description={executor.description}
            status={status?.[executor.key]}
          />
        ))}
      </div>

      {/* Environment variable info */}
      <div className="mt-6 p-4 bg-gray-800/20 border border-gray-700 rounded-lg">
        <h4 className="text-sm font-medium text-gray-300 mb-2">Environment Variables</h4>
        <p className="text-xs text-gray-500 mb-3">
          Configure custom CLI paths via environment variables:
        </p>
        <div className="font-mono text-xs text-gray-400 space-y-1 bg-gray-800/50 p-3 rounded">
          {EXECUTOR_INFO.map((executor) => (
            <div key={executor.key}>
              {executor.envVar}=&lt;path&gt;
            </div>
          ))}
        </div>
      </div>

      {/* Installation hints */}
      <div className="mt-4 p-4 bg-blue-900/20 border border-blue-800/50 rounded-lg">
        <h4 className="text-sm font-medium text-blue-300 mb-3">Installation</h4>
        <div className="space-y-3 text-xs">
          <div>
            <span className="text-blue-400 font-medium">Claude Code:</span>
            <code className="ml-2 text-gray-400 bg-gray-800/50 px-2 py-0.5 rounded">
              npm install -g @anthropic-ai/claude-code
            </code>
          </div>
          <div>
            <span className="text-blue-400 font-medium">Codex CLI:</span>
            <code className="ml-2 text-gray-400 bg-gray-800/50 px-2 py-0.5 rounded">
              npm install -g @openai/codex
            </code>
          </div>
          <div>
            <span className="text-blue-400 font-medium">Gemini CLI:</span>
            <code className="ml-2 text-gray-400 bg-gray-800/50 px-2 py-0.5 rounded">
              npm install -g @google/gemini-cli
            </code>
          </div>
        </div>
      </div>
    </div>
  );
}
