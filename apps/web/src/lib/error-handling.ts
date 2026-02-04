/**
 * Error classification and recommended action utilities
 */

export type ErrorType =
  | 'network' // Temporary network error
  | 'auth' // Authentication error
  | 'permission' // Permission error
  | 'rate_limit' // API rate limit
  | 'conflict' // Git conflict
  | 'execution' // Runtime execution error
  | 'unknown'; // Unknown error

export interface ErrorAction {
  label: string;
  type: 'retry' | 'retry_delayed' | 'switch_model' | 'view_logs' | 'settings' | 'external';
  delayMs?: number;
  href?: string;
}

export interface ErrorDisplay {
  title: string;
  message: string;
  type: ErrorType;
  actions: ErrorAction[];
  retryable: boolean;
}

export interface ErrorTranslations {
  unknownError: string;
  connectionError: string;
  connectionErrorDesc: string;
  authError: string;
  authErrorDesc: string;
  checkModelSettings: string;
  tryDifferentModel: string;
  permissionError: string;
  permissionErrorDesc: string;
  checkGitHubSettings: string;
  rateLimitError: string;
  rateLimitErrorDesc: string;
  retryInOneMinute: string;
  conflictError: string;
  conflictErrorDesc: string;
  executionError: string;
  genericError: string;
  retry: string;
  viewLogs: string;
}

// Default English translations
const defaultTranslations: ErrorTranslations = {
  unknownError: 'An unknown error occurred',
  connectionError: 'Connection Error',
  connectionErrorDesc: 'Failed to connect to the server. Please check your internet connection.',
  authError: 'Authentication Error',
  authErrorDesc: 'Your API key is invalid or expired. Please check your settings.',
  checkModelSettings: 'Check model settings',
  tryDifferentModel: 'Try different model',
  permissionError: 'Permission Error',
  permissionErrorDesc: 'You do not have permission to access this resource.',
  checkGitHubSettings: 'Check GitHub settings',
  rateLimitError: 'API Rate Limit Reached',
  rateLimitErrorDesc: 'You have reached the API rate limit. Please wait and try again.',
  retryInOneMinute: 'Retry in 1 minute',
  conflictError: 'Conflict Error',
  conflictErrorDesc: 'There is a conflict in the branch. Manual resolution is required.',
  executionError: 'Execution Error',
  genericError: 'An error occurred',
  retry: 'Retry',
  viewLogs: 'View logs',
};

/**
 * Classify error type based on error message
 */
export function classifyError(error: string | null | undefined): ErrorType {
  if (!error) return 'unknown';

  const lowerError = error.toLowerCase();

  // Network errors
  if (
    lowerError.includes('network') ||
    lowerError.includes('connection') ||
    lowerError.includes('timeout') ||
    lowerError.includes('econnrefused') ||
    lowerError.includes('fetch failed')
  ) {
    return 'network';
  }

  // Authentication errors
  if (
    lowerError.includes('unauthorized') ||
    lowerError.includes('401') ||
    lowerError.includes('authentication') ||
    lowerError.includes('invalid api key') ||
    lowerError.includes('api key')
  ) {
    return 'auth';
  }

  // Permission errors
  if (
    lowerError.includes('permission') ||
    lowerError.includes('403') ||
    lowerError.includes('forbidden') ||
    lowerError.includes('access denied')
  ) {
    return 'permission';
  }

  // Rate limit errors
  if (
    lowerError.includes('rate limit') ||
    lowerError.includes('429') ||
    lowerError.includes('too many requests') ||
    lowerError.includes('quota')
  ) {
    return 'rate_limit';
  }

  // Git conflict errors
  if (
    lowerError.includes('conflict') ||
    lowerError.includes('merge') ||
    lowerError.includes('rebase')
  ) {
    return 'conflict';
  }

  // Execution errors (fallback for other runtime errors)
  if (
    lowerError.includes('error') ||
    lowerError.includes('failed') ||
    lowerError.includes('exception')
  ) {
    return 'execution';
  }

  return 'unknown';
}

/**
 * Get display information for an error
 */
export function getErrorDisplay(
  error: string | null | undefined,
  translations: ErrorTranslations = defaultTranslations
): ErrorDisplay {
  const errorType = classifyError(error);
  const errorMessage = error || translations.unknownError;

  switch (errorType) {
    case 'network':
      return {
        title: translations.connectionError,
        message: translations.connectionErrorDesc,
        type: 'network',
        actions: [{ label: translations.retry, type: 'retry' }],
        retryable: true,
      };

    case 'auth':
      return {
        title: translations.authError,
        message: translations.authErrorDesc,
        type: 'auth',
        actions: [
          { label: translations.checkModelSettings, type: 'settings', href: '#settings-models' },
          { label: translations.tryDifferentModel, type: 'switch_model' },
        ],
        retryable: false,
      };

    case 'permission':
      return {
        title: translations.permissionError,
        message: translations.permissionErrorDesc,
        type: 'permission',
        actions: [
          { label: translations.checkGitHubSettings, type: 'settings', href: '#settings-github' },
        ],
        retryable: false,
      };

    case 'rate_limit':
      return {
        title: translations.rateLimitError,
        message: translations.rateLimitErrorDesc,
        type: 'rate_limit',
        actions: [
          { label: translations.retryInOneMinute, type: 'retry_delayed', delayMs: 60000 },
          { label: translations.tryDifferentModel, type: 'switch_model' },
        ],
        retryable: true,
      };

    case 'conflict':
      return {
        title: translations.conflictError,
        message: translations.conflictErrorDesc,
        type: 'conflict',
        actions: [{ label: translations.viewLogs, type: 'view_logs' }],
        retryable: false,
      };

    case 'execution':
      return {
        title: translations.executionError,
        message: errorMessage,
        type: 'execution',
        actions: [
          { label: translations.retry, type: 'retry' },
          { label: translations.viewLogs, type: 'view_logs' },
        ],
        retryable: true,
      };

    default:
      return {
        title: translations.genericError,
        message: errorMessage,
        type: 'unknown',
        actions: [
          { label: translations.retry, type: 'retry' },
          { label: translations.viewLogs, type: 'view_logs' },
        ],
        retryable: true,
      };
  }
}
