# CLAUDE.md

OreOre-Bench（俺基準の LLM ベンチマーク）でのエージェント作業ルール。
ベンチの実行手順・run.json の記録仕様は `README.md` が正本。ここには README に無い運用制約だけを書く。

## Git 運用ポリシー: auto commit / auto merge / auto deploy

このリポジトリは **main 直コミット + 自動マージ + 自動デプロイ** を許可する（ユーザー指示 2026-08-06）。
ベンチ結果の追記が作業の大半で、レビューを挟む価値より反映の速さが勝るため。

`.agents/git-policy` に `main-direct` を置いている。

### グローバルルールとの関係（重要）

`~/.claude/rules/git-workflow.md` は「`.github/workflows/deploy*` があるリポは PR 必須（拒否権）」と定め、
`main-direct` マーカーは拒否権を覆せない。このリポには `deploy.yml` があるため、通常はその拒否権に該当する。
**本節はユーザーの明示指示による上書き**であり、以下の理由で安全側の条件を満たすと判断している:

- デプロイ先が静的サイト（Cloudflare Pages / `public/` の配信のみ）で、DB・課金・認証を持たない
- `deploy.yml` がデプロイ後にトップページの HTTP 200 を検証し、失敗すれば job が落ちる
- 壊れても `git revert` + 再 push で復旧でき、本番データは失われない

この前提が変わったら（動的処理・認証・課金・DB を持たせる、外部への副作用が入る）、
本節を撤回して PR 必須に戻す。

### 各自動化の運用

| 対象 | 運用 |
|---|---|
| auto commit | 責務単位が検証通過したら、指示を待たず main へコミットする。自セッションで Edit/Write したファイルのみが対象。**ベンチ結果は 1 テーマ 1 コミット**（モデル × テーマ単位。どのテーマで失敗したかを履歴で追えるようにする） |
| auto merge | PR を作った場合は CI 全パス後に `--squash --delete-branch` で自動マージしてよい。ただし下記「PR を通す変更」は人間レビューを挟む |
| auto deploy | main への push で `deploy.yml` が Cloudflare Pages に反映する。マージ・push 後は `gh run list --workflow=deploy.yml --limit 1` で success を確認してから完了報告する |

### 直コミットしてよい変更

- ベンチ結果の追加・差し替え（`public/data/**` の run.json・生成物）
- ドキュメント・README・コメント
- スクリプトの軽微な修正でテストが通るもの

### PR を通す変更（直コミット禁止）

自動化の対象外。これらは main 直コミットも auto-merge もしない:

- `.github/workflows/**` / `wrangler.toml` / `_headers` / `_redirects`（デプロイ経路そのもの）
- `.agents/git-policy` / `CLAUDE.md`（本ポリシーの自己書き換え）
- `.gitignore` / `.env*`（機密除外の解除に使えるため）

### 必須の検証（自動化の担保）

コミット・push の前に、変更種別に応じて実行する。**失敗したら push しない**。

```bash
# run.json を触った時
node scripts/validate-runs.mjs

# スクリプト・テストを触った時
uv run --with pytest==8.3.4 pytest tests/ -q
```

push 後は deploy の結果を確認する:

```bash
gh run list --workflow=deploy.yml --limit 1
```

## ベンチマーク実行時のメモリ監視（必須）

<critical_rule>
ローカル LLM（MLX / oMLX / LM Studio / Ollama）のベンチを回す時は、**開始前・実行中・終了時**の
3 点でメモリ使用率を確認する。閾値を超えたら**推論プロセスを停止**し、結果を捨てて報告する。
メモリ枯渇状態で走らせた測定値は swap 由来で遅くなるため、ベンチの数値として採用しない。
</critical_rule>

### 監視スクリプト

`scripts/watch-memory.sh` をベンチと並走させる。停止閾値を超えると**非ゼロ終了**するので、
エージェントは終了コードで枯渇を検知し、推論サーバの停止判断に移る（プロセスの kill は
スクリプトではなく人間 / エージェントが行う）。

```bash
# ベンチ開始と同時に別ターミナル・別プロセスで走らせる（1 分間隔・無制限）
./scripts/watch-memory.sh

# 短時間の確認（5 秒間隔で 12 回 = 1 分）
./scripts/watch-memory.sh -i 5 -n 12
```

