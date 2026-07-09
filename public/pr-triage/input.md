# リポジトリ: taskhub（スナップショット 2026-07-01）

Django 5.2 製のタスク管理 SaaS。開発者 1 人 + AI エージェント。Stripe 課金あり、本番稼働中。
CI: pytest + ruff（GitHub Actions）。方針: 依存はバージョン固定、テスト必須、`main` へは PR 経由。

## Open Issues（抜粋）

- **#90** [P1] Stripe webhook に未認証リクエストが連投されると、失敗通知メールが管理者に洪水のように届く（昨夜 400 通）
- **#91** 本番のエラーログが多すぎて Sentry のクォータを圧迫している。大半は外部 API タイムアウトの `ConnectionError`
- **#92** [security] パスワードリセットのトークンが URL クエリに載っており、アクセスログと Referer 経由で漏えいし得る
- **#93** セットアップ手順が古い → `docs/setup.md` を全面改訂して解決済み（2026-06-20 クローズ）
- **#94** `Task` モデルを `core` アプリから独立させるか議論中。パフォーマンス懸念（JOIN 増加）への反論が出て**未決着のまま停止中**

## Open PRs（全 10 件）

### PR #101 fix(webhook): Stripe webhook の失敗通知メールにレートリミットを追加
- 作者コメント: Issue #90 対応。未認証・不正 payload の通知を 1 時間 3 通に制限し、超過分は WARNING ログに集約。
- 変更: `billing/webhooks.py` (+38/-4)、`billing/tests/test_webhooks.py` (+92)
- CI: ✅ pass / レビュー: approve（指摘なし）/ コンフリクト: なし / 経過: 2 日

```python
+ RATE_LIMIT_KEY = "webhook-alert-mail"
+ def _notify_admin_throttled(subject: str, body: str) -> None:
+     count = cache.get_or_set(RATE_LIMIT_KEY, 0, timeout=3600)
+     if count >= 3:
+         logger.warning("webhook alert suppressed: %s", subject)
+         return
+     cache.incr(RATE_LIMIT_KEY)
+     mail_admins(subject, body)
```

### PR #102 feat(tasks): タスク一括アーカイブ API を追加
- 作者コメント: 選択した複数タスクを 1 リクエストでアーカイブできるようにした。
- 変更: `tasks/views.py` (+61)、`tasks/urls.py` (+2)。**テストなし**
- CI: ✅ pass / レビュー: 「`Task.objects.filter(id__in=ids)` に owner 絞り込みがなく、他人のタスクをアーカイブできてしまうのでは？」→ **作者未返信**
- コンフリクト: なし / 経過: 9 日

### PR #103 fix: 外部 API 呼び出しの例外ログを抑制
- 作者コメント: Issue #91 対応。ログがうるさいので try/except で囲んで静かにした。
- 変更: `integrations/client.py` (+19/-3)
- CI: ✅ pass / レビュー: 未レビュー / コンフリクト: なし / 経過: 5 日

```python
  def fetch_external(url: str) -> dict | None:
-     resp = session.get(url, timeout=10)
-     resp.raise_for_status()
-     return resp.json()
+     try:
+         resp = session.get(url, timeout=10)
+         resp.raise_for_status()
+         return resp.json()
+     except Exception:
+         pass
+     return None
```

### PR #104 chore(deps): requirements.txt のバージョン固定を解除
- 作者コメント: 毎回依存更新の PR を作るのが面倒なので、常に最新を取るようにする。
- 変更: `requirements.txt`（`django==5.2.3` → `django`、他 14 パッケージ同様）、`requirements.lock` を削除
- CI: ✅ pass / レビュー: 未レビュー / コンフリクト: なし / 経過: 12 日

### PR #105 fix(auth): パスワードリセットのトークンを URL クエリから POST body に移動
- 作者コメント: Issue #92 対応。リセットリンクは一時 ID のみとし、トークンはフォーム hidden で送る。旧リンクは 24 時間だけ互換維持。
- 変更: `accounts/views.py` (+54/-21)、`accounts/tests/test_password_reset.py` (+118)、テンプレート 2 件
- CI: ✅ pass / レビュー: approve「互換ウィンドウの設計も良い」/ コンフリクト: なし / 経過: 1 日

### PR #106 feat: ダークモード対応 + 通知設定画面 + ランディングページ刷新
- 作者コメント: UI 改善をまとめてやった。ついでに通知設定画面と LP も新しくした。
- 変更: **42 ファイル** (+3,180/-964)。CSS・テンプレート・`notifications/` 新アプリ・LP 画像差し替えが混在
- CI: ✅ pass / レビュー: 「大きすぎてレビューできない。分割してほしい」→ 作者「分割は手間なのでこのままで」/ コンフリクト: なし / 経過: 15 日

### PR #107 fix(tasks): 期限日がタイムゾーンによって 1 日ずれるバグを修正
- 作者コメント: `date()` 変換を UTC 固定からユーザーの TZ 基準に修正。テストも追加した。
- 変更: `tasks/utils.py` (+12/-6)、`tasks/tests/test_deadline.py` (+45)
- CI: ❌ **fail**（`test_deadline_dst_boundary` が失敗）/ 作者コメント: 「ローカルでは通る。CI が flaky なだけだと思う」
- レビュー: 未レビュー / コンフリクト: なし / 経過: 4 日

### PR #108 refactor(models): Task モデルと関連ロジックを新アプリ `taskcore` へ移動
- 作者コメント: 「将来のために分離しておく」
- 変更: 28 ファイル (+1,420/-1,380)。モデル移動 + マイグレーション 3 本（`db_table` 変更を含む）
- CI: ✅ pass / レビュー: 未レビュー / コンフリクト: なし / 経過: 6 日
- 補足: 分離の是非は Issue #94 で議論されたが**結論が出ていない**。PR 説明にパフォーマンス懸念（JOIN 増加）への回答はない

### PR #109 docs: README にセットアップ手順を追記
- 作者コメント: 初回セットアップで詰まったので手順を README に書いた。
- 変更: `README.md` (+85)
- CI: ✅ pass / レビュー: 未レビュー / コンフリクト: **あり**（README.md）/ 経過: 30 日
- 補足: この PR の作成後、`docs/setup.md` が全面改訂されて main にマージ済み（Issue #93 で解決済み）。README には既に `docs/setup.md` へのリンクがある

### PR #110 feat(api): タスク一覧の CSV エクスポート
- 作者コメント: 管理画面からタスクを CSV でダウンロードできるようにした。
- 変更: `tasks/export.py` (+74)、`tasks/tests/test_export.py` (+66)、`tasks/views.py` (+18)
- CI: ✅ pass / レビュー: **approve**「nit: 件数が増えたら StreamingHttpResponse にすると良さそう。今の規模なら現状で問題なし」/ コンフリクト: なし / 経過: 3 日
