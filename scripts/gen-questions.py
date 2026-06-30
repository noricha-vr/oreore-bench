#!/usr/bin/env python3
"""LM Studio に 3 Gemma モデルで extract-questions の生成を投げる。
Claude Opus は別途 Agent ツール経由。
"""
from __future__ import annotations
import argparse, json, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
THEME_DIR = ROOT / "public" / "extract-questions"
API = "http://127.0.0.1:1234/v1/chat/completions"

MODELS = [
    ("google/gemma-4-12b-qat", "gemma-4-12b-qat"),
    ("google/gemma-4-26b-a4b-qat", "gemma-4-26b-a4b-qat"),
    ("google/gemma-4-31b", "gemma-4-31b"),
]


def build_prompt() -> str:
    prompt_md = (THEME_DIR / "PROMPT.md").read_text(encoding="utf-8")
    prompt_md = prompt_md.replace(
        "[input.md の本文をここに展開してプロンプトに含める]", ""
    )
    input_md = (THEME_DIR / "input.md").read_text(encoding="utf-8")
    return f"{prompt_md.strip()}\n\n{input_md.strip()}\n\n---\n\nJSON 単体で出力してください。"


def gen_one(model_id: str, dir_name: str, prompt: str, overwrite: bool = False) -> str:
    out_dir = THEME_DIR / dir_name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "output.json"
    if out_file.exists() and not overwrite:
        return f"{dir_name}: skip (exists)"
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 12000,
    }
    req = urllib.request.Request(
        API,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    print(f"[{dir_name}] sending...", file=sys.stderr, flush=True)
    with urllib.request.urlopen(req, timeout=900) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    content = body["choices"][0]["message"]["content"]
    out_file.write_text(content, encoding="utf-8")
    return f"{dir_name}: saved {len(content)} chars"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    prompt = build_prompt()
    print(f"prompt length: {len(prompt)} chars", file=sys.stderr)
    for mid, dn in MODELS:
        if args.model and args.model not in dn:
            continue
        try:
            print(gen_one(mid, dn, prompt, args.overwrite))
        except Exception as e:
            print(f"[ERROR] {dn}: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
