#!/usr/bin/env python3
"""LM Studio に Gemma モデルで HTML 系テーマの生成を投げる。
lp-nishibi / othello など、index.html を 1 枚出力するテーマ用。

使い方:
  python3 scripts/gen-html.py --theme lp-nishibi
  python3 scripts/gen-html.py --theme othello --model 12b
  python3 scripts/gen-html.py --theme mario-like-2d --model 31b
"""
from __future__ import annotations
import argparse, json, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
API = "http://127.0.0.1:1234/v1/chat/completions"

MODELS = [
    ("google/gemma-4-12b-qat", "gemma-4-12b-qat"),
    ("google/gemma-4-26b-a4b-qat", "gemma-4-26b-a4b-qat"),
    ("google/gemma-4-31b", "gemma-4-31b"),
]


def build_prompt(theme_dir: Path) -> str:
    """テーマ PROMPT.md を読み込む。HTML テーマは PROMPT.md がそのまま指示書。"""
    prompt_md = (theme_dir / "PROMPT.md").read_text(encoding="utf-8")
    return f"{prompt_md.strip()}\n\n---\n\n完成した index.html 単体を出力してください。説明・前置き・コードフェンスは一切不要です。"


def strip_fence(text: str) -> str:
    """コードフェンスを剥がす。```html ... ``` / ``` ... ```"""
    s = text.strip()
    if s.startswith("```"):
        # 最初のフェンス行を落として、末尾フェンスも落とす
        lines = s.split("\n", 1)
        if len(lines) > 1:
            s = lines[1]
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3].rstrip()
    return s


def gen_one(theme_dir: Path, model_id: str, dir_name: str, prompt: str, max_tokens: int, overwrite: bool = False) -> str:
    out_dir = theme_dir / dir_name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "index.html"
    if out_file.exists() and not overwrite:
        return f"{dir_name}: skip (exists)"
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": max_tokens,
    }
    req = urllib.request.Request(
        API,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    print(f"[{theme_dir.name}/{dir_name}] sending (max_tokens={max_tokens})...", file=sys.stderr, flush=True)
    with urllib.request.urlopen(req, timeout=1800) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    content = body["choices"][0]["message"]["content"]
    content = strip_fence(content)
    out_file.write_text(content, encoding="utf-8")
    return f"{theme_dir.name}/{dir_name}: saved {len(content)} chars"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--theme", required=True, help="lp-nishibi / othello / hasami-shogi / mario-like-2d など")
    ap.add_argument("--model", help="モデル名の部分一致で絞る")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--max-tokens", type=int, default=24000)
    args = ap.parse_args()

    theme_dir = PUBLIC / args.theme
    if not (theme_dir / "PROMPT.md").exists():
        print(f"[ERROR] {theme_dir}/PROMPT.md not found", file=sys.stderr)
        return 1

    prompt = build_prompt(theme_dir)
    print(f"=== {args.theme} (prompt {len(prompt)} chars) ===", file=sys.stderr)
    for mid, dn in MODELS:
        if args.model and args.model not in dn:
            continue
        try:
            print(gen_one(theme_dir, mid, dn, prompt, args.max_tokens, args.overwrite))
        except Exception as e:
            print(f"[ERROR] {dn}: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
