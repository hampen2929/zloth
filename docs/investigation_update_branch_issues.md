# Investigation: Update Branch後の課題

## 課題サマリー

リモートのUpdate Branch（GitHubのPRでmainをマージ）した後に以下の3つの課題が発生:

1. **AIに指示を出してもCommit&Pushがリモートに反映されない**
2. **Sessionが継続されない** ("No conversation found with session ID")
3. **元々作業していたブランチと異なるブランチで作業を始める**

---

## 課題1: Session継続失敗

### 現象
```
Continuing session: a59797dd-451f-4434-a652-4d178626f009
No conversation found with session ID: a59797dd-451f-4434-a652-4d178626f009
```

### 原因分析

Claude Codeのセッション情報は、Claude CLI側で管理されており、以下の場所に保存される:
- `~/.claude/projects/<project_hash>/sessions/`

**問題のシナリオ:**
1. 最初のRun実行時にsession_id（例: `a59797dd...`）が生成され、DBに保存
2. GitHubでUpdate Branchを実行（これはリモート側の操作）
3. 次のRun実行時に、DBから前回のsession_idを取得して`--resume`で渡す
4. しかし、Claude CLIはワークスペースパスベースでセッションを管理しているため、以下のケースでセッションが見つからない:
   - ワークスペースパスが変更された場合
   - セッションファイルが期限切れや削除された場合
   - 異なるClaude CLI設定/バージョン

**コードの該当箇所** (`run_service.py:836-863`):
```python
result = await executor.execute(
    worktree_path=worktree_info.path,
    instruction=instruction_with_constraints,
    on_output=lambda line: self._log_output(run.id, line),
    resume_session_id=attempt_session_id,  # ← ここで前回のsession_idを渡す
)
# 失敗したらリトライ
if (not result.success and attempt_session_id and ...):
    logs.append(f"Session continuation failed ({result.error}). Retrying without session_id.")
    result = await executor.execute(...)  # ← リトライ時はsession_id=None
```

**現状の動作:**
- リトライロジックは存在するが、リトライ時に新しいセッションが開始される
- これ自体は正常な動作（フォールバック）

### 解決策

**A. セッション継続の信頼性向上（推奨）**

1. **セッションの有効性事前チェック**
   - `--resume`で渡す前に、セッションファイルの存在を確認
   - Claude CLIのセッションディレクトリを直接チェック

2. **ワークスペースパスの一貫性確保**
   - 既存ワークスペース再利用時のパス変更を防ぐ
   - `run_id`ではなく`task_id + executor_type`でワークスペースを識別

```python
# 提案: セッションの存在確認
async def _check_session_valid(self, session_id: str, workspace_path: Path) -> bool:
    """Check if a Claude Code session is still valid."""
    # Claude stores sessions in ~/.claude/projects/<hash>/sessions/
    claude_dir = Path.home() / ".claude"
    if not claude_dir.exists():
        return False
    # Hash calculation based on workspace path (Claude's internal logic)
    # ... implementation
```

**B. セッション継続をオプショナル化**

- フロントエンドからセッション継続を明示的に選択可能にする
- 新規セッションか継続かをユーザーが選べるようにする

---

## 課題2: Commit&Pushがリモートに反映されない

### 現象
- AIがファイルを編集
- `git add` と `git commit` は成功
- しかしリモートにpushされていない、またはPRに反映されない

### 原因分析

サーバーログより:
```
Failed to get PR data: Client error '404 Not Found' for url
'https://api.github.com/repos/hampen2929/zloth/pulls/267'
```

**考えられる原因:**

1. **PRが存在しない/削除された**
   - PR #267 が存在しない（番号が間違っている、または削除された）

2. **ブランチ名の不一致**
   - 新しいRunが異なるブランチで作業を開始
   - PRは元のブランチ（例: `zloth/7adabce0`）を参照
   - 新しい作業は別のブランチ（新しいrun_id由来）で行われた

3. **Push失敗の見落とし**
   - `run_service.py:941-966` でpush失敗時のエラー処理
   ```python
   try:
       await self.workspace_service.push(...)
       logs.append(f"Pushed to branch: {worktree_info.branch_name}")
   except Exception as push_error:
       logs.append(f"Push failed (will retry on PR creation): {push_error}")
   ```
   - Push失敗しても処理が継続し、成功扱いになる可能性

**コードの流れ確認** (`run_service.py:676-1001`):

```
1. Update status to running
2. Sync with remote (is_behind_remote → sync_with_remote)
3. Execute CLI (AI edits files)
4. Read summary file
5. Stage all changes (git add -A)
6. Get diff
7. Commit (git commit)
8. Push (git push -u origin <branch>)  ← ここで失敗する可能性
9. Save results (RunStatus.SUCCEEDED)
```

### 解決策

**A. Push結果のステータス追跡（必須）**

```python
# run_service.py修正案
push_success = False
try:
    await self.workspace_service.push(...)
    push_success = True
    logs.append(f"Pushed to branch: {worktree_info.branch_name}")
except Exception as push_error:
    logs.append(f"Push failed: {push_error}")
    # Push失敗を明示的にエラーとして扱う
    await self.run_dao.update_status(
        run.id,
        RunStatus.FAILED,  # または新しいステータス PUSH_FAILED
        error=f"Push failed: {push_error}",
        ...
    )
    return
```

