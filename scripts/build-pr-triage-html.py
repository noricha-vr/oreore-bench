#!/usr/bin/env python3
"""pr-triage テーマの output.html を生成する。
入力 JSON と検証済み meta.json から、判定結果と answer-key 突合を表で表示する。
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
THEME_DIR = ROOT / "public" / "pr-triage"

MODEL_INFO = {
    "claude-opus-4-8": {
        "label": "Claude Opus 4.8", "provider": "Anthropic", "type": "API LLM",
        "color": "#CC785C", "color_dark": "#A8553D",
    },
    "gemma-4-31b": {
        "label": "Gemma 4 31B", "provider": "Google", "type": "ローカル LLM",
        "color": "#4285F4", "color_dark": "#1A56DB",
    },
    "gemma-4-26b-a4b-qat": {
        "label": "Gemma 4 26B-A4B (QAT)", "provider": "Google", "type": "ローカル LLM",
        "color": "#4285F4", "color_dark": "#1A56DB",
    },
    "gemma-4-12b-qat": {
        "label": "Gemma 4 12B (QAT)", "provider": "Google", "type": "ローカル LLM",
        "color": "#4285F4", "color_dark": "#1A56DB",
    },
    "grok-4-5": {
        "label": "Grok 4.5", "provider": "xAI", "type": "API LLM",
        "color": "#3A3A3C", "color_dark": "#111111",
    },
    "laguna-s-2.1": {
        "label": "Laguna S 2.1", "provider": "poolside", "type": "API LLM",
        "color": "#0891B2", "color_dark": "#0E7490",
    },
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
  .verify-bar {{ background: var(--bg); border-bottom: 1px solid var(--border);
                 padding: 14px 24px; font-size: 0.875rem; }}
  .verify-bar-inner {{ max-width: 1200px; margin: 0 auto;
                       display: flex; flex-wrap: wrap; gap: 12px 24px; align-items: center; }}
  .badge {{ display: inline-flex; align-items: center; gap: 6px;
            font-weight: 800; padding: 4px 12px; border-radius: 999px;
            font-size: 0.875rem; }}
  .badge.pass {{ background: rgba(16,185,129,0.12); color: #047857; }}
  .badge.fail {{ background: rgba(239,68,68,0.12); color: #b91c1c; }}
  .badge.score {{ background: rgba(37,99,235,0.10); color: #1d4ed8; }}
  .stat {{ color: var(--fg-soft); }}
  .stat strong {{ color: var(--fg); font-weight: 800; }}
  .wrap {{ max-width: 1200px; margin: 0 auto; padding: 24px; }}
  .panel {{ background: var(--bg); border: 1px solid var(--border);
            border-radius: 14px; overflow: hidden; margin-bottom: 20px; }}
  .panel-head {{ padding: 16px 20px; border-bottom: 1px solid var(--border);
                 display: flex; align-items: center; justify-content: space-between;
                 gap: 12px; background: var(--bg-soft); }}
  .panel-head h2 {{ font-size: 0.875rem; font-weight: 800; letter-spacing: 0.06em;
                    text-transform: uppercase; color: var(--fg); }}
  .panel-body {{ padding: 20px; }}
  .table-scroll {{ overflow-x: auto; }}
  table {{ border-collapse: collapse; width: 100%; min-width: 980px; }}
  th, td {{ padding: 10px 12px; border-bottom: 1px solid var(--border);
            text-align: left; vertical-align: top; }}
  th {{ font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em;
        color: var(--muted-fg); background: var(--bg-soft); white-space: nowrap; }}
  td {{ font-size: 0.875rem; }}
  .mono {{ font-family: 'JetBrains Mono', monospace; }}
  .verdict {{ display: inline-block; padding: 2px 8px; border-radius: 999px;
              font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; font-weight: 700;
              background: var(--bg-soft); border: 1px solid var(--border); }}
  .match-primary {{ color: #047857; font-weight: 800; }}
  .match-acceptable {{ color: #b45309; font-weight: 800; }}
  .match-miss {{ color: #b91c1c; font-weight: 800; }}
  ul {{ margin: 0; padding-left: 1.15rem; }}
  li {{ margin-bottom: 3px; }}
  .summary {{ white-space: pre-wrap; color: var(--fg-soft); }}
  .priority {{ display: flex; flex-wrap: wrap; gap: 6px; }}
  .priority span {{ font-family: 'JetBrains Mono', monospace; font-size: 0.8125rem;
                    padding: 4px 8px; border-radius: 6px;
                    background: var(--bg-soft); border: 1px solid var(--border); }}
  .error {{ border: 1px solid #fecaca; background: #fef2f2; color: #991b1b;
            padding: 16px 20px; border-radius: 10px; }}
  .raw {{ margin-top: 12px; background: #1a1a1a; color: #e5e7eb;
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
    <span class="tag">pr-triage ・ {provider} ・ {type_label}</span>
    <h1>{model_label}</h1>
    <p class="sub">架空リポジトリの Open PR 10 件を、マージ可否・リスク・次アクション込みでトリアージ。</p>
  </div>
</header>

<div class="verify-bar">
  <div class="verify-bar-inner">
    <span class="badge {status_class}">{status_text}</span>
    <span class="badge score">agreement {agreement_pct}%</span>
    <span class="stat">primary <strong>{primary_match}</strong> / acceptable <strong>{acceptable_match}</strong></span>
    <span class="stat">出力 <strong>{raw_length}</strong> chars</span>
  </div>
</div>

<main class="wrap">
  {body}
</main>

</body>
</html>
"""


