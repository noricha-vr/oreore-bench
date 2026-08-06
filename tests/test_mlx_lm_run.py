#!/usr/bin/env python3
"""Exercise the loopback-only mlx_lm.server benchmark runner with fake HTTP."""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_runner() -> Any:
    """Load the hyphenated runner file as a Python module."""
    path = ROOT / "scripts" / "mlx-lm-run.py"
    spec = importlib.util.spec_from_file_location("mlx_lm_run", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load_runner()


class FakeResponse:
    """Represent one JSON response from the external HTTP boundary."""

    def __init__(self, body: object) -> None:
        self._raw = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def install_fake_http(monkeypatch: pytest.MonkeyPatch, bodies: list[object]) -> list[Any]:
    """Install deterministic fake HTTP responses and retain sent requests."""
    sent: list[Any] = []

    def fake_open(request: Any, timeout: int) -> FakeResponse:
        sent.append((request, timeout))
        body = bodies.pop(0)
        if isinstance(body, Exception):
            raise body
        return FakeResponse(body)

    monkeypatch.setattr(runner.HTTP_OPENER, "open", fake_open)
    return sent


def make_args(**overrides: object) -> argparse.Namespace:
    """Create complete CLI input for one local HTML benchmark."""
    values: dict[str, object] = {
        "theme": "demo",
        "model": "hy3-t512",
        "api_model_id": "/private/models/hy3-t512",
        "public_model_id": "example/Hy3-T512",
        "base_url": runner.DEFAULT_BASE_URL,
        "max_tokens": 65000,
        "timeout": 3600,
        "resume": False,
        "version": "0.31.3",
        "framework": "MLX 0.32.0",
        "model_revision": "abc123",
        "quantization": "t512",
        "hardware": "M3 Ultra",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def make_public(tmp_path: Path, theme: str = "demo") -> Path:
    """Create a minimal public tree containing one HTML benchmark theme."""
    public = tmp_path / "public"
    theme_dir = public / theme
    theme_dir.mkdir(parents=True)
    (theme_dir / "PROMPT.md").write_text("make it\n", encoding="utf-8")
    return public


def completion(content: str = "<html>ok</html>", finish_reason: str = "stop") -> dict[str, object]:
    """Build a valid OpenAI-compatible completion body."""
    return {
        "choices": [
            {
                "finish_reason": finish_reason,
                "message": {
                    "content": content,
                    "reasoning_content": "not an artifact",
                    "tool_calls": [{"id": "not-an-artifact"}],
                },
            }
        ],
        "usage": {"prompt_tokens": 12, "completion_tokens": 34},
    }


def test_main_writes_raw_content_and_measured_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A normal completion publishes exact content and no local API path."""
    public = make_public(tmp_path)
    monkeypatch.setattr(runner, "PUBLIC", public)
    monkeypatch.setattr(runner, "parse_args", lambda: make_args())
    raw_content = "  <html>exact</html>  \n"
    sent = install_fake_http(monkeypatch, [{"data": []}, completion(raw_content)])

    assert runner.main() == 0

    model_dir = public / "demo" / "hy3-t512"
    assert (model_dir / "index.html").read_text(encoding="utf-8") == raw_content
    run = json.loads((model_dir / "run.json").read_text(encoding="utf-8"))
    assert run["harness"] == "mlx-lm-api"
    assert run["model_id"] == "example/Hy3-T512"
    assert "/private/models" not in json.dumps(run)
    assert run["sampling"] == {"temperature": 0.3, "max_tokens": 65000, "top_p": "default"}
    assert run["runtime"]["api"] == "openai-compat-chat"
    assert run["runtime"]["version"] == "0.31.3"
    assert run["runtime"]["framework"] == "MLX 0.32.0"
    assert "chat template" in run["usage"]["note"]
    payload = json.loads(sent[1][0].data.decode("utf-8"))
    assert payload["messages"] == [{"role": "user", "content": "make it\n"}]
    assert payload["stream"] is False
    assert "system" not in json.dumps(payload)


def test_finish_reason_length_is_saved_as_a_model_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A nonempty length completion remains a quality result, not a runner error."""
    public = make_public(tmp_path)
    monkeypatch.setattr(runner, "PUBLIC", public)
    monkeypatch.setattr(runner, "parse_args", lambda: make_args())
    install_fake_http(monkeypatch, [{"data": []}, completion("<html>cut</html>", "length")])

    assert runner.main() == 0
    run = json.loads((public / "demo" / "hy3-t512" / "run.json").read_text(encoding="utf-8"))
    assert "finish_reason=length" in run["usage"]["note"]


@pytest.mark.parametrize(
    "body",
    [
        {"choices": [{"finish_reason": "stop", "message": {"content": None}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}},
        {"choices": [{"finish_reason": "stop", "message": {"content": ""}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}},
        {"choices": [{"finish_reason": "stop", "message": {"content": "x"}}]},
        {"choices": [{"finish_reason": "stop", "message": {"content": "x"}}], "usage": {"prompt_tokens": True, "completion_tokens": 1}},
        {"error": {"message": "failed"}},
        {"choices": []},
        b"not-json",
        runner.urllib.error.HTTPError("http://127.0.0.1/v1/chat/completions", 500, "failed", {}, None),
    ],
)
def test_invalid_completion_publishes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: object
) -> None:
    """Null, empty, usage-less, error, and choice-less bodies never create a model directory."""
    public = make_public(tmp_path)
    monkeypatch.setattr(runner, "PUBLIC", public)
    monkeypatch.setattr(runner, "parse_args", lambda: make_args())
    install_fake_http(monkeypatch, [{"data": []}, body])

    assert runner.main() == 1
    assert not (public / "demo" / "hy3-t512").exists()


def test_existing_output_is_rejected_and_resume_skips_complete_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Atomic publication leaves no partial dir, rejects overwrite, and resumes completed work."""
    public = make_public(tmp_path)
    monkeypatch.setattr(runner, "PUBLIC", public)
    monkeypatch.setattr(runner, "parse_args", lambda: make_args())
    install_fake_http(monkeypatch, [{"data": []}, completion()])
    assert runner.main() == 0
    assert not [path for path in (public / "demo").iterdir() if path.name.startswith(".")]

    monkeypatch.setattr(runner, "parse_args", lambda: make_args())
    install_fake_http(monkeypatch, [{"data": []}])
    assert runner.main() == 1

    monkeypatch.setattr(runner, "parse_args", lambda: make_args(resume=True))
    install_fake_http(monkeypatch, [{"data": []}])
    assert runner.main() == 0


@pytest.mark.parametrize(
    "damage",
    ["empty-artifact", "invalid-json", "wrong-theme", "wrong-model", "missing-harness", "bool-usage"],
)
def test_resume_rejects_incomplete_or_mismatched_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, damage: str
) -> None:
    """Resume never treats corrupt or unrelated metadata as completed work."""
    public = make_public(tmp_path)
    monkeypatch.setattr(runner, "PUBLIC", public)
    monkeypatch.setattr(runner, "parse_args", lambda: make_args())
    install_fake_http(monkeypatch, [{"data": []}, completion()])
    assert runner.main() == 0

    model_dir = public / "demo" / "hy3-t512"
    artifact = model_dir / "index.html"
    run_path = model_dir / "run.json"
    if damage == "empty-artifact":
        artifact.write_text("", encoding="utf-8")
    elif damage == "invalid-json":
        run_path.write_text("not-json", encoding="utf-8")
    else:
        run = json.loads(run_path.read_text(encoding="utf-8"))
        if damage == "wrong-theme":
            run["theme"] = "other"
        elif damage == "wrong-model":
            run["model"] = "other"
        elif damage == "missing-harness":
            del run["harness"]
        elif damage == "bool-usage":
            run["usage"]["prompt_tokens"] = True
        run_path.write_text(json.dumps(run), encoding="utf-8")

    artifact_before = artifact.read_bytes()
    run_before = run_path.read_bytes()
    monkeypatch.setattr(runner, "parse_args", lambda: make_args(resume=True))
    sent = install_fake_http(monkeypatch, [{"data": []}])

    assert runner.main() == 1
    assert len(sent) == 1
    assert artifact.read_bytes() == artifact_before
    assert run_path.read_bytes() == run_before


def test_loopback_base_url_restriction() -> None:
    """A direct local runner never accepts a remote or credential-bearing target."""
    assert runner.resolve_base_url("http://127.0.0.2:18081/v1") == "http://127.0.0.2:18081/v1"
    assert runner.resolve_base_url("http://[::1]:18081/v1") == "http://[::1]:18081/v1"
    with pytest.raises(ValueError, match="loopback IP literal"):
        runner.resolve_base_url("http://localhost:18081/v1")
    with pytest.raises(ValueError, match="loopback IP literal"):
        runner.resolve_base_url("http://example.com/v1")
    with pytest.raises(ValueError, match="credentials"):
        runner.resolve_base_url("http://user@127.0.0.1:18081/v1")


@pytest.mark.parametrize("status", [302, 307, 308])
def test_redirect_is_rejected_without_followup_request(status: int) -> None:
    """A redirect to an external URL fails at the first loopback response."""
    requests: list[str] = []

    class RedirectHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            requests.append(self.path)
            self.send_response(status)
            self.send_header("Location", "https://example.com/must-not-be-requested")
            self.end_headers()

        def log_message(self, _format: str, *_args: object) -> None:
            return None

    server = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    try:
        with pytest.raises(runner.MlxApiError, match=f"HTTP {status}"):
            runner.request_json(f"http://127.0.0.1:{server.server_port}/v1/models", timeout=2)
    finally:
        thread.join(timeout=2)
        server.server_close()

    assert requests == ["/v1/models"]


def test_http_opener_ignores_environment_proxies(monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit empty proxy configuration wins even when every proxy env is set."""
    proxy_url = "http://192.0.2.1:8888"
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.setenv(name, proxy_url)

    opener = runner.build_http_opener()
    proxy_handlers = [
        handler
        for handler in opener.handlers
        if isinstance(handler, runner.urllib.request.ProxyHandler)
    ]

    assert runner.urllib.request.getproxies().get("http") == proxy_url
    # build_opener sees the explicit ProxyHandler({}) and suppresses its
    # environment-derived default.  The empty handler itself has no protocol
    # methods, so urllib intentionally omits it from the final handler list.
    assert proxy_handlers == []


@pytest.mark.parametrize(
    "model_id",
    [
        "/private/models/hy3",
        "../models/hy3",
        "owner/../hy3",
        "file:///private/models/hy3",
        "~/models/hy3",
        "owner",
        "owner/name/extra",
        ".hidden/name",
    ],
)
def test_public_model_id_rejects_non_registry_paths(model_id: str) -> None:
    with pytest.raises(ValueError, match="owner/name"):
        runner.validate_public_model_id(model_id)


def test_public_model_id_allows_hy3_registry_id() -> None:
    runner.validate_public_model_id("avlp12/Hy3-Alis-MLX-Dynamic")


def test_framework_cli_option_is_distinct_from_runner_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "mlx-lm-run.py",
            "--theme",
            "demo",
            "--model",
            "hy3-t512",
            "--api-model-id",
            "/models/hy3",
            "--public-model-id",
            "avlp12/Hy3-Alis-MLX-Dynamic",
            "--version",
            "0.31.3",
            "--framework",
            "MLX 0.32.0",
        ],
    )

    args = runner.parse_args()

    assert args.version == "0.31.3"
    assert args.framework == "MLX 0.32.0"


@pytest.mark.parametrize("theme", [".", ".."])
def test_theme_rejects_dot_segments(theme: str) -> None:
    with pytest.raises(ValueError, match="directory name"):
        runner.validate_name("--theme", theme)


def test_theme_symlink_is_rejected_before_reading(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    public = tmp_path / "public"
    outside = tmp_path / "outside"
    public.mkdir()
    outside.mkdir()
    (outside / "PROMPT.md").write_text("outside", encoding="utf-8")
    (public / "linked").symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(runner, "PUBLIC", public)

    with pytest.raises(ValueError, match="must not be a symlink"):
        runner.resolve_theme_dir("linked")


def test_all_selects_every_prompt_theme(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The all selector expands only benchmark themes that have a prompt file."""
    public = make_public(tmp_path, "one")
    make_public(tmp_path, "two")
    (public / "unrelated").mkdir()
    monkeypatch.setattr(runner, "PUBLIC", public)

    assert runner.select_themes("all") == ["one", "two"]


def test_pr_triage_uses_canonical_placeholder_expansion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The JSON theme request uses openrouter-run.py's canonical prompt expansion."""
    public = make_public(tmp_path, "pr-triage")
    theme_dir = public / "pr-triage"
    placeholder = runner.PROMPTS.INPUT_PLACEHOLDER
    (theme_dir / "PROMPT.md").write_text(f"classify\n{placeholder}\n", encoding="utf-8")
    (theme_dir / "input.md").write_text("# inputs\n", encoding="utf-8")
    monkeypatch.setattr(runner, "PUBLIC", public)
    monkeypatch.setattr(runner, "parse_args", lambda: make_args(theme="pr-triage"))
    sent = install_fake_http(monkeypatch, [{"data": []}, completion('{"triage": []}')])

    assert runner.main() == 0
    payload = json.loads(sent[1][0].data.decode("utf-8"))
    assert payload["messages"][0]["content"] == runner.PROMPTS.build_prompt(theme_dir, "json")
    assert (theme_dir / "hy3-t512" / "output.json").read_text(encoding="utf-8") == '{"triage": []}'
