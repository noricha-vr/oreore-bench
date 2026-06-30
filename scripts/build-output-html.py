#!/usr/bin/env python3
"""各モデルの output.json + meta.json を読み込んで、左右 2 カラム表示の
output.html を生成する。
"""
from __future__ import annotations
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
PUBLIC_DIR = ROOT / "public"
THEMES = ["json-quiz-easy", "json-quiz-medium", "json-quiz-hard"]
THEME_LABELS = {
    "json-quiz-easy": "最小スキーマ",
    "json-quiz-medium": "基本スキーマ",
    "json-quiz-hard": "複雑スキーマ",
}

# モデルの色（トップページの MODELS と同期）
MODEL_INFO = {
    "claude-opus-4-8": {
        "label": "Claude Opus 4.8",
        "provider": "Anthropic",
        "type": "API LLM",
        "color": "#CC785C",
        "color_dark": "#A8553D",
    },
    "gemma-4-31b": {
        "label": "Gemma 4 31B",
        "provider": "Google",
        "type": "ローカル LLM",
        "color": "#4285F4",
        "color_dark": "#1A56DB",
    },
    "gemma-4-26b-a4b-qat": {
        "label": "Gemma 4 26B-A4B (QAT)",
        "provider": "Google",
        "type": "ローカル LLM",
        "color": "#4285F4",
        "color_dark": "#1A56DB",
    },
    "gemma-4-12b-qat": {
        "label": "Gemma 4 12B (QAT)",
        "provider": "Google",
        "type": "ローカル LLM",
        "color": "#4285F4",
        "color_dark": "#1A56DB",
    },
}

TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&family=Noto+Sans+JP:wght@400;500;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css" crossorigin="anonymous" referrerpolicy="no-referrer">
<style>
  :root {{
    --bg: #ffffff;
    --bg-soft: #f7f8fa;
    --fg: #1a1a1a;
    --fg-soft: #4a4a4a;
    --muted-fg: #6b7280;
    --border: #e5e7eb;
    --primary: #2563eb;
    --accent: {color};
    --accent-dark: {color_dark};
    --success: #10b981;
    --danger: #ef4444;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Plus Jakarta Sans', 'Noto Sans JP', sans-serif;
    background-color: var(--bg-soft);
    color: var(--fg);
    line-height: 1.7;
    font-size: 0.9375rem;
    -webkit-font-smoothing: antialiased;
  }}
  a {{ color: var(--primary); text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}

  /* Hero */
  .hero {{
    padding: 28px 24px 32px;
    background: linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%);
    color: #ffffff;
  }}
  .hero-inner {{ max-width: 1200px; margin: 0 auto; }}
  .hero a.back {{
    color: #ffffff; opacity: 0.85; font-size: 0.875rem; font-weight: 600;
    display: inline-block; margin-bottom: 12px;
  }}
  .hero a.back:hover {{ opacity: 1; text-decoration: underline; }}
  .hero .tag {{
    display: inline-block; font-size: 0.75rem; font-weight: 800;
    letter-spacing: 0.06em; text-transform: uppercase;
    background: rgba(255,255,255,0.22); padding: 5px 12px;
    border-radius: 999px; margin-bottom: 12px;
  }}
  .hero h1 {{
    font-size: 1.75rem; font-weight: 800; letter-spacing: -0.01em;
    color: #ffffff; margin-bottom: 4px;
  }}
  .hero .sub {{ font-size: 0.9rem; opacity: 0.9; }}

  /* Verify bar */
  .verify-bar {{
    background: var(--bg);
    border-bottom: 1px solid var(--border);
    padding: 14px 24px;
    font-size: 0.875rem;
  }}
  .verify-bar-inner {{
    max-width: 1200px; margin: 0 auto;
    display: flex; flex-wrap: wrap; gap: 12px 24px;
    align-items: center;
  }}
  .vb-status {{
    display: inline-flex; align-items: center; gap: 6px;
    font-weight: 800; padding: 4px 12px; border-radius: 999px;
    font-size: 0.875rem;
  }}
  .vb-status.pass {{ background: rgba(16,185,129,0.12); color: #047857; }}
  .vb-status.fail {{ background: rgba(239,68,68,0.12); color: #b91c1c; }}
  .vb-stat {{
    display: inline-flex; align-items: center; gap: 6px;
    color: var(--fg-soft);
  }}
  .vb-stat strong {{ color: var(--fg); font-weight: 800; }}
  .vb-stat.ng strong {{ color: var(--danger); }}
  .vb-stat.ok strong {{ color: var(--success); }}

  /* Two-pane layout */
  .panes {{
    max-width: 1200px;
    margin: 0 auto;
    padding: 24px;
    display: grid;
    grid-template-columns: minmax(0, 5fr) minmax(0, 7fr);
    gap: 24px;
  }}
  @media (max-width: 900px) {{
    .panes {{ grid-template-columns: 1fr; }}
  }}

  .pane {{
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 14px;
    overflow: hidden;
  }}
  .pane-header {{
    padding: 16px 20px;
    border-bottom: 1px solid var(--border);
    display: flex; align-items: center; justify-content: space-between;
    background: var(--bg-soft);
  }}
  .pane-header h2 {{
    font-size: 0.875rem; font-weight: 800; letter-spacing: 0.06em;
    text-transform: uppercase; color: var(--fg);
  }}
  .pane-header .pane-meta {{ font-size: 0.75rem; color: var(--muted-fg); font-weight: 600; }}

  .pane-body {{ padding: 20px; }}

  /* Left pane: input */
  .input-text {{
    white-space: pre-wrap;
    font-family: 'Noto Sans JP', sans-serif;
    font-size: 0.875rem;
    line-height: 1.9;
    color: var(--fg);
    max-height: 1200px;
    overflow-y: auto;
  }}
  .input-text::-webkit-scrollbar {{ width: 8px; }}
  .input-text::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 4px; }}

  /* Right pane: quiz */
  .quiz-card {{
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px;
    margin-bottom: 12px;
  }}
  .quiz-card-head {{
    display: flex; align-items: baseline; gap: 10px;
    margin-bottom: 10px;
  }}
  .quiz-num {{
    flex-shrink: 0;
    width: 26px; height: 26px;
    background: var(--accent); color: #ffffff;
    border-radius: 50%;
    display: inline-flex; align-items: center; justify-content: center;
    font-weight: 800; font-size: 0.8125rem;
  }}
  .quiz-q {{
    font-weight: 700; font-size: 0.9375rem;
    line-height: 1.6; color: var(--fg);
  }}
  .quiz-choices {{ list-style: none; padding: 0; margin: 8px 0 10px 0; }}
  .quiz-choice {{
    display: flex; align-items: flex-start; gap: 10px;
    padding: 6px 10px; border-radius: 6px;
    font-size: 0.875rem;
    color: var(--fg-soft);
    margin-bottom: 3px;
  }}
  .quiz-choice .label {{
    flex-shrink: 0;
    display: inline-flex; align-items: center; justify-content: center;
    width: 24px; height: 24px;
    border: 1px solid var(--border);
    border-radius: 6px;
    font-weight: 800; font-size: 0.8125rem;
    color: var(--muted-fg);
  }}
  .quiz-choice.correct {{
    background: rgba(16,185,129,0.08);
  }}
  .quiz-choice.correct .label {{
    background: var(--success);
    border-color: var(--success);
    color: #ffffff;
  }}
  .quiz-choice.correct .text {{ color: var(--fg); font-weight: 600; }}
  .quiz-explain {{
    font-size: 0.8125rem;
    color: var(--muted-fg);
    background: var(--bg-soft);
    padding: 8px 12px;
    border-radius: 6px;
    line-height: 1.6;
  }}
  .quiz-explain strong {{ color: var(--fg); }}

  /* Error card */
  .error-card {{
    border: 1px solid #fecaca;
    background: #fef2f2;
    color: #991b1b;
    padding: 16px 20px;
    border-radius: 10px;
    margin-bottom: 12px;
  }}
  .error-card h3 {{ font-size: 0.9375rem; font-weight: 800; margin-bottom: 6px; }}
  .error-card ul {{ margin: 8px 0 0 1.25rem; font-size: 0.875rem; }}
  .raw-output {{
    margin-top: 12px;
    background: #1a1a1a;
    color: #e5e7eb;
    padding: 12px;
    border-radius: 6px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    line-height: 1.6;
    overflow-x: auto;
    max-height: 400px;
    overflow-y: auto;
    white-space: pre-wrap;
  }}
</style>
</head>
<body>

<header class="hero">
  <div class="hero-inner">
    <a href="../../" class="back">← OreOre-Bench に戻る</a>
    <span class="tag">{theme_name} ・ {theme_label} ・ {provider}</span>
    <h1>{model_label}</h1>
    <p class="sub">同じ Wikipedia 記事から JSON クイズを 1 ショット生成。スキーマ準拠を検証。</p>
  </div>
</header>

<div class="verify-bar">
  <div class="verify-bar-inner">
    <span class="vb-status {status_class}">
      <i class="fa-solid {status_icon}"></i>
      {status_text}
    </span>
    <span class="vb-stat {q_class}">quiz <strong>{quiz_count}/{expected_count}</strong></span>
    <span class="vb-stat {c_class}">choices <strong>{choices_status}</strong></span>
    <span class="vb-stat {a_class}">answers <strong>{answers_status}</strong></span>
    {extra_stats}
    <span class="vb-stat">出力 <strong>{raw_length}</strong> chars</span>
  </div>
</div>

<main class="panes">
  <section class="pane">
    <div class="pane-header">
      <h2>入力（Wikipedia「大規模言語モデル」）</h2>
      <span class="pane-meta"><a href="../input.html" target="_blank">全文 →</a></span>
    </div>
    <div class="pane-body">
      <pre class="input-text" id="input-text">読み込み中...</pre>
    </div>
  </section>

  <section class="pane">
    <div class="pane-header">
      <h2>出力（10 問四択クイズ）</h2>
      <span class="pane-meta"><a href="./output.json" target="_blank">JSON →</a></span>
    </div>
    <div class="pane-body" id="quiz-body"></div>
  </section>
</main>

<script>
  // 入力本文を読み込み
  fetch('../input.md').then(r => r.text()).then(t => {{
    document.getElementById('input-text').textContent = t;
  }}).catch(() => {{
    document.getElementById('input-text').textContent = '読み込み失敗';
  }});

  const meta = {meta_json};

  function renderQuiz(data) {{
    const body = document.getElementById('quiz-body');
    if (!Array.isArray(data?.quiz)) {{
      body.innerHTML = '';
      return;
    }}
    body.innerHTML = data.quiz.map((q, i) => {{
      const num = q.id ?? (i + 1);
      const question = q.question || '(question 欠落)';
      const explain = q.explanation || '';
      const ans = q.answer;
      const choices = Array.isArray(q.choices) ? q.choices : [];
      const choicesHtml = choices.map(c => `
        <li class="quiz-choice ${{c?.label === ans ? 'correct' : ''}}">
          <span class="label">${{c?.label ?? '?'}}</span>
          <span class="text">${{(c?.text ?? '').replace(/[<>&]/g, ch => ({{'<':'&lt;','>':'&gt;','&':'&amp;'}}[ch]))}}</span>
        </li>
      `).join('');
      return `
        <article class="quiz-card">
          <div class="quiz-card-head">
            <span class="quiz-num">${{num}}</span>
            <span class="quiz-q">${{question.replace(/[<>&]/g, ch => ({{'<':'&lt;','>':'&gt;','&':'&amp;'}}[ch]))}}</span>
          </div>
          <ul class="quiz-choices">${{choicesHtml}}</ul>
          ${{explain ? `<div class="quiz-explain"><strong>解説</strong> ${{explain.replace(/[<>&]/g, ch => ({{'<':'&lt;','>':'&gt;','&':'&amp;'}}[ch]))}}</div>` : ''}}
        </article>
      `;
    }}).join('');
  }}

  function renderError(reason, raw) {{
    const body = document.getElementById('quiz-body');
    body.innerHTML = `
      <div class="error-card">
        <h3><i class="fa-solid fa-triangle-exclamation"></i> JSON として解析できませんでした</h3>
        <p>このモデルは長文 JSON 出力の途中で構造が崩れています。これが json-quiz ベンチの「失敗の見せ場」です。</p>
        ${{meta.issues && meta.issues.length ? `<ul>${{meta.issues.slice(0,5).map(i => `<li>${{i}}</li>`).join('')}}</ul>` : ''}}
        <details style="margin-top:12px;">
          <summary style="cursor:pointer; font-weight:700;">生出力を見る</summary>
          <pre class="raw-output">${{(raw || '').replace(/[<>&]/g, ch => ({{'<':'&lt;','>':'&gt;','&':'&amp;'}}[ch]))}}</pre>
        </details>
      </div>
    `;
  }}

  // output.json を読み込み
  fetch('./output.json').then(r => r.text()).then(raw => {{
    if (!meta.valid_json) {{
      renderError('parse failed', raw);
      return;
    }}
    try {{
      // PROMPT.md と同様、たまにコードフェンスが残るのでゆるく剥がす
      let s = raw.trim();
      s = s.replace(/^```(?:json)?\\s*/i, '').replace(/```\\s*$/i, '').trim();
      const idx = s.indexOf('{{');
      if (idx > 0) s = s.slice(idx);
      const data = JSON.parse(s);
      renderQuiz(data);
    }} catch (e) {{
      renderError(e.message, raw);
    }}
  }}).catch(e => renderError(e.message, ''));
</script>

</body>
</html>
"""

def render(theme_name: str, model_dir: Path) -> None:
    model_name = model_dir.name
    info = MODEL_INFO.get(model_name)
    if not info:
        print(f"skip {theme_name}/{model_name}: not in MODEL_INFO", file=sys.stderr)
        return

    meta_path = model_dir / "meta.json"
    if not meta_path.exists():
        print(f"skip {theme_name}/{model_name}: meta.json not found", file=sys.stderr)
        return
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    schema_pass = meta.get("schema_pass", False)
    status_class = "pass" if schema_pass else "fail"
    status_icon = "fa-circle-check" if schema_pass else "fa-circle-xmark"
    status_text = "スキーマ準拠 PASS" if schema_pass else "スキーマ準拠 FAIL"

    quiz_count = meta.get("quiz_count", 0)
    expected = meta.get("expected_quiz_count", 10)
    q_class = "ok" if quiz_count == expected else "ng"

    each_ok = meta.get("each_choices_ok", meta.get("each_choices_4", False))
    c_class = "ok" if each_ok else "ng"
    choices_status = "全 ✓" if each_ok else "崩れあり"

    ans_ok = meta.get("all_answers_valid", False)
    a_class = "ok" if ans_ok else "ng"
    answers_status = "OK" if ans_ok else "NG"

    raw_length = meta.get("raw_length", 0)

    # hard 用の追加統計
    extra_stats = ""
    if theme_name == "json-quiz-hard" and meta.get("valid_json"):
        inv_diff = meta.get("invalid_difficulty", 0)
        miss_rt = meta.get("missing_related_topics", 0)
        inv_se = meta.get("invalid_source_excerpt", 0)
        diff_class = "ok" if inv_diff == 0 else "ng"
        rt_class = "ok" if miss_rt == 0 else "ng"
        se_class = "ok" if inv_se == 0 else "ng"
        extra_stats = (
            f'<span class="vb-stat {diff_class}">difficulty <strong>{"OK" if inv_diff == 0 else f"NG×{inv_diff}"}</strong></span>'
            f'<span class="vb-stat {rt_class}">related_topics <strong>{"OK" if miss_rt == 0 else f"NG×{miss_rt}"}</strong></span>'
            f'<span class="vb-stat {se_class}">source_excerpt <strong>{"OK" if inv_se == 0 else f"NG×{inv_se}"}</strong></span>'
        )

    html = TEMPLATE.format(
        title=f"{info['label']} — {theme_name} / OreOre-Bench",
        color=info["color"],
        color_dark=info["color_dark"],
        theme_name=theme_name,
        theme_label=THEME_LABELS.get(theme_name, ""),
        provider=info["provider"],
        type_label=info["type"],
        model_label=info["label"],
        status_class=status_class,
        status_icon=status_icon,
        status_text=status_text,
        quiz_count=quiz_count,
        expected_count=expected,
        q_class=q_class,
        c_class=c_class,
        choices_status=choices_status,
        a_class=a_class,
        answers_status=answers_status,
        extra_stats=extra_stats,
        raw_length=f"{raw_length:,}",
        meta_json=json.dumps(meta, ensure_ascii=False),
    )

    (model_dir / "output.html").write_text(html, encoding="utf-8")
    print(f"wrote {model_dir / 'output.html'}")


def main() -> int:
    for theme in THEMES:
        theme_dir = PUBLIC_DIR / theme
        if not theme_dir.exists():
            continue
        for d in sorted(theme_dir.iterdir()):
            if d.is_dir():
                render(theme, d)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
