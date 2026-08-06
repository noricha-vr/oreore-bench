#!/usr/bin/env bash
# 新しいモデルでテーマを再現するワンライナー。
# 使い方:
#   bash scripts/add-model.sh <theme> <model-slug> [--runner gptme|claude|openrouter|copy]
#                                                  [--reasoning-effort none|low|medium|high]
#                                                  [--max-tokens N] [--overwrite] [--dry-run]
#
# 例:
#   bash scripts/add-model.sh lp-nishibi gemma-4-12b-qat
#   bash scripts/add-model.sh othello claude-haiku-4-5 --runner claude
#   bash scripts/add-model.sh lp-nishibi claude-opus-5 --runner openrouter          # API モデル (PR #24/#25 の手順)
#   bash scripts/add-model.sh pr-triage kimi-k3 --runner openrouter --dry-run       # 前提確認のみ (API 課金なし)
#   bash scripts/add-model.sh lp-nishibi gpt-5-codex --runner copy   # 既存ファイルを置きたいだけ
#
# 動作:
#   1. public/<theme>/PROMPT.md を読む
#   2. 指定の runner で <model-slug> に投げて public/<theme>/<model-slug>/ に出力を生成
#      (HTML テーマ → index.html / JSON テーマ → output.json。openrouter runner のみ JSON 対応)
#   3. ユーザーに「public/index.html の ENTRIES 配列に下記を追加して」とテンプレを表示
#
# runner 自動判定 (--runner 省略時):
#   - local/*  または モデル名が gemma|qwen|llama|mistral|phi で始まる → gptme + LM Studio (1234)
#   - claude-*                                                          → echo で「Claude Code Agent ツールで投げて」と案内
#   - それ以外                                                           → エラー、--runner を明示
#   (openrouter は自動判定しない。API 課金が走るため明示指定を必須にする)
#
# --runner openrouter は scripts/openrouter-run.py に委譲し、usage 実測入りの run.json まで生成する。
# OPENROUTER_API_KEY は環境変数または .env から読む (キー実値はログに出さない)。

set -euo pipefail

THEME="${1:-}"
MODEL="${2:-}"
RUNNER="auto"
REASONING_EFFORT="high"
MAX_TOKENS=""
OVERWRITE=0
DRY_RUN=0

usage() {
  cat >&2 <<'EOF'
Usage: bash scripts/add-model.sh <theme> <model-slug> [options]

Options:
  --runner gptme|claude|openrouter|copy   実行方式 (省略時は自動判定。openrouter は明示必須)
  --reasoning-effort none|low|medium|high openrouter runner の reasoning effort (既定 high)
  --max-tokens N                          openrouter runner の max_tokens (既定 65000)
  --overwrite                             既存出力を上書き (attempts を +1)
  --dry-run                               openrouter runner で API を叩かず前提だけ検証
EOF
}

shift 2 2>/dev/null || true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --runner)
      [[ $# -ge 2 ]] || { echo "--runner requires a value" >&2; exit 1; }
      RUNNER="$2"; shift 2 ;;
    --reasoning-effort)
      [[ $# -ge 2 ]] || { echo "--reasoning-effort requires a value" >&2; exit 1; }
      REASONING_EFFORT="$2"; shift 2 ;;
    --max-tokens)
      [[ $# -ge 2 ]] || { echo "--max-tokens requires a value" >&2; exit 1; }
      MAX_TOKENS="$2"; shift 2 ;;
    --overwrite) OVERWRITE=1; shift ;;
    --dry-run)   DRY_RUN=1; shift ;;
    -h|--help)   usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "$THEME" || -z "$MODEL" ]]; then
  usage
  exit 1
fi

