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
export function getErrorDisplay(error: string | null | undefined): ErrorDisplay {
  const errorType = classifyError(error);
  const errorMessage = error || '不明なエラーが発生しました';

  switch (errorType) {
    case 'network':
      return {
        title: '接続エラー',
        message: 'サーバーに接続できませんでした。インターネット接続を確認してください。',
        type: 'network',
        actions: [{ label: '再試行', type: 'retry' }],
        retryable: true,
      };

    case 'auth':
      return {
        title: '認証エラー',
        message: 'APIキーが無効または期限切れです。設定を確認してください。',
        type: 'auth',
        actions: [
          { label: 'モデル設定を確認', type: 'settings', href: '#settings-models' },
          { label: '別のモデルで実行', type: 'switch_model' },
        ],
        retryable: false,
      };

    case 'permission':
      return {
        title: '権限エラー',
        message: 'このリソースへのアクセス権限がありません。',
        type: 'permission',
        actions: [
          { label: 'GitHub設定を確認', type: 'settings', href: '#settings-github' },
        ],
        retryable: false,
      };

    case 'rate_limit':
      return {
        title: 'API制限に達しました',
        message: 'APIのレート制限に達しました。しばらく待ってから再試行してください。',
        type: 'rate_limit',
        actions: [
          { label: '1分後に再試行', type: 'retry_delayed', delayMs: 60000 },
          { label: '別のモデルで実行', type: 'switch_model' },
        ],
        retryable: true,
      };

    case 'conflict':
      return {
        title: 'コンフリクトエラー',
        message: 'ブランチにコンフリクトが発生しています。手動で解決が必要です。',
        type: 'conflict',
        actions: [{ label: 'ログを確認', type: 'view_logs' }],
        retryable: false,
      };

    case 'execution':
      return {
        title: '実行エラー',
        message: errorMessage,
        type: 'execution',
        actions: [
          { label: '再試行', type: 'retry' },
          { label: 'ログを確認', type: 'view_logs' },
        ],
        retryable: true,
      };

    default:
      return {
        title: 'エラーが発生しました',
        message: errorMessage,
        type: 'unknown',
        actions: [
          { label: '再試行', type: 'retry' },
          { label: 'ログを確認', type: 'view_logs' },
        ],
        retryable: true,
      };
  }
}
