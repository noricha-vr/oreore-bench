# OreOre-Bench

> 俺基準の LLM ベンチマーク。**同じプロンプトを違う AI に投げて、何が出てくるかを残す**。

公開サイト: <https://oreore-bench.pages.dev>

## 何をしているか

LLM を「業務タスクの一発再現性」で評価する場。現実の制作タスクをそのままぶつけて、生成物をそのまま晒す。指標は `tokens/sec` でも `MMLU` でもなく、**「これは仕事で使えるか」** の一点。

各エントリには:

- 元のプロンプト (`PROMPT.md`)
- 各モデルの 1 ショット出力（手直しなし）
- HTML テーマは `index.html`、JSON テーマは `output.json` + 描画用 `output.html`
- 生成方法のメモ・検証結果 (`meta.json`)

がセットで置いてある。**同じプロンプトを別のモデルに投げ直せば、誰でも比較を追加できる**。

## 収録テーマ

| テーマ | タイプ | 入力 → 出力 | 評価軸 |
|---|---|---|---|
| `lp-nishibi` | HTML | サービス概要 → 1 枚 LP | コピー力・配色・情報設計・細部の遊び |
| `othello` | HTML | ゲーム仕様 → 1 枚で動く 8x8 オセロ | ロジック正しさ・UI 状態管理・CPU AI |
| `hasami-shogi` | HTML | ルール完全記述 → 1 枚で動く 9x9 はさみ将棋 | 学習データ耐性（公開実装が稀）・仕様追従・CPU AI |
| `mario-like-2d` | HTML | マリオ風仕様 → 1 枚で動く横スク 2D プラットフォーマー | リアルタイム物理・当たり判定・カメラ・状態遷移の一発再現性 |
| `lp-fable5` | HTML | 水彩絵本トーンの詳細プロンプト → AI モデル発表 LP | 世界観再現・SVG イラスト表現・構成追従・禁止事項遵守 |
| `suminagashi` | HTML | 実装方式名指しのプロンプト → WebGL 流体マーブリングアート | GPU シェーダーの一発実装・減法混色・和のミニマル UI |
| `extract-questions` | JSON | AI アシスタント出力 → ユーザー向け質問フォーム JSON | 本番運用スキーマ準拠・抽出判断・オプション補完 |
| `pr-triage` | JSON | リポジトリのスナップショット → Open PR 10 件のトリアージ判断 JSON | 判断の妥当性（正解キー一致率）・グレーケースの慎重さ・理由の具体性 |

## 比較対象モデル（2026-07 時点）

| モデル | プロバイダー | タイプ | 量子化 |
|---|---|---|---|
| Claude Opus 4.8 | Anthropic | API | — |
| Grok 4.5 | xAI | API | — |
| Claude Fable 5 (effort high) | Anthropic | API | — |
| GPT-5.6 Luna (reasoning high) | OpenAI | API | — |
| GPT-5.6 Terra (reasoning high) | OpenAI | API | — |
| GPT-5.6 Sol (reasoning high) | OpenAI | API | — |
| Gemini 3.1 Pro (High) | Google | API | — |
| Gemma 4 31B | Google | ローカル | 4-bit (MLX / GGUF Q4_K_M) |
| Gemma 4 26B-A4B (QAT) | Google | ローカル (MoE) | QAT 4-bit |
| Gemma 4 12B (QAT) | Google | ローカル | QAT 4-bit |

スペック値はサブエージェントによるファクトチェック済み（リリース日 / context window / output 上限などは Google DeepMind / Anthropic / xAI / Hugging Face / LM Studio の一次情報を参照）。

## 構造

