/**
 * Terminology and Microcopy for zloth UI
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
    description: 'Add a model in Settings to start using zloth',
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
    description: '設定からモデルを追加してzlothを使い始めましょう',
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

/**
 * Settings UI labels
 */
export const settingsLabels = {
  title: 'Settings',
  tabs: {
    executors: 'Executors',
    github: 'GitHub App',
    defaults: 'Defaults',
  },
  defaults: {
    title: 'Default Repository & Branch',
    description: 'Set default repository and branch to use when creating new tasks.',
    currentDefault: 'Default',
    configureGithubFirst: 'Configure GitHub App first to select default repository.',
    repository: 'Repository',
    repositoryHint: 'Select the repository that will be pre-selected when creating new tasks.',
    selectRepository: 'Select a repository',
    branch: 'Branch',
    branchHint: 'Select the branch that will be pre-selected when creating new tasks.',
    selectBranch: 'Select a branch',
    loadingBranches: 'Loading branches...',
    branchPrefix: 'Branch Prefix',
    branchPrefixHint: 'Prefix used for new work branches (e.g., zloth/abcd1234). Leave blank to use the default.',
    codingMode: 'Default Coding Mode',
    codingModeHint: 'Choose the default coding mode for new tasks.',
    codingModeOptions: {
      interactive: 'Interactive - Manual control',
      semiAuto: 'Semi Auto - Autonomous with human approval for merge',
      fullAuto: 'Full Auto - Fully autonomous including merge',
    },
    prCreationMode: 'Create PR behavior',
    prCreationModeHint: 'Choose whether "Create PR" creates the PR immediately or opens the GitHub PR creation page.',
    prCreationModeOptions: {
      create: 'Create PR automatically',
      link: 'Open PR link (manual creation)',
    },
    autoGeneratePrDescription: 'Auto-generate PR description',
    autoGeneratePrDescriptionHint: 'If enabled, AI will generate the PR description when creating a PR (slower). If disabled, a simple description is used and you can generate it later with "Update PR".',
    enableGating: 'Enable Gating status',
    enableGatingHint: 'If enabled, tasks with open PRs and pending CI will show in "Gating" column. When CI completes, they move to "In Review".',
    mergeMethod: 'Merge Method',
    mergeMethodHint: 'Choose the default merge strategy for full auto mode.',
    mergeMethodOptions: {
      merge: 'Merge commit',
      squash: 'Squash and merge',
      rebase: 'Rebase and merge',
    },
    reviewMinScore: 'Review minimum score',
    reviewMinScoreHint: 'Minimum review score required before auto-merge (0.0 - 1.0).',
    notifications: 'Notification preferences',
    notificationsHint: 'Notification toggles apply to Slack and log notifications.',
    notifyOnReady: 'Notify when PR is ready',
    notifyOnComplete: 'Notify when run completes',
    notifyOnFailure: 'Notify on failures',
    notifyOnWarning: 'Notify on warnings',
    language: 'Language',
    languageHint: 'Select the display language for the UI.',
    languageOptions: {
      en: 'English',
      ja: '日本語',
    },
    saveDefaults: 'Save Defaults',
    clearDefaults: 'Clear',
    savedSuccess: 'Default settings saved successfully',
    clearedSuccess: 'Default settings cleared',
    saveFailed: 'Failed to save settings',
    clearFailed: 'Failed to clear settings',
  },
  github: {
    title: 'GitHub App Configuration',
    description: 'Connect a GitHub App to create pull requests and access repositories.',
    configured: 'GitHub App is configured',
    notConfigured: 'GitHub App not configured',
    viaEnv: 'via .env',
    envConfig: 'Configuration from Environment Variables',
    appId: 'App ID',
    privateKey: 'Private Key',
    privateKeyConfigured: 'Configured',
    privateKeyNotSet: 'Not set',
    installationId: 'Installation ID (optional)',
    installationIdAuto: 'Auto (all installations)',
    envConfigHint: 'To modify these values, update your .env file and restart the application.',
    appIdHint: 'Find this in your GitHub App settings page',
    privateKeyHint: 'Paste the private key generated from your GitHub App',
    privateKeyUpdateHint: 'Leave blank to keep existing key. Paste new key to update.',
    installationIdHint: 'Optional: If not set, all installations of this GitHub App will be available. Find this in your organization\'s installed apps settings.',
    saveConfig: 'Save Configuration',
    savedSuccess: 'GitHub App configuration saved successfully',
    requiredPermissions: 'Required Permissions',
    requiredPermissionsDescription: 'Your GitHub App must have the following permissions:',
    permissions: {
      contents: 'Contents',
      contentsDesc: 'Read & Write - Clone repos, push commits, create branches',
      pullRequests: 'Pull requests',
      pullRequestsDesc: 'Read & Write - Create and update pull requests',
      metadata: 'Metadata',
      metadataDesc: 'Read-only - Access repository metadata (auto-granted)',
    },
    optionalPermissions: 'Optional: Checks (read-only) and Workflows (read & write) for CI integration',
    envVars: 'Environment Variables',
    envVarsDescription: 'You can also configure the GitHub App via environment variables:',
  },
  executors: {
    title: 'CLI Executors',
    description: 'Check availability of AI coding CLIs for parallel execution',
    refresh: 'Refresh',
    available: 'Available',
    notAvailable: 'Not Available',
    path: 'Path',
    version: 'Version',
    envVars: 'Environment Variables',
    envVarsDescription: 'Configure custom CLI paths via environment variables:',
    installation: 'Installation',
    claudeCode: 'Claude Code',
    claudeCodeDesc: 'Anthropic Claude Code CLI for code generation',
    codexCli: 'Codex CLI',
    codexCliDesc: 'OpenAI Codex CLI for code generation',
    geminiCli: 'Gemini CLI',
    geminiCliDesc: 'Google Gemini CLI for code generation',
    checkFailed: 'Failed to check executor status.',
  },
} as const;

