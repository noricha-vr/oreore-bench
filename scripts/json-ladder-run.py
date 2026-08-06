#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Run all five json-ladder levels through OpenRouter as independent requests.

Each level gets the frozen common prompt, its own level instruction, and the
shared input. No published files are created until every response has valid
measured usage and was not truncated.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
THEME = "json-ladder"
LEVEL_NUMBERS = (1, 2, 3, 4, 5)
LEVEL_PLACEHOLDER = "[levels/l<N>.md の設問をここに展開する]"
INPUT_PLACEHOLDER = "[input.md の本文をここに展開してプロンプトに含める]"


def load_openrouter_helpers() -> Any:
    """Load OpenRouter request and metadata helpers without copying their logic."""
    path = ROOT / "scripts" / "openrouter-run.py"
    spec = importlib.util.spec_from_file_location("json_ladder_openrouter", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load OpenRouter helpers: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_mlx_helpers() -> Any:
    """Load loopback MLX helpers without duplicating local API safeguards."""
    path = ROOT / "scripts" / "mlx-lm-run.py"
    spec = importlib.util.spec_from_file_location("json_ladder_mlx", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load MLX helpers: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


OPENROUTER = load_openrouter_helpers()
LOCAL = load_mlx_helpers()

# importlib 経由の再利用は依存シンボルが暗黙になるため、起動時に契約を検証して
# ヘルパー側の将来変更（リネーム・削除）を実行前に検出する
_REQUIRED_OPENROUTER = (
    "DEFAULT_MAX_TOKENS", "JSON_PROMPT_SUFFIX", "NAME_RE", "OpenRouterError",
    "TruncatedOutputError", "UsageMissingError", "build_run_json", "call_openrouter",
    "check_not_truncated", "load_api_key", "load_pricing", "read_usage",
    "resolve_api_url", "resolve_model_id",
)
_REQUIRED_LOCAL = (
    "DEFAULT_BASE_URL", "DEFAULT_TIMEOUT_SECONDS", "MlxApiError", "UsageMissingError",
    "build_local_cost", "call_model", "preflight", "resolve_base_url",
)
for _module, _names in ((OPENROUTER, _REQUIRED_OPENROUTER), (LOCAL, _REQUIRED_LOCAL)):
    _missing = [n for n in _names if not hasattr(_module, n)]
    if _missing:
        raise RuntimeError(f"{_module.__name__}: missing required helpers: {_missing}")


def build_level_prompt(theme_dir: Path, level: int) -> str:
    """Build one frozen json-ladder request with level and input substitutions."""
    template = (theme_dir / "PROMPT.md").read_text(encoding="utf-8")
    level_text = (theme_dir / "levels" / f"l{level}.md").read_text(encoding="utf-8")
    input_text = (theme_dir / "input.md").read_text(encoding="utf-8")
    if template.count(LEVEL_PLACEHOLDER) != 1 or template.count(INPUT_PLACEHOLDER) != 1:
        raise ValueError("PROMPT.md must contain each json-ladder placeholder exactly once")
    prompt = template.replace(LEVEL_PLACEHOLDER, level_text.strip())
    prompt = prompt.replace(INPUT_PLACEHOLDER, input_text.strip())
    return f"{prompt.strip()}{OPENROUTER.JSON_PROMPT_SUFFIX}"


def validate_theme_dir() -> Path:
    """Return the complete frozen json-ladder source directory."""
    theme_dir = PUBLIC / THEME
    required = [theme_dir / "PROMPT.md", theme_dir / "input.md"]
    required.extend(theme_dir / "levels" / f"l{level}.md" for level in LEVEL_NUMBERS)
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"json-ladder source files are missing: {', '.join(missing)}")
    return theme_dir


def previous_attempts(out_dir: Path, overwrite: bool) -> int:
    """Reject existing output unless overwrite can safely increment its attempts."""
    if not out_dir.exists():
        return 1
    if not overwrite:
        raise FileExistsError(f"already exists: {out_dir}; pass --overwrite to regenerate")
    run_path = out_dir / "run.json"
    try:
        previous = json.loads(run_path.read_text(encoding="utf-8"))
        attempts = previous["attempts"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot determine prior attempts from {run_path}") from exc
    if type(attempts) is not int or attempts < 1:
        raise ValueError(f"invalid prior attempts in {run_path}")
    return attempts + 1


def response_content(body: dict[str, Any], level: int) -> tuple[str, str]:
    """Return a nonempty raw response and finish reason for one level."""
    choice = (body.get("choices") or [{}])[0]
    message = choice.get("message") if isinstance(choice, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise OPENROUTER.OpenRouterError(f"level {level}: model returned empty content")
    finish_reason = choice.get("finish_reason")
    return content, finish_reason if isinstance(finish_reason, str) else "unknown"


def run_levels(
    api_key: str,
    model_id: str,
    theme_dir: Path,
    reasoning_effort: str,
    max_tokens: int,
) -> tuple[list[dict[str, Any]], int, int, int, float]:
    """Make five sequential requests and aggregate their measured accounting."""
    levels: list[dict[str, Any]] = []
    prompt_total = completion_total = reasoning_total = 0
    actual_cost_total = 0.0
    for level in LEVEL_NUMBERS:
        prompt = build_level_prompt(theme_dir, level)
        body = OPENROUTER.call_openrouter(api_key, model_id, prompt, reasoning_effort, max_tokens)
        OPENROUTER.check_not_truncated(body, f"{THEME}/l{level}")
        content, finish_reason = response_content(body, level)
        prompt_tokens, completion_tokens, reasoning_tokens, actual_cost = OPENROUTER.read_usage(
            body, f"{THEME}/l{level}"
        )
        levels.append(
            {
                "level": level,
                "raw": content,
                "finish_reason": finish_reason,
                "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
            }
        )
        prompt_total += prompt_tokens
        completion_total += completion_tokens
        reasoning_total += reasoning_tokens
        actual_cost_total += actual_cost or 0.0
    return levels, prompt_total, completion_total, reasoning_total, actual_cost_total


def run_local_levels(
    model: str, theme_dir: Path, base_url: str, max_tokens: int
) -> tuple[list[dict[str, Any]], int, int]:
    """Make five sequential loopback requests without rejecting length responses."""
    levels: list[dict[str, Any]] = []
    prompt_total = completion_total = 0
    for level in LEVEL_NUMBERS:
        content, finish_reason, prompt_tokens, completion_tokens, _elapsed = LOCAL.call_model(
            model,
            build_level_prompt(theme_dir, level),
            base_url,
            max_tokens,
            LOCAL.DEFAULT_TIMEOUT_SECONDS,
        )
        levels.append(
            {
                "level": level,
                "raw": content,
                "finish_reason": finish_reason,
                "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
            }
        )
        prompt_total += prompt_tokens
        completion_total += completion_tokens
    return levels, prompt_total, completion_total


def build_output(levels: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the json-ladder format consumed by validate-json-ladder.mjs."""
    return {"schema_version": 1, "theme": THEME, "levels": levels}


def build_run(
    model: str,
    model_id: str,
    reasoning_effort: str,
    max_tokens: int,
    attempts: int,
    prompt_tokens: int,
    completion_tokens: int,
    reasoning_tokens: int,
    pricing: dict[str, Any],
) -> dict[str, Any]:
    """Build validator-compatible aggregate metadata for all five requests."""
    run = OPENROUTER.build_run_json(
        theme=THEME,
        model_slug=model,
        model_id=model_id,
        reasoning_effort=reasoning_effort,
        max_tokens=max_tokens,
        attempts=attempts,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        reasoning_tokens=reasoning_tokens,
        pricing=pricing,
        post_processing="json-ladder-5-levels",
    )
    reasoning_note = (
        f"completion に reasoning {reasoning_tokens} tokens を含む"
        if reasoning_tokens
        else "reasoning トークンの内訳は API 未提供"
    )
    run["usage"]["note"] = f"OpenRouter API 実測。5段階を独立リクエストで合算。{reasoning_note}"
    return run


def build_local_run(
    model: str, max_tokens: int, attempts: int, prompt_tokens: int, completion_tokens: int
) -> dict[str, Any]:
    """Build validator-compatible aggregate metadata for local inference."""
    return {
        "schema_version": 1,
        "theme": THEME,
        "model": model,
        "model_id": model,
        "harness": "mlx-lm-api",
        "reasoning_effort": "unknown",
        "attempts": attempts,
        "generated_at": None,
        "generated_at_source": "unknown",
        "sampling": {"temperature": 0.3, "max_tokens": max_tokens, "top_p": "default"},
        "system_prompt": "none",
        "post_processing": "json-ladder-5-levels",
        "runtime": {"engine": "mlx-lm", "api": "openai-compat-chat"},
        "usage": {
            "estimated": False,
            "method": "api-usage",
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "note": "ローカル MLX API 実測。5段階を独立リクエストで合算。",
        },
        "cost": LOCAL.build_local_cost(),
    }


def write_atomically(out_dir: Path, levels: list[dict[str, Any]], run: dict[str, Any]) -> None:
    """Publish raw responses, aggregate output, and metadata as one directory."""
    temp_dir = Path(tempfile.mkdtemp(prefix=f".{out_dir.name}.tmp-", dir=out_dir.parent))
    try:
        for level in levels:
            (temp_dir / f"raw-l{level['level']}.txt").write_text(level["raw"], encoding="utf-8")
        (temp_dir / "output.json").write_text(
            json.dumps(build_output(levels), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (temp_dir / "run.json").write_text(
            json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if not out_dir.exists():
            temp_dir.rename(out_dir)
            return
        backup_dir = out_dir.with_name(f".{out_dir.name}.previous-{uuid.uuid4().hex}")
        out_dir.rename(backup_dir)
        try:
            temp_dir.rename(out_dir)
        except Exception:
            backup_dir.rename(out_dir)
            raise
        shutil.rmtree(backup_dir)
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def parse_args() -> argparse.Namespace:
    """Parse the dedicated OpenRouter runner options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="model-map.json の API model slug")
    parser.add_argument("--backend", required=True, choices=["openrouter", "local"])
    parser.add_argument(
        "--reasoning-effort", default="high", choices=["none", "low", "medium", "high"]
    )
    parser.add_argument("--max-tokens", type=int, default=OPENROUTER.DEFAULT_MAX_TOKENS)
    parser.add_argument(
        "--base-url",
        default=LOCAL.DEFAULT_BASE_URL,
        help="local backend の loopback OpenAI-compatible API base URL",
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="complete existing result を原子的に置換する"
    )
    parser.add_argument("--dry-run", action="store_true", help="API 呼び出し・書き込みなしで前提を検証する")
    return parser.parse_args()


def prepare_run(args: argparse.Namespace) -> tuple[Path, Path, int, str | None]:
    """Validate common inputs and resolve the target before requests start."""
    if not OPENROUTER.NAME_RE.fullmatch(args.model):
        raise ValueError(
            f"--model must match {OPENROUTER.NAME_RE.pattern}; it is used as a directory name"
        )
    if args.max_tokens <= 0:
        raise ValueError("--max-tokens must be greater than zero")
    theme_dir = validate_theme_dir()
    out_dir = theme_dir / args.model
    attempts = previous_attempts(out_dir, args.overwrite)
    base_url = LOCAL.resolve_base_url(args.base_url) if args.backend == "local" else None
    return theme_dir, out_dir, attempts, base_url


def run_openrouter_backend(
    args: argparse.Namespace, theme_dir: Path, attempts: int
) -> tuple[list[dict[str, Any]], dict[str, Any], float]:
    """Generate all levels through OpenRouter and aggregate their metadata."""
    model_id = OPENROUTER.resolve_model_id(args.model)
    pricing = OPENROUTER.load_pricing(args.model)
    api_key = OPENROUTER.load_api_key()
    OPENROUTER.resolve_api_url()
    levels, prompt_tokens, completion_tokens, reasoning_tokens, actual_cost = run_levels(
        api_key, model_id, theme_dir, args.reasoning_effort, args.max_tokens
    )
    run = build_run(
        args.model, model_id, args.reasoning_effort, args.max_tokens, attempts,
        prompt_tokens, completion_tokens, reasoning_tokens, pricing,
    )
    return levels, run, actual_cost


def run_local_backend(
    args: argparse.Namespace, theme_dir: Path, attempts: int, base_url: str
) -> tuple[list[dict[str, Any]], dict[str, Any], float]:
    """Generate all levels through the loopback MLX endpoint."""
    LOCAL.preflight(base_url, LOCAL.DEFAULT_TIMEOUT_SECONDS)
    levels, prompt_tokens, completion_tokens = run_local_levels(
        args.model, theme_dir, base_url, args.max_tokens
    )
    run = build_local_run(args.model, args.max_tokens, attempts, prompt_tokens, completion_tokens)
    return levels, run, 0.0


def main() -> int:
    """Run json-ladder and publish only a complete five-level result."""
    args = parse_args()
    try:
        theme_dir, out_dir, attempts, base_url = prepare_run(args)
        if args.dry_run:
            print(
                f"[dry-run] json-ladder/{args.model} backend={args.backend}: "
                "five requests would be sent; no files written",
                file=sys.stderr,
            )
            return 0
        if args.backend == "openrouter":
            levels, run, actual_cost = run_openrouter_backend(args, theme_dir, attempts)
        else:
            assert base_url is not None
            levels, run, actual_cost = run_local_backend(args, theme_dir, attempts, base_url)
        write_atomically(out_dir, levels, run)
    except (
        OPENROUTER.OpenRouterError,
        OPENROUTER.TruncatedOutputError,
        OPENROUTER.UsageMissingError,
        LOCAL.MlxApiError,
        LOCAL.UsageMissingError,
    ) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    except (OSError, RuntimeError, ValueError, FileExistsError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    print(
        f"[ok] wrote {out_dir} (5 levels, prompt={run['usage']['prompt_tokens']}, "
        f"completion={run['usage']['completion_tokens']}, "
        f"openrouter_reported=${actual_cost:.6f})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
