'use client';

import { useState, useEffect } from 'react';
import useSWR, { mutate } from 'swr';
import { modelsApi, githubApi, preferencesApi } from '@/lib/api';
import type { Provider, ModelProfileCreate, GitHubAppConfig, GitHubRepository, UserPreferences } from '@/types';
import { Modal, ModalBody } from './ui/Modal';
import { Button } from './ui/Button';
import { Input, Textarea } from './ui/Input';
import { useToast } from './ui/Toast';
import { useConfirmDialog } from './ui/ConfirmDialog';
import { cn } from '@/lib/utils';
import {
  CpuChipIcon,
  KeyIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  TrashIcon,
  PlusIcon,
  Cog6ToothIcon,
} from '@heroicons/react/24/outline';

const PROVIDERS: { value: Provider; label: string; models: string[] }[] = [
  {
    value: 'openai',
    label: 'OpenAI',
    models: ['gpt-5-mini'],
  },
  {
    value: 'anthropic',
    label: 'Anthropic',
    models: ['claude-3-5-sonnet-20241022', 'claude-3-opus-20240229', 'claude-3-haiku-20240307'],
  },
  {
    value: 'google',
    label: 'Google',
    models: ['gemini-2.0-flash-exp', 'gemini-1.5-pro', 'gemini-1.5-flash'],
  },
];

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type TabType = 'models' | 'github' | 'defaults';

const tabConfig: { id: TabType; label: string; icon: React.ReactNode }[] = [
  { id: 'models', label: 'Models', icon: <CpuChipIcon className="w-4 h-4" /> },
  { id: 'github', label: 'GitHub App', icon: <KeyIcon className="w-4 h-4" /> },
  { id: 'defaults', label: 'Defaults', icon: <Cog6ToothIcon className="w-4 h-4" /> },
];