/**
 * Keyboard shortcuts labels
 */
export const keyboardShortcuts = {
  title: 'Keyboard Shortcuts',
  hint: 'Tip: Most shortcuts work from anywhere',
  openSettings: 'Open settings',
  showShortcuts: 'Show shortcuts list',
  newTask: 'New task',
  submitTask: 'Submit task',
  focusInput: 'Focus input field',
  closeModal: 'Close modal',
} as const;

export const keyboardShortcutsJa = {
  title: 'キーボードショートカット',
  hint: 'ヒント: ほとんどのショートカットはどこからでも使えます',
  openSettings: '設定を開く',
  showShortcuts: 'ショートカット一覧を表示',
  newTask: '新規タスク',
  submitTask: 'タスクを送信',
  focusInput: '入力欄にフォーカス',
  closeModal: 'モーダルを閉じる',
} as const;

/**
 * Home page labels
 */
export const homeLabels = {
  githubNotConfigured: 'GitHub App is not configured',
  configureGithub: 'Configure',
  selectRepository: 'Please select a repository',
  selectBranch: 'Please select a branch',
  selectCLI: 'Please select a CLI',
  settingUpWorkspace: 'Setting up workspace...',
  loadingRepositories: 'Loading repositories...',
  noRepositoriesFound: 'No repositories found',
} as const;

export const homeLabelsJa = {
  githubNotConfigured: 'GitHub Appが未設定です',
  configureGithub: '設定する',
  selectRepository: 'リポジトリを選択してください',
  selectBranch: 'ブランチを選択してください',
  selectCLI: 'CLIを選択してください',
  settingUpWorkspace: 'ワークスペースを設定中...',
  loadingRepositories: 'リポジトリを読み込み中...',
  noRepositoriesFound: 'リポジトリが見つかりません',
} as const;

/**
 * Metrics page labels
 */
export const metricsLabels = {
  pageTitle: 'Metrics & Analysis',
  northStar: 'NORTH STAR',
  northStarDesc: '- Value Definition',
  coreKpi: 'CORE KPI',
  coreKpiDesc: '- Decision Making Metrics (6)',
  diagnosticKpi: 'DIAGNOSTIC KPI',
  diagnosticKpiDesc: '- Root Cause Analysis (7)',
  exploratory: 'EXPLORATORY',
  exploratoryDesc: '- Hypothesis Testing (as needed)',
  repositories: 'REPOSITORIES',
  repositoriesDesc: '- Repository List',
  analysis: 'ANALYSIS',
  analysisDesc: '- Prompt Analysis',
  period: 'Period',
  refresh: 'Refresh',
} as const;

export const metricsLabelsJa = {
  pageTitle: 'メトリクス & 分析',
  northStar: 'NORTH STAR',
  northStarDesc: '- 価値の定義',
  coreKpi: 'CORE KPI',
  coreKpiDesc: '- 改善の意思決定（6指標）',
  diagnosticKpi: 'DIAGNOSTIC KPI',
  diagnosticKpiDesc: '- 原因分析（7指標）',
  exploratory: 'EXPLORATORY',
  exploratoryDesc: '- 仮説検証（必要時）',
  repositories: 'REPOSITORIES',
  repositoriesDesc: '- リポジトリ一覧',
  analysis: 'ANALYSIS',
  analysisDesc: '- プロンプト分析',
  period: '期間',
  refresh: '更新',
} as const;