```
oreore-bench/
├── README.md
├── public/                              ← Cloudflare Pages build root
│   ├── index.html                       ← トップ（フィルター付きカード一覧）
│   ├── <theme>/
│   │   ├── PROMPT.md                    ← 凍結プロンプト（再現用、人間用）
│   │   ├── prompt.html                  ← 凍結プロンプト整形ビュー
│   │   ├── input.md / input.html        ← JSON 系テーマの共通入力
│   │   └── <model>/
│   │       ├── index.html               ← HTML 系テーマの 1 ショット出力
│   │       ├── output.json              ← JSON 系テーマの 1 ショット出力
│   │       ├── output.html              ← 上記を左右 2 カラムで描画
│   │       ├── meta.json                ← スキーマ検証結果（事前計算）
│   │       └── run.json                 ← 生成条件の正本（後述）
│   └── runs.json                        ← run.json を集約して index.html が 1 回で fetch
└── scripts/
    ├── add-model.sh                     ← 新モデル追加の汎用スクリプト
    ├── gen-questions.py                 ← extract-questions 用、3 Gemma 順次生成
    ├── validate-questions.mjs           ← extract-questions スキーマ検証
    ├── build-questions-html.py          ← extract-questions output.html ビルド
    ├── model-map.json                   ← slug → OpenRouter モデル ID の単一情報源
    ├── pricing.json                     ← per-Mtok 単価キャッシュ（fetch-pricing.py で更新）
    ├── fetch-pricing.py                 ← OpenRouter API から単価取得
    ├── estimate-run-cost.py             ← tiktoken 代理でトークン推定 + コスト算出
    ├── backfill-runs.py                 ← ENTRIES から run.json スケルトン生成
    ├── build-runs-json.py               ← run.json を public/runs.json に集約
    ├── validate-runs.mjs                ← run.json / runs.json のスキーマ検証
    ├── gen-quiz.py                      ← (legacy) 旧 json-quiz 用
    ├── validate-quiz.mjs                ← (legacy) 旧 json-quiz 用
    └── build-output-html.py             ← (legacy) 旧 json-quiz 用
```

## run.json（生成条件の記録）

各 `<theme>/<model>/` に生成条件の正本 `run.json`（`schema_version: 1`）を置き、
`public/runs.json` に集約してトップページのカードが 1 回の fetch でメタを引けるようにしている。
カードには「ハーネス ・ effort ・ コスト」が表示される。

### スキーマ（抜粋）

```json
{
  "schema_version": 1,
  "theme": "lp-fable5",
  "model": "claude-fable-5",
  "harness": "claude-cli-headless",
  "reasoning_effort": "high",
  "generated_at": "2026-07-16T14:24:21+09:00",
  "generated_at_source": "git-first-commit",
  "sampling": { "temperature": "default", "max_tokens": "default" },
  "system_prompt": "harness-default",
  "usage": {
    "estimated": true,
    "method": "tiktoken-o200k_base-proxy",
    "prompt_tokens": 1122,
    "completion_tokens": 15410,
    "note": "reasoning トークン・ハーネス側 system prompt を含まない下限値"
  },
  "cost": {
    "estimated": true,
    "usd": 0.7817,
    "prompt_usd_per_mtok": 10.0,
    "completion_usd_per_mtok": 50.0,
    "pricing_source": "openrouter"
  }
}
```

### enum / 規約

- `harness`: `lmstudio-api` / `gptme-lmstudio` / `claude-agent-sdk` / `claude-cli-headless` / `grok-cli` / `openai-api` / `openrouter-api` / `antigravity-cli` / `unknown`
- `reasoning_effort`: `none` / `low` / `medium` / `high` / `unknown`
- `system_prompt`: `none` / `harness-default` / `custom` / `unknown` — **ラベルのみ。本文は絶対に記録しない**（公開配信されるためプライバシー保護。`validate-runs.mjs` で enum 外を必ず失敗させる）
- `"unknown"` = 復元不能、`"default"` = 既定に任せた、`"none"` = 明示的に無し。確定値のみ数値で書く

### コスト表示は「推定・下限」

- `o200k_base` トークナイザは Gemma/Claude/Grok の実トークナイザと乖離するため、`estimated: true` かつ `method` を明記した上で下限値として扱う
- 単価は OpenRouter API から取得（`fetch-pricing.py`）。gemma-4-12b-qat は OpenRouter に存在しないため `actual_usd: 0` + 参考単価なし
- **reasoning トークン・ハーネス側 system prompt を含まない**（実測 API `usage` があるモデルのみ完全値）

### 更新ワークフロー

```bash
# 単価更新（月次程度）
uv run scripts/fetch-pricing.py

# 過去エントリの run.json 再生成
uv run scripts/backfill-runs.py
uv run scripts/estimate-run-cost.py --write

# runs.json 集約 + 検証
uv run scripts/build-runs-json.py
node scripts/validate-runs.mjs   # exit 0 で通過
```

新規モデル追加時は `scripts/add-model.sh` が `estimate-run-cost.py --write` を自動で呼び、
生成完了後に「run.json の harness/effort を確認 → build-runs-json.py → validate-runs.mjs」の案内を出す。

