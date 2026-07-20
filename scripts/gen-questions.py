#!/usr/bin/env python3
"""LM Studio のローカルモデルで JSON テーマを生成する。

API モデルは別のハーネス経由で生成する。

使い方:
  python3 scripts/gen-questions.py                              # extract-questions
  python3 scripts/gen-questions.py --theme extract-questions-v2 # v2
  python3 scripts/gen-questions.py --theme pr-triage --temperature default
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
    ("google/gemma-4-12b-qat", "gemma-4-12b-qat", "qat-4bit"),
    ("google/gemma-4-26b-a4b-qat", "gemma-4-26b-a4b-qat", "qat-4bit"),
    ("google/gemma-4-31b", "gemma-4-31b", "q4_k_m"),
    ("wcamon/agents-a1-4b-mlx-4bit", "agents-a1-4b", "mlx-4bit"),
]


def build_prompt(theme_dir: Path) -> str:
    prompt_md = (theme_dir / "PROMPT.md").read_text(encoding="utf-8")
    placeholder = "[input.md の本文をここに展開してプロンプトに含める]"
    input_path = theme_dir / "input.md"
    if placeholder in prompt_md:
        if not input_path.exists():
            raise FileNotFoundError(f"input file not found: {input_path}")
        prompt_md = prompt_md.replace(placeholder, "")
        input_md = input_path.read_text(encoding="utf-8")
        prompt_md = f"{prompt_md.strip()}\n\n{input_md.strip()}"
    return f"{prompt_md.strip()}\n\n---\n\nJSON 単体で出力してください。"


def gen_one(
    theme_dir: Path,
    model_id: str,
    dir_name: str,
    quantization: str,
    prompt: str,
    sampling: dict,
    overwrite: bool = False,
) -> str:
    out_dir = theme_dir / dir_name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "output.json"
    if out_file.exists() and not overwrite:
        return f"{dir_name}: skip (exists)"
    attempts = 1
    run_file = out_dir / "run.json"
    if overwrite and run_file.exists():
        previous_run = json.loads(run_file.read_text(encoding="utf-8"))
        attempts = int(previous_run.get("attempts") or 0) + 1
    payload: dict = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
    }
    if sampling["temperature"] != "default":
        payload["temperature"] = sampling["temperature"]
    if sampling["max_tokens"] != "default":
        payload["max_tokens"] = sampling["max_tokens"]
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

    _write_run_measured(
        theme_dir,
        out_dir,
        dir_name,
        model_id,
        quantization,
        attempts,
        pt,
        ct,
        sampling,
    )

    return f"{dir_name}: saved {len(content)} chars"


def _write_run_measured(
    theme_dir: Path,
    out_dir: Path,
    model_slug: str,
    model_id: str,
    quantization: str,
    attempts: int,
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
        "reasoning_effort": (
            "unknown" if model_slug == "agents-a1-4b" else "none"
        ),
        "attempts": attempts,
        "generated_at": now_iso,
        "generated_at_source": "measured",
        "sampling": {
            "temperature": sampling["temperature"],
            "max_tokens": sampling["max_tokens"],  # #6 実際にリクエストした値
            "top_p": "default",
        },
        "system_prompt": "harness-default",
        "post_processing": "none",
        "runtime": {
            "engine": "lmstudio",
            "quantization": quantization,
            "api": "openai-compat",
        },
        "usage": {
            "estimated": False,
            "method": "api-usage",
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        },
    }

    # gen-questions.py はローカル (type=local) 専用。参考単価があれば「参考仮想コスト」として
    # usd に記録 (pricing_source=openrouter-reference)、無ければ usd=null。
    # cost.estimated=true = 「参考推定」の意味。usage 実測フラグ (usage.estimated) と分離。
    pricing = _load_pricing_for(model_slug)
    if pricing:
        usd = round(
            prompt_tokens * pricing["prompt_usd_per_mtok"] / 1_000_000
            + completion_tokens * pricing["completion_usd_per_mtok"] / 1_000_000,
            6,
        )
        run["cost"] = {
            "estimated": True,
            "usd": usd,
            "actual_usd": 0,
            "prompt_usd_per_mtok": pricing["prompt_usd_per_mtok"],
            "completion_usd_per_mtok": pricing["completion_usd_per_mtok"],
            "pricing_source": "openrouter-reference",
            "pricing_model": pricing["pricing_model"],
            "pricing_fetched_at": pricing["pricing_fetched_at"],
        }
    else:
        run["cost"] = {
            "estimated": True,
            "usd": None,
            "actual_usd": 0,
            "prompt_usd_per_mtok": None,
            "completion_usd_per_mtok": None,
            "pricing_source": "local-no-reference",
            "pricing_model": None,
            "pricing_fetched_at": None,
        }
    (out_dir / "run.json").write_text(json.dumps(run, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _load_pricing_for(model_slug: str) -> dict | None:
    """pricing.json から該当 slug の単価を返す。無ければ None。"""
    if not PRICING_PATH.exists():
        return None
    pricing = json.loads(PRICING_PATH.read_text(encoding="utf-8"))
    return pricing.get(model_slug)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--theme", default="extract-questions",
                    help="テーマ名（デフォルト extract-questions）")
    ap.add_argument("--model", help="モデル名の部分一致で絞る")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--temperature", default="0.2",
                    help="LM Studio に投げる temperature。default なら省略")
    ap.add_argument("--max-tokens", default="16000",
                    help="LM Studio に投げる max_tokens。default なら省略")
    args = ap.parse_args()

    theme_dir = PUBLIC / args.theme
    if not (theme_dir / "PROMPT.md").exists():
        print(f"[ERROR] theme not found: {theme_dir}", file=sys.stderr)
        return 1

    prompt = build_prompt(theme_dir)
    try:
        temperature: float | str = (
            "default" if args.temperature == "default" else float(args.temperature)
        )
        max_tokens: int | str = (
            "default" if args.max_tokens == "default" else int(args.max_tokens)
        )
    except ValueError as exc:
        print(f"[ERROR] invalid sampling value: {exc}", file=sys.stderr)
        return 1

    sampling = {"temperature": temperature, "max_tokens": max_tokens}
    print(f"=== {args.theme} (prompt {len(prompt)} chars) ===", file=sys.stderr)
    for mid, dn, quantization in MODELS:
        if args.model and args.model not in dn:
            continue
        try:
            print(
                gen_one(
                    theme_dir,
                    mid,
                    dn,
                    quantization,
                    prompt,
                    sampling,
                    args.overwrite,
                )
            )
        except Exception as e:
            print(f"[ERROR] {dn}: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