if [[ "$THEME" == "." || "$THEME" == ".." || ! "$THEME" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "Invalid theme: $THEME (must be a safe directory name)" >&2
  exit 1
fi

if [[ "$MODEL" == "." || "$MODEL" == ".." || ! "$MODEL" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "Invalid model: $MODEL (must be a safe directory name)" >&2
  exit 1
fi

case "$REASONING_EFFORT" in
  none|low|medium|high) ;;
  *) echo "Invalid --reasoning-effort: $REASONING_EFFORT (none|low|medium|high)" >&2; exit 1 ;;
esac

if [[ -n "$MAX_TOKENS" && ! "$MAX_TOKENS" =~ ^[1-9][0-9]*$ ]]; then
  echo "Invalid --max-tokens: $MAX_TOKENS (positive integer)" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
THEME_DIR="$ROOT/public/$THEME"
PROMPT_FILE="$THEME_DIR/PROMPT.md"
OUT_DIR="$THEME_DIR/$MODEL"
OUT_FILE="$OUT_DIR/index.html"

# JSON テーマ (input.md を持つ pr-triage 等) は output.json が出力になる。
# openrouter runner のみ JSON テーマ対応 (gptme/claude runner は index.html 前提のまま)。
if [[ -f "$THEME_DIR/input.md" ]]; then
  OUT_FILE="$OUT_DIR/output.json"
fi

if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "Theme not found: $PROMPT_FILE" >&2
  echo "Available themes:" >&2
  ls "$ROOT/public" | grep -v '\.' | sed 's/^/  - /' >&2
  exit 1
fi

if [[ -d "$THEME_DIR/levels" ]]; then
  echo "[ERROR] $THEME is a json-levels theme. Use scripts/json-ladder-run.py instead." >&2
  exit 1
fi

if [[ -e "$OUT_FILE" && "$OVERWRITE" -eq 0 ]]; then
  echo "Already exists: $OUT_FILE" >&2
  echo "Delete it first, or pass --overwrite, if you want to regenerate." >&2
  exit 1
fi

# Runner 自動判定 (openrouter は API 課金が走るため自動判定に含めない)
if [[ "$RUNNER" == "auto" ]]; then
  case "$MODEL" in
    local/*|gemma*|qwen*|llama*|mistral*|phi*) RUNNER="gptme" ;;
    claude-*)                                  RUNNER="claude" ;;
    *) echo "Cannot auto-detect runner for '$MODEL'. Pass --runner gptme|claude|openrouter|copy." >&2; exit 1 ;;
  esac
fi

# openrouter runner は生成成功後に openrouter-run.py 側でディレクトリを作る。
# ここで先に掘ると、前提不備 / dry-run で終わった時に空ディレクトリが残る。
if [[ "$RUNNER" != "openrouter" ]]; then
  mkdir -p "$OUT_DIR"
fi

echo "==> Theme:   $THEME"
echo "==> Model:   $MODEL"
echo "==> Runner:  $RUNNER"
echo "==> Output:  $OUT_FILE"
echo

case "$RUNNER" in
  gptme)
    # LM Studio 上のモデルに gptme で投げる
    # モデル名は LM Studio 表示そのまま (例: google/gemma-4-12b-qat) を期待
    LMS_MODEL="$MODEL"
    # gemma-4-12b-qat → google/gemma-4-12b-qat の補完
    if [[ "$LMS_MODEL" != */* ]]; then
      case "$LMS_MODEL" in
        gemma*) LMS_MODEL="google/$LMS_MODEL" ;;
        qwen*)  LMS_MODEL="$LMS_MODEL" ;;
      esac
    fi
    PROMPT_BODY="$(cat "$PROMPT_FILE")
保存先のファイル名は index.html です。save ツールで書き出してから 'done' とだけ返してください。"

    OPENAI_BASE_URL=http://127.0.0.1:1234/v1 \
    OPENAI_API_KEY=lm-studio \
    gptme -y --workspace "$OUT_DIR" -m "local/$LMS_MODEL" --non-interactive "$PROMPT_BODY"
    ;;

  claude)
    cat >&2 <<EOF
Claude モデルは Bash から直接叩けないので、Claude Code 上で以下を実行:

  Agent ツール (subagent_type=implementer, model=$MODEL):
    プロンプト = $PROMPT_FILE の中身
    出力先     = $OUT_FILE
