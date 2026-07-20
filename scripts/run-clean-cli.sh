#!/usr/bin/env bash
# 1ショット生成ラッパ。個人ハーネス（~/.claude / ~/.codex の設定・CLAUDE.md・skills）を
# 遮断した素の状態で各 CLI / API を叩き、応答から index.html を抽出して保存する。
# ベンチの公平性のため、どのモデルにも同一プロンプト + 同一の出力指示だけを渡す。
#
# Usage: run-clean-cli.sh <runner> <model> <prompt_md> <out_html> <log_file>
#   runner: claude | codex | agy | openrouter | lmstudio
#   claude:     claude -p --setting-sources "" で user 設定を読まずサブスク認証だけ使う
#   codex:      auth.json のみコピーした空の CODEX_HOME で AGENTS.md を遮断
#   agy:        AntiGravity CLI --print（独自設定のみで ~/.claude を読まない）
#   openrouter: OpenRouter chat/completions API（要 OPENROUTER_API_KEY）
#   lmstudio:   LM Studio OpenAI 互換 API（対象モデルは事前に lms load しておく）
set -euo pipefail

RUNNER=$1; MODEL=$2; PROMPT_MD=$3; OUT=$4; LOG=$5
WORK=$(mktemp -d)
CODEX_CLEAN=""
# auth.json の一時コピーを異常終了時にも確実に消す（trap に両方登録）
trap 'rm -rf "$WORK" "${CODEX_CLEAN:-}"' EXIT

PROMPT="$(cat "$PROMPT_MD")

重要: 応答には完成した index.html の全内容だけを 1 つのコードブロックで出力してください。説明・前置き・後書きは不要です。ファイル操作やツールは使わず、本文としてコードを出力してください。"

mkdir -p "$(dirname "$OUT")" "$(dirname "$LOG")"

case "$RUNNER" in
  claude)
    (cd "$WORK" && claude -p "$PROMPT" --model "$MODEL" --setting-sources "" \
      --disable-slash-commands --tools "" --no-session-persistence --effort high) >"$LOG" 2>&1
    ;;
  codex)
    CODEX_CLEAN=$(mktemp -d)
    chmod 700 "$CODEX_CLEAN"
    cp "$HOME/.codex/auth.json" "$CODEX_CLEAN/"
    chmod 600 "$CODEX_CLEAN/auth.json"
    (cd "$WORK" && CODEX_HOME="$CODEX_CLEAN" codex exec --skip-git-repo-check \
      -c model_reasoning_effort=high --model "$MODEL" "$PROMPT") >"$LOG" 2>&1
    ;;
  agy)
    (cd "$WORK" && agy --print "$PROMPT" --model "$MODEL" --print-timeout 30m) >"$LOG" 2>&1
    ;;
  openrouter)
    : "${OPENROUTER_API_KEY:?OPENROUTER_API_KEY required}"
    jq -n --arg model "$MODEL" --arg prompt "$PROMPT" \
      '{model: $model, reasoning: {effort: "high"}, max_tokens: 65000, stream: false,
        messages: [{role: "user", content: $prompt}]}' > "$WORK/req.json"
    curl -sS --max-time 1800 https://openrouter.ai/api/v1/chat/completions \
      -H "Authorization: Bearer $OPENROUTER_API_KEY" -H "Content-Type: application/json" \
      -d @"$WORK/req.json" > "$LOG"
    ;;
  lmstudio)
    jq -n --arg model "$MODEL" --arg prompt "$PROMPT" \
      '{model: $model, max_tokens: 26000, stream: false,
        messages: [{role: "user", content: $prompt}]}' > "$WORK/req.json"
    curl -sS --max-time 3600 http://127.0.0.1:1234/v1/chat/completions \
      -H "Content-Type: application/json" -d @"$WORK/req.json" > "$LOG"
    ;;
  *)
    echo "unknown runner: $RUNNER" >&2; exit 2
    ;;
esac

python3 - "$RUNNER" "$LOG" "$OUT" <<'PY'
import json, sys

runner, log, out = sys.argv[1:4]
raw = open(log, encoding="utf-8", errors="replace").read()
if runner in ("openrouter", "lmstudio"):
    data = json.loads(raw)
    if "choices" not in data:
        sys.exit(f"API error in {log}: {str(data)[:300]}")
    raw = data["choices"][0]["message"]["content"] or ""
lo = raw.lower()
start = lo.find("<!doctype")
if start < 0:
    start = lo.find("<html")
end = lo.rfind("</html>")
if start < 0 or end < 0 or end <= start:
    sys.exit(f"HTML not found in {log}")
html = raw[start:end + len("</html>")]
if len(html) < 3000:
    sys.exit(f"HTML too small ({len(html)} bytes)")
with open(out, "w", encoding="utf-8") as f:
    f.write(html + "\n")
print(f"OK {out} {len(html)} bytes")
PY
