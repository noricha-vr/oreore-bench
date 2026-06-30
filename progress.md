# OreOre-Bench 進捗

LLM ベンチマーク作品集の作業ログと次やることリスト。
sleep-mode / morning-briefing で参照されるエントリーポイント。

公開サイト: <https://oreore-bench.pages.dev>

## 現状（2026-06-30）

- [x] サイトの骨組み（フィルター付きカード一覧、モーダル詳細表示）
- [x] テーマ 3 種実装: `lp-nishibi` / `othello` / `extract-questions`
- [x] モデル 4 種: Claude Opus 4.8 / Gemma 4 31B / Gemma 4 26B-A4B QAT / Gemma 4 12B QAT
- [x] PUBLIC GitHub: <https://github.com/noricha-vr/oreore-bench>
- [x] Cloudflare Pages 自動デプロイ稼働中
- [x] モデルスペック ファクトチェック済み（リリース日 / context / output / 量子化）
- [x] 全モーダルにテーマカラーバンド + stat-card + ナンバリングバッジ
- [x] 旧 json-quiz（Wikipedia → クイズ出題）を extract-questions（AI 出力 → 質問抽出）に置換

## やりたいことリスト

優先度高いものから順に。判断保留要素は morning-queue 行きで明記。

### 短期（次セッションで進められる）

- [ ] extract-questions の入力を 30〜50 問規模に拡張して、モデル間の差を顕在化させる
  - 現状 20 問では 4 モデル全て PASS してグラデーションが出ない
  - 拡張時は過去 4 モデルの再生成が必要（プロンプト凍結ルール継承で `extract-questions-v2` テーマとして追加？要相談）
- [ ] `lp-nishibi` / `othello` テーマも Gemma 4 12B QAT で生成して 4 モデル × 3 テーマ揃える
  - 既に 12B はモデル定数に入っているのに lp-nishibi / othello エントリは未生成
- [ ] `wrangler.toml` を作って Cloudflare Pages デプロイ設定をリポに固定化
  - 現状 CLI 経由のオプション指定だけで明示設定なし

### 中期

- [ ] 新モデル追加（要ユーザー判断）
  - Gemini 2.5 Pro / Gemini 3 Flash（無料枠あるが Google API キー）
  - Claude Haiku 4.5（Anthropic サブスク内）
  - Qwen3.5 系（LM Studio に既にロード済みの場合）
- [ ] `add-model.sh` を新スキーマ（kind/stats/colorDark/links 等）対応にアップデート
- [ ] テーマ間の集約比較ビュー（モデル横、テーマ縦のマトリクス）

### 長期

- [ ] 自動再生成 CI（GitHub Actions で月次に全モデル再走、変動チェック）
- [ ] ユーザーが自分のローカル LLM を試せる「Bring Your Own Model」モード
- [ ] テーマ提案フォーム（自分以外がベンチネタを投稿できるように）

## 判断保留中（morning-queue.md 参照）

`docs/tmp/morning-queue.md` を見る。

## アーカイブ（過去にやって完了）

完了タスクは `git log` で追える状態にしてあるので、ここには書かない。

---

## 更新ルール

- セッション終了時に「やりたいことリスト」のチェックを最新化
- 完了したものは削除（git log で履歴を辿る）
- 新発見の懸念は「やりたいことリスト」の適切な位置に追加
