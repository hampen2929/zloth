'use client';

import { useState, useEffect } from 'react';
import useSWR, { mutate } from 'swr';
import { modelsApi, githubApi } from '@/lib/api';
import type { Provider, ModelProfileCreate, GitHubAppConfig } from '@/types';

const PROVIDERS: { value: Provider; label: string; models: string[] }[] = [
  {
    value: 'openai',
    label: 'OpenAI',
    models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'o1', 'o1-mini'],
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

type TabType = 'models' | 'github';

export default function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const [activeTab, setActiveTab] = useState<TabType>('models');

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative w-full max-w-3xl max-h-[85vh] bg-gray-900 border border-gray-700 rounded-xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <h2 className="text-xl font-semibold text-white">Settings</h2>
          <button
            onClick={onClose}
            className="p-1 text-gray-400 hover:text-white transition-colors rounded-lg hover:bg-gray-800"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-800">
          <button
            onClick={() => setActiveTab('models')}
            className={`px-6 py-3 text-sm font-medium transition-colors ${
              activeTab === 'models'
                ? 'text-white border-b-2 border-blue-500'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            Configured Models
          </button>
          <button
            onClick={() => setActiveTab('github')}
            className={`px-6 py-3 text-sm font-medium transition-colors ${
              activeTab === 'github'
                ? 'text-white border-b-2 border-blue-500'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            GitHub App
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[calc(85vh-140px)]">
          {activeTab === 'models' && <ModelsTab />}
          {activeTab === 'github' && <GitHubAppTab />}
        </div>
      </div>
    </div>
  );
}

function ModelsTab() {
  const { data: models, error } = useSWR('models', modelsApi.list);
  const [showForm, setShowForm] = useState(false);

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-medium text-white">Model Profiles</h3>
          <p className="text-sm text-gray-400 mt-1">
            Configure LLM providers and API keys for parallel execution
          </p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 rounded text-sm font-medium transition-colors"
        >
          {showForm ? 'Cancel' : 'Add Model'}
        </button>
      </div>

      {showForm && <AddModelForm onSuccess={() => setShowForm(false)} />}

      {error && (
        <p className="text-red-400 text-sm mt-4">Failed to load models.</p>
      )}

      {models && models.length === 0 && !showForm && (
        <div className="mt-4 p-4 bg-gray-800/50 border border-gray-700 rounded-lg text-center">
          <p className="text-gray-400 text-sm">
            No models configured. Add your API keys to get started.
          </p>
        </div>
      )}

      {models && models.length > 0 && (
        <div className="space-y-2 mt-4">
          {models.map((model) => (
            <div
              key={model.id}
              className="flex items-center justify-between p-4 bg-gray-800/50 rounded-lg border border-gray-700"
            >
              <div>
                <div className="font-medium text-white">
                  {model.display_name || model.model_name}
                </div>
                <div className="text-sm text-gray-500">
                  {model.provider} / {model.model_name}
                </div>
              </div>
              <button
                onClick={async () => {
                  await modelsApi.delete(model.id);
                  mutate('models');
                }}
                className="text-red-400 hover:text-red-300 text-sm font-medium transition-colors"
              >
                Delete
              </button>
            </div>
          ))}
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
  const [error, setError] = useState<string | null>(null);

  const selectedProvider = PROVIDERS.find((p) => p.value === provider);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!modelName || !apiKey) return;

    setLoading(true);
    setError(null);

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
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add model');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="p-4 bg-gray-800/50 rounded-lg border border-gray-700 space-y-4 mb-4"
    >
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Provider
          </label>
          <select
            value={provider}
            onChange={(e) => {
              setProvider(e.target.value as Provider);
              setModelName('');
            }}
            className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {PROVIDERS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Model
          </label>
          <select
            value={modelName}
            onChange={(e) => setModelName(e.target.value)}
            className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
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

      <div>
        <label className="block text-sm font-medium text-gray-300 mb-2">
          Display Name (optional)
        </label>
        <input
          type="text"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          placeholder="e.g., GPT-4o (fast)"
          className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-300 mb-2">
          API Key
        </label>
        <input
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder="sk-..."
          className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {error && (
        <div className="p-3 bg-red-900/30 border border-red-800 rounded text-red-400 text-sm">
          {error}
        </div>
      )}

      <button
        type="submit"
        disabled={loading || !modelName || !apiKey}
        className="w-full py-2 px-4 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:cursor-not-allowed rounded font-medium transition-colors"
      >
        {loading ? 'Adding...' : 'Add Model'}
      </button>
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
  const [success, setSuccess] = useState(false);

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
    setSuccess(false);

    try {
      await githubApi.saveConfig({
        app_id: appId,
        private_key: privateKey || undefined,
        installation_id: installationId,
      });
      mutate('github-config');
      setSuccess(true);
      setPrivateKey(''); // Clear private key input after save
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to save configuration');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="mb-6">
        <h3 className="text-lg font-medium text-white">GitHub App Configuration</h3>
        <p className="text-sm text-gray-400 mt-1">
          Connect a GitHub App to create pull requests and access repositories.
          Settings can also be configured via environment variables.
        </p>
      </div>

      {/* Status indicator */}
      {!isLoading && config && (
        <div className={`mb-4 p-3 rounded-lg border ${
          config.is_configured
            ? 'bg-green-900/20 border-green-800 text-green-400'
            : 'bg-yellow-900/20 border-yellow-800 text-yellow-400'
        }`}>
          <div className="flex items-center gap-2">
            {config.is_configured ? (
              <>
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                <span className="text-sm font-medium">GitHub App is configured</span>
                {config.source === 'env' && (
                  <span className="text-xs bg-green-800/50 px-2 py-0.5 rounded">via .env</span>
                )}
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                <span className="text-sm font-medium">GitHub App not configured</span>
              </>
            )}
          </div>
        </div>
      )}

      {/* Environment variables display (read-only) */}
      {isEnvConfig && (
        <div className="space-y-4 mb-6">
          <div className="p-4 bg-gray-800/50 border border-gray-700 rounded-lg">
            <h4 className="text-sm font-medium text-gray-300 mb-3">Configuration from Environment Variables</h4>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-400">App ID</span>
                <span className="font-mono text-sm text-white bg-gray-700 px-2 py-1 rounded">
                  {config?.app_id_masked || '***'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-400">Private Key</span>
                <span className={`text-sm px-2 py-1 rounded ${
                  config?.has_private_key
                    ? 'text-green-400 bg-green-900/30'
                    : 'text-red-400 bg-red-900/30'
                }`}>
                  {config?.has_private_key ? 'Configured' : 'Not set'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-400">Installation ID</span>
                <span className="font-mono text-sm text-white bg-gray-700 px-2 py-1 rounded">
                  {config?.installation_id_masked || '***'}
                </span>
              </div>
            </div>
            <p className="text-xs text-gray-500 mt-3">
              To modify these values, update your .env file and restart the application.
            </p>
          </div>
        </div>
      )}

      {/* Manual configuration form (only when not using env) */}
      {!isEnvConfig && (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              App ID
            </label>
            <input
              type="text"
              value={appId}
              onChange={(e) => setAppId(e.target.value)}
              placeholder="123456"
              className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p className="text-xs text-gray-500 mt-1">
              Find this in your GitHub App settings page
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Private Key
            </label>
            <textarea
              value={privateKey}
              onChange={(e) => setPrivateKey(e.target.value)}
              placeholder="-----BEGIN RSA PRIVATE KEY-----&#10;...&#10;-----END RSA PRIVATE KEY-----"
              rows={4}
              className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-xs"
            />
            <p className="text-xs text-gray-500 mt-1">
              {config?.is_configured
                ? 'Leave blank to keep existing key. Paste new key to update.'
                : 'Paste the private key generated from your GitHub App'}
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Installation ID
            </label>
            <input
              type="text"
              value={installationId}
              onChange={(e) => setInstallationId(e.target.value)}
              placeholder="12345678"
              className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p className="text-xs text-gray-500 mt-1">
              Find this in your organization's installed apps settings
            </p>
          </div>

          {saveError && (
            <div className="p-3 bg-red-900/30 border border-red-800 rounded text-red-400 text-sm">
              {saveError}
            </div>
          )}

          {success && (
            <div className="p-3 bg-green-900/30 border border-green-800 rounded text-green-400 text-sm">
              Configuration saved successfully!
            </div>
          )}

          <div className="flex gap-3">
            <button
              type="submit"
              disabled={loading || !appId || !installationId}
              className="flex-1 py-2 px-4 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:cursor-not-allowed rounded font-medium transition-colors"
            >
              {loading ? 'Saving...' : 'Save Configuration'}
            </button>
          </div>
        </form>
      )}

      {/* Environment variable info */}
      <div className="mt-6 p-4 bg-gray-800/30 border border-gray-700 rounded-lg">
        <h4 className="text-sm font-medium text-gray-300 mb-2">Environment Variables</h4>
        <p className="text-xs text-gray-500 mb-3">
          You can also configure the GitHub App via environment variables:
        </p>
        <div className="font-mono text-xs text-gray-400 space-y-1">
          <div>DURSOR_GITHUB_APP_ID=&lt;app_id&gt;</div>
          <div>DURSOR_GITHUB_APP_PRIVATE_KEY=&lt;base64_encoded_key&gt;</div>
          <div>DURSOR_GITHUB_APP_INSTALLATION_ID=&lt;installation_id&gt;</div>
        </div>
      </div>
    </div>
  );
}
