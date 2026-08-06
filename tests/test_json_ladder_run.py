#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest==8.3.4"]
# ///
"""Behavior tests for the five-request json-ladder OpenRouter runner."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str, filename: str) -> Any:
    """Load a hyphenated script by its path."""
    path = ROOT / "scripts" / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ladder = load_script("json_ladder_run", "json-ladder-run.py")


class StubServer:
    """Serve deterministic OpenRouter-shaped responses on loopback only."""

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = responses
        self.requests: list[dict[str, Any]] = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self.handler())
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def handler(self) -> type[BaseHTTPRequestHandler]:
        parent = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                size = int(self.headers["Content-Length"])
                parent.requests.append(json.loads(self.rfile.read(size)))
                response = parent.responses.pop(0)
                payload = json.dumps(response).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_GET(self) -> None:  # noqa: N802
                payload = b'{"data": []}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, _format: str, *args: object) -> None:
                return

        return Handler

    def __enter__(self) -> "StubServer":
        self.thread.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_port}/chat/completions"


def response(level: int, *, finish_reason: str = "stop", usage: bool = True) -> dict[str, Any]:
    """Build one minimal successful OpenRouter response."""
    body: dict[str, Any] = {
        "choices": [{"finish_reason": finish_reason, "message": {"content": f'{{"level": {level}}}'}}]
    }
    if usage:
        body["usage"] = {"prompt_tokens": 10 * level, "completion_tokens": 20 * level}
    return body


def make_theme(tmp_path: Path) -> Path:
    """Create a small frozen source fixture with all five level files."""
    theme = tmp_path / "json-ladder"
    (theme / "levels").mkdir(parents=True)
    (theme / "PROMPT.md").write_text(
        "common\n\n[levels/l<N>.md の設問をここに展開する]\n\n"
        "[input.md の本文をここに展開してプロンプトに含める]\n",
        encoding="utf-8",
    )
    (theme / "input.md").write_text("shared input", encoding="utf-8")
    for level in ladder.LEVEL_NUMBERS:
        (theme / "levels" / f"l{level}.md").write_text(f"level instruction {level}", encoding="utf-8")
    return theme


def invoke(monkeypatch: pytest.MonkeyPatch, public: Path, *args: str) -> int:
    """Call main directly with a safe test API key and temporary public root."""
    monkeypatch.setattr(ladder, "PUBLIC", public)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(sys, "argv", ["json-ladder-run.py", *args])
    return ladder.main()


def test_build_level_prompt_substitutes_exactly_one_level_and_json_suffix(tmp_path: Path) -> None:
    theme = make_theme(tmp_path)

    prompt = ladder.build_level_prompt(theme, 3)

    assert "level instruction 3" in prompt
    assert "level instruction 2" not in prompt
    assert "shared input" in prompt
    assert prompt.endswith(ladder.OPENROUTER.JSON_PROMPT_SUFFIX)


def test_main_makes_five_sequential_requests_and_publishes_all_artifacts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    make_theme(tmp_path)
    with StubServer([response(level) for level in ladder.LEVEL_NUMBERS]) as server:
        monkeypatch.setenv("OPENROUTER_API_URL", server.url)
        assert invoke(monkeypatch, tmp_path, "--model", "claude-opus-5", "--backend", "openrouter") == 0

        assert len(server.requests) == 5
        for level, request in enumerate(server.requests, start=1):
            content = request["messages"][0]["content"]
            assert f"level instruction {level}" in content

    out_dir = tmp_path / "json-ladder" / "claude-opus-5"
    assert {path.name for path in out_dir.iterdir()} == {
        "raw-l1.txt", "raw-l2.txt", "raw-l3.txt", "raw-l4.txt", "raw-l5.txt", "output.json", "run.json"
    }
    output = json.loads((out_dir / "output.json").read_text(encoding="utf-8"))
    run = json.loads((out_dir / "run.json").read_text(encoding="utf-8"))
    assert [entry["level"] for entry in output["levels"]] == [1, 2, 3, 4, 5]
    assert run["attempts"] == 1
    assert run["usage"]["prompt_tokens"] == 150
    assert run["usage"]["completion_tokens"] == 300
    assert "5段階を独立リクエストで合算" in run["usage"]["note"]


def test_local_length_response_is_saved(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Local MLX runs keep length responses, unlike the OpenRouter batch runner."""
    make_theme(tmp_path)
    with StubServer([response(level, finish_reason="length") for level in ladder.LEVEL_NUMBERS]) as server:
        base_url = server.url.removesuffix("/chat/completions") + "/v1"
        assert invoke(
            monkeypatch,
            tmp_path,
            "--model",
            "local-model",
            "--backend",
            "local",
            "--base-url",
            base_url,
        ) == 0

    run = json.loads((tmp_path / "json-ladder" / "local-model" / "run.json").read_text(encoding="utf-8"))
    assert run["harness"] == "mlx-lm-api"
    assert run["usage"]["completion_tokens"] == 300


