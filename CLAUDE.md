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
| auto commit | 責務単位（1機能 / 1修正 / 1データ追加）が検証通過したら、指示を待たず main へコミットする。自セッションで Edit/Write したファイルのみが対象 |
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

### 確認コマンド

```bash
# 1行サマリ（total / free / wired / compressor / used%）
memory_pressure | awk '/^The system has/{tot=$4} /Pages free/{f=$3} /Pages wired down/{w=$4} \
  /used by compressor/{c=$5} END{p=16384; printf "total %.0fGB / free %.1fGB / wired %.1fGB / compressor %.1fGB / used %.1f%%\n", \
  tot/1073741824, f*p/1073741824, w*p/1073741824, c*p/1073741824, 100-(f*p*100/tot)}'

# swapout 累積（増え続けたら赤信号）
memory_pressure | awk '/Swapouts/{print "swapouts:", $2}'
```

`sysctl`（`hw.memsize` / `vm.swapusage`）と `ps -r` はサンドボックスで拒否されるため使わない。
`memory_pressure` はサンドボックス内で実行できる。

### 3 点の実施内容

| タイミング | やること |
|---|---|
| 開始前 | 上記サマリを取り、baseline として記録。swapouts の値も控える。**used が 80% 超なら開始しない**（先に不要プロセスを落とす） |
| 実行中 | 1〜3 分間隔でサマリを取り、used% と swapouts の推移を見る。20 秒超の待機は Sonnet サブエージェントへ同期委譲する（`rules/claude-async-heartbeat.md`） |
| 終了時 | サマリを取り、baseline と比較。推論プロセス終了後も free が戻らなければリークを疑い報告する |

### 閾値と対応

| used% | swapouts | 対応 |
|---|---|---|
| 〜85% | 開始時から横ばい | 続行 |
| 85〜90% | 増加傾向 | 警告を出し、監視間隔を 1 分に縮める。次のモデルへは進まない |
| 90% 超 | または swapouts が継続増加 | **即停止**。推論プロセスを終了し、実行中だったモデルの run.json は書かない |

停止は推論サーバ側のプロセスを落とす（oMLX / LM Studio / Ollama のサーバ）。
`kill -9` の前に通常終了（`kill -TERM`）を試し、モデルのアンロードで回収されるか確認する。

### 報告フォーマット

ベンチ完了報告には次の 1 行を必ず含める:

```
メモリ: 開始 {X}% → ピーク {Y}% → 終了 {Z}% / swapouts {A}→{B}（判定: 正常 / 停止）
```

停止した場合は、どのモデルのどのテーマで停止したか、run.json を書いていないことを明記する。

## 測定値の扱い

- メモリ枯渇（used 90% 超 / swap 継続増加）中に計測した latency・tok/s は run.json に記録しない
- 再測定する時は、開始前サマリが baseline 相当まで戻ってから回す
