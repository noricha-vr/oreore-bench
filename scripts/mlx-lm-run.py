#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Generate benchmark artifacts through a loopback-only mlx_lm.server API.

The runner writes a response and its measured run.json to a hidden directory,
then atomically renames that directory into public/<theme>/<model>.  It never
sends credentials and deliberately keeps the API model identifier out of the
published metadata, so a local absolute model path cannot leak into run.json.
"""
from __future__ import annotations

import argparse
import importlib.util
import ipaddress
import json
import re
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runaway_detector import THRESHOLD as DEFAULT_RUNAWAY_THRESHOLD  # noqa: E402
from runaway_detector import RunawayDetector, RunawayVerdict  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
DEFAULT_BASE_URL = "http://127.0.0.1:18081/v1"
DEFAULT_MAX_TOKENS = 65000
DEFAULT_TIMEOUT_SECONDS = 3600
NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
PUBLIC_MODEL_ID_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$"
)
RUNTIME_VALUE_RE = re.compile(r"^[A-Za-z0-9._ ()-]{1,40}$")


class MlxApiError(RuntimeError):
    """Represent a failed or malformed mlx_lm.server API response."""


class UsageMissingError(MlxApiError):
    """Represent a response that cannot support measured benchmark metadata."""


class RunawayDetected(MlxApiError):
    """Represent a generation aborted because it began repeating itself."""

    def __init__(self, verdict: RunawayVerdict) -> None:
        super().__init__(verdict.describe())
        self.verdict = verdict


class RejectRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject every HTTP redirect instead of issuing a second request."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        """Return no redirected request so urllib raises the original HTTP error."""
        return None


def build_http_opener() -> urllib.request.OpenerDirector:
    """Build a redirect- and proxy-free opener for trusted loopback requests."""
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        RejectRedirectHandler(),
    )


HTTP_OPENER = build_http_opener()


def load_prompt_helpers() -> Any:
    """Load the canonical theme prompt builder without duplicating JSON rules."""
    path = ROOT / "scripts" / "openrouter-run.py"
    spec = importlib.util.spec_from_file_location("openrouter_prompt_helpers", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load prompt helpers: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PROMPTS = load_prompt_helpers()


def resolve_base_url(raw_url: str) -> str:
    """Accept an HTTP base URL only when its host is a loopback IP literal."""
    parsed = urllib.parse.urlparse(raw_url.strip())
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("--base-url must not include credentials, query, or fragment")
    try:
        host = ipaddress.ip_address(parsed.hostname or "")
    except ValueError as exc:
        raise ValueError("--base-url must use http on a loopback IP literal") from exc
    if parsed.scheme != "http" or not host.is_loopback:
        raise ValueError("--base-url must use http on a loopback IP literal")
    path = parsed.path.rstrip("/")
    if not path:
        path = "/v1"
    return urllib.parse.urlunparse(("http", parsed.netloc, path, "", "", ""))


def endpoint(base_url: str, suffix: str) -> str:
    """Build an API endpoint from a validated base URL."""
    return f"{base_url.rstrip('/')}/{suffix.lstrip('/')}"


def request_json(url: str, timeout: int, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Send one JSON request without authentication and require an object response."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with HTTP_OPENER.open(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise MlxApiError(f"HTTP {exc.code} from mlx_lm.server") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise MlxApiError(f"network error calling mlx_lm.server: {exc}") from exc
    try:
        body = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MlxApiError("mlx_lm.server returned invalid JSON") from exc
    if not isinstance(body, dict):
        raise MlxApiError("mlx_lm.server response must be a JSON object")
    if body.get("error"):
        raise MlxApiError("mlx_lm.server returned an error response")
    return body


def parse_sse_chunk(line: bytes) -> dict[str, Any] | None:
    """Return one decoded SSE data payload, or None for keepalives and the terminator."""
    text = line.decode("utf-8", errors="replace").strip()
    if not text.startswith("data:"):
        return None
    payload = text[len("data:") :].strip()
    if not payload or payload == "[DONE]":
        return None
    try:
        chunk = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise MlxApiError("mlx_lm.server sent an invalid SSE chunk") from exc
    if not isinstance(chunk, dict):
        raise MlxApiError("mlx_lm.server SSE chunk must be a JSON object")
    if chunk.get("error"):
        raise MlxApiError("mlx_lm.server returned an error response")
    return chunk


def read_stream_delta(chunk: dict[str, Any]) -> tuple[str, str | None]:
    """Return the text delta and any finish_reason carried by one SSE chunk."""
    choices = chunk.get("choices")
    if not isinstance(choices, list) or not choices:
        return "", None
    choice = choices[0]
    if not isinstance(choice, dict):
        return "", None
    delta = choice.get("delta")
    content = delta.get("content") if isinstance(delta, dict) else None
    finish_reason = choice.get("finish_reason")
    return (
        content if isinstance(content, str) else "",
        finish_reason if isinstance(finish_reason, str) and finish_reason else None,
    )


def stream_completion(
    url: str,
    timeout: int,
    payload: dict[str, Any],
    detector: RunawayDetector | None,
) -> tuple[str, str, int, int]:
    """Stream one completion, aborting the connection as soon as it starts repeating.

    Streaming exists for the abort: a non-streamed request hides the generation
    until it finishes, so a runaway can only be observed after it has already
    burned the whole token budget.
    """
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
    request = urllib.request.Request(url, data=data, headers=headers)
    finish_reason: str | None = None
    usage: dict[str, Any] | None = None
    parts: list[str] = []
    try:
        with HTTP_OPENER.open(request, timeout=timeout) as response:
            for line in response:
                chunk = parse_sse_chunk(line)
                if chunk is None:
                    continue
                if isinstance(chunk.get("usage"), dict):
                    usage = chunk["usage"]
                content, reason = read_stream_delta(chunk)
                if reason is not None:
                    finish_reason = reason
                if not content:
                    continue
                parts.append(content)
                if detector is None:
                    continue
                verdict = detector.feed(content)
                if verdict is not None:
                    response.close()
                    raise RunawayDetected(verdict)
    except urllib.error.HTTPError as exc:
        raise MlxApiError(f"HTTP {exc.code} from mlx_lm.server") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise MlxApiError(f"network error calling mlx_lm.server: {exc}") from exc
    content = "".join(parts)
    if not content:
        raise MlxApiError("chat completion stream produced no content")
    if finish_reason is None:
        raise MlxApiError("chat completion stream has no finish_reason")
    if not isinstance(usage, dict):
        raise UsageMissingError("chat completion stream has no usage object")
    prompt_tokens = usage.get("prompt_tokens")
    completion_tokens = usage.get("completion_tokens")
    if type(prompt_tokens) is not int or type(completion_tokens) is not int:
        raise UsageMissingError("usage token counts must be integers")
    if prompt_tokens <= 0 or completion_tokens <= 0:
        raise UsageMissingError("usage token counts must both be greater than zero")
    return content, finish_reason, prompt_tokens, completion_tokens


def preflight(base_url: str, timeout: int) -> None:
    """Confirm that the configured endpoint is a responding mlx_lm.server API."""
    body = request_json(endpoint(base_url, "models"), timeout)
    if not isinstance(body.get("data"), list):
        raise MlxApiError("/v1/models response has no data list")


def read_response(body: dict[str, Any]) -> tuple[str, str, int, int]:
    """Return raw content and measured tokens from a valid chat completion body."""
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise MlxApiError("chat completion response has no choices")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise MlxApiError("chat completion choice has no message")
    content = message.get("content")
    if not isinstance(content, str) or not content:
        raise MlxApiError("chat completion response has null or empty content")
    finish_reason = choices[0].get("finish_reason")
    if not isinstance(finish_reason, str) or not finish_reason:
        raise MlxApiError("chat completion response has no finish_reason")
    usage = body.get("usage")
    if not isinstance(usage, dict):
        raise UsageMissingError("chat completion response has no usage object")
    prompt_tokens = usage.get("prompt_tokens")
    completion_tokens = usage.get("completion_tokens")
    if type(prompt_tokens) is not int or type(completion_tokens) is not int:
        raise UsageMissingError("usage token counts must be integers")
    if prompt_tokens <= 0 or completion_tokens <= 0:
        raise UsageMissingError("usage token counts must both be greater than zero")
    return content, finish_reason, prompt_tokens, completion_tokens


def build_usage(
    prompt_tokens: int,
    completion_tokens: int,
    finish_reason: str,
    elapsed_seconds: float,
) -> dict[str, Any]:
    """Build measured API usage metadata for one generation."""
    note = (
        "mlx_lm.server applied the model chat template; "
        f"finish_reason={finish_reason}; elapsed_seconds={elapsed_seconds:.3f}."
    )
    return {
        "estimated": False,
        "method": "api-usage",
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "note": note,
    }


def build_local_cost() -> dict[str, Any]:
    """Build the no-charge local inference cost block."""
    return {
        "estimated": True,
        "usd": None,
        "actual_usd": 0,
        "prompt_usd_per_mtok": None,
        "completion_usd_per_mtok": None,
        "pricing_source": "local-no-reference",
        "pricing_model": None,
        "pricing_fetched_at": None,
    }


def build_run_json(
    *,
    theme: str,
    model: str,
    public_model_id: str,
    max_tokens: int,
    prompt_tokens: int,
    completion_tokens: int,
    finish_reason: str,
    elapsed_seconds: float,
    runtime: dict[str, str],
) -> dict[str, Any]:
    """Build schema-versioned metadata for one measured local API generation."""
    return {
        "schema_version": 1,
        "theme": theme,
        "model": model,
        "model_id": public_model_id,
        "harness": "mlx-lm-api",
        "reasoning_effort": "unknown",
        "attempts": 1,
        "generated_at": datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat(),
        "generated_at_source": "measured",
        "sampling": {"temperature": 0.3, "max_tokens": max_tokens, "top_p": "default"},
        "system_prompt": "none",
        "post_processing": "none",
        "runtime": runtime,
        "usage": build_usage(prompt_tokens, completion_tokens, finish_reason, elapsed_seconds),
        "cost": build_local_cost(),
    }


def validate_name(label: str, value: str) -> None:
    """Reject a path component that could escape its theme directory."""
    if value in {".", ".."} or not NAME_RE.fullmatch(value):
        raise ValueError(f"{label} must match {NAME_RE.pattern}; it is used as a directory name")


def validate_public_model_id(value: str) -> None:
    """Require a public registry identifier with exactly one owner/name pair."""
    if not PUBLIC_MODEL_ID_RE.fullmatch(value):
        raise ValueError("--public-model-id must use the public registry form owner/name")


def validate_runtime(runtime: dict[str, str]) -> None:
    """Keep user-provided runtime metadata compatible with the public schema."""
    for key, value in runtime.items():
        if not RUNTIME_VALUE_RE.fullmatch(value):
            raise ValueError(f"--{key.replace('_', '-')} must be a safe value up to 40 characters")


def select_themes(theme: str) -> list[str]:
    """Expand ``all`` into every benchmark theme that has a PROMPT.md file."""
    if theme != "all":
        return [theme]
    themes: list[str] = []
    for path in sorted(PUBLIC.iterdir()):
        if path.is_symlink() or not path.is_dir() or not (path / "PROMPT.md").is_file():
            continue
        if (path / "levels").is_dir():
            print(
                f"[skip] {path.name}: json-levels uses scripts/json-ladder-run.py",
                file=sys.stderr,
            )
            continue
        themes.append(path.name)
    return themes


def resolve_theme_dir(theme: str) -> Path:
    """Resolve a real direct child directory under PUBLIC without following symlinks."""
    validate_name("--theme", theme)
    public_dir = PUBLIC.resolve(strict=True)
    theme_dir = PUBLIC / theme
    if theme_dir.is_symlink():
        raise ValueError(f"theme must not be a symlink: {theme_dir}")
    try:
        resolved = theme_dir.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ValueError(f"theme not found: {theme_dir}") from exc
    if not resolved.is_dir() or resolved.parent != public_dir:
        raise ValueError(f"theme must be a real directory directly under {PUBLIC}: {theme_dir}")
    return resolved


def load_resume_run(out_dir: Path, output_name: str) -> tuple[dict[str, Any], Path]:
    """Load resume metadata only when both stored files are real and nonempty."""
    artifact = out_dir / output_name
    run_path = out_dir / "run.json"
    if artifact.is_symlink() or not artifact.is_file() or artifact.stat().st_size <= 0:
        raise ValueError(f"resume output is missing or empty: {artifact}")
    if run_path.is_symlink() or not run_path.is_file():
        raise ValueError(f"resume metadata is missing: {run_path}")
    try:
        run = json.loads(run_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"resume metadata is not valid JSON: {run_path}") from exc
    if not isinstance(run, dict):
        raise ValueError(f"resume metadata must be an object: {run_path}")
    return run, run_path


def validate_resume_identity(
    run: dict[str, Any],
    run_path: Path,
    theme: str,
    model: str,
    public_model_id: str,
) -> None:
    """Validate that resume metadata identifies this exact runner invocation."""
    expected = {
        "schema_version": 1,
        "theme": theme,
        "model": model,
        "harness": "mlx-lm-api",
        "reasoning_effort": "unknown",
        "attempts": 1,
        "generated_at_source": "measured",
        "system_prompt": "none",
        "post_processing": "none",
    }
    if any(type(run.get(key)) is not type(value) or run.get(key) != value for key, value in expected.items()):
        raise ValueError(f"resume metadata does not match this run: {run_path}")
    if not isinstance(run.get("generated_at"), str) or not run["generated_at"]:
        raise ValueError(f"resume metadata has no measured generation time: {run_path}")
    if run.get("model_id") != public_model_id or not PUBLIC_MODEL_ID_RE.fullmatch(public_model_id):
        raise ValueError(f"resume metadata has an invalid public model ID: {run_path}")


def validate_resume_sampling_usage(run: dict[str, Any], run_path: Path) -> None:
    """Validate measured sampling and positive non-boolean token counts."""
    sampling = run.get("sampling")
    if (
        not isinstance(sampling, dict)
        or type(sampling.get("temperature")) is not float
        or sampling.get("temperature") != 0.3
        or type(sampling.get("max_tokens")) is not int
        or sampling["max_tokens"] <= 0
        or sampling.get("top_p") != "default"
    ):
        raise ValueError(f"resume metadata has invalid sampling: {run_path}")
    usage = run.get("usage")
    if not isinstance(usage, dict) or usage.get("estimated") is not False or usage.get("method") != "api-usage":
        raise ValueError(f"resume metadata has invalid usage: {run_path}")
    for key in ("prompt_tokens", "completion_tokens"):
        if type(usage.get(key)) is not int or usage[key] <= 0:
            raise ValueError(f"resume metadata has invalid usage.{key}: {run_path}")


def validate_resume_runtime_cost(run: dict[str, Any], run_path: Path) -> None:
    """Validate local runtime identity and the no-charge cost block."""
    runtime = run.get("runtime")
    if not isinstance(runtime, dict) or runtime.get("engine") != "mlx-lm" or runtime.get("api") != "openai-compat-chat":
        raise ValueError(f"resume metadata has invalid runtime: {run_path}")
    for key in ("version", "framework", "model_revision", "quantization", "hardware"):
        if not isinstance(runtime.get(key), str) or not RUNTIME_VALUE_RE.fullmatch(runtime[key]):
            raise ValueError(f"resume metadata has invalid runtime.{key}: {run_path}")
    cost = run.get("cost")
    if (
        not isinstance(cost, dict)
        or cost.get("estimated") is not True
        or cost.get("usd") is not None
        or type(cost.get("actual_usd")) is not int
        or cost["actual_usd"] != 0
        or cost.get("prompt_usd_per_mtok") is not None
        or cost.get("completion_usd_per_mtok") is not None
        or cost.get("pricing_source") != "local-no-reference"
    ):
        raise ValueError(f"resume metadata has invalid local cost: {run_path}")


def validate_resume_output(
    out_dir: Path,
    output_name: str,
    theme: str,
    model: str,
    public_model_id: str,
) -> None:
    """Require a complete, matching prior MLX-LM result before resume skips it."""
    run, run_path = load_resume_run(out_dir, output_name)
    validate_resume_identity(run, run_path, theme, model, public_model_id)
    validate_resume_sampling_usage(run, run_path)
    validate_resume_runtime_cost(run, run_path)


def write_atomically(out_dir: Path, output_name: str, content: str, run: dict[str, Any]) -> None:
    """Publish a complete artifact directory atomically without overwriting a run."""
    if out_dir.exists():
        raise FileExistsError(f"already exists: {out_dir}")
    temp_dir = Path(tempfile.mkdtemp(prefix=f".{out_dir.name}.tmp-", dir=out_dir.parent))
    try:
        (temp_dir / output_name).write_text(content, encoding="utf-8")
        (temp_dir / "run.json").write_text(
            json.dumps(run, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        temp_dir.rename(out_dir)
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def build_theme_prompt(theme_dir: Path, kind: str) -> str:
    """Build a prompt while preserving HTML and sharing canonical JSON expansion."""
    if kind == "html":
        return (theme_dir / "PROMPT.md").read_text(encoding="utf-8")
    return PROMPTS.build_prompt(theme_dir, kind)


def call_model(
    api_model_id: str,
    prompt: str,
    base_url: str,
    max_tokens: int,
    timeout: int,
    runaway_threshold: float | None,
) -> tuple[str, str, int, int, float]:
    """Call the chat endpoint once and return validated content, usage, and elapsed time."""
    started = time.monotonic()
    detector = RunawayDetector(runaway_threshold) if runaway_threshold is not None else None
    content, finish_reason, prompt_tokens, completion_tokens = stream_completion(
        endpoint(base_url, "chat/completions"),
        timeout,
        {
            "model": api_model_id,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
        },
        detector,
    )
    elapsed_seconds = time.monotonic() - started
    return content, finish_reason, prompt_tokens, completion_tokens, elapsed_seconds


def run_theme(
    *,
    theme: str,
    model: str,
    api_model_id: str,
    public_model_id: str,
    base_url: str,
    max_tokens: int,
    timeout: int,
    runtime: dict[str, str],
    resume: bool,
    runaway_threshold: float | None,
) -> str:
    """Generate and publish one theme, or skip an already complete resumed run."""
    theme_dir = resolve_theme_dir(theme)
    if not (theme_dir / "PROMPT.md").is_file():
        raise ValueError(f"theme not found: {theme_dir / 'PROMPT.md'}")
    if (theme_dir / "levels").is_dir():
        raise ValueError(f"{theme}: json-levels uses scripts/json-ladder-run.py")
    out_dir = theme_dir / model
    kind = PROMPTS.detect_theme_kind(theme_dir)
    output_name = "output.json" if kind == "json" else "index.html"
    if out_dir.is_symlink():
        raise ValueError(f"model output must not be a symlink: {out_dir}")
    if out_dir.exists():
        if resume:
            validate_resume_output(out_dir, output_name, theme, model, public_model_id)
            return "skipped"
        raise FileExistsError(f"already exists: {out_dir}; use --resume only for a complete run")

    prompt = build_theme_prompt(theme_dir, kind)
    content, finish_reason, prompt_tokens, completion_tokens, elapsed_seconds = call_model(
        api_model_id, prompt, base_url, max_tokens, timeout, runaway_threshold
    )
    run = build_run_json(
        theme=theme,
        model=model,
        public_model_id=public_model_id,
        max_tokens=max_tokens,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        finish_reason=finish_reason,
        elapsed_seconds=elapsed_seconds,
        runtime=runtime,
    )
    write_atomically(out_dir, output_name, content, run)
    return "written"


def parse_args() -> argparse.Namespace:
    """Parse runner options while keeping local and public model identities distinct."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--theme", required=True, help="theme slug, or all")
    parser.add_argument("--model", required=True, help="public directory slug")
    parser.add_argument("--api-model-id", required=True, help="mlx_lm.server model ID; never published")
    parser.add_argument("--public-model-id", required=True, help="published non-local model identifier")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--resume", action="store_true", help="skip complete existing theme outputs")
    parser.add_argument(
        "--runaway-threshold",
        type=float,
        default=DEFAULT_RUNAWAY_THRESHOLD,
        help="abort a generation once its repetition score drops below this value",
    )
    parser.add_argument(
        "--no-runaway-check",
        action="store_true",
        help="let a repeating generation run to max_tokens instead of aborting it",
    )
    parser.add_argument("--version", default="unknown", help="safe mlx-lm version metadata")
    parser.add_argument("--framework", default="unknown", help="safe MLX version metadata")
    parser.add_argument("--model-revision", default="unknown", help="safe model revision metadata")
    parser.add_argument("--quantization", default="unknown", help="safe quantization metadata")
    parser.add_argument("--hardware", default="unknown", help="safe hardware metadata")
    return parser.parse_args()