def escape(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def parse_json(raw: str) -> object | None:
    trimmed = raw.strip()
    # Prefer fenced JSON so braces in preamble examples do not become parse anchors.
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", trimmed, flags=re.I)
    text = fence.group(1).strip() if fence else trimmed
    if not fence:
        first = text.find("{")
        last = text.rfind("}")
        if first >= 0 and last > first:
            text = text[first:last + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        if not fence:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                pass
        return None


def as_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def list_html(items: object) -> str:
    values = as_list(items)
    if not values:
        return '<span class="mono">[]</span>'
    return "<ul>" + "".join(f"<li>{escape(item)}</li>" for item in values) + "</ul>"


def match_label(match: str) -> str:
    if match == "primary":
        return '<span class="match-primary">✓ primary</span>'
    if match == "acceptable":
        return '<span class="match-acceptable">△ acceptable</span>'
    return '<span class="match-miss">✗ miss</span>'


def render_body(data: object | None, meta: dict[str, object], raw: str) -> str:
    if data is None or not isinstance(data, dict):
        return f"""
  <section class="panel">
    <div class="panel-body">
      <div class="error">
        <strong>JSON として解析できませんでした。</strong>
        <pre class="raw">{escape(raw)}</pre>
      </div>
    </div>
  </section>
"""

    triage_by_pr = {}
    for item in as_list(data.get("triage")):
        if isinstance(item, dict):
            triage_by_pr[item.get("pr")] = item

    verdict_meta = {
        item.get("pr"): item
        for item in as_list(meta.get("verdicts"))
        if isinstance(item, dict)
    }

    rows = []
    for pr in range(101, 111):
        item = triage_by_pr.get(pr, {})
        vm = verdict_meta.get(pr, {})
        verdict = item.get("verdict") if isinstance(item, dict) else None
        expected = vm.get("expected")
        match = vm.get("match", "miss")
        rows.append(f"""
        <tr>
          <td class="mono">{pr}</td>
          <td><span class="verdict">{escape(verdict)}</span></td>
          <td><span class="verdict">{escape(expected)}</span></td>
          <td>{match_label(str(match))}</td>
          <td>{list_html(item.get("reasons") if isinstance(item, dict) else [])}</td>
          <td>{list_html(item.get("actions") if isinstance(item, dict) else [])}</td>
          <td><span class="verdict">{escape(item.get("risk_if_merged") if isinstance(item, dict) else None)}</span></td>
        </tr>""")

    priority = as_list(data.get("priority_order"))
    priority_html = "".join(f"<span>{escape(pr)}</span>" for pr in priority) or '<span class="mono">[]</span>'
    summary = escape(data.get("summary", ""))

    issues = as_list(meta.get("issues"))
    issues_html = ""
    if issues:
        issues_html = f"""
  <section class="panel">
    <div class="panel-head"><h2>Validation Issues</h2></div>
    <div class="panel-body">{list_html(issues)}</div>
  </section>
"""

    return f"""
  <section class="panel">
    <div class="panel-head">
      <h2>PR verdicts</h2>
      <a href="./output.json" target="_blank">JSON →</a>
    </div>
    <div class="panel-body">
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>PR</th>
              <th>model verdict</th>
              <th>primary</th>
              <th>match</th>
              <th>reasons</th>
              <th>actions</th>
              <th>risk</th>
            </tr>
          </thead>
          <tbody>{''.join(rows)}
          </tbody>
        </table>
      </div>
    </div>
  </section>

  <section class="panel">
    <div class="panel-head"><h2>Priority Order</h2></div>
    <div class="panel-body"><div class="priority">{priority_html}</div></div>
  </section>

  <section class="panel">
    <div class="panel-head"><h2>Summary</h2></div>
    <div class="panel-body"><p class="summary">{summary}</p></div>
  </section>
{issues_html}
"""


def render(model_dir: Path) -> None:
    name = model_dir.name
    info = MODEL_INFO.get(name)
    if not info:
        print(f"skip pr-triage/{name}: unknown model", file=sys.stderr)
        return

    output_path = model_dir / "output.json"
    meta_path = model_dir / "meta.json"
    if not output_path.exists():
        print(f"skip pr-triage/{name}: output.json", file=sys.stderr)
        return
    if not meta_path.exists():
        print(f"skip pr-triage/{name}: meta.json", file=sys.stderr)
        return

    raw = output_path.read_text(encoding="utf-8")
    data = parse_json(raw)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    schema_pass = bool(meta.get("schema_pass"))

    html_text = TEMPLATE.format(
        title=f"{info['label']} — pr-triage / OreOre-Bench",
        color=info["color"],
        color_dark=info["color_dark"],
        provider=info["provider"],
        type_label=info["type"],
        model_label=info["label"],
        status_class="pass" if schema_pass else "fail",
        status_text="スキーマ準拠 PASS" if schema_pass else "スキーマ準拠 FAIL",
        agreement_pct=meta.get("agreement_pct", 0),
        primary_match=meta.get("primary_match", 0),
        acceptable_match=meta.get("acceptable_match", 0),
        raw_length=f"{int(meta.get('raw_length', 0)):,}",
        body=render_body(data, meta, raw),
    )
    (model_dir / "output.html").write_text(html_text, encoding="utf-8")
    print(f"wrote {model_dir / 'output.html'}")


def main() -> int:
    if not THEME_DIR.exists():
        print(f"theme not found: {THEME_DIR}", file=sys.stderr)
        return 1
    for model_dir in sorted(THEME_DIR.iterdir()):
        if model_dir.is_dir():
            render(model_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
