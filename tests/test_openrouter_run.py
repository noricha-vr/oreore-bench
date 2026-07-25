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


def test_backticks_inside_html_do_not_truncate_body():
    """回帰: HTML 本文中の ``` を閉じフェンスと誤認して本文が切れないこと。

    <pre><code> 内にコードフェンスを含む LP は珍しくなく、以前は先頭の ``` で
    切断されて壊れた HTML が保存されていた。
    """
    body = (
        "<!DOCTYPE html>\n<html>\n<body>\n"
        "<pre><code>```\nsample fence in content\n```</code></pre>\n"
        "<p>fence より後ろの段落</p>\n</body>\n</html>"
    )
    out, extracted = orun.extract_fenced_html(f"どうぞ。\n\n```html\n{body}\n```\n\n以上です。")
    assert extracted is True
    assert out == body
    assert "fence より後ろの段落" in out
    assert out.rstrip().endswith("</html>")


def test_html_fence_after_json_fence_is_found():
    """回帰: 先行する ```json ブロックで開き/閉じのペアリングがずれないこと。"""
    body = "<!DOCTYPE html>\n<html><body><h1>real</h1></body></html>"
    response = f'設定例:\n\n```json\n{{"a": 1}}\n```\n\n本体:\n\n```html\n{body}\n```\n'
    out, extracted = orun.extract_fenced_html(response)
    assert extracted is True
    assert out == body
    assert '"a": 1' not in out


def test_html_after_long_leading_comment_is_detected():
    """回帰: 先頭の長いコメントで HTML 判定に失敗しないこと（先頭N文字制限の撤廃）。"""
    body = "<!-- " + "x" * 500 + " -->\n<!DOCTYPE html>\n<html><body>ok</body></html>"
    out, extracted = orun.extract_fenced_html(f"どうぞ\n\n```html\n{body}\n```\n")
    assert extracted is True
    assert out == body


def test_unterminated_fence_is_not_extracted():
    """閉じフェンスが無い（打ち切り）ブロックは抽出対象にしない。"""
    truncated = "はい。\n\n```html\n<!DOCTYPE html>\n<html><body><h1>途中で"
    _out, extracted = orun.extract_fenced_html(truncated)
    assert extracted is False


def test_four_backtick_fence_pairs_with_four():
    """4連バッククォートの開きは、3連の行では閉じない（同数以上で閉じる）。"""
    body = "<!DOCTYPE html>\n<html><body>\n```\ninner\n```\n</body></html>"
    out, extracted = orun.extract_fenced_html(f"````html\n{body}\n````")
    assert extracted is True
    assert out == body


# --- 打ち切り検出 --------------------------------------------------------


def test_finish_reason_length_raises():
    """max_tokens 打ち切りは成果物を書かずに停止する。"""
    body = {"choices": [{"finish_reason": "length", "message": {"content": "<html>"}}]}
    with pytest.raises(orun.TruncatedOutputError, match="max_tokens"):
        orun.check_not_truncated(body, "m")


def test_finish_reason_stop_passes():
    body = {"choices": [{"finish_reason": "stop", "message": {"content": "<html>"}}]}
    orun.check_not_truncated(body, "m")  # 例外が出ないこと


def test_html_without_closing_tag_raises():
    """finish_reason を返さないプロバイダ向けの二重チェック。"""
    with pytest.raises(orun.TruncatedOutputError, match="closing </html>"):
        orun.verify_html_complete("<!DOCTYPE html>\n<html><body>途中で", "m")


def test_complete_html_passes_verification():
    orun.verify_html_complete("<!DOCTYPE html>\n<html><body>ok</body></html>", "m")


# --- 機密マスク ----------------------------------------------------------


def test_api_key_is_masked_in_error_detail():
    """エラー本文にリクエストが反射されても鍵を stderr に出さない。"""
    masked = orun.mask_secrets(
        '{"error":"bad key sk-or-v1-abc123DEF_ghi","auth":"Bearer sk-or-v1-xyz789"}'
    )
    assert "sk-or-v1-abc123DEF_ghi" not in masked
    assert "sk-or-v1-xyz789" not in masked
    assert "***" in masked


# --- API URL のスキーム制限 ----------------------------------------------


def test_api_url_defaults_to_production(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_URL", raising=False)
    assert orun.resolve_api_url() == orun.DEFAULT_API_URL


def test_api_url_allows_localhost_http(monkeypatch):
    """テストスタブ（localhost）は許可する。"""
    monkeypatch.setenv("OPENROUTER_API_URL", "http://127.0.0.1:8799/v1/chat/completions")
    assert orun.resolve_api_url() == "http://127.0.0.1:8799/v1/chat/completions"


def test_api_url_rejects_plain_http_remote(monkeypatch):
    """平文 http で外部ホストへ API キーを送らせない。"""
    monkeypatch.setenv("OPENROUTER_API_URL", "http://evil.example.com/v1")
    with pytest.raises(RuntimeError, match="must use https"):
        orun.resolve_api_url()


def test_api_url_rejects_non_http_scheme(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_URL", "file:///etc/passwd")
    with pytest.raises(RuntimeError, match="must use https"):
        orun.resolve_api_url()


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


def test_dotenv_supports_export_prefix(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    (tmp_path / ".env").write_text("export OPENROUTER_API_KEY=exported-value\n", encoding="utf-8")
    monkeypatch.setattr(orun, "ROOT", tmp_path)
    assert orun.load_api_key() == "exported-value"


def test_dotenv_strips_trailing_comment(monkeypatch, tmp_path):
    """裸の値の行末コメントを鍵に混ぜない（認証失敗の原因になる）。"""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    (tmp_path / ".env").write_text("OPENROUTER_API_KEY=abc123  # 本番用\n", encoding="utf-8")
    monkeypatch.setattr(orun, "ROOT", tmp_path)
    assert orun.load_api_key() == "abc123"


def test_dotenv_keeps_hash_inside_quotes(monkeypatch, tmp_path):
    """クォート内の # は値の一部なので落とさない。"""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    (tmp_path / ".env").write_text('OPENROUTER_API_KEY="abc#123"\n', encoding="utf-8")
    monkeypatch.setattr(orun, "ROOT", tmp_path)
    assert orun.load_api_key() == "abc#123"


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


# --- theme / model のパス検証 --------------------------------------------


@pytest.mark.parametrize(
    "theme,model",
    [
        ("../../etc", "claude-opus-5"),
        ("lp-nishibi", "../../../tmp/evil"),
        ("lp-nishibi", "a/b"),
        ("lp nishibi", "claude-opus-5"),
    ],
)
def test_path_traversal_names_are_rejected(monkeypatch, capsys, theme, model):
    """theme / model はディレクトリ名になるので、区切り文字や .. を弾く。"""
    monkeypatch.setattr(
        sys, "argv", ["openrouter-run.py", "--theme", theme, "--model", model, "--dry-run"]
    )
    assert orun.main() == 1
    assert "used as a directory name" in capsys.readouterr().err


def test_valid_names_pass_validation(monkeypatch, capsys):
    """正常な slug は名前検証を通過し、後続の判定へ進む。

    exit code はリポジトリの中身（既存出力の有無）に依存するため、
    「名前検証で弾かれていない」ことだけを検証する。
    """
    monkeypatch.setattr(
        sys,
        "argv",
        ["openrouter-run.py", "--theme", "lp-nishibi", "--model", "claude-opus-5", "--dry-run"],
    )
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    orun.main()
    assert "used as a directory name" not in capsys.readouterr().err


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