def main() -> int:
    """Run the requested local benchmark themes once each, without retries."""
    args = parse_args()
    try:
        validate_name("--model", args.model)
        validate_public_model_id(args.public_model_id)
        if args.max_tokens <= 0 or args.timeout <= 0:
            raise ValueError("--max-tokens and --timeout must be greater than zero")
        runaway_threshold = None if args.no_runaway_check else args.runaway_threshold
        if runaway_threshold is not None and not 0.0 < runaway_threshold < 1.0:
            raise ValueError("--runaway-threshold must be between 0 and 1")
        base_url = resolve_base_url(args.base_url)
        runtime = {
            "engine": "mlx-lm",
            "version": args.version,
            "framework": args.framework,
            "model_revision": args.model_revision,
            "quantization": args.quantization,
            "hardware": args.hardware,
            "api": "openai-compat-chat",
        }
        validate_runtime(runtime)
        themes = select_themes(args.theme)
        if not themes:
            raise ValueError("no themes with PROMPT.md found")
        if args.theme != "all" and (PUBLIC / args.theme / "levels").is_dir():
            raise ValueError(f"{args.theme}: json-levels uses scripts/json-ladder-run.py")
        preflight(base_url, args.timeout)
        for theme in themes:
            result = run_theme(
                theme=theme,
                model=args.model,
                api_model_id=args.api_model_id,
                public_model_id=args.public_model_id,
                base_url=base_url,
                max_tokens=args.max_tokens,
                timeout=args.timeout,
                runtime=runtime,
                resume=args.resume,
                runaway_threshold=runaway_threshold,
            )
            print(f"[ok] {theme}/{args.model}: {result}", file=sys.stderr)
    except (MlxApiError, UsageMissingError, ValueError, FileExistsError, OSError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
