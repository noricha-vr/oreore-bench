#!/usr/bin/env python3
"""json-ladder テーマの output.html を生成する。
レベル別の生応答 output.json と検証済み meta.json から、パース可否と answer-key 突合を表示する。
"""
from __future__ import annotations

import argparse
import functools
import html
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
THEME_DIR = ROOT / "public" / "json-ladder"
DATA_JS = ROOT / "public" / "data.js"

ACCENT = "#0e7490"
ACCENT_DARK = "#67e8f9"

# 表示情報の単一情報源は public/data.js の window.MODELS。
# ビルダー側にラベル・色を複製すると data.js への追加だけでは HTML に反映されず、
# 新モデルが黙って skip される（旧 MODEL_INFO 定数の実害）。
# JS を正規表現でパースすると構文変更に追従できないため、node に評価させて JSON で受け取る。
LOAD_MODELS_JS = """
global.window = {};
require(process.argv[1]);
console.log(JSON.stringify(window.MODELS || {}));
"""

class ModelDataError(RuntimeError):
    """Raised when public/data.js cannot supply a model's display metadata."""


@functools.lru_cache(maxsize=1)
def load_models(data_js: Path = DATA_JS) -> dict[str, dict[str, object]]:
    """Return window.MODELS from data.js by evaluating it with node."""
    if not data_js.is_file():
        raise ModelDataError(f"data.js not found: {data_js}")
    try:
        completed = subprocess.run(
            ["node", "-e", LOAD_MODELS_JS, str(data_js)],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise ModelDataError("node is required to read public/data.js") from exc
    except subprocess.CalledProcessError as exc:
        raise ModelDataError(f"cannot evaluate {data_js}: {exc.stderr.strip()}") from exc
    models = json.loads(completed.stdout)
    if not isinstance(models, dict) or not models:
        raise ModelDataError(f"window.MODELS is empty in {data_js}")
    return models


def model_info(name: str) -> dict[str, str]:
    """Map one window.MODELS entry to the fields this template renders."""
    entry = load_models().get(name)
    if not isinstance(entry, dict):
        raise ModelDataError(
            f"json-ladder/{name}: window.MODELS に定義がありません。public/data.js に追加してください"
        )
    missing = [key for key in ("label", "provider", "type", "color", "colorDark") if key not in entry]
    if missing:
        raise ModelDataError(
            f"json-ladder/{name}: window.MODELS のキー不足: {', '.join(missing)}"
        )
    return {
        "label": str(entry["label"]),
        "provider": str(entry["provider"]),
        "type": "ローカル LLM" if entry["type"] == "local" else "API LLM",
        "color": str(entry["color"]),
        "color_dark": str(entry["colorDark"]),
    }

TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&family=Noto+Sans+JP:wght@400;500;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #ffffff; --bg-soft: #f7f8fa;
    --fg: #1a1a1a; --fg-soft: #4a4a4a; --muted-fg: #6b7280;
    --border: #e5e7eb; --primary: #2563eb;
    --accent: {color}; --accent-dark: {color_dark};
    --theme-accent: {accent}; --theme-accent-dark: {accent_dark};
    --success: #10b981; --danger: #ef4444; --warning: #f59e0b;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Plus Jakarta Sans', 'Noto Sans JP', sans-serif;
          background: var(--bg-soft); color: var(--fg);
          line-height: 1.7; font-size: 0.9375rem; -webkit-font-smoothing: antialiased; }}
  a {{ color: var(--primary); text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .hero {{ padding: 28px 24px 32px; color: #fff;
           background: linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%); }}
  .hero-inner {{ max-width: 1200px; margin: 0 auto; }}
  .hero a.back {{ color: #fff; opacity: 0.85; font-size: 0.875rem;
                  font-weight: 600; display: inline-block; margin-bottom: 12px; }}
  .hero h1 {{ font-size: 1.75rem; font-weight: 800; letter-spacing: -0.01em;
              color: #fff; margin-bottom: 4px; }}
  .hero .tag {{ display: inline-block; font-size: 0.75rem; font-weight: 800;
                letter-spacing: 0.06em; text-transform: uppercase;
                background: rgba(255,255,255,0.22); padding: 5px 12px;
                border-radius: 999px; margin-bottom: 12px; }}
  .hero .sub {{ font-size: 0.9rem; opacity: 0.9; }}
  .headline {{ background: var(--bg); border-bottom: 1px solid var(--border);
               padding: 20px 24px; }}
  .headline-inner {{ max-width: 1200px; margin: 0 auto;
                     display: flex; flex-wrap: wrap; gap: 16px 36px; align-items: baseline; }}
  .metric {{ display: flex; flex-direction: column; gap: 2px; }}
  .metric .value {{ font-size: 2rem; font-weight: 800; line-height: 1.1;
                    color: var(--theme-accent); font-family: 'JetBrains Mono', monospace; }}
  .metric .label {{ font-size: 0.75rem; font-weight: 800; letter-spacing: 0.08em;
                    text-transform: uppercase; color: var(--muted-fg); }}
  .wrap {{ max-width: 1200px; margin: 0 auto; padding: 24px; }}
  .panel {{ background: var(--bg); border: 1px solid var(--border);
            border-radius: 14px; overflow: hidden; margin-bottom: 20px; }}
  .panel-head {{ padding: 16px 20px; border-bottom: 1px solid var(--border);
                 display: flex; align-items: center; justify-content: space-between;
                 gap: 12px; flex-wrap: wrap; background: var(--bg-soft); }}
  .panel-head h2 {{ font-size: 0.9375rem; font-weight: 800; color: var(--fg); }}
  .badges {{ display: flex; flex-wrap: wrap; gap: 8px; }}
  .badge {{ display: inline-flex; align-items: center; gap: 6px;
            font-weight: 800; padding: 4px 12px; border-radius: 999px;
            font-size: 0.8125rem; }}
  .badge.pass {{ background: rgba(16,185,129,0.12); color: #047857; }}
  .badge.fail {{ background: rgba(239,68,68,0.12); color: #b91c1c; }}
  .badge.score {{ background: rgba(14,116,144,0.12); color: #0e7490; }}
  .panel-body {{ padding: 20px; }}
  .table-scroll {{ overflow-x: auto; }}
  table {{ border-collapse: collapse; width: 100%; min-width: 720px; }}
  th, td {{ padding: 9px 12px; border-bottom: 1px solid var(--border);
            text-align: left; vertical-align: top; }}
  th {{ font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em;
        color: var(--muted-fg); background: var(--bg-soft); white-space: nowrap; }}
  td {{ font-size: 0.875rem; }}
  tr.row-miss td {{ background: rgba(239,68,68,0.05); }}
  .mono {{ font-family: 'JetBrains Mono', monospace; word-break: break-word; }}
  .match-primary {{ color: #047857; font-weight: 800; }}
  .match-acceptable {{ color: #b45309; font-weight: 800; }}
  .match-miss {{ color: #b91c1c; font-weight: 800; }}
  ul {{ margin: 0; padding-left: 1.15rem; }}
  li {{ margin-bottom: 3px; }}
  .issues {{ color: #b91c1c; }}
  details {{ margin-top: 14px; }}
  summary {{ cursor: pointer; font-weight: 700; font-size: 0.8125rem;
             color: var(--muted-fg); }}
  .raw {{ margin-top: 10px; background: #1a1a1a; color: #e5e7eb;
          padding: 12px; border-radius: 6px; font-family: 'JetBrains Mono', monospace;
          font-size: 0.75rem; line-height: 1.6; overflow-x: auto;
          max-height: 420px; overflow-y: auto; white-space: pre-wrap; }}
  @media (max-width: 700px) {{
    .hero h1 {{ font-size: 1.45rem; }}
    .wrap {{ padding: 16px; }}
    .panel-body {{ padding: 14px; }}
  }}
</style>
</head>
<body>

<header class="hero">
  <div class="hero-inner">
    <a href="../../" class="back">← OreOre-Bench に戻る</a>
    <span class="tag">json-ladder ・ {provider} ・ {type_label}</span>
    <h1>{model_label}</h1>
    <p class="sub">長文随筆から、レベル1〜5 のスキーマで JSON を抽出させる書式遵守テスト。</p>
  </div>
</header>

<div class="headline">
  <div class="headline-inner">
    <div class="metric">
      <span class="value">parse {parse_pass_count}/{levels_total}</span>
      <span class="label">JSON パース成功</span>
    </div>
    <div class="metric">
      <span class="value">score {score_pct}%</span>
      <span class="label">answer-key 一致率</span>
    </div>
  </div>
</div>

<main class="wrap">
{body}
</main>

</body>
</html>
"""


def escape(value: object) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (dict, list)):
        return html.escape(json.dumps(value, ensure_ascii=False), quote=True)
    return html.escape(str(value), quote=True)


def as_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def match_label(match: str) -> str:
    if match == "primary":
        return '<span class="match-primary">✓ primary</span>'
    if match == "acceptable":
        return '<span class="match-acceptable">△ acceptable</span>'
    return '<span class="match-miss">✗ miss</span>'


def raw_by_level(data: object) -> dict[object, str]:
    raws: dict[object, str] = {}
    if isinstance(data, dict):
        for item in as_list(data.get("levels")):
            if isinstance(item, dict) and isinstance(item.get("raw"), str):
                raws[item.get("level")] = item["raw"]
    return raws


def verdict_rows(verdicts: list[object]) -> str:
    rows = []
    for verdict in verdicts:
        if not isinstance(verdict, dict):
            continue
        match = str(verdict.get("match", "miss"))
        row_class = ' class="row-miss"' if match == "miss" else ""
        rows.append(f"""
          <tr{row_class}>
            <td class="mono">{escape(verdict.get("path"))}</td>
            <td class="mono">{escape(verdict.get("got"))}</td>
            <td class="mono">{escape(verdict.get("expected"))}</td>
            <td>{match_label(match)}</td>
          </tr>""")
    if not rows:
        return ""
    return f"""
      <div class="table-scroll">
        <table>
          <thead>
            <tr><th>path</th><th>got</th><th>expected</th><th>match</th></tr>
          </thead>
          <tbody>{''.join(rows)}
          </tbody>
        </table>
      </div>"""


def render_level(level: dict[str, object], raw: str) -> str:
    valid = bool(level.get("valid_json"))
    schema_pass = bool(level.get("schema_pass"))
    issues = as_list(level.get("issues"))
    issues_html = ""
    if issues:
        items = "".join(f"<li>{escape(item)}</li>" for item in issues)
        issues_html = f'<ul class="issues">{items}</ul>'

    raw_html = ""
    if raw:
        raw_html = f"""
      <details>
        <summary>生応答を表示（{len(raw):,} chars）</summary>
        <pre class="raw">{escape(raw)}</pre>
      </details>"""

    return f"""
  <section class="panel">
    <div class="panel-head">
      <h2>レベル {escape(level.get("level"))}</h2>
      <div class="badges">
        <span class="badge {'pass' if valid else 'fail'}">{'JSON パース OK' if valid else 'JSON パース NG'}</span>
        <span class="badge {'pass' if schema_pass else 'fail'}">{'スキーマ準拠 PASS' if schema_pass else 'スキーマ準拠 FAIL'}</span>
        <span class="badge score">accuracy {escape(level.get("accuracy_pct", 0))}%</span>
      </div>
    </div>
    <div class="panel-body">
{verdict_rows(as_list(level.get("verdicts")))}
{issues_html}
{raw_html}
    </div>
  </section>
"""


def render_body(meta: dict[str, object], raws: dict[object, str]) -> str:
    levels = [item for item in as_list(meta.get("levels")) if isinstance(item, dict)]
    if not levels:
        issues = as_list(meta.get("issues")) or ["meta.json に levels がありません。"]
        items = "".join(f"<li>{escape(item)}</li>" for item in issues)
        return f"""
  <section class="panel">
    <div class="panel-head"><h2>検証結果なし</h2></div>
    <div class="panel-body"><ul class="issues">{items}</ul></div>
  </section>
"""
    return "".join(render_level(level, raws.get(level.get("level"), "")) for level in levels)


def render(model_dir: Path) -> bool:
    name = model_dir.name
    # 未知モデルは skip せず ModelDataError で落とす（表示情報の登録漏れを黙って通さない）
    info = model_info(name)

    output_path = model_dir / "output.json"
    meta_path = model_dir / "meta.json"
    if not output_path.exists():
        print(f"skip json-ladder/{name}: output.json", file=sys.stderr)
        return False
    if not meta_path.exists():
        print(f"skip json-ladder/{name}: meta.json", file=sys.stderr)
        return False

    try:
        data = json.loads(output_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = None
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    html_text = TEMPLATE.format(
        title=f"{info['label']} — json-ladder / OreOre-Bench",
        color=info["color"],
        color_dark=info["color_dark"],
        accent=ACCENT,
        accent_dark=ACCENT_DARK,
        provider=info["provider"],
        type_label=info["type"],
        model_label=info["label"],
        parse_pass_count=escape(str(meta.get("parse_pass_count", 0))),
        levels_total=escape(str(meta.get("levels_total", 5))),
        score_pct=escape(str(meta.get("score_pct", 0))),
        body=render_body(meta, raw_by_level(data)),
    )
    (model_dir / "output.html").write_text(html_text, encoding="utf-8")
    print(f"wrote {model_dir / 'output.html'}")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="指定モデルだけを生成する")
    parser.add_argument("--theme-dir", type=Path, default=THEME_DIR)
    args = parser.parse_args(argv)

    theme_dir = args.theme_dir.resolve()
    if not theme_dir.exists():
        print(f"theme not found: {theme_dir}", file=sys.stderr)
        return 1

    try:
        if args.model:
            model_dir = theme_dir / args.model
            if not model_dir.is_dir():
                print(f"model not found: {args.model}", file=sys.stderr)
                return 1
            return 0 if render(model_dir) else 1

        for model_dir in sorted(theme_dir.iterdir()):
            if model_dir.is_dir() and model_dir.name != "levels":
                render(model_dir)
    except ModelDataError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
