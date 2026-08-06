import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "public" / "index.html"


def extract_between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    end_index = source.index(end, start_index)
    return source[start_index:end_index]


def test_format_run_meta_labels_runtime_engines() -> None:
    source = INDEX_HTML.read_text(encoding="utf-8")
    definitions = "\n".join(
        [
            extract_between(source, "const HARNESS_LABEL =", "// HTML エスケープ"),
            extract_between(source, "function escapeHtml", "// cost.usd"),
            extract_between(source, "function formatRunMeta", "// run.json → 独立"),
        ]
    )
    cases = [
        {
            "harness": "lmstudio-api",
            "reasoning_effort": "none",
            "runtime": {"engine": "lmstudio", "quantization": "mlx-4bit"},
        },
        {
            "harness": "omlx-api",
            "reasoning_effort": "unknown",
            "runtime": {"engine": "omlx", "quantization": "mxfp4-mxfp8-mixed"},
        },
        {
            "harness": "omlx-api",
            "reasoning_effort": "unknown",
            "runtime": {"engine": "untrusted", "quantization": "ignored"},
        },
        {
            "harness": "mlx-lm-api",
            "reasoning_effort": "unknown",
            "runtime": {"engine": "mlx-lm", "quantization": "t512"},
        },
    ]
    script = (
        definitions
        + f"\nconst cases = {json.dumps(cases)};"
        + "\nconsole.log(JSON.stringify(cases.map(formatRunMeta)));"
    )

    completed = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert json.loads(completed.stdout) == [
        "LM Studio API ・ LM Studio (mlx-4bit)",
        "oMLX API ・ oMLX (mxfp4-mxfp8-mixed)",
        "oMLX API",
        "MLX-LM API ・ MLX-LM (t512)",
    ]
