#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""public/<theme>/<model>/run.json を集約して public/runs.json に書き出す。

index.html は 1 回だけ fetch すればカード全件のメタが揃うようにする。

キー形式: "<theme>/<model>" (index.html 側で `RUNS[theme + '/' + model]` で引ける)。

Exit: 0 成功
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
OUT = PUBLIC / "runs.json"


def main() -> int:
    runs: dict[str, dict] = {}
    for theme_dir in sorted(PUBLIC.iterdir()):
        if not theme_dir.is_dir():
            continue
        for model_dir in sorted(theme_dir.iterdir()):
            if not model_dir.is_dir():
                continue
            run_path = model_dir / "run.json"
            if not run_path.exists():
                continue
            data = json.loads(run_path.read_text(encoding="utf-8"))
            key = f"{theme_dir.name}/{model_dir.name}"
            runs[key] = data

    OUT.write_text(json.dumps(runs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(runs)} entries)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
