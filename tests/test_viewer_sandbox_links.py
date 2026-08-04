import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_new_tab_link_keeps_generated_html_in_sandbox() -> None:
    viewer = (ROOT / "public" / "viewer.html").read_text(encoding="utf-8")
    function_match = re.search(
        r"function updateDetails\(\) \{.*?\n        \}", viewer, re.DOTALL
    )
    assert function_match is not None

    script = f"""
const activeTheme = 'othello';
const activeEntry = {{ model: 'deepseek-v4-flash-0731-mlx', note: 'FAIL' }};
const THEMES = {{ othello: {{ title: 'Othello' }} }};
const MODELS = {{ 'deepseek-v4-flash-0731-mlx': {{ label: 'DeepSeek' }} }};
const location = {{ pathname: '/viewer.html' }};
const backLink = {{}};
const detailTitle = {{}};
const entryNote = {{}};
const openLink = {{}};
const promptLink = {{}};
const sourceLink = {{}};
const artifactFrame = {{ focus() {{}} }};
const document = {{ title: '' }};
const requestAnimationFrame = callback => callback();
function artifactUrl(entry) {{
  return `./${{entry.theme || activeTheme}}/${{entry.model}}/index.html`;
}}
{function_match.group(0)}
updateDetails();
console.log(JSON.stringify({{ openHref: openLink.href, frameSrc: artifactFrame.src }}));
"""
    result = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    rendered = json.loads(result.stdout)

    assert rendered["openHref"] == (
        "/viewer.html?theme=othello&model=deepseek-v4-flash-0731-mlx"
    )
    assert rendered["frameSrc"] == (
        "./othello/deepseek-v4-flash-0731-mlx/index.html"
    )


def test_cloudflare_headers_sandbox_direct_artifact_routes() -> None:
    headers = (ROOT / "public" / "_headers").read_text(encoding="utf-8")

    for route in (
        "/:theme/:model/",
        "/:theme/:model/index.html",
        "/pr-triage/:model/output",
        "/pr-triage/:model/output.html",
    ):
        assert f"{route}\n  Content-Security-Policy: sandbox allow-scripts" in headers

    assert "allow-same-origin" not in headers