export default function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const [activeTab, setActiveTab] = useState<TabType>('models');

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Settings"
      size="xl"
    >
      {/* Tabs */}
      <div className="flex border-b border-gray-800" role="tablist">
        {tabConfig.map((tab) => (
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
        {activeTab === 'models' && <ModelsTab />}
        {activeTab === 'github' && <GitHubAppTab />}
        {activeTab === 'defaults' && <DefaultsTab />}
      </ModalBody>
    </Modal>
  );
}

function ModelsTab() {
  const { data: models, error } = useSWR('models', modelsApi.list);
  const [showForm, setShowForm] = useState(false);
  const { confirm, ConfirmDialog } = useConfirmDialog();
  const { success, error: toastError } = useToast();

  const handleDelete = async (modelId: string, modelName: string) => {
    const confirmed = await confirm({
      title: 'Delete Model',
      message: `Are you sure you want to delete "${modelName}"? This action cannot be undone.`,
      confirmLabel: 'Delete',
      variant: 'danger',
    });

    if (confirmed) {
      try {
        await modelsApi.delete(modelId);
        mutate('models');
        success('Model deleted successfully');
      } catch (err) {
        toastError('Failed to delete model');
      }
    }
  };

  return (
    <div>
      {ConfirmDialog}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-100">Model Profiles</h3>
          <p className="text-sm text-gray-400 mt-1">
            Configure LLM providers and API keys for parallel execution
          </p>
        </div>
        <Button
          onClick={() => setShowForm(!showForm)}
          variant={showForm ? 'secondary' : 'primary'}
          size="sm"
          leftIcon={showForm ? undefined : <PlusIcon className="w-4 h-4" />}
        >
          {showForm ? 'Cancel' : 'Add Model'}
        </Button>
      </div>

      {showForm && <AddModelForm onSuccess={() => setShowForm(false)} />}

      {error && (
        <div className="flex items-center gap-2 p-3 bg-red-900/20 border border-red-800/50 rounded-lg text-red-400 text-sm mt-4">
          <ExclamationTriangleIcon className="w-4 h-4 flex-shrink-0" />
          Failed to load models.
        </div>
      )}

      {models && models.length === 0 && !showForm && (
        <div className="mt-4 p-6 bg-gray-800/30 border border-gray-700 rounded-lg text-center">
          <CpuChipIcon className="w-10 h-10 text-gray-600 mx-auto mb-3" />
          <p className="text-gray-400 text-sm">
            No models configured. Add your API keys to get started.
          </p>
        </div>
      )}

      {models && models.length > 0 && (
        <div className="space-y-2 mt-4">
          {models.map((model) => {
            const isEnvModel = model.id.startsWith('env-');
            return (
              <div
                key={model.id}
                className="flex items-center justify-between p-4 bg-gray-800/30 rounded-lg border border-gray-700 hover:border-gray-600 transition-colors"
              >
                <div>
                  <div className="font-medium text-gray-100 flex items-center gap-2">
                    {model.display_name || model.model_name}
                    {isEnvModel && (
                      <span className="text-xs bg-gray-700 text-gray-400 px-2 py-0.5 rounded">
                        .env
                      </span>
                    )}
                  </div>
                  <div className="text-sm text-gray-500">
                    {model.provider} / {model.model_name}
                  </div>
                </div>
                {isEnvModel ? (
                  <span className="text-xs text-gray-500">
                    Configured via .env
                  </span>
                ) : (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDelete(model.id, model.display_name || model.model_name)}
                    className="text-red-400 hover:text-red-300 hover:bg-red-900/20"
                  >
                    <TrashIcon className="w-4 h-4" />
                  </Button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function AddModelForm({ onSuccess }: { onSuccess: () => void }) {
  const [provider, setProvider] = useState<Provider>('openai');
  const [modelName, setModelName] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [loading, setLoading] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const { success } = useToast();

  const selectedProvider = PROVIDERS.find((p) => p.value === provider);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!modelName || !apiKey) return;

    setLoading(true);
    setFormError(null);

    try {
      const data: ModelProfileCreate = {
        provider,
        model_name: modelName,
        api_key: apiKey,
      };
      if (displayName) {
        data.display_name = displayName;
      }

      await modelsApi.create(data);
      mutate('models');
      success('Model added successfully');
      onSuccess();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Failed to add model');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="p-4 bg-gray-800/30 rounded-lg border border-gray-700 space-y-4 mb-4 animate-in fade-in duration-200"
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="space-y-1">
          <label className="block text-sm font-medium text-gray-300">
            Provider
          </label>
          <select
            value={provider}
            onChange={(e) => {
              setProvider(e.target.value as Provider);
              setModelName('');
            }}
            className={cn(
              'w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-md',
              'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
              'text-gray-100 transition-colors'
            )}
          >
            {PROVIDERS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-1">
          <label className="block text-sm font-medium text-gray-300">
            Model
          </label>
          <select
            value={modelName}
            onChange={(e) => setModelName(e.target.value)}
            className={cn(
              'w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-md',
              'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
              'text-gray-100 transition-colors'
            )}
          >
            <option value="">Select a model</option>
            {selectedProvider?.models.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>
      </div>

      <Input
        label="Display Name (optional)"
        value={displayName}
        onChange={(e) => setDisplayName(e.target.value)}
        placeholder="e.g., GPT-4o (fast)"
        hint="A friendly name to identify this model"
      />

      <Input
        label="API Key"
        type="password"
        value={apiKey}
        onChange={(e) => setApiKey(e.target.value)}
        placeholder="sk-..."
        error={formError || undefined}
      />

      <Button
        type="submit"
        disabled={!modelName || !apiKey}
        isLoading={loading}
        className="w-full"
      >
        Add Model
      </Button>
    </form>
  );
}

function GitHubAppTab() {
  const { data: config, error, isLoading } = useSWR('github-config', githubApi.getConfig);
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
        installation_id: installationId,
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
                <span className="font-mono text-sm text-gray-200 bg-gray-700 px-2 py-1 rounded">
                  {config?.installation_id_masked || '***'}
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
            label="Installation ID"
            value={installationId}
            onChange={(e) => setInstallationId(e.target.value)}
            placeholder="12345678"
            hint="Find this in your organization's installed apps settings"
            error={saveError || undefined}
          />

          <Button
            type="submit"
            disabled={!appId || !installationId}
            isLoading={loading}
            className="w-full"
          >
            Save Configuration
          </Button>
        </form>
      )}

      {/* Environment variable info */}
      <div className="mt-6 p-4 bg-gray-800/20 border border-gray-700 rounded-lg">
        <h4 className="text-sm font-medium text-gray-300 mb-2">Environment Variables</h4>
        <p className="text-xs text-gray-500 mb-3">
          You can also configure the GitHub App via environment variables:
        </p>
        <div className="font-mono text-xs text-gray-400 space-y-1 bg-gray-800/50 p-3 rounded">
          <div>DURSOR_GITHUB_APP_ID=&lt;app_id&gt;</div>
          <div>DURSOR_GITHUB_APP_PRIVATE_KEY=&lt;base64_encoded_key&gt;</div>
          <div>DURSOR_GITHUB_APP_INSTALLATION_ID=&lt;installation_id&gt;</div>
        </div>
      </div>
    </div>
  );
}

function DefaultsTab() {
  const { data: preferences, isLoading: prefsLoading } = useSWR('preferences', preferencesApi.get);
  const { data: githubConfig } = useSWR('github-config', githubApi.getConfig);
  const { data: repos, isLoading: reposLoading } = useSWR(
    githubConfig?.is_configured ? 'github-repos' : null,
    githubApi.listRepos
  );

  const [selectedRepo, setSelectedRepo] = useState<string>('');
  const [selectedBranch, setSelectedBranch] = useState<string>('');
  const [branches, setBranches] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [branchesLoading, setBranchesLoading] = useState(false);
  const { success, error: toastError } = useToast();

  // Initialize from saved preferences
  useEffect(() => {
    if (preferences && repos) {
      if (preferences.default_repo_owner && preferences.default_repo_name) {
        const repoFullName = `${preferences.default_repo_owner}/${preferences.default_repo_name}`;
        setSelectedRepo(repoFullName);
        // Load branches for the default repo
        loadBranches(preferences.default_repo_owner, preferences.default_repo_name, preferences.default_branch);
      }
    }
  }, [preferences, repos]);

  const loadBranches = async (owner: string, repo: string, defaultBranch?: string | null) => {
    setBranchesLoading(true);
    try {
      const branchList = await githubApi.listBranches(owner, repo);
      setBranches(branchList);
      if (defaultBranch && branchList.includes(defaultBranch)) {
        setSelectedBranch(defaultBranch);
      } else if (branchList.length > 0) {
        // Try to select 'main' or 'master' or the first branch
        const mainBranch = branchList.find(b => b === 'main') || branchList.find(b => b === 'master') || branchList[0];
        setSelectedBranch(mainBranch);
      }
    } catch (err) {
      console.error('Failed to load branches:', err);
      setBranches([]);
    } finally {
      setBranchesLoading(false);
    }
  };

  const handleRepoChange = async (fullName: string) => {
    setSelectedRepo(fullName);
    setSelectedBranch('');
    setBranches([]);

    if (fullName) {
      const [owner, repo] = fullName.split('/');
      await loadBranches(owner, repo);
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
      });
      mutate('preferences');
      success('Default settings saved successfully');
    } catch (err) {
      toastError('Failed to save settings');
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
      });
      setSelectedRepo('');
      setSelectedBranch('');
      setBranches([]);
      mutate('preferences');
      success('Default settings cleared');
    } catch (err) {
      toastError('Failed to clear settings');
    } finally {
      setLoading(false);
    }
  };

  if (!githubConfig?.is_configured) {
    return (
      <div>
        <div className="mb-6">
          <h3 className="text-lg font-semibold text-gray-100">Default Repository & Branch</h3>
          <p className="text-sm text-gray-400 mt-1">
            Set default repository and branch to use when creating new tasks.
          </p>
        </div>
        <div className="flex items-center gap-2 p-3 bg-yellow-900/20 border border-yellow-800/50 rounded-lg text-yellow-400 text-sm">
          <ExclamationTriangleIcon className="w-5 h-5 flex-shrink-0" />
          <span>Configure GitHub App first to select default repository.</span>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6">
        <h3 className="text-lg font-semibold text-gray-100">Default Repository & Branch</h3>
        <p className="text-sm text-gray-400 mt-1">
          Set default repository and branch to use when creating new tasks.
        </p>
      </div>

      {/* Current defaults display */}
      {preferences?.default_repo_owner && preferences?.default_repo_name && (
        <div className="mb-4 p-3 bg-green-900/20 border border-green-800/50 rounded-lg flex items-center gap-2 text-green-400">
          <CheckCircleIcon className="w-5 h-5 flex-shrink-0" />
          <span className="text-sm">
            Default: <span className="font-medium">{preferences.default_repo_owner}/{preferences.default_repo_name}</span>
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
            Repository
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
            <option value="">Select a repository</option>
            {repos?.map((repo) => (
              <option key={repo.id} value={repo.full_name}>
                {repo.full_name}
              </option>
            ))}
          </select>
          <p className="text-xs text-gray-500">
            Select the repository that will be pre-selected when creating new tasks.
          </p>
        </div>

        {/* Branch selection */}
        <div className="space-y-1">
          <label className="block text-sm font-medium text-gray-300">
            Branch
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
              {branchesLoading ? 'Loading branches...' : 'Select a branch'}
            </option>
            {branches.map((branch) => (
              <option key={branch} value={branch}>
                {branch}
              </option>
            ))}
          </select>
          <p className="text-xs text-gray-500">
            Select the branch that will be pre-selected when creating new tasks.
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
            Save Defaults
          </Button>
          <Button
            onClick={handleClear}
            variant="secondary"
            disabled={!preferences?.default_repo_owner}
            isLoading={loading}
          >
            Clear
          </Button>
        </div>
      </div>
    </div>
  );
}
