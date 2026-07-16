#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "tiktoken==0.13.0",
# ]
# ///
"""過去エントリの入出力トークン数を tiktoken (o200k_base) で推定し、pricing.json の単価を掛けて概算コストを算出する。

- 主手法: tiktoken o200k_base で実カウント (各社トークナイザの代理)。
- フォールバック: 文字種係数 ascii/4 + cjk*1.0 + other/2 (method: char-heuristic-v1)
- prompt = PROMPT.md (JSON テーマは + input.md + gen-questions.py が付ける接尾辞)
- completion = index.html or output.json の生ファイル
- estimated: false (実測 usage あり) の run.json はスキップ

使い方:
  uv run scripts/estimate-run-cost.py                     # dry-run 表 (全エントリ)
  uv run scripts/estimate-run-cost.py --theme lp-fable5   # テーマ絞り
  uv run scripts/estimate-run-cost.py --model claude-fable-5
  uv run scripts/estimate-run-cost.py --write             # run.json を更新 (usage/cost セクションのみ)

Exit: 0 成功 / 1 pricing.json 不在 or 対象エントリ 0 件
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
PRICING_PATH = ROOT / "scripts" / "pricing.json"

# JSON テーマは gen-questions.py が末尾に付ける定型接尾辞。プロンプト長推定を実運用と一致させるため含める。
JSON_PROMPT_SUFFIX = "\n\n---\n\nJSON 単体で出力してください。"

# gen-questions.py が PROMPT.md 内で置換するプレースホルダ (入力本文を挿入する位置)。
INPUT_PLACEHOLDER = "[input.md の本文をここに展開してプロンプトに含める]"


def load_encoder():
    """tiktoken o200k_base を返す。失敗時 None。"""
    try:
        import tiktoken
        return tiktoken.get_encoding("o200k_base")
    except Exception as e:
        print(f"[WARN] tiktoken load failed: {e} -> char-heuristic fallback", file=sys.stderr)
        return None


def count_tokens_tiktoken(enc, text: str) -> int:
    return len(enc.encode(text))


def count_tokens_heuristic(text: str) -> int:
    ascii_ct = 0
    cjk_ct = 0
    other_ct = 0
    for ch in text:
        code = ord(ch)
        if code < 128:
            ascii_ct += 1
        # CJK Unified Ideographs, Hiragana, Katakana, Hangul の主要ブロック
        elif 0x3040 <= code <= 0x30FF or 0x3400 <= code <= 0x9FFF or 0xAC00 <= code <= 0xD7AF or 0xF900 <= code <= 0xFAFF:
            cjk_ct += 1
        else:
            other_ct += 1
    return int(ascii_ct / 4 + cjk_ct * 1.0 + other_ct / 2)


def build_prompt(theme_dir: Path, kind: str) -> str:
    prompt_md = (theme_dir / "PROMPT.md").read_text(encoding="utf-8")
    if kind == "json":
        input_md_path = theme_dir / "input.md"
        input_md = input_md_path.read_text(encoding="utf-8") if input_md_path.exists() else ""
        # gen-questions.py の build_prompt と同じ組み立て
        prompt_md = prompt_md.replace(INPUT_PLACEHOLDER, "")
        return f"{prompt_md.strip()}\n\n{input_md.strip()}{JSON_PROMPT_SUFFIX}"
    return prompt_md.strip()


def detect_kind(model_dir: Path) -> str | None:
    if (model_dir / "output.json").exists():
        return "json"
    if (model_dir / "index.html").exists():
        return "html"
    return None


def completion_text(model_dir: Path, kind: str) -> str:
    if kind == "json":
        return (model_dir / "output.json").read_text(encoding="utf-8")
    return (model_dir / "index.html").read_text(encoding="utf-8")


def compute_cost_usd(prompt_tokens: int, completion_tokens: int, pricing: dict) -> float:
    return round(
        prompt_tokens * pricing["prompt_usd_per_mtok"] / 1_000_000
        + completion_tokens * pricing["completion_usd_per_mtok"] / 1_000_000,
        6,
    )


def load_run(model_dir: Path) -> dict[str, Any] | None:
    p = model_dir / "run.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def is_estimated(run: dict) -> bool:
    """estimated: false (実測 usage あり) なら再推定しない。"""
    usage = run.get("usage") or {}
    return usage.get("estimated", True) is not False


def iter_entries(theme_filter: str | None, model_filter: str | None):
    for theme_dir in sorted(PUBLIC.iterdir()):
        if not theme_dir.is_dir():
            continue
        if theme_filter and theme_dir.name != theme_filter:
            continue
        if not (theme_dir / "PROMPT.md").exists():
            continue
        for model_dir in sorted(theme_dir.iterdir()):
            if not model_dir.is_dir():
                continue
            if model_filter and model_dir.name != model_filter:
                continue
            kind = detect_kind(model_dir)
            if kind is None:
                continue
            yield theme_dir, model_dir, kind


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--theme")
    ap.add_argument("--model")
    ap.add_argument("--write", action="store_true", help="run.json の usage/cost セクションを更新")
    args = ap.parse_args()

    if not PRICING_PATH.exists():
        print(f"[ERROR] {PRICING_PATH} not found. Run fetch-pricing.py first.", file=sys.stderr)
        return 1

    pricing_all = json.loads(PRICING_PATH.read_text(encoding="utf-8"))
    enc = load_encoder()
    method = "tiktoken-o200k_base-proxy" if enc else "char-heuristic-v1"

    rows: list[tuple[str, str, int, int, float | None, str]] = []
    entries = list(iter_entries(args.theme, args.model))
    if not entries:
        print("[ERROR] no matching entries", file=sys.stderr)
        return 1

    for theme_dir, model_dir, kind in entries:
        theme = theme_dir.name
        model = model_dir.name

        # 既存 run.json が実測値を持っていたらスキップ
        existing = load_run(model_dir)
        if existing and not is_estimated(existing):
            usage = existing.get("usage") or {}
            cost = existing.get("cost") or {}
            rows.append((
                theme, model,
                int(usage.get("prompt_tokens", 0)),
                int(usage.get("completion_tokens", 0)),
                cost.get("usd") if isinstance(cost.get("usd"), (int, float)) else None,
                "measured (skipped)",
            ))
            continue

        prompt_text = build_prompt(theme_dir, kind)
        comp_text = completion_text(model_dir, kind)

        if enc:
            p_tok = count_tokens_tiktoken(enc, prompt_text)
            c_tok = count_tokens_tiktoken(enc, comp_text)
        else:
            p_tok = count_tokens_heuristic(prompt_text)
            c_tok = count_tokens_heuristic(comp_text)

        pricing = pricing_all.get(model)
        usd: float | None = None
        note = method
        if pricing:
            usd = compute_cost_usd(p_tok, c_tok, pricing)
        else:
            note = f"{method} (no pricing: local-only)"

        rows.append((theme, model, p_tok, c_tok, usd, note))

        if args.write:
            _write_run(model_dir, theme, model, kind, p_tok, c_tok, usd, pricing, method)

    # 表出力 (stdout = 機械可読タブ区切り、stderr = 人間向けヘッダ)
    print("theme\tmodel\tprompt_tok\tcompletion_tok\tusd\tnote")
    for theme, model, p, c, usd, note in rows:
        usd_str = f"{usd:.4f}" if isinstance(usd, (int, float)) else "-"
        print(f"{theme}\t{model}\t{p}\t{c}\t{usd_str}\t{note}")

    # サマリ
    with_cost = [r for r in rows if isinstance(r[4], (int, float))]
    if with_cost:
        total = sum(r[4] for r in with_cost)
        print(f"\n# {len(rows)} entries, total estimated: ${total:.4f}", file=sys.stderr)
    return 0


def _write_run(
    model_dir: Path,
    theme: str,
    model: str,
    kind: str,
    p_tok: int,
    c_tok: int,
    usd: float | None,
    pricing: dict | None,
    method: str,
) -> None:
    """既存 run.json の usage/cost のみ差し替える。他フィールドは backfill-runs.py が担当。
    run.json 不在時はスケルトンを作る (schema_version=1、他フィールドは 'unknown')。"""
    run_path = model_dir / "run.json"
    if run_path.exists():
        run = json.loads(run_path.read_text(encoding="utf-8"))
    else:
        run = {
            "schema_version": 1,
            "theme": theme,
            "model": model,
            "model_id": model,
            "harness": "unknown",
            "reasoning_effort": "unknown",
            "attempts": 1,
            "generated_at": None,
            "generated_at_source": "unknown",
            "sampling": {"temperature": "default", "max_tokens": "default", "top_p": "default"},
            "system_prompt": "unknown",
            "post_processing": "none",
            "runtime": None,
        }

    run["usage"] = {
        "estimated": True,
        "method": method,
        "prompt_tokens": p_tok,
        "completion_tokens": c_tok,
        "note": "reasoning トークン・ハーネス側 system prompt を含まない下限値",
    }
    if pricing:
        run["cost"] = {
            "estimated": True,
            "usd": usd,
            "actual_usd": None,
            "prompt_usd_per_mtok": pricing["prompt_usd_per_mtok"],
            "completion_usd_per_mtok": pricing["completion_usd_per_mtok"],
            "pricing_source": pricing["pricing_source"],
            "pricing_model": pricing["pricing_model"],
            "pricing_fetched_at": pricing["pricing_fetched_at"],
        }
    else:
        # ローカル専用 (gemma-4-12b-qat)。actual_usd=0, usd=null。参考単価なし
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
    run_path.write_text(json.dumps(run, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