/**
 * Run detail panel labels
 */
export const runDetailLabels = {
  recommendedActions: 'Recommended Actions',
  retryInSeconds: 'Retry in {seconds}s',
  viewLogs: 'View logs',
} as const;

export const runDetailLabelsJa = {
  recommendedActions: '推奨アクション',
  retryInSeconds: '{seconds}秒後に再試行',
  viewLogs: 'ログを確認',
} as const;

/**
 * Runs panel labels
 */
export const runsPanelLabels = {
  noRunsYet: 'No runs yet',
  enterInstructionsToStart: 'Enter instructions to start',
  noSucceededRuns: 'No succeeded runs',
  noFailedRuns: 'No failed runs',
  noRunningRuns: 'No running tasks',
  showAll: 'Show all',
} as const;

export const runsPanelLabelsJa = {
  noRunsYet: '実行履歴がありません',
  enterInstructionsToStart: '指示を入力して開始してください',
  noSucceededRuns: '成功した実行はありません',
  noFailedRuns: '失敗した実行はありません',
  noRunningRuns: '実行中のタスクはありません',
  showAll: 'すべて表示',
} as const;

/**
 * Accessibility announcements for screen readers
 */
export const announcements = {
  runStarted: '{model} run started',
  runCompleted: '{model} run completed',
  runFailed: '{model} run failed',
  runCancelled: '{model} run cancelled',
} as const;

export const announcementsJa = {
  runStarted: '{model} の実行を開始しました',
  runCompleted: '{model} の実行が完了しました',
  runFailed: '{model} の実行が失敗しました',
  runCancelled: '{model} の実行がキャンセルされました',
} as const;

/**
 * Error messages
 */
export const errorMessages = {
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
} as const;

export const errorMessagesJa = {
  unknownError: '不明なエラーが発生しました',
  connectionError: '接続エラー',
  connectionErrorDesc: 'サーバーに接続できませんでした。インターネット接続を確認してください。',
  authError: '認証エラー',
  authErrorDesc: 'APIキーが無効または期限切れです。設定を確認してください。',
  checkModelSettings: 'モデル設定を確認',
  tryDifferentModel: '別のモデルで実行',
  permissionError: '権限エラー',
  permissionErrorDesc: 'このリソースへのアクセス権限がありません。',
  checkGitHubSettings: 'GitHub設定を確認',
  rateLimitError: 'API制限に達しました',
  rateLimitErrorDesc: 'APIのレート制限に達しました。しばらく待ってから再試行してください。',
  retryInOneMinute: '1分後に再試行',
  conflictError: 'コンフリクトエラー',
  conflictErrorDesc: 'ブランチにコンフリクトが発生しています。手動で解決が必要です。',
  executionError: '実行エラー',
  genericError: 'エラーが発生しました',
  retry: '再試行',
  viewLogs: 'ログを確認',
} as const;