**B. ブランチ整合性の確認**

- Push前にリモートブランチの存在を確認
- PRが参照しているブランチと作業ブランチの一致を検証

---

## 課題3: 異なるブランチで作業を開始

### 現象
- 元々作業していたブランチ（例: `zloth/7adabce0`）とは異なるブランチで新しい作業が開始される

### 原因分析

**ワークスペース再利用のロジック** (`run_service.py:373-426`):

```python
existing_run = await self.run_dao.get_latest_worktree_run(
    task_id=task_id,
    executor_type=executor_type,
)

if existing_run and existing_run.worktree_path:
    workspace_path = Path(existing_run.worktree_path)
    is_valid = await self.workspace_service.is_valid_workspace(workspace_path)

    if is_valid:
        # default branchからの場合、最新性チェック
        if should_check_default:
            up_to_date = await self.git_service.is_ancestor(...)
            if not up_to_date:
                # 最新でない場合、workspace_info = None のまま
                # → 新しいワークスペースが作成される
```

**問題点:**

1. **`is_ancestor`チェックの挙動**
   - Update Branchによりリモートが更新されると、ローカルHEADがリモートより古くなる
   - `is_ancestor(origin/main, HEAD)` がFalseを返す
   - 結果として、新しいワークスペースが作成される

2. **新しいワークスペース = 新しいブランチ名**
   - `create_workspace`で新しい`run_id`由来のブランチ名が生成される
   - 例: `zloth/7adabce0` → `zloth/xxxx1234`（新run_id）

3. **PRとブランチの不整合**
   - PRは元のブランチ `zloth/7adabce0` を参照
   - 新しい作業は `zloth/xxxx1234` で行われる
   - Pushしても、PRには反映されない

### 解決策

**A. 既存ブランチの継続使用（推奨）**

Update Branch後も同じブランチで作業を継続するように修正:

```python
# run_service.py 修正案
if existing_run and existing_run.worktree_path:
    workspace_path = Path(existing_run.worktree_path)
    is_valid = await self.workspace_service.is_valid_workspace(workspace_path)

    if is_valid:
        # リモートが先行している場合は、pull/syncを行う（新しいワークスペース作成ではなく）
        if self.use_clone_isolation:
            is_behind = await self.workspace_service.is_behind_remote(
                workspace_path,
                existing_run.working_branch,
                auth_url=auth_url,
            )
            if is_behind:
                # 新しいワークスペースを作成するのではなく、既存をsyncする
                sync_result = await self.workspace_service.sync_with_remote(
                    workspace_path,
                    branch=existing_run.working_branch,
                    auth_url=auth_url,
                )
                if sync_result.success:
                    # 既存ワークスペースを再利用
                    workspace_info = WorktreeInfo(
                        path=workspace_path,
                        branch_name=existing_run.working_branch or "",
                        base_branch=existing_run.base_ref or base_ref,
                        created_at=existing_run.created_at,
                    )
```

**B. ブランチ名の固定化**

- ワークスペースのブランチ名を`task_id`ベースにする（run_idではなく）
- 同じTask内では常に同じブランチ名を使用

```python
def _generate_branch_name(self, task_id: str, branch_prefix: str | None = None) -> str:
    """Generate a branch name based on task_id (not run_id)."""
    prefix = branch_prefix.strip().strip("/") if branch_prefix else "zloth"
    short_id = task_id[:8]  # task_id を使用
    return f"{prefix}/{short_id}"
```

---

## 推奨修正計画

### Phase 1: 緊急修正（ブランチ整合性）

1. **既存ワークスペースの再利用ロジック修正** (`run_service.py`)
   - リモートが先行している場合、新規作成ではなくsyncを行う
   - `is_ancestor`チェックの結果に関わらず、既存ワークスペースを優先

2. **Push失敗の明示的エラー処理**
   - Push失敗時はRunをFAILEDステータスにする
   - ユーザーに明確なエラーメッセージを表示

### Phase 2: セッション管理改善

3. **セッション有効性の事前チェック**
   - 無効なセッションで`--resume`を呼ばないようにする
   - リトライロジックの改善

4. **セッションとワークスペースの関連付け**
   - session_idをワークスペースパスと紐付けて管理
   - ワークスペース再利用時のセッション継続を確実にする

### Phase 3: 根本的改善

5. **ブランチ名のTask紐付け**
   - `run_id`ではなく`task_id`ベースのブランチ名
   - 同一Task内での一貫したブランチ使用

6. **状態管理の改善**
   - Run, Workspace, Branch, PR, Sessionの関係を明確化
   - 状態遷移の可視化とバリデーション

---

## 関連ファイル

| ファイル | 修正内容 |
|---------|---------|
| `apps/api/src/zloth_api/services/run_service.py` | ワークスペース再利用ロジック、Push処理 |
| `apps/api/src/zloth_api/services/workspace_service.py` | sync_with_remote、is_behind_remote |
| `apps/api/src/zloth_api/storage/dao.py` | get_latest_worktree_run |
| `apps/api/src/zloth_api/executors/claude_code_executor.py` | セッション管理 |