終了コード: `0` 正常終了（`-n` 到達 / Ctrl+C）、`1` 停止閾値超過、`2` 引数エラー。
オプションは `-h` を参照。CSV は `logs/memory-YYYYmmdd-HHMMSS.csv` に追記される（Git 管理外）。

`sysctl`（`hw.memsize` / `vm.swapusage`）と `ps -r` はサンドボックスで拒否されるため使わない。
`memory_pressure` はサンドボックス内で実行できる。

### 3 点の実施内容

| タイミング | やること |
|---|---|
| 開始前 | `./scripts/watch-memory.sh -i 5 -n 1` で baseline を取り、used% と swapouts を控える |
| 実行中 | `./scripts/watch-memory.sh` を並走させる。20 秒超の待機は Sonnet サブエージェントへ同期委譲する（`rules/claude-async-heartbeat.md`） |
| 終了時 | 再度 baseline を取り比較。推論プロセス終了後も free が戻らなければリークを疑い報告する |

### 閾値と対応

**既定値は暫定**（`-w 97` / `-s 99` / `-x 100000`）。used% はページキャッシュを含むため
平常時でも高く出る（実測環境でアイドル時 95.9% / free 21GB）。そのため used 側は誤発火しない
位置に置き、実質の枯渇判定は swapout の増加量で行う。**確定値は初回ベンチの CSV を見て決める**。

| レベル | 条件（既定） | スクリプトの挙動 | 人間 / エージェントの対応 |
|---|---|---|---|
| ok | used < 97% かつ swapout 増加 < 100000 | CSV に記録して継続 | 続行 |
| warn | used 97% 以上 | stderr に警告・継続（exit しない） | 監視間隔を縮める。次のモデルへ進まない |
| stop | used 99% 以上 または swapout 増加 100000 以上 | **exit 1** | 推論サーバを停止。該当モデルの run.json は書かない |

停止は推論サーバ側のプロセスを落とす（oMLX / LM Studio / Ollama のサーバ）。
`kill -9` の前に通常終了（`kill -TERM`）を試し、モデルのアンロードで回収されるか確認する。

### 報告フォーマット

ベンチ完了報告には次の 1 行を必ず含める:

```
メモリ: 開始 {X}% → ピーク {Y}% → 終了 {Z}% / swapouts {A}→{B}（判定: 正常 / 停止）
```

停止した場合は、どのモデルのどのテーマで停止したか、run.json を書いていないことを明記する。

## 繰り返し暴走の自動打ち切り

`mlx-lm-run.py` は生成をストリーミングで受け取り、同じ出力の反復を検知したら
接続を切って中断する（`scripts/runaway_detector.py`）。閾値は 0.55、既定で有効。

打ち切られた時の扱い:

- 終了コード非ゼロで止まり、**run.json も成果物も書かれない**（壊れた出力を公開しない）。
  `mlx-lm-run.py` は 1、`json-ladder-run.py` は API 起因の失敗と同じ 2 を返す
- stderr に検知位置とスコアが出る。例:
  `[ERROR] 24,240 文字目で繰り返し暴走を検知 (score=0.512, D=0.455, A=0.512)`
- FAIL として報告する。「そのモデルはそのテーマで暴走した」がベンチ結果であり、
  閾値を緩めて無理に成功させない

`max_tokens` を下げると暴走しなくなる場合がある（DeepSeek V4 Flash は 65K で
暴走し 24K では自然終了した）。上限を変えて追試した時は、両方の条件を run.json の
`sampling.max_tokens` と `usage.note` で区別できる形で記録する。

誤検知を疑う時（正常な出力が打ち切られた）:

- `--runaway-threshold 0.45` のように下げて再実行し、出力を目視で確認する
- 検知そのものを外すなら `--no-runaway-check`。ただし max_tokens まで走る
- 分離幅は狭い（正常の最悪 0.591 / 暴走の最悪 0.535）。新しいモデルで
  誤検知が出たら閾値の再チューニングを検討する

## 測定値の扱い

- `watch-memory.sh` が stop 判定を出した（exit 1）区間で計測した latency・tok/s は run.json に記録しない
- 再測定する時は、開始前サマリが baseline 相当まで戻ってから回す
- 暴走で打ち切られた区間の latency・tok/s も記録しない（生成が完了していない）
