#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""public/index.html の ENTRIES から harness / reasoning_effort を機械変換し、run.json のスケルトンを埋める。

- generated_at は git log --diff-filter=A --format=%aI -- <path> の初回コミット時刻を使う
  (「手直しなし」ルールにより生成日と一致するはずという計画の前提)
- sampling: gen-questions.py 由来 (Gemma × extract-questions 系) のみ temperature 0.2 / max_tokens 16000 が確定
- #5 デフォルトは既存 run.json のあるエントリをスキップする (手動修正の無警告巻き戻しを防ぐ)
- --overwrite 指定時のみ既存 run.json を再生成 (usage/cost は保持)
- 実測 (estimated: false) の run.json は --overwrite でも触らない
- estimate-run-cost.py --write と組み合わせて完成させる (順序: backfill -> estimate --write -> build-runs-json)

Exit: 0 成功 / 1 index.html パース失敗
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
INDEX_HTML = PUBLIC / "index.html"

# ENTRIES の runner 自由記述 → (harness, reasoning_effort) の変換テーブル。
# ここに載っていない runner は harness/effort ともに "unknown"。
# 実測確認済みの対応関係のみ登録する。
RUNNER_MAP: dict[str, tuple[str, str]] = {
    "LM Studio API": ("lmstudio-api", "none"),
    "gptme (LM Studio)": ("gptme-lmstudio", "none"),
    "Claude Agent SDK": ("claude-agent-sdk", "none"),
    "claude CLI headless (effort high)": ("claude-cli-headless", "high"),
    "OpenAI API (reasoning high)": ("openai-api", "high"),
    "grok CLI (single-turn)": ("grok-cli", "none"),
    "OpenRouter API": ("openrouter-api", "none"),
    "AntiGravity CLI (High)": ("antigravity-cli", "high"),
}

# gen-questions.py で生成される (Gemma × extract-questions*) は sampling 確定。
GEN_QUESTIONS_MODELS = {"gemma-4-12b-qat", "gemma-4-26b-a4b-qat", "gemma-4-31b"}
GEN_QUESTIONS_THEMES = {"extract-questions", "extract-questions-v2"}

# ENTRIES 配列を抜き出す正規表現。1 行 1 エントリ想定 (現状の index.html はその形式)。
ENTRY_LINE_RE = re.compile(
    r'\{\s*theme:\s*"(?P<theme>[^"]+)",\s*model:\s*"(?P<model>[^"]+)",\s*runner:\s*"(?P<runner>[^"]+)"'
)


def parse_entries() -> list[dict]:
    text = INDEX_HTML.read_text(encoding="utf-8")
    # ENTRIES = [ ... ]; の中身を切り出す
    m = re.search(r"const ENTRIES = \[(.+?)\];", text, re.DOTALL)
    if not m:
        raise RuntimeError("ENTRIES literal not found in public/index.html")
    body = m.group(1)
    entries: list[dict] = []
    for line in body.splitlines():
        m2 = ENTRY_LINE_RE.search(line)
        if m2:
            entries.append({
                "theme": m2.group("theme"),
                "model": m2.group("model"),
                "runner": m2.group("runner"),
            })
    return entries


def git_first_commit_time(path: Path) -> str | None:
    """指定パスを追加した最初のコミット時刻 (ISO8601)。取得失敗時 None。"""
    try:
        rel = path.relative_to(ROOT)
    except ValueError:
        rel = path
    try:
        res = subprocess.run(
            ["git", "log", "--diff-filter=A", "--format=%aI", "--", str(rel)],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError:
        return None
    lines = [ln.strip() for ln in res.stdout.splitlines() if ln.strip()]
    if not lines:
        return None
    # --diff-filter=A の最初 = 追加時。複数ファイルが該当する場合は最古 (tail) を採用
    return lines[-1]


def _is_estimated(run: dict) -> bool:
    usage = run.get("usage") or {}
    return usage.get("estimated", True) is not False


def build_run(entry: dict) -> dict[str, Any]:
    theme = entry["theme"]
    model = entry["model"]
    runner = entry["runner"]
    harness, effort = RUNNER_MAP.get(runner, ("unknown", "unknown"))

    model_dir = PUBLIC / theme / model
    generated_at = git_first_commit_time(model_dir) if model_dir.exists() else None

    # sampling は gen-questions.py 由来のみ確定
    if theme in GEN_QUESTIONS_THEMES and model in GEN_QUESTIONS_MODELS:
        sampling = {"temperature": 0.2, "max_tokens": 16000, "top_p": "default"}
    else:
        sampling = {"temperature": "default", "max_tokens": "default", "top_p": "default"}

    # ローカルモデルは runtime を付ける (量子化・エンジン情報)
    if model.startswith("gemma-"):
        runtime = {"engine": "lmstudio", "quantization": "qat-4bit" if "qat" in model else "q4_k_m", "api": "openai-compat"}
    else:
        runtime = None

    return {
        "schema_version": 1,
        "theme": theme,
        "model": model,
        "model_id": model,
        "harness": harness,
        "reasoning_effort": effort,
        "attempts": 1,
        "generated_at": generated_at,
        "generated_at_source": "git-first-commit" if generated_at else "unknown",
        "sampling": sampling,
        "system_prompt": "harness-default" if harness != "unknown" else "unknown",
        "post_processing": "none",
        "runtime": runtime,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--theme")
    ap.add_argument("--model")
    ap.add_argument("--overwrite", action="store_true",
                    help="既存 run.json も再生成する (usage/cost は保持、手動修正は失う)")
    args = ap.parse_args()

    entries = parse_entries()
    print(f"# parsed {len(entries)} entries from index.html", file=sys.stderr)

    processed = 0
    skipped_measured = 0
    skipped_existing = 0
    for e in entries:
        if args.theme and e["theme"] != args.theme:
            continue
        if args.model and e["model"] != args.model:
            continue

        model_dir = PUBLIC / e["theme"] / e["model"]
        if not model_dir.exists():
            print(f"[warn] dir not found: {model_dir}", file=sys.stderr)
            continue

        run_path = model_dir / "run.json"

        # #5 デフォルトは既存 run.json をスキップ (手動修正の無警告巻き戻しを防ぐ)
        if run_path.exists():
            existing = json.loads(run_path.read_text(encoding="utf-8"))
            if not _is_estimated(existing):
                # 実測 usage あり: --overwrite でも触らない (measured を尊重)
                skipped_measured += 1
                continue
            if not args.overwrite:
                skipped_existing += 1
                continue
            # --overwrite: usage/cost は保持しつつフィールドを再生成
            new_run = build_run(e)
            for k in ("usage", "cost"):
                if k in existing:
                    new_run[k] = existing[k]
        else:
            new_run = build_run(e)

        run_path.write_text(json.dumps(new_run, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        processed += 1
        print(f"[ok] {e['theme']}/{e['model']} harness={new_run['harness']} effort={new_run['reasoning_effort']} generated_at={new_run['generated_at']}", file=sys.stderr)

    print(f"\n# processed={processed} skipped_measured={skipped_measured} skipped_existing={skipped_existing}", file=sys.stderr)
    if skipped_existing > 0 and not args.overwrite:
        print(f"# {skipped_existing} entries already have run.json. Use --overwrite to regenerate.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