export const settingsLabelsJa = {
  title: '設定',
  tabs: {
    executors: '実行環境',
    github: 'GitHub App',
    defaults: 'デフォルト',
  },
  defaults: {
    title: 'デフォルトリポジトリとブランチ',
    description: '新しいタスク作成時に使用するデフォルトのリポジトリとブランチを設定します。',
    currentDefault: 'デフォルト',
    configureGithubFirst: '先にGitHub Appを設定してリポジトリを選択してください。',
    repository: 'リポジトリ',
    repositoryHint: '新しいタスク作成時に事前選択されるリポジトリを選択します。',
    selectRepository: 'リポジトリを選択',
    branch: 'ブランチ',
    branchHint: '新しいタスク作成時に事前選択されるブランチを選択します。',
    selectBranch: 'ブランチを選択',
    loadingBranches: 'ブランチを読み込み中...',
    branchPrefix: 'ブランチプレフィックス',
    branchPrefixHint: '新しい作業ブランチに使用するプレフィックス（例: zloth/abcd1234）。空欄の場合はデフォルトを使用します。',
    codingMode: 'デフォルトコーディングモード',
    codingModeHint: '新しいタスクのデフォルトコーディングモードを選択します。',
    codingModeOptions: {
      interactive: 'インタラクティブ - 手動制御',
      semiAuto: 'セミオート - マージ前に人間の承認が必要',
      fullAuto: 'フルオート - マージを含めて完全自動',
    },
    prCreationMode: 'PR作成時の動作',
    prCreationModeHint: '「PRを作成」がPRを即座に作成するか、GitHubのPR作成ページを開くかを選択します。',
    prCreationModeOptions: {
      create: 'PRを自動作成',
      link: 'PRリンクを開く（手動作成）',
    },
    autoGeneratePrDescription: 'PR説明文を自動生成',
    autoGeneratePrDescriptionHint: '有効にすると、PR作成時にAIが説明文を生成します（やや遅くなります）。無効の場合はシンプルな説明文が使用され、後から「PRを更新」で生成できます。',
    enableGating: 'ゲーティングステータスを有効化',
    enableGatingHint: '有効にすると、オープンなPRとペンディング中のCIがあるタスクは「ゲーティング」列に表示されます。CI完了後、「レビュー中」に移動します。',
    mergeMethod: 'マージ方法',
    mergeMethodHint: 'フルオートモードでのデフォルトのマージ戦略を選択します。',
    mergeMethodOptions: {
      merge: 'マージコミット',
      squash: 'スカッシュしてマージ',
      rebase: 'リベースしてマージ',
    },
    reviewMinScore: 'レビュー最低スコア',
    reviewMinScoreHint: '自動マージに必要な最低レビュースコア（0.0 - 1.0）。',
    notifications: '通知設定',
    notificationsHint: '通知設定はSlackとログ通知に適用されます。',
    notifyOnReady: 'PRの準備ができたら通知',
    notifyOnComplete: '実行完了時に通知',
    notifyOnFailure: '失敗時に通知',
    notifyOnWarning: '警告時に通知',
    language: '言語',
    languageHint: 'UIの表示言語を選択します。',
    languageOptions: {
      en: 'English',
      ja: '日本語',
    },
    saveDefaults: 'デフォルト設定を保存',
    clearDefaults: 'クリア',
    savedSuccess: 'デフォルト設定を保存しました',
    clearedSuccess: 'デフォルト設定をクリアしました',
    saveFailed: '設定の保存に失敗しました',
    clearFailed: '設定のクリアに失敗しました',
  },
  github: {
    title: 'GitHub App 設定',
    description: 'GitHub Appを接続してプルリクエストの作成とリポジトリへのアクセスを有効にします。',
    configured: 'GitHub Appは設定済みです',
    notConfigured: 'GitHub Appが未設定です',
    viaEnv: '.env経由',
    envConfig: '環境変数からの設定',
    appId: 'App ID',
    privateKey: '秘密鍵',
    privateKeyConfigured: '設定済み',
    privateKeyNotSet: '未設定',
    installationId: 'Installation ID（オプション）',
    installationIdAuto: '自動（全インストール）',
    envConfigHint: 'これらの値を変更するには、.envファイルを更新してアプリケーションを再起動してください。',
    appIdHint: 'GitHub Appの設定ページで確認できます',
    privateKeyHint: 'GitHub Appから生成した秘密鍵を貼り付けてください',
    privateKeyUpdateHint: '既存のキーを保持する場合は空欄のままにしてください。新しいキーに更新する場合は貼り付けてください。',
    installationIdHint: 'オプション：設定しない場合、このGitHub Appの全インストールが利用可能になります。組織のインストール済みアプリ設定で確認できます。',
    saveConfig: '設定を保存',
    savedSuccess: 'GitHub App設定を保存しました',
    requiredPermissions: '必要な権限',
    requiredPermissionsDescription: 'GitHub Appには以下の権限が必要です:',
    permissions: {
      contents: 'Contents',
      contentsDesc: '読み取り/書き込み - リポジトリのクローン、コミットのプッシュ、ブランチの作成',
      pullRequests: 'Pull requests',
      pullRequestsDesc: '読み取り/書き込み - プルリクエストの作成と更新',
      metadata: 'Metadata',
      metadataDesc: '読み取り専用 - リポジトリメタデータへのアクセス（自動付与）',
    },
    optionalPermissions: 'オプション：Checks（読み取り専用）とWorkflows（読み取り/書き込み）でCI連携',
    envVars: '環境変数',
    envVarsDescription: '環境変数でもGitHub Appを設定できます:',
  },
  executors: {
    title: 'CLI実行環境',
    description: '並列実行用のAIコーディングCLIの利用可能状況を確認',
    refresh: '更新',
    available: '利用可能',
    notAvailable: '利用不可',
    path: 'パス',
    version: 'バージョン',
    envVars: '環境変数',
    envVarsDescription: '環境変数でカスタムCLIパスを設定できます:',
    installation: 'インストール',
    claudeCode: 'Claude Code',
    claudeCodeDesc: 'AnthropicのClaude Code CLI（コード生成用）',
    codexCli: 'Codex CLI',
    codexCliDesc: 'OpenAIのCodex CLI（コード生成用）',
    geminiCli: 'Gemini CLI',
    geminiCliDesc: 'GoogleのGemini CLI（コード生成用）',
    checkFailed: '実行環境のステータス確認に失敗しました。',
  },
} as const;
