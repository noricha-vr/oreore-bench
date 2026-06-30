#!/usr/bin/env python3
"""LM Studio に 3 Gemma モデルで JSON クイズ生成を投げる。
3 テーマ (easy/medium/hard) × 3 モデル = 9 件を直列実行。
Claude Opus は別途 Agent ツール経由。

使い方:
  python3 scripts/gen-quiz.py                 # 全部
  python3 scripts/gen-quiz.py --theme hard    # 指定テーマのみ
  python3 scripts/gen-quiz.py --model 12b     # モデル絞り込み（部分一致）
"""
from __future__ import annotations
import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUIZ_BASE = ROOT / "public"
API = "http://127.0.0.1:1234/v1/chat/completions"

THEMES = ["json-quiz-easy", "json-quiz-medium", "json-quiz-hard"]
MODELS = [
    ("google/gemma-4-12b-qat", "gemma-4-12b-qat"),
    ("google/gemma-4-26b-a4b-qat", "gemma-4-26b-a4b-qat"),
    ("google/gemma-4-31b", "gemma-4-31b"),
]

# テーマごとに max_tokens を変える（hard は出力長め）
THEME_MAX_TOKENS = {
    "json-quiz-easy": 3000,
    "json-quiz-medium": 8000,
    "json-quiz-hard": 12000,
}


def build_prompt(theme: str) -> str:
    theme_dir = QUIZ_BASE / theme
    prompt_md = (theme_dir / "PROMPT.md").read_text(encoding="utf-8")
    prompt_md = prompt_md.replace(
        "[input.md の本文をここに展開してプロンプトに含める]", ""
    )
    input_md = (theme_dir / "input.md").read_text(encoding="utf-8")
    return f"{prompt_md.strip()}\n\n{input_md.strip()}\n\n---\n\nJSON 単体で出力してください。"


def gen_one(theme: str, model_id: str, dir_name: str, prompt: str, overwrite: bool = False) -> str:
    out_dir = QUIZ_BASE / theme / dir_name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "output.json"
    if out_file.exists() and not overwrite:
        return f"{theme}/{dir_name}: skip (exists)"

    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": THEME_MAX_TOKENS.get(theme, 8000),
    }
    req = urllib.request.Request(
        API,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    print(f"[{theme}/{dir_name}] sending (max_tokens={payload['max_tokens']})...", file=sys.stderr, flush=True)
    with urllib.request.urlopen(req, timeout=900) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    content = body["choices"][0]["message"]["content"]
    out_file.write_text(content, encoding="utf-8")
    return f"{theme}/{dir_name}: saved {len(content)} chars"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--theme", choices=THEMES, help="特定テーマのみ実行")
    ap.add_argument("--model", help="モデル名に含まれる文字列で絞り込み")
    ap.add_argument("--overwrite", action="store_true", help="既存の output.json を上書き")
    args = ap.parse_args()

    themes = [args.theme] if args.theme else THEMES
    for theme in themes:
        prompt = build_prompt(theme)
        print(f"=== {theme} (prompt {len(prompt)} chars) ===", file=sys.stderr)
        for mid, dn in MODELS:
            if args.model and args.model not in dn:
                continue
            try:
                print(gen_one(theme, mid, dn, prompt, args.overwrite))
            except Exception as e:
                print(f"[ERROR] {theme}/{dn}: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
