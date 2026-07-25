#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pytest==8.3.4",
# ]
# ///
"""scripts/openrouter-run.py の純粋関数（外部 API を叩かない部分）のテスト。

実行:
  uv run tests/test_openrouter_run.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load_module():
    """ハイフン入りファイル名のためパス指定でロードする。"""
    path = ROOT / "scripts" / "openrouter-run.py"
    spec = importlib.util.spec_from_file_location("openrouter_run", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


orun = _load_module()


# --- フェンス抽出 --------------------------------------------------------


def test_plain_html_is_returned_as_is():
    """フェンスなしの生 HTML は抽出扱いにしない（post_processing=none になる）。"""
    html = "<!DOCTYPE html>\n<html><body><h1>hi</h1></body></html>"
    out, extracted = orun.extract_fenced_html(html)
    assert extracted is False
    assert out == html


def test_whole_response_wrapped_in_fence():
    """応答全体が ```html フェンスで包まれているパターン。"""
    body = "<!DOCTYPE html>\n<html><body>x</body></html>"
    out, extracted = orun.extract_fenced_html(f"```html\n{body}\n```")
    assert extracted is True
    assert out == body


def test_preamble_fence_and_trailing_commentary():
    """claude-opus-5 実績パターン: 前置き文 + フェンス + 末尾解説。"""
    body = '<!DOCTYPE html>\n<html lang="ja">\n<body>ok</body>\n</html>'
    response = (
        "承知しました。以下に完成版を示します。\n\n"
        f"```html\n{body}\n```\n\n"
        "## 実装のポイント\n\n- レスポンシブ対応しました\n"
    )
    out, extracted = orun.extract_fenced_html(response)
    assert extracted is True
    assert out == body
    assert "実装のポイント" not in out
    assert "承知しました" not in out


def test_fence_without_language_tag():
    """言語指定なしフェンスでも中身が HTML なら抽出する。"""
    body = "<html><body>y</body></html>"
    out, extracted = orun.extract_fenced_html(f"説明\n\n```\n{body}\n```\n")
    assert extracted is True
    assert out == body


def test_non_html_fence_is_ignored():
    """本文が生 HTML で、解説に ```bash フェンスが混ざるだけなら抽出しない。"""
    response = "<!DOCTYPE html>\n<html><body>z</body></html>\n\n```bash\nnpm run dev\n```"
    out, extracted = orun.extract_fenced_html(response)
    assert extracted is False
    assert "npm run dev" in out


def test_longest_html_fence_wins():
    """HTML フェンスが複数ある時は本体（最長）を採用する。"""
    snippet = "<html><body>a</body></html>"
    full = "<!DOCTYPE html>\n<html><body>" + "b" * 200 + "</body></html>"
    response = f"抜粋:\n```html\n{snippet}\n```\n全体:\n```html\n{full}\n```"
    out, extracted = orun.extract_fenced_html(response)
    assert extracted is True
    assert out == full


# --- プロンプト組み立て --------------------------------------------------


def test_html_theme_prompt_is_prompt_md_verbatim(tmp_path):
    theme_dir = tmp_path / "lp-x"
    theme_dir.mkdir()
    (theme_dir / "PROMPT.md").write_text("LP を作って\n", encoding="utf-8")
    assert orun.build_prompt(theme_dir, "html") == "LP を作って"


def test_json_theme_prompt_matches_gen_questions(tmp_path):
    """JSON テーマは gen-questions.py の build_prompt と同一結果になる。"""
    theme_dir = tmp_path / "pr-triage"
    theme_dir.mkdir()
    (theme_dir / "PROMPT.md").write_text(
        f"分類してください。\n\n{orun.INPUT_PLACEHOLDER}\n", encoding="utf-8"
    )
    (theme_dir / "input.md").write_text("# PR 一覧\n- #1 fix\n", encoding="utf-8")

    got = orun.build_prompt(theme_dir, "json")
    expected = "分類してください。\n\n# PR 一覧\n- #1 fix" + orun.JSON_PROMPT_SUFFIX
    assert got == expected
    assert orun.INPUT_PLACEHOLDER not in got


def test_json_theme_missing_input_fails_fast(tmp_path):
    theme_dir = tmp_path / "pr-triage"
    theme_dir.mkdir()
    (theme_dir / "PROMPT.md").write_text(orun.INPUT_PLACEHOLDER, encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        orun.build_prompt(theme_dir, "json")


# --- テーマ種別判定 ------------------------------------------------------


def test_detect_kind_json_by_input_md(tmp_path):
    theme_dir = tmp_path / "pr-triage"
    theme_dir.mkdir()
    (theme_dir / "input.md").write_text("x", encoding="utf-8")
    assert orun.detect_theme_kind(theme_dir) == "json"


def test_detect_kind_html_by_existing_output(tmp_path):
    theme_dir = tmp_path / "lp-x"
    (theme_dir / "some-model").mkdir(parents=True)
    (theme_dir / "some-model" / "index.html").write_text("<html></html>", encoding="utf-8")
    assert orun.detect_theme_kind(theme_dir) == "html"


# --- usage 実測 ----------------------------------------------------------


def test_read_usage_extracts_reasoning_and_cost():
    body = {
        "usage": {
            "prompt_tokens": 1029,
            "completion_tokens": 19628,
            "completion_tokens_details": {"reasoning_tokens": 996},
            "cost": 0.4958,
        }
    }
    assert orun.read_usage(body, "m") == (1029, 19628, 996, 0.4958)


def test_read_usage_without_usage_object_raises():
    with pytest.raises(orun.UsageMissingError):
        orun.read_usage({"choices": []}, "m")


def test_read_usage_with_zero_tokens_raises():
    """0 トークンで実測 run.json を書くと $0.00 という隠れ嘘になるので拒否する。"""
    with pytest.raises(orun.UsageMissingError):
        orun.read_usage({"usage": {"prompt_tokens": 0, "completion_tokens": 100}}, "m")


# --- run.json 生成 -------------------------------------------------------


def _sample_pricing():
    return {
        "prompt_usd_per_mtok": 5.0,
        "completion_usd_per_mtok": 25.0,
        "pricing_source": "openrouter",
        "pricing_model": "anthropic/claude-opus-5",
        "pricing_fetched_at": "2026-07-25",
    }


def test_run_json_matches_existing_api_model_shape():
    run = orun.build_run_json(
        theme="lp-nishibi",
        model_slug="claude-opus-5",
        model_id="anthropic/claude-opus-5",
        reasoning_effort="high",
        max_tokens=65000,
        attempts=1,
        prompt_tokens=1029,
        completion_tokens=19628,
        reasoning_tokens=996,
        pricing=_sample_pricing(),
        post_processing="extract-fenced-html",
    )
    assert run["schema_version"] == 1
    assert run["harness"] == "openrouter-api"
    assert run["system_prompt"] == "none"
    assert run["generated_at_source"] == "measured"
    assert run["runtime"] is None
    assert run["usage"]["estimated"] is False
    assert run["usage"]["method"] == "api-usage"
    assert run["cost"]["pricing_source"] == "openrouter"
    # pricing_source=openrouter は actual_usd=null が validate-runs.mjs の規約
    assert run["cost"]["actual_usd"] is None
    # cost.usd は tokens × 単価と 1% 以内で一致する必要がある
    expected = 1029 * 5.0 / 1_000_000 + 19628 * 25.0 / 1_000_000
    assert abs(run["cost"]["usd"] - expected) / expected < 0.01


def test_run_json_has_no_keys_outside_validator_allowlist():
    """validate-runs.mjs のキー allowlist を壊さないこと。"""
    run_allowed = {
        "schema_version", "theme", "model", "model_id", "harness", "reasoning_effort",
        "attempts", "generated_at", "generated_at_source", "sampling", "system_prompt",
        "post_processing", "runtime", "usage", "cost",
    }
    run = orun.build_run_json(
        theme="pr-triage",
        model_slug="claude-opus-5",
        model_id="anthropic/claude-opus-5",
        reasoning_effort="high",
        max_tokens=65000,
        attempts=1,
        prompt_tokens=100,
        completion_tokens=200,
        reasoning_tokens=0,
        pricing=_sample_pricing(),
        post_processing="none",
    )
    assert set(run) <= run_allowed
    assert set(run["sampling"]) <= {"temperature", "max_tokens", "top_p"}
    assert set(run["usage"]) <= {"estimated", "method", "prompt_tokens", "completion_tokens", "note"}
    assert set(run["cost"]) <= {
        "estimated", "usd", "actual_usd", "prompt_usd_per_mtok",
        "completion_usd_per_mtok", "pricing_source", "pricing_model", "pricing_fetched_at",
    }


# --- API キー読み取り ----------------------------------------------------


def test_api_key_missing_fails_fast(monkeypatch, tmp_path):
    """キー未設定は Fail Fast。メッセージにキー実値の形跡を残さない。"""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(orun, "ROOT", tmp_path)  # .env のない場所を見せる
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY is not set"):
        orun.load_api_key()


def test_api_key_read_from_dotenv(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    (tmp_path / ".env").write_text(
        '# comment\nOTHER=1\nOPENROUTER_API_KEY="sk-test-value"\n', encoding="utf-8"
    )
    monkeypatch.setattr(orun, "ROOT", tmp_path)
    assert orun.load_api_key() == "sk-test-value"


def test_env_var_takes_precedence(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "from-env")
    (tmp_path / ".env").write_text("OPENROUTER_API_KEY=from-dotenv\n", encoding="utf-8")
    monkeypatch.setattr(orun, "ROOT", tmp_path)
    assert orun.load_api_key() == "from-env"


# --- model-map 検証 ------------------------------------------------------


def test_local_model_is_rejected():
    """type=local のモデルを openrouter runner に流すのは誤用なので拒否する。"""
    with pytest.raises(RuntimeError, match="only handles type=api"):
        orun.resolve_model_id("gemma-4-12b-qat")


def test_unknown_model_is_rejected():
    with pytest.raises(RuntimeError, match="not in model-map.json"):
        orun.resolve_model_id("no-such-model-xyz")


def test_known_api_model_resolves():
    assert orun.resolve_model_id("claude-opus-5") == "anthropic/claude-opus-5"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
