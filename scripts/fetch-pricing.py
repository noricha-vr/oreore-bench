#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""OpenRouter API (認証不要) から model-map.json の単価を取得して pricing.json に保存する。

- 入力: scripts/model-map.json (slug -> OpenRouter ID)
- 出力: scripts/pricing.json (slug -> {prompt_usd_per_mtok, completion_usd_per_mtok, pricing_source, pricing_model, pricing_fetched_at})
- OpenRouter は per-token 単価 (USD) を返すので 1_000_000 倍して per-Mtok に換算する
- model_id が null の slug はスキップ (OpenRouter 未対応)

Exit: 0 成功 / 1 API 取得失敗 or 対象モデルが 1 つでも見つからず
"""
from __future__ import annotations
import json
import sys
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAP_PATH = ROOT / "model-map.json"
OUT_PATH = ROOT / "pricing.json"
API = "https://openrouter.ai/api/v1/models"


def fetch_models() -> dict[str, dict]:
    req = urllib.request.Request(API, headers={"User-Agent": "oreore-bench/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return {m["id"]: m for m in data.get("data", [])}


def main() -> int:
    model_map = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    try:
        models = fetch_models()
    except Exception as e:
        print(f"[ERROR] failed to fetch OpenRouter API: {e}", file=sys.stderr)
        return 1

    today = date.today().isoformat()
    out: dict[str, dict] = {}
    missing: list[str] = []
    for slug, entry in model_map.items():
        if slug.startswith("_"):
            continue
        # 後方互換: 旧形式 (str) と新形式 ({id, type}) の両対応
        if isinstance(entry, dict):
            model_id = entry.get("id")
        else:
            model_id = entry
        if model_id is None:
            print(f"[skip] {slug}: no OpenRouter model", file=sys.stderr)
            continue
        m = models.get(model_id)
        if not m:
            missing.append(f"{slug} -> {model_id}")
            continue
        pricing = m.get("pricing", {})
        p_prompt = pricing.get("prompt")
        p_comp = pricing.get("completion")
        if p_prompt is None or p_comp is None:
            missing.append(f"{slug} -> {model_id} (pricing missing)")
            continue
        # OpenRouter は per-token 単価 (USD)。per-Mtok にするため 1_000_000 倍。
        # 直積 (完了に prompt 単価を掛ける等) を防ぐため名前で明示。
        prompt_per_mtok = round(float(p_prompt) * 1_000_000, 6)
        completion_per_mtok = round(float(p_comp) * 1_000_000, 6)
        out[slug] = {
            "prompt_usd_per_mtok": prompt_per_mtok,
            "completion_usd_per_mtok": completion_per_mtok,
            "pricing_source": "openrouter",
            "pricing_model": model_id,
            "pricing_fetched_at": today,
        }
        print(
            f"[ok] {slug}: prompt=${prompt_per_mtok}/Mtok completion=${completion_per_mtok}/Mtok",
            file=sys.stderr,
        )

    if missing:
        print(f"[ERROR] missing on OpenRouter: {missing}", file=sys.stderr)
        return 1

    OUT_PATH.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
