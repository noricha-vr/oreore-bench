import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_select_theme(initial_model: str, next_theme: str) -> dict:
    """viewer.html の selectTheme() を抜き出し、テーマ切替後の選択状態を返す。

    実データ（data.js）には依存させず、テスト内のエントリだけで振る舞いを見る。
    """
    viewer = (ROOT / "public" / "viewer.html").read_text(encoding="utf-8")
    function_match = re.search(
        r"function selectTheme\(themeKey\) \{.*?\n        \}", viewer, re.DOTALL
    )
    assert function_match is not None

    script = f"""
const ENTRIES = [
  {{ theme: 'roguelike', model: 'gemma-4-12b' }},
  {{ theme: 'roguelike', model: 'hy3-t512' }},
  {{ theme: 'roguelike', model: 'gpt-5.6-sol' }},
  {{ theme: 'othello', model: 'gemma-4-12b' }},
  {{ theme: 'othello', model: 'hy3-t512' }},
];
let activeTheme = 'roguelike';
let themeEntries = ENTRIES.filter(entry => entry.theme === activeTheme);
let activeEntry = themeEntries.find(entry => entry.model === {initial_model!r});
const themeSelect = {{ value: activeTheme }};
function renderModelList() {{}}
function updateDetails() {{}}
function syncUrl() {{}}
{function_match.group(0)}
selectTheme({next_theme!r});
console.log(JSON.stringify({{
  model: activeEntry.model,
  isRealEntry: ENTRIES.includes(activeEntry),
  themeSelectValue: themeSelect.value,
}}));
"""
    result = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_theme_switch_keeps_selected_model_when_available() -> None:
    result = run_select_theme(initial_model="hy3-t512", next_theme="othello")

    assert result["model"] == "hy3-t512"
    assert result["themeSelectValue"] == "othello"


def test_theme_switch_falls_back_to_first_model_when_missing() -> None:
    result = run_select_theme(initial_model="gpt-5.6-sol", next_theme="othello")

    assert result["model"] == "gemma-4-12b"


def test_theme_switch_keeps_entry_object_identity() -> None:
    """renderModelList() は entry === activeEntry で選択表示を決めるため、
    activeEntry は ENTRIES の実オブジェクトでなければならない。"""
    result = run_select_theme(initial_model="hy3-t512", next_theme="othello")

    assert result["isRealEntry"] is True


def test_back_link_carries_selected_model_as_index_filter() -> None:
    """一覧側は models（複数形のフィルター）で受けるため、単数 model から変換して渡す。"""
    viewer = (ROOT / "public" / "viewer.html").read_text(encoding="utf-8")
    function_match = re.search(
        r"function updateDetails\(\) \{.*?\n        \}", viewer, re.DOTALL
    )
    assert function_match is not None

    script = f"""
const activeTheme = 'othello';
const activeEntry = {{ model: 'hy3-t512', note: 'PASS' }};
const THEMES = {{ othello: {{ title: 'Othello' }} }};
const MODELS = {{ 'hy3-t512': {{ label: 'Hy3 T512 MLX' }} }};
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
console.log(JSON.stringify({{ backHref: backLink.href }}));
"""
    result = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout)["backHref"] == (
        "./index.html?theme=othello&models=hy3-t512"
    )
