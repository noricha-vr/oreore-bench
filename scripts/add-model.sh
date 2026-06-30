#!/usr/bin/env bash
# 新しいモデルでテーマを再現するワンライナー。
# 使い方:
#   bash scripts/add-model.sh <theme> <model-slug> [--runner gptme|claude|copy]
#
# 例:
#   bash scripts/add-model.sh lp-nishibi gemma-4-12b-qat
#   bash scripts/add-model.sh othello claude-haiku-4-5 --runner claude
#   bash scripts/add-model.sh lp-nishibi gpt-5-codex --runner copy   # 既存ファイルを置きたいだけ
#
# 動作:
#   1. public/<theme>/PROMPT.md を読む
#   2. 指定の runner で <model-slug> に投げて public/<theme>/<model-slug>/index.html を生成
#   3. ユーザーに「public/index.html の ENTRIES 配列に下記を追加して」とテンプレを表示
#
# runner 自動判定 (--runner 省略時):
#   - local/*  または モデル名が gemma|qwen|llama|mistral|phi で始まる → gptme + LM Studio (1234)
#   - claude-*                                                          → echo で「Claude Code Agent ツールで投げて」と案内
#   - それ以外                                                           → エラー、--runner を明示

set -euo pipefail

THEME="${1:-}"
MODEL="${2:-}"
RUNNER="auto"

shift 2 2>/dev/null || true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --runner) RUNNER="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$THEME" || -z "$MODEL" ]]; then
  echo "Usage: bash scripts/add-model.sh <theme> <model-slug> [--runner gptme|claude|copy]" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
THEME_DIR="$ROOT/public/$THEME"
PROMPT_FILE="$THEME_DIR/PROMPT.md"
OUT_DIR="$THEME_DIR/$MODEL"
OUT_FILE="$OUT_DIR/index.html"

if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "Theme not found: $PROMPT_FILE" >&2
  echo "Available themes:" >&2
  ls "$ROOT/public" | grep -v '\.' | sed 's/^/  - /' >&2
  exit 1
fi

if [[ -e "$OUT_FILE" ]]; then
  echo "Already exists: $OUT_FILE" >&2
  echo "Delete it first if you want to regenerate." >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

# Runner 自動判定
if [[ "$RUNNER" == "auto" ]]; then
  case "$MODEL" in
    local/*|gemma*|qwen*|llama*|mistral*|phi*) RUNNER="gptme" ;;
    claude-*)                                  RUNNER="claude" ;;
    *) echo "Cannot auto-detect runner for '$MODEL'. Pass --runner gptme|claude|copy." >&2; exit 1 ;;
  esac
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
echo "次のステップ: public/index.html の ENTRIES 配列に以下を追加してください。"
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
