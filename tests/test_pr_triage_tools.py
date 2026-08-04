import importlib.util
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "scripts" / "build-pr-triage-html.py"
VALIDATE_SCRIPT = ROOT / "scripts" / "validate-pr-triage.mjs"
ANSWER_KEY = ROOT / "public" / "pr-triage" / "answer-key.json"
MODEL = "deepseek-v4-flash-0731-mlx"


def load_python_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def valid_output() -> dict:
    answers = json.loads(ANSWER_KEY.read_text(encoding="utf-8"))["answers"]
    triage = [
        {
            "pr": answer["pr"],
            "verdict": answer["primary"],
            "confidence": "high",
            "reasons": ["test reason"],
            "actions": [],
            "risk_if_merged": "low",
        }
        for answer in answers
    ]
    return {
        "triage": triage,
        "priority_order": [answer["pr"] for answer in answers],
        "summary": "test summary",
    }


def write_model(theme_dir: Path, model: str, output: object, schema_pass: bool = True) -> Path:
    model_dir = theme_dir / model
    model_dir.mkdir(parents=True)
    raw = json.dumps(output, ensure_ascii=False)
    (model_dir / "output.json").write_text(raw, encoding="utf-8")
    meta = {
        "schema_pass": schema_pass,
        "agreement_pct": 100,
        "primary_match": 10,
        "acceptable_match": 0,
        "raw_length": len(raw),
        "verdicts": [],
        "issues": [],
    }
    (model_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return model_dir


def test_build_pr_triage_html_model_filter(tmp_path: Path) -> None:
    theme_dir = tmp_path / "pr-triage"
    selected = write_model(theme_dir, MODEL, valid_output())
    other = write_model(theme_dir, "gemma-4-31b", valid_output())
    module = load_python_script(BUILD_SCRIPT, "build_pr_triage_html")

    result = module.main(["--theme-dir", str(theme_dir), "--model", MODEL])

    assert result == 0
    assert (selected / "output.html").exists()
    assert "DeepSeek V4 Flash 0731 MLX" in (selected / "output.html").read_text(encoding="utf-8")
    assert not (other / "output.html").exists()


def test_validate_pr_triage_model_filter_and_exit_status(tmp_path: Path) -> None:
    theme_dir = tmp_path / "pr-triage"
    selected = write_model(theme_dir, MODEL, valid_output())
    broken = write_model(theme_dir, "broken-model", {}, schema_pass=False)
    broken_meta = broken / "meta.json"
    broken_meta.unlink()

    passed = subprocess.run(
        [
            "node",
            str(VALIDATE_SCRIPT),
            "--theme-dir",
            str(theme_dir),
            "--answer-key",
            str(ANSWER_KEY),
            "--model",
            MODEL,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert passed.returncode == 0, passed.stderr
    assert "PASS" in passed.stdout
    assert (selected / "meta.json").exists()
    assert not broken_meta.exists()

    failed = subprocess.run(
        [
            "node",
            str(VALIDATE_SCRIPT),
            "--theme-dir",
            str(theme_dir),
            "--answer-key",
            str(ANSWER_KEY),
            "--model",
            "broken-model",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert failed.returncode == 1
    assert "FAIL" in failed.stdout


def test_backfill_maps_omlx_runtime_and_model_id() -> None:
    module = load_python_script(ROOT / "scripts" / "backfill-runs.py", "backfill_runs")

    run = module.build_run(
        {"theme": "lp-nishibi", "model": MODEL, "runner": "oMLX API"}
    )

    assert run["harness"] == "omlx-api"
    assert run["reasoning_effort"] == "unknown"
    assert run["system_prompt"] == "none"
    assert run["model_id"] == "inferencerlabs/DeepSeek-V4-Flash-0731-MLX"
    assert run["runtime"] == {
        "engine": "omlx",
        "version": "0.5.4rc1",
        "framework": "MLX 0.32.0",
        "model_revision": "750040be1d918280cf1c55ccb56d02dee4520b16",
        "quantization": "mxfp4-mxfp8-mixed",
        "api": "openai-compat",
    }