## 新しいモデルを追加する

### 1. ローカル LLM（LM Studio 経由）の場合

LM Studio で対象モデルをロード → API サーバを `http://localhost:1234` で立ち上げ → 各テーマ用スクリプトを叩く。

```bash
# extract-questions テーマで全 Gemma に投げる（既存ファイルはスキップ）
python3 scripts/gen-questions.py

# 特定モデルだけ
python3 scripts/gen-questions.py --model 12b

# 上書き
python3 scripts/gen-questions.py --overwrite

# 検証 + HTML ビルド
node scripts/validate-questions.mjs
python3 scripts/build-questions-html.py
```

### 2. API モデル（Claude Opus 等）の場合

Claude Code 上で `Agent` ツール（`subagent_type=implementer`, `model=opus`）にプロンプトを渡して、`Write` で `output.json` を保存させる。生成プロセスはコードベースに固定しない（モデルアクセス方法はユーザー環境依存）。

### 3. 新規モデル定数の追加

`public/index.html` の `MODELS` 定数に追加。スペック値は**必ず一次情報でファクトチェック**してから書く（モデルカード上に出る）。

```js
"<model-key>": {
  label: "...",            provider: "...",         type: "local|api",
  color: "#...",            colorDark: "#...",
  release: "YYYY-MM-DD",   size: "...",            context: "...",
  output: "...",            quantization: "...",    runtime: "...",
  stats: [
    { value: "...", label: "パラメータ", note: "..." },
    { value: "...", label: "量子化",    note: "..." },
    { value: "...", label: "コンテキスト", note: "..." },
    { value: "...", label: "最大出力",  note: "..." }
  ],
  strengths: "...",  weaknesses: "...",
  links: [{ label: "公式", href: "..." }]
}
```

そして `ENTRIES` に該当テーマ × モデルの行を追加（`kind: "html" | "json"`）。

### 4. デプロイ

```bash
wrangler pages deploy public/ --project-name=oreore-bench --branch=main
```

GitHub に push すれば Cloudflare Pages 側でも自動デプロイされる構成。

## ルール

- **手直しなし**: モデルが書いたものをそのまま置く。バグも残す（バグの「見せ場」になる）
- **プロンプトは凍結**: 一度出した `PROMPT.md` は編集しない。改訂したい時は別テーマを切る（過去結果との比較性を守る）
- **ローカルもクラウドも同じ俎上に乗せる**: `local/...` モデルと `claude-...` モデルを分け隔てなく並べる
- **スペック値は一次情報のみ**: 公式ドキュメント / Hugging Face / モデルカードから引く。推測値には注記を入れる

## 観察された面白い現象

- **MoE 26B-A4B が dense 12B より JSON 安定性で劣る場面がある**: 旧 json-quiz-medium で唯一 parse 失敗を起こした（履歴は `git log` 参照）
- **Gemma 4 31B は中規模 LP / オセロで Opus 4.8 級の品質を 1 ショットで出すことがある**: ローカルで完結する選択肢として実用ライン
- **Claude Opus 4.8 は情報密度が桁違い**: 同じプロンプトから架空人物名・メタジョーク・SVG 可視化まで自発的に補完する（lp-nishibi での観察）
- **WebGL シェーダーはローカルとフロンティアの断層が最も鮮明**: suminagashi では実装方式（Stable Fluids・減法混色）をプロンプトで名指ししても Gemma 4 は 3 モデルともシェーダーがコンパイル不能または uniform 未定義で全滅。Opus 4.8 / Grok 4.5 は JS エラー 0 で流体が動いた
- **「JS エラー 0」と「動く」は別物**: GPT-5.6 Luna / Sol（reasoning high）の suminagashi はエラーなしでロードされるが、ドラッグしてもインクが一切描画されない。例外を出さずに壊れる方が、シェーダーエラーで壊れる Gemma より検出しにくい失敗モード

## 関連リンク

- 元の実験リポ（private）: <https://github.com/noricha-vr/note> の `experiments/` 配下
- lifelog note: `gptme-lmstudio-model-override`, `gemma4-26b-vs-31b-coding-comparison`
- 本番運用（extract-questions テーマの本番運用元）: 別プロジェクト

## ライセンス

ベンチマーク本体（HTML/CSS/JS、スクリプト、ドキュメント）は自由に参照・改変可。
各モデルが生成した output は各モデルプロバイダーの利用規約に従う。