def test_local_empty_content_is_saved_as_a_failed_level(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """空 content は実行を止めず、そのレベルのフォーマット遵守失敗として残す。

    reasoning を出し切って本文を返さないローカルモデルがあり（Gemma 4 12B QAT の L5）、
    これを例外にすると 5 レベル全部が失われてベンチ結果として記録できない。
    """
    make_theme(tmp_path)
    bodies = [response(level) for level in ladder.LEVEL_NUMBERS]
    bodies[4]["choices"][0]["message"]["content"] = None
    bodies[4]["choices"][0]["finish_reason"] = "length"
    with StubServer(bodies) as server:
        base_url = server.url.removesuffix("/chat/completions") + "/v1"
        assert invoke(
            monkeypatch,
            tmp_path,
            "--model", "local-model",
            "--backend", "local",
            "--base-url", base_url,
        ) == 0

    model_dir = tmp_path / "json-ladder" / "local-model"
    output = json.loads((model_dir / "output.json").read_text(encoding="utf-8"))
    assert output["levels"][4]["raw"] == ""
    assert output["levels"][4]["finish_reason"] == "length"
    assert (model_dir / "raw-l5.txt").read_text(encoding="utf-8") == ""
    assert [level["level"] for level in output["levels"]] == list(ladder.LEVEL_NUMBERS)


def test_local_path_model_id_requires_a_public_model_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """ローカル絶対パスがそのまま公開 run.json に載るのを防ぐ。"""
    make_theme(tmp_path)
    with StubServer([response(level) for level in ladder.LEVEL_NUMBERS]) as server:
        base_url = server.url.removesuffix("/chat/completions") + "/v1"
        assert invoke(
            monkeypatch,
            tmp_path,
            "--model", "hy3-t512",
            "--backend", "local",
            "--base-url", base_url,
            "--model-id", "/Users/someone/models/hy3-t512",
        ) != 0
    assert not (tmp_path / "json-ladder" / "hy3-t512").exists()


def test_public_model_id_is_published_instead_of_the_api_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """API にはローカルパス、run.json には公開識別子を書き分ける。"""
    make_theme(tmp_path)
    with StubServer([response(level) for level in ladder.LEVEL_NUMBERS]) as server:
        base_url = server.url.removesuffix("/chat/completions") + "/v1"
        assert invoke(
            monkeypatch,
            tmp_path,
            "--model", "hy3-t512",
            "--backend", "local",
            "--base-url", base_url,
            "--model-id", "/Users/someone/models/hy3-t512",
            "--public-model-id", "avlp12/Hy3-Alis-MLX-Dynamic",
        ) == 0
        assert server.requests[0]["model"] == "/Users/someone/models/hy3-t512"

    run = json.loads(
        (tmp_path / "json-ladder" / "hy3-t512" / "run.json").read_text(encoding="utf-8")
    )
    assert run["model_id"] == "avlp12/Hy3-Alis-MLX-Dynamic"
    assert "/Users/" not in json.dumps(run)


def test_lmstudio_run_records_harness_model_id_and_runtime(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """LM Studio runs follow the existing pr-triage recording conventions."""
    make_theme(tmp_path)
    with StubServer([response(level) for level in ladder.LEVEL_NUMBERS]) as server:
        base_url = server.url.removesuffix("/chat/completions") + "/v1"
        assert invoke(
            monkeypatch,
            tmp_path,
            "--model", "gemma-4-12b-qat",
            "--backend", "local",
            "--base-url", base_url,
            "--harness", "lmstudio-api",
            "--model-id", "google/gemma-4-12b-qat",
            "--runtime-extra", '{"quantization": "mlx-4bit", "hardware": "Mac Studio M3 Ultra 512GB"}',
            "--reasoning-label", "none",
        ) == 0

        assert [request["model"] for request in server.requests] == ["google/gemma-4-12b-qat"] * 5

    run = json.loads(
        (tmp_path / "json-ladder" / "gemma-4-12b-qat" / "run.json").read_text(encoding="utf-8")
    )
    assert run["model"] == "gemma-4-12b-qat"
    assert run["model_id"] == "google/gemma-4-12b-qat"
    assert run["harness"] == "lmstudio-api"
    assert run["reasoning_effort"] == "none"
    assert run["runtime"] == {
        "engine": "lmstudio",
        "api": "openai-compat",
        "quantization": "mlx-4bit",
        "hardware": "Mac Studio M3 Ultra 512GB",
    }
    assert "LM Studio API 実測" in run["usage"]["note"]


def test_runtime_extra_rejects_keys_outside_validator_allowlist(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    make_theme(tmp_path)

    assert invoke(
        monkeypatch,
        tmp_path,
        "--model", "local-model",
        "--backend", "local",
        "--base-url", "http://127.0.0.1:9/v1",
        "--runtime-extra", '{"engine_notes": "leaked"}',
    ) == 1

    assert "engine_notes" in capsys.readouterr().err
    assert not (tmp_path / "json-ladder" / "local-model").exists()


def test_reasoning_label_is_rejected_on_openrouter_backend(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    make_theme(tmp_path)
    monkeypatch.setenv("OPENROUTER_API_URL", "http://127.0.0.1:9/unused")

    assert invoke(
        monkeypatch,
        tmp_path,
        "--model", "claude-opus-5",
        "--backend", "openrouter",
        "--reasoning-label", "high",
    ) == 1

    assert "--reasoning-label" in capsys.readouterr().err
    assert not (tmp_path / "json-ladder" / "claude-opus-5").exists()


def test_length_response_aborts_without_creating_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    make_theme(tmp_path)
    responses = [response(1), response(2, finish_reason="length")]
    with StubServer(responses) as server:
        monkeypatch.setenv("OPENROUTER_API_URL", server.url)
        assert invoke(monkeypatch, tmp_path, "--model", "claude-opus-5", "--backend", "openrouter") == 2

    assert not (tmp_path / "json-ladder" / "claude-opus-5").exists()


def test_missing_usage_aborts_without_creating_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    make_theme(tmp_path)
    with StubServer([response(1, usage=False)]) as server:
        monkeypatch.setenv("OPENROUTER_API_URL", server.url)
        assert invoke(monkeypatch, tmp_path, "--model", "claude-opus-5", "--backend", "openrouter") == 2

    assert not (tmp_path / "json-ladder" / "claude-opus-5").exists()


def test_existing_directory_requires_overwrite(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    theme = make_theme(tmp_path)
    (theme / "claude-opus-5").mkdir()
    monkeypatch.setenv("OPENROUTER_API_URL", "http://127.0.0.1:9/unused")

    assert invoke(monkeypatch, tmp_path, "--model", "claude-opus-5", "--backend", "openrouter") == 1


def test_dry_run_makes_no_request_and_creates_no_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    make_theme(tmp_path)
    with StubServer([]) as server:
        monkeypatch.setenv("OPENROUTER_API_URL", server.url)

        assert invoke(
            monkeypatch, tmp_path, "--model", "claude-opus-5", "--backend", "openrouter", "--dry-run"
        ) == 0

        assert server.requests == []
    assert not (tmp_path / "json-ladder" / "claude-opus-5").exists()


def test_dry_run_reports_resolved_model_without_leaking_the_api_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    make_theme(tmp_path)
    monkeypatch.setenv("OPENROUTER_API_URL", "http://127.0.0.1:9/unused")

    assert invoke(
        monkeypatch, tmp_path, "--model", "claude-opus-5", "--backend", "openrouter", "--dry-run"
    ) == 0

    stderr = capsys.readouterr().err
    assert "anthropic/claude-opus-5" in stderr
    assert "test-key" not in stderr


def test_dry_run_rejects_a_model_missing_from_the_model_map(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    make_theme(tmp_path)
    monkeypatch.setenv("OPENROUTER_API_URL", "http://127.0.0.1:9/unused")

    assert invoke(
        monkeypatch, tmp_path, "--model", "no-such-model-x", "--backend", "openrouter", "--dry-run"
    ) == 1
    assert not (tmp_path / "json-ladder" / "no-such-model-x").exists()


def test_local_dry_run_succeeds_against_a_running_server(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    make_theme(tmp_path)
    with StubServer([]) as server:
        base_url = server.url.removesuffix("/chat/completions") + "/v1"

        assert invoke(
            monkeypatch, tmp_path, "--model", "local-model", "--backend", "local",
            "--base-url", base_url, "--dry-run",
        ) == 0

        assert server.requests == []
    assert not (tmp_path / "json-ladder" / "local-model").exists()


def test_local_dry_run_fails_when_the_server_is_not_running(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    make_theme(tmp_path)

    assert invoke(
        monkeypatch, tmp_path, "--model", "local-model", "--backend", "local",
        "--base-url", "http://127.0.0.1:9/v1", "--dry-run",
    ) == 2
    assert not (tmp_path / "json-ladder" / "local-model").exists()


def test_backend_is_required(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "argv", ["json-ladder-run.py", "--model", "test-model", "--dry-run"])

    with pytest.raises(SystemExit) as exc_info:
        ladder.main()

    assert exc_info.value.code == 2
    assert "--backend" in capsys.readouterr().err


def test_openrouter_cli_rejects_json_ladder(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(
        sys, "argv", ["openrouter-run.py", "--theme", "json-ladder", "--model", "test-model", "--dry-run"]
    )

    assert ladder.OPENROUTER.main() == 1
    assert "json-ladder-run.py" in capsys.readouterr().err


def test_mlx_explicit_theme_rejects_json_ladder(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "mlx-lm-run.py", "--theme", "json-ladder", "--model", "test-model",
            "--api-model-id", "local-test", "--public-model-id", "owner/name",
        ],
    )

    assert ladder.LOCAL.main() == 1
    assert "json-ladder-run.py" in capsys.readouterr().err


def test_mlx_all_skips_json_ladder(capsys: pytest.CaptureFixture[str]) -> None:
    themes = ladder.LOCAL.select_themes("all")

    assert "json-ladder" not in themes
    assert "[skip] json-ladder" in capsys.readouterr().err


def test_add_model_directs_json_ladder_to_dedicated_runner() -> None:
    result = subprocess.run(
        ["bash", str(ROOT / "scripts" / "add-model.sh"), "json-ladder", "test-model", "--dry-run"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "json-ladder-run.py" in result.stderr


@pytest.mark.parametrize("theme,model", [("../outside", "valid-model"), ("valid-theme", "../outside")])
def test_add_model_rejects_path_components(theme: str, model: str) -> None:
    result = subprocess.run(
        ["bash", str(ROOT / "scripts" / "add-model.sh"), theme, model, "--dry-run"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "safe directory name" in result.stderr
