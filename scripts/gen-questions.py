#!/usr/bin/env python3
"""LM Studio に 3 Gemma モデルで extract-questions 系テーマの生成を投げる。
Claude Opus は別途 Agent ツール経由。

使い方:
  python3 scripts/gen-questions.py                              # extract-questions
  python3 scripts/gen-questions.py --theme extract-questions-v2 # v2
  python3 scripts/gen-questions.py --model 12b --overwrite
"""
from __future__ import annotations
import argparse, json, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
PRICING_PATH = ROOT / "scripts" / "pricing.json"
API = "http://127.0.0.1:1234/v1/chat/completions"

MODELS = [
    ("google/gemma-4-12b-qat", "gemma-4-12b-qat"),
    ("google/gemma-4-26b-a4b-qat", "gemma-4-26b-a4b-qat"),
    ("google/gemma-4-31b", "gemma-4-31b"),
]


def build_prompt(theme_dir: Path) -> str:
    prompt_md = (theme_dir / "PROMPT.md").read_text(encoding="utf-8")
    prompt_md = prompt_md.replace(
        "[input.md の本文をここに展開してプロンプトに含める]", ""
    )
    input_md = (theme_dir / "input.md").read_text(encoding="utf-8")
    return f"{prompt_md.strip()}\n\n{input_md.strip()}\n\n---\n\nJSON 単体で出力してください。"


def gen_one(theme_dir: Path, model_id: str, dir_name: str, prompt: str, max_tokens: int, overwrite: bool = False) -> str:
    out_dir = theme_dir / dir_name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "output.json"
    if out_file.exists() and not overwrite:
        return f"{dir_name}: skip (exists)"
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    req = urllib.request.Request(
        API,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    print(f"[{dir_name}] sending (max_tokens={max_tokens})...", file=sys.stderr, flush=True)
    with urllib.request.urlopen(req, timeout=1800) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    content = body["choices"][0]["message"]["content"]
    out_file.write_text(content, encoding="utf-8")

    # API レスポンスの usage を実測記録して run.json に書く。
    # estimate-run-cost.py --write を使わなくても実測値が入るので、
    # 生成時点で最も正確な usage を残せる (推定より下限問題がない)。
    usage = body.get("usage") or {}
    _write_run_measured(theme_dir, out_dir, dir_name, model_id, usage)

    return f"{dir_name}: saved {len(content)} chars"


def _load_pricing_for(model_slug: str) -> dict | None:
    """model-map.json → pricing.json から該当 slug の単価を返す。ローカル (単価なし) は None。"""
    if not PRICING_PATH.exists():
        return None
    pricing = json.loads(PRICING_PATH.read_text(encoding="utf-8"))
    return pricing.get(model_slug)


def _write_run_measured(theme_dir: Path, out_dir: Path, model_slug: str, model_id: str, usage: dict) -> None:
    """LM Studio (OpenAI 互換) の usage から run.json を書く。
    estimated=False, method=api-usage, generated_at_source=measured。"""
    theme = theme_dir.name
    prompt_tokens = int(usage.get("prompt_tokens", 0))
    completion_tokens = int(usage.get("completion_tokens", 0))
    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    run: dict = {
        "schema_version": 1,
        "theme": theme,
        "model": model_slug,
        "model_id": model_id,
        # LM Studio のみ (gen-questions.py の担当領域)
        "harness": "lmstudio-api",
        "reasoning_effort": "none",
        "attempts": 1,
        "generated_at": now_iso,
        "generated_at_source": "measured",
        "sampling": {"temperature": 0.2, "max_tokens": 16000, "top_p": "default"},
        "system_prompt": "harness-default",
        "post_processing": "none",
        "runtime": {"engine": "lmstudio", "quantization": "qat-4bit" if "qat" in model_slug else "q4_k_m", "api": "openai-compat"},
        "usage": {
            "estimated": False,
            "method": "api-usage",
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        },
    }
    # ローカル: 参考単価なし。actual_usd=0
    pricing = _load_pricing_for(model_slug)
    if pricing:
        usd = round(
            prompt_tokens * pricing["prompt_usd_per_mtok"] / 1_000_000
            + completion_tokens * pricing["completion_usd_per_mtok"] / 1_000_000,
            6,
        )
        run["cost"] = {
            "estimated": False,
            "usd": usd,
            "actual_usd": None,
            "prompt_usd_per_mtok": pricing["prompt_usd_per_mtok"],
            "completion_usd_per_mtok": pricing["completion_usd_per_mtok"],
            "pricing_source": pricing["pricing_source"],
            "pricing_model": pricing["pricing_model"],
            "pricing_fetched_at": pricing["pricing_fetched_at"],
        }
    else:
        run["cost"] = {
            "estimated": False,
            "usd": None,
            "actual_usd": 0,
            "prompt_usd_per_mtok": None,
            "completion_usd_per_mtok": None,
            "pricing_source": "local-no-reference",
            "pricing_model": None,
            "pricing_fetched_at": None,
        }
    (out_dir / "run.json").write_text(json.dumps(run, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--theme", default="extract-questions",
                    help="テーマ名（デフォルト extract-questions）")
    ap.add_argument("--model", help="モデル名の部分一致で絞る")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--max-tokens", type=int, default=16000,
                    help="LM Studio に投げる max_tokens (デフォルト 16000)")
    args = ap.parse_args()

    theme_dir = PUBLIC / args.theme
    if not (theme_dir / "PROMPT.md").exists():
        print(f"[ERROR] theme not found: {theme_dir}", file=sys.stderr)
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
