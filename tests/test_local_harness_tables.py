#!/usr/bin/env python3
"""Keep the duplicated local-harness tables and their public labels in sync.

LOCAL_HARNESSES lives in two runners, the harness enum lives in a JS validator,
and the display labels live in index.html.  A harness added to one place only is
silently invisible on the site, so these tests compare the four definitions
directly instead of trusting that an author updated all of them.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VALIDATE_RUNS = ROOT / "scripts" / "validate-runs.mjs"
INDEX_HTML = ROOT / "public" / "index.html"


def load_script(name: str, filename: str) -> Any:
    """Load a hyphenated script by its path."""
    path = ROOT / "scripts" / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def harness_runtime(table: dict[str, dict[str, Any]]) -> dict[str, tuple[str, str]]:
    """Reduce either table shape to harness -> (engine, api)."""
    reduced: dict[str, tuple[str, str]] = {}
    for harness, profile in table.items():
        runtime = profile.get("runtime", profile)
        reduced[harness] = (runtime["engine"], runtime["api"])
    return reduced


def js_string_keys(source: str, start: str, end: str) -> set[str]:
    """Collect the quoted keys or entries of one JS block."""
    block = source[source.index(start) : source.index(end, source.index(start))]
    return set(re.findall(r"['\"]([A-Za-z0-9._-]+)['\"]", block))


def js_object_keys(source: str, start: str, end: str) -> set[str]:
    """Collect the property names of one JS object literal, quoted or bare."""
    block = source[source.index(start) : source.index(end, source.index(start))]
    return set(re.findall(r"(?:^|[{,]\s*)['\"]?([A-Za-z0-9._-]+)['\"]?\s*:", block))


MLX_TABLE = harness_runtime(load_script("mlx_lm_run", "mlx-lm-run.py").LOCAL_HARNESSES)
LADDER_TABLE = harness_runtime(load_script("json_ladder_run", "json-ladder-run.py").LOCAL_HARNESSES)


def test_both_runners_agree_on_every_local_harness_runtime() -> None:
    """The two duplicated tables describe the same engine and api per harness."""
    assert MLX_TABLE == LADDER_TABLE


def test_local_harnesses_are_accepted_by_the_run_json_validator() -> None:
    """Every harness a runner can write passes validate-runs.mjs's enum."""
    enum = js_string_keys(VALIDATE_RUNS.read_text(encoding="utf-8"), "const HARNESS_ENUM", "]);")

    assert set(MLX_TABLE) <= enum
    assert set(LADDER_TABLE) <= enum


def test_local_harnesses_and_engines_are_labelled_on_the_site() -> None:
    """Every written harness and engine has a display label, so no card hides them."""
    source = INDEX_HTML.read_text(encoding="utf-8")
    harness_labels = js_object_keys(source, "const HARNESS_LABEL", "};")
    engine_labels = js_object_keys(source, "const RUNTIME_ENGINE_LABEL", "};")
    engines = {engine for engine, _api in {**MLX_TABLE, **LADDER_TABLE}.values()}

    assert set(MLX_TABLE) | set(LADDER_TABLE) <= harness_labels
    assert engines <= engine_labels
