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


def gen_one(theme_dir: Path, model_id: str, dir_name: str, prompt: str, sampling: dict, overwrite: bool = False) -> str:
    out_dir = theme_dir / dir_name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "output.json"
    if out_file.exists() and not overwrite:
        return f"{dir_name}: skip (exists)"
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": sampling["temperature"],
        "max_tokens": sampling["max_tokens"],
    }
    req = urllib.request.Request(
        API,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    print(f"[{dir_name}] sending (max_tokens={sampling['max_tokens']})...", file=sys.stderr, flush=True)
    with urllib.request.urlopen(req, timeout=1800) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    content = body["choices"][0]["message"]["content"]
    out_file.write_text(content, encoding="utf-8")

    # #3 Fail Fast: usage が無い / 0 トークンなら run.json を「実測」で書かない。
    # 「usage 欠損 → estimated=false でゼロ実測固定」は最悪の隠れ嘘 (コスト $0.00 表示になる)。
    usage = body.get("usage")
    if not isinstance(usage, dict):
        raise RuntimeError(f"{dir_name}: API response has no usage object. Cannot record measured run.json.")
    pt = int(usage.get("prompt_tokens") or 0)
    ct = int(usage.get("completion_tokens") or 0)
    if pt == 0 or ct == 0:
        raise RuntimeError(f"{dir_name}: usage tokens are zero (prompt={pt}, completion={ct}). Refusing to write measured run.json.")

    _write_run_measured(theme_dir, out_dir, dir_name, model_id, pt, ct, sampling)

    return f"{dir_name}: saved {len(content)} chars"


def _write_run_measured(
    theme_dir: Path,
    out_dir: Path,
    model_slug: str,
    model_id: str,
    prompt_tokens: int,
    completion_tokens: int,
    sampling: dict,
) -> None:
    """LM Studio (OpenAI 互換) の usage から run.json を書く。

    - gen-questions.py はローカル LM Studio 専用なので type=local 固定 (cost は actual_usd=0)
    - #4後半: 参考単価の cost は estimated=true (usage 実測フラグと混同しないため。実測 usage の傍らに
      「参考」というラベルで単価だけ残す設計)
    - #6: sampling.max_tokens は実際にリクエストした値をそのまま記録
    """
    theme = theme_dir.name
    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    run: dict = {
        "schema_version": 1,
        "theme": theme,
        "model": model_slug,
        "model_id": model_id,
        # gen-questions.py の担当領域は LM Studio 経由の LMS-API 生成のみ
        "harness": "lmstudio-api",
        "reasoning_effort": "none",
        "attempts": 1,
        "generated_at": now_iso,
        "generated_at_source": "measured",
        "sampling": {
            "temperature": sampling["temperature"],
            "max_tokens": sampling["max_tokens"],  # #6 実際にリクエストした値
            "top_p": "default",
        },
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

    # #4後半: type=local なので actual_usd=0 が意味。参考単価は cost には反映しない
    # (index.html 側の $0 (ローカル) 表示ロジックと一貫)。
    run["cost"] = {
        "estimated": True,  # cost 側は「参考推定」の意味。usage の実測とは別レイヤ
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
    sampling = {"temperature": 0.2, "max_tokens": args.max_tokens}
    print(f"=== {args.theme} (prompt {len(prompt)} chars) ===", file=sys.stderr)
    for mid, dn in MODELS:
        if args.model and args.model not in dn:
            continue
        try:
            print(gen_one(theme_dir, mid, dn, prompt, sampling, args.overwrite))
        except Exception as e:
            print(f"[ERROR] {dn}: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