EOF
    exit 2
    ;;

  openrouter)
    # OpenRouter API 経由。openrouter-run.py が出力ファイルと usage 実測入り run.json を書く。
    # PR #24 / #25 で使い捨てスクリプトになっていた手順の固定版。
    if ! command -v uv >/dev/null 2>&1; then
      echo "  [ERROR] uv not found. Install uv (openrouter runner requires it)." >&2
      exit 4
    fi
    # set -e 下では `[[ cond ]] && cmd` を単独行に置くと、cond が偽の時に行全体が
    # 非ゼロを返してスクリプトが止まる。条件付き追加は必ず if で書く。
    OR_ARGS=(--theme "$THEME" --model "$MODEL" --reasoning-effort "$REASONING_EFFORT")
    if [[ -n "$MAX_TOKENS" ]]; then
      OR_ARGS+=(--max-tokens "$MAX_TOKENS")
    fi
    if [[ "$OVERWRITE" -eq 1 ]]; then
      OR_ARGS+=(--overwrite)
    fi
    if [[ "$DRY_RUN" -eq 1 ]]; then
      OR_ARGS+=(--dry-run)
    fi

    if ! uv run "$ROOT/scripts/openrouter-run.py" "${OR_ARGS[@]}" >/dev/null; then
      echo "  [ERROR] openrouter-run.py failed. Nothing was recorded." >&2
      exit 6
    fi
    if [[ "$DRY_RUN" -eq 1 ]]; then
      echo
      echo "==> dry-run 完了。API は呼び出していません。"
      exit 0
    fi
    ;;

  copy)
    echo "手動で $OUT_FILE を配置してから、下記の ENTRIES を追加してください。"
    ;;

  *)
    echo "Unknown runner: $RUNNER" >&2
    exit 1
    ;;
esac

# 生成確認
if [[ ! -s "$OUT_FILE" ]]; then
  echo "WARN: $OUT_FILE が生成されていません。" >&2
  exit 3
fi

LINE_COUNT="$(wc -l < "$OUT_FILE" | tr -d ' ')"
BYTE_COUNT="$(wc -c < "$OUT_FILE" | tr -d ' ')"

echo
echo "==> 生成完了: $LINE_COUNT 行 / $BYTE_COUNT bytes"
echo

if [[ "$RUNNER" == "openrouter" ]]; then
  # openrouter-run.py が usage 実測入り run.json を既に書いている。
  # ここで estimate-run-cost.py を走らせると推定値で上書きしかねないので呼ばない。
  echo "==> run.json は openrouter-run.py が実測 usage で生成済み"
  echo
  echo "次のステップ:"
  echo "  1. public/$THEME/$MODEL/run.json の内容を確認 (harness=openrouter-api / usage.estimated=false)"
  echo "  2. uv run scripts/build-runs-json.py で public/runs.json を更新"
  echo "  3. node scripts/validate-runs.mjs でスキーマ検証"
  echo "  4. public/index.html の ENTRIES 配列に以下を追加してください。"
else
  # run.json スケルトン生成 + 推定コスト算出。
  # API 経由で usage が取れなかった場合の下限値を埋める。実測 usage を後で埋めたい時は
  # 手で run.json の usage.estimated=false と method="api-usage" に更新してから re-run。
  # #7 Fail Fast: 失敗を握り潰さず非ゼロ exit で停止 (CLAUDE.md「失敗したのに成功扱い」禁止)
  echo "==> run.json スケルトン生成 (uv run scripts/estimate-run-cost.py --write)..."
  if ! command -v uv >/dev/null 2>&1; then
    echo "  [ERROR] uv not found. Install uv or run scripts/estimate-run-cost.py manually." >&2
    exit 4
  fi
  if ! uv run "$ROOT/scripts/estimate-run-cost.py" --theme "$THEME" --model "$MODEL" --write >/dev/null; then
    echo "  [ERROR] estimate-run-cost.py failed. run.json is not written. Fix and re-run." >&2
    exit 5
  fi

  echo
  echo "次のステップ:"
  echo "  1. public/$THEME/$MODEL/run.json の harness / reasoning_effort を実際の生成条件に合わせて修正"
  echo "     (自動判定は unknown。RUNNER_MAP の一覧は scripts/backfill-runs.py を参照)"
  echo "  2. uv run scripts/build-runs-json.py で public/runs.json を更新"
  echo "  3. node scripts/validate-runs.mjs でスキーマ検証"
  echo "  4. public/index.html の ENTRIES 配列に以下を追加してください。"
fi
echo
cat <<EOF
    {
      theme: "$THEME",
      model: "$MODEL",
      model_label: "$(echo "$MODEL" | tr '-' ' ' | awk '{for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) tolower(substr($i,2)); print}')",
      provider: "TODO",
      runner: "$RUNNER",
      note: "TODO: 1行で要約"
    },
EOF

echo
echo "デプロイ: cd $ROOT && wrangler pages deploy public/ --project-name=oreore-bench"
