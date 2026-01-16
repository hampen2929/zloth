/**
 * Terminology and Microcopy for dursor UI
 * Centralized text strings for consistent UI language
 */

/**
 * Core terminology definitions
 * These are the standardized terms used throughout the application
 */
export const terms = {
  task: 'Task',
  run: 'Run',
  executor: 'Executor',
  instruction: 'Instruction',
  model: 'Model',
  repo: 'Repository',
  branch: 'Branch',
  pr: 'Pull Request',
} as const;

/**
 * Japanese translations for core terms
 */
export const termsJa = {
  task: 'タスク',
  run: '実行',
  executor: '実行器',
  instruction: '指示',
  model: 'モデル',
  repo: 'リポジトリ',
  branch: 'ブランチ',
  pr: 'プルリクエスト',
} as const;

/**
 * Status labels for runs
 */
export const runStatusLabels = {
  queued: 'Queued',
  running: 'Running',
  succeeded: 'Completed',
  failed: 'Failed',
  cancelled: 'Cancelled',
} as const;

export const runStatusLabelsJa = {
  queued: '待機中',
  running: '実行中',
  succeeded: '完了',
  failed: '失敗',
  cancelled: 'キャンセル',
} as const;

/**
 * Action button labels
 */
export const actionLabels = {
  create: 'Create',
  submit: 'Submit',
  cancel: 'Cancel',
  delete: 'Delete',
  save: 'Save',
  retry: 'Retry',
  run: 'Run',
  stop: 'Stop',
  copy: 'Copy',
  expand: 'Expand',
  collapse: 'Collapse',
  close: 'Close',
  view: 'View',
  edit: 'Edit',
  confirm: 'Confirm',
} as const;

export const actionLabelsJa = {
  create: '作成',
  submit: '送信',
  cancel: 'キャンセル',
  delete: '削除',
  save: '保存',
  retry: '再試行',
  run: '実行',
  stop: '停止',
  copy: 'コピー',
  expand: '展開',
  collapse: '折りたたむ',
  close: '閉じる',
  view: '表示',
  edit: '編集',
  confirm: '確認',
} as const;

/**
 * Empty state messages
 */
export const emptyStates = {
  noTasks: {
    title: 'No tasks yet',
    description: 'Create your first task to get started',
    action: 'Create Task',
  },
  noRuns: {
    title: 'No runs yet',
    description: 'Run your first task to see results here',
    action: 'Run Task',
  },
  noModels: {
    title: 'No models configured',
    description: 'Add a model in Settings to start using dursor',
    action: 'Add Model',
  },
  noRepos: {
    title: 'No repositories',
    description: 'Configure GitHub App to access your repositories',
    action: 'Configure GitHub',
  },
} as const;

export const emptyStatesJa = {
  noTasks: {
    title: 'タスクがありません',
    description: '最初のタスクを作成して始めましょう',
    action: 'タスクを作成',
  },
  noRuns: {
    title: '実行履歴がありません',
    description: 'タスクを実行すると結果がここに表示されます',
    action: 'タスクを実行',
  },
  noModels: {
    title: 'モデルが未設定です',
    description: '設定からモデルを追加してdursorを使い始めましょう',
    action: 'モデルを追加',
  },
  noRepos: {
    title: 'リポジトリがありません',
    description: 'GitHub Appを設定してリポジトリにアクセスできるようにしましょう',
    action: 'GitHubを設定',
  },
} as const;

/**
 * Validation messages
 */
export const validationMessages = {
  required: (field: string) => `${field} is required`,
  minLength: (field: string, min: number) => `${field} must be at least ${min} characters`,
  maxLength: (field: string, max: number) => `${field} must be at most ${max} characters`,
  invalidFormat: (field: string) => `${field} has an invalid format`,
  selectRequired: (field: string) => `Please select a ${field.toLowerCase()}`,
} as const;

export const validationMessagesJa = {
  required: (field: string) => `${field}を入力してください`,
  minLength: (field: string, min: number) => `${field}は${min}文字以上で入力してください`,
  maxLength: (field: string, max: number) => `${field}は${max}文字以内で入力してください`,
  invalidFormat: (field: string) => `${field}の形式が正しくありません`,
  selectRequired: (field: string) => `${field}を選択してください`,
} as const;

/**
 * Success messages
 */
export const successMessages = {
  taskCreated: 'Task created successfully',
  runStarted: 'Run started',
  prCreated: 'Pull request created',
  settingsSaved: 'Settings saved',
  copied: 'Copied to clipboard',
  deleted: 'Deleted successfully',
} as const;

export const successMessagesJa = {
  taskCreated: 'タスクを作成しました',
  runStarted: '実行を開始しました',
  prCreated: 'プルリクエストを作成しました',
  settingsSaved: '設定を保存しました',
  copied: 'クリップボードにコピーしました',
  deleted: '削除しました',
} as const;

/**
 * Tab labels for run detail panel
 */
export const runDetailTabs = {
  summary: 'Summary',
  diff: 'Diff',
  logs: 'Logs',
} as const;

export const runDetailTabsJa = {
  summary: 'サマリー',
  diff: '差分',
  logs: 'ログ',
} as const;

/**
 * Filter labels
 */
export const filterLabels = {
  all: 'All',
  succeeded: 'Succeeded',
  failed: 'Failed',
  running: 'Running',
} as const;

export const filterLabelsJa = {
  all: 'すべて',
  succeeded: '成功',
  failed: '失敗',
  running: '実行中',
} as const;

/**
 * Executor type labels
 */
export const executorTypeLabels = {
  patch_agent: 'Models',
  claude_code: 'Claude Code',
  codex: 'Codex',
  gemini_cli: 'Gemini CLI',
} as const;

export const executorTypeLabelsJa = {
  patch_agent: 'モデル',
  claude_code: 'Claude Code',
  codex: 'Codex',
  gemini_cli: 'Gemini CLI',
} as const;

/**
 * Aria labels for accessibility
 */
export const ariaLabels = {
  closeModal: 'Close modal',
  closeDialog: 'Close dialog',
  dismissNotification: 'Dismiss notification',
  toggleMenu: 'Toggle menu',
  expandSection: 'Expand section',
  collapseSection: 'Collapse section',
  copyToClipboard: 'Copy to clipboard',
  selectOption: 'Select option',
  removeItem: 'Remove item',
  loadMore: 'Load more',
  refresh: 'Refresh',
  search: 'Search',
} as const;

export const ariaLabelsJa = {
  closeModal: 'モーダルを閉じる',
  closeDialog: 'ダイアログを閉じる',
  dismissNotification: '通知を閉じる',
  toggleMenu: 'メニューを切り替え',
  expandSection: 'セクションを展開',
  collapseSection: 'セクションを折りたたむ',
  copyToClipboard: 'クリップボードにコピー',
  selectOption: 'オプションを選択',
  removeItem: '削除',
  loadMore: 'さらに読み込む',
  refresh: '更新',
  search: '検索',
} as const;
