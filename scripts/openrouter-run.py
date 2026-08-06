#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""OpenRouter API 経由で 1 テーマ × 1 モデルを生成し、usage 実測入りの run.json を書く。

PR #24 / #25 で毎回使い捨てスクリプトを書いていた手順（scratchpad の gen-opus5.py 相当）を
リポジトリに固定したもの。scripts/add-model.sh --runner openrouter から呼ばれる。

テーマ種別:
  - HTML テーマ (index.html を出力): PROMPT.md をそのまま投げる
  - JSON テーマ (input.md がある / output.json を出力): gen-questions.py の build_prompt を再現

出力:
  - public/<theme>/<model>/index.html または output.json
  - public/<theme>/<model>/run.json (harness=openrouter-api, usage 実測, cost 実単価)

使い方:
  uv run scripts/openrouter-run.py --theme lp-nishibi --model claude-opus-5
  uv run scripts/openrouter-run.py --theme pr-triage --model kimi-k3 --reasoning-effort high
  uv run scripts/openrouter-run.py --theme lp-nishibi --model kimi-k3 --dry-run  # API を叩かず前提だけ検証

Exit: 0 成功 / 1 引数・前提不備 / 2 API エラー / 3 usage 欠損（実測 run.json を書けない）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
SCRIPTS = ROOT / "scripts"
PRICING_PATH = SCRIPTS / "pricing.json"
MODEL_MAP_PATH = SCRIPTS / "model-map.json"

DEFAULT_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# theme / model はディレクトリ名になるため、パス区切りや `..` を含む値を弾く
NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def resolve_api_url() -> str:
    """API エンドポイントを決める。

    既定は本番。OPENROUTER_API_URL はスタブサーバを差し込んで非 dry-run 経路を
    課金なしで検証するためのテスト用フックだが、API キーを載せて送る先なので
    https か localhost のみに限定する（平文 http で外部ホストへ鍵を送らせない）。
    """
    url = os.environ.get("OPENROUTER_API_URL", "").strip()
    if not url:
        return DEFAULT_API_URL
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme == "https":
        return url
    if parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost", "::1"):
        return url
    raise RuntimeError(
        "OPENROUTER_API_URL must use https, or http on localhost only "
        f"(got scheme={parsed.scheme!r} host={parsed.hostname!r}). "
        "The API key is sent to this URL."
    )

# gen-questions.py の build_prompt と同一の定数（JSON テーマのプロンプト再現）
JSON_PROMPT_SUFFIX = "\n\n---\n\nJSON 単体で出力してください。"
INPUT_PLACEHOLDER = "[input.md の本文をここに展開してプロンプトに含める]"

# PR #25 実績値。reasoning を含めても打ち切られない実用上限として固定する
DEFAULT_MAX_TOKENS = 65000
REQUEST_TIMEOUT_SECONDS = 1800

# フェンスは「行頭のバッククォート3個以上 + 任意の言語指定」で開き、
# 開きと同数以上のバッククォートだけの行で閉じる（CommonMark 準拠の簡易版）。
#
# 行頭アンカー (^ + MULTILINE) が必須な理由:
#   - HTML 本文中の <pre><code>``` を閉じフェンスと誤認して本文が途中で切れる事故を防ぐ
#     （インデントされた ``` や行内の ``` にマッチしなくなる）
#   - 先行する ```json 等の別言語ブロックと開き/閉じのペアリングがずれるのを防ぐ
_FENCE_OPEN_RE = re.compile(
    r"^[ \t]*(?P<ticks>`{3,})[ \t]*(?P<lang>[A-Za-z0-9._+-]*)[ \t]*$",
    re.MULTILINE,
)
# 本文が HTML かどうかの判定。先頭だけを見るとライセンスコメントや長い
# <!-- --> が先行した時に取りこぼすため全文を検索する。
_HTML_MARKER_RE = re.compile(r"<!doctype\s+html|<html[\s>]", re.IGNORECASE)


class OpenRouterError(RuntimeError):
    """API 呼び出しが失敗した（exit 2 相当）。"""


class UsageMissingError(RuntimeError):
    """usage 実測が取れず run.json を書けない（exit 3 相当）。"""


class TruncatedOutputError(RuntimeError):
    """応答が途中で切れており、成果物として保存できない（exit 2 相当）。"""


# API キーらしき文字列。エラー本文にリクエストが反射された時の漏洩を防ぐ。
_SECRET_RE = re.compile(r"sk-or-[A-Za-z0-9_-]+|Bearer\s+[A-Za-z0-9._-]{8,}")


def mask_secrets(text: str) -> str:
    """ログ出力前に API キーらしき文字列を伏せる。"""
    return _SECRET_RE.sub("***", text)


def _iter_fenced_blocks(text: str):
    """行頭フェンスで囲まれたブロックを (lang, body) で順に返す。

    開きフェンスと同数以上のバッククォートだけの行を閉じとみなす。閉じが無い
    ブロック（max_tokens 打ち切り等）は未完成なので yield しない。
    """
    pos = 0
    while True:
        open_match = _FENCE_OPEN_RE.search(text, pos)
        if not open_match:
            return
        ticks = open_match.group("ticks")
        lang = open_match.group("lang").lower()
        body_start = open_match.end()
        # 本文直後の改行を1つ食う
        if text[body_start : body_start + 2] == "\r\n":
            body_start += 2
        elif text[body_start : body_start + 1] == "\n":
            body_start += 1

        close_re = re.compile(rf"^[ \t]*`{{{len(ticks)},}}[ \t]*$", re.MULTILINE)
        close_match = close_re.search(text, body_start)
        if not close_match:
            # 閉じフェンスが無い = 打ち切りの疑い。以降に有効なブロックは無い
            return
        yield lang, text[body_start : close_match.start()]
        pos = close_match.end()


def extract_fenced_html(text: str) -> tuple[str, bool]:
    """応答テキストから HTML 本体を取り出す。

    「前置き文 + ```html フェンス + 末尾解説」パターンからフェンス内だけを抽出する。
    フェンスが無い（= 生 HTML をそのまま返した）場合は入力をそのまま返す。

    Args:
        text: モデル応答の生テキスト。

    Returns:
        (html, extracted): extracted=True ならフェンス抽出を行った。
    """
    # HTML らしいフェンスに限定する（説明中の ```bash / ```json 等を誤って拾わない）
    html_like = [body for _lang, body in _iter_fenced_blocks(text) if _looks_like_html(body)]
    if not html_like:
        return text.strip(), False
    # 複数ある場合は最長を採用（分割説明の断片より本体が長い）
    body = max(html_like, key=len)
    return body.strip(), True


def _looks_like_html(text: str) -> bool:
    """HTML 文書らしさを判定する。

    先頭 N 文字に限定すると、ライセンスヘッダや長い <!-- --> コメントが先行した
    場合に取りこぼすため全文を検索する。
    """
    return _HTML_MARKER_RE.search(text) is not None


def detect_theme_kind(theme_dir: Path) -> str:
    """テーマが JSON 系か HTML 系かを判定する。

    input.md があれば JSON テーマ（pr-triage 等）、無ければ HTML テーマ。
    既存モデルディレクトリの出力ファイル名でも裏取りする。
    """
    if (theme_dir / "levels").is_dir():
        return "json-levels"
    if (theme_dir / "input.md").exists():
        return "json"
    for model_dir in sorted(theme_dir.iterdir()):
        if not model_dir.is_dir():
            continue
        if (model_dir / "output.json").exists():
            return "json"
        if (model_dir / "index.html").exists():
            return "html"
    return "html"


def build_prompt(theme_dir: Path, kind: str) -> str:
    """テーマ種別に応じたプロンプトを組む。

    JSON テーマは gen-questions.py の build_prompt と同一手順（PROMPT.md のプレースホルダを
    input.md で置換 + 「JSON 単体で出力してください。」の接尾辞）。
    HTML テーマは PROMPT.md をそのまま投げる。
    """
    prompt_md = (theme_dir / "PROMPT.md").read_text(encoding="utf-8")
    if kind != "json":
        return prompt_md.strip()

    input_path = theme_dir / "input.md"
    if INPUT_PLACEHOLDER in prompt_md:
        if not input_path.exists():
            raise FileNotFoundError(f"input file not found: {input_path}")
        prompt_md = prompt_md.replace(INPUT_PLACEHOLDER, "")
        input_md = input_path.read_text(encoding="utf-8")
        prompt_md = f"{prompt_md.strip()}\n\n{input_md.strip()}"
    return f"{prompt_md.strip()}{JSON_PROMPT_SUFFIX}"


def load_api_key() -> str:
    """OPENROUTER_API_KEY を環境変数、なければリポジトリ直下 .env から読む。

    キー実値はログに出さない（Fail Fast のメッセージも名前のみ）。
    """
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if key:
        return key
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            # `export FOO=bar` 形式にも対応する
            name = name.strip()
            if name.startswith("export "):
                name = name[len("export ") :].strip()
            if name != "OPENROUTER_API_KEY":
                continue
            parsed = _parse_env_value(value)
            if parsed:
                return parsed
    raise RuntimeError(
        "OPENROUTER_API_KEY is not set. Export it or add it to .env (value is never logged)."
    )


def _parse_env_value(raw: str) -> str:
    """.env の値部分を解釈する。

    クォートされていれば中身をそのまま返し、されていなければ行末コメント
    （` #` 以降）を落とす。クォート内の # はコメントではないので残す。
    """
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    # 裸の値は最初の # 以降をコメントとして落とす
    return value.split("#", 1)[0].strip()


def resolve_model_id(model_slug: str) -> str:
    """model-map.json から OpenRouter モデル ID を引く。type=api でないものは拒否。"""
    if not MODEL_MAP_PATH.exists():
        raise RuntimeError(f"model-map.json not found: {MODEL_MAP_PATH}")
    model_map = json.loads(MODEL_MAP_PATH.read_text(encoding="utf-8"))
    entry = model_map.get(model_slug)
    if entry is None:
        raise RuntimeError(
            f"'{model_slug}' is not in model-map.json. Add it as "
            f'"{model_slug}": {{"id": "<openrouter-id>", "type": "api"}} first.'
        )
    model_id = entry.get("id") if isinstance(entry, dict) else entry
    model_type = entry.get("type") if isinstance(entry, dict) else None
    # type を先に見る: type=local は id が null のこともあり、
    # 「id が無い」より「runner の対象外」の方が原因が伝わる
    if model_type != "api":
        raise RuntimeError(
            f"'{model_slug}' has type={model_type!r} in model-map.json. "
            "The openrouter runner only handles type=api models."
        )
    if not model_id:
        raise RuntimeError(f"'{model_slug}' has no OpenRouter model id in model-map.json.")
    return model_id


def load_pricing(model_slug: str) -> dict:
    """pricing.json から単価を引く。API モデルで単価不在は $0 表示事故になるので Fail Fast。"""
    if not PRICING_PATH.exists():
        raise RuntimeError(f"pricing.json not found: {PRICING_PATH}. Run fetch-pricing.py first.")
    pricing_all = json.loads(PRICING_PATH.read_text(encoding="utf-8"))
    pricing = pricing_all.get(model_slug)
    if not pricing:
        raise RuntimeError(
            f"'{model_slug}' has no pricing in pricing.json. "
            "Run 'uv run scripts/fetch-pricing.py' after adding it to model-map.json."
        )
    return pricing


def call_openrouter(
    api_key: str,
    model_id: str,
    prompt: str,
    reasoning_effort: str,
    max_tokens: int,
) -> dict:
    """OpenRouter chat/completions を 1 回叩いてレスポンス JSON を返す。

    usage.include=true で実測トークン・コストを要求する（accounting 拡張）。
    reasoning_effort が "none" の場合は reasoning パラメータを送らない。
    """
    payload: dict = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "usage": {"include": True},
    }
    if reasoning_effort != "none":
        payload["reasoning"] = {"effort": reasoning_effort}

    req = urllib.request.Request(
        resolve_api_url(),
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://oreore-bench.pages.dev/",
            "X-Title": "oreore-bench",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # エラー本文にリクエストが反射されることがあるため、鍵らしき文字列を必ず伏せる
        detail = mask_secrets(exc.read().decode("utf-8", errors="replace")[:500])
        raise OpenRouterError(f"HTTP {exc.code} from OpenRouter: {detail}") from exc
    except urllib.error.URLError as exc:
        raise OpenRouterError(f"network error calling OpenRouter: {exc.reason}") from exc

    # OpenRouter は HTTP 200 でも body に error を載せることがある（Fail Fast で握り潰さない）
    if isinstance(body.get("error"), dict):
        raise OpenRouterError(f"OpenRouter returned error: {body['error'].get('message')}")
    choices = body.get("choices")
    if not choices:
        raise OpenRouterError("OpenRouter response has no choices")
    return body


def check_not_truncated(body: dict, model_slug: str) -> None:
    """max_tokens 打ち切りを検出して停止する。

    finish_reason="length" は本文が途中で切れていることを意味する。そのまま保存すると
    「未終端フェンス付きの壊れた HTML」がベンチ成果物として残り、モデルの実力ではなく
    こちらの設定ミスを記録してしまう。
    """
    finish_reason = (body.get("choices") or [{}])[0].get("finish_reason")
    if finish_reason == "length":
        raise TruncatedOutputError(
            f"{model_slug}: response was truncated by max_tokens (finish_reason='length'). "
            "Re-run with a larger --max-tokens. Nothing was written."
        )


def verify_html_complete(html: str, model_slug: str) -> None:
    """抽出後の HTML が文書として閉じているかを確認する。

    finish_reason を返さないプロバイダもあるため、成果物側からも打ち切りを検出する
    二重の安全網。
    """
    if not re.search(r"</html\s*>", html, re.IGNORECASE):
        raise TruncatedOutputError(
            f"{model_slug}: extracted HTML has no closing </html> tag "
            "(truncated response or unterminated fence). Nothing was written."
        )


def read_usage(body: dict, model_slug: str) -> tuple[int, int, int, float | None]:
    """usage から (prompt_tokens, completion_tokens, reasoning_tokens, actual_cost) を取り出す。

    gen-questions.py と同じ思想で、usage 欠損・0 トークンなら実測 run.json を書かない
    （コスト $0.00 表示という隠れ嘘を作らない）。
    """
    usage = body.get("usage")
    if not isinstance(usage, dict):
        raise UsageMissingError(
            f"{model_slug}: API response has no usage object. Cannot record measured run.json."
        )
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or 0)
    if prompt_tokens == 0 or completion_tokens == 0:
        raise UsageMissingError(
            f"{model_slug}: usage tokens are zero "
            f"(prompt={prompt_tokens}, completion={completion_tokens}). "
            "Refusing to write measured run.json."
        )
    details = usage.get("completion_tokens_details") or {}
    reasoning_tokens = int(details.get("reasoning_tokens") or 0) if isinstance(details, dict) else 0
    raw_cost = usage.get("cost")
    actual_cost = float(raw_cost) if isinstance(raw_cost, (int, float)) else None
    return prompt_tokens, completion_tokens, reasoning_tokens, actual_cost


def build_run_json(
    *,
    theme: str,
    model_slug: str,
    model_id: str,
    reasoning_effort: str,
    max_tokens: int,
    attempts: int,
    prompt_tokens: int,
    completion_tokens: int,
    reasoning_tokens: int,
    pricing: dict,
    post_processing: str,
) -> dict:
    """run.json（schema_version=1）を組む。既存 API モデルの形式に完全準拠。"""
    now_iso = datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()
    usd = round(
        prompt_tokens * pricing["prompt_usd_per_mtok"] / 1_000_000
        + completion_tokens * pricing["completion_usd_per_mtok"] / 1_000_000,
        6,
    )
    note = "OpenRouter API 実測。"
    note += (
        f"completion に reasoning {reasoning_tokens} tokens を含む"
        if reasoning_tokens
        else "reasoning トークンの内訳は API 未提供"
    )
    return {
        "schema_version": 1,
        "theme": theme,
        "model": model_slug,
        "model_id": model_id,
        "harness": "openrouter-api",
        "reasoning_effort": reasoning_effort,
        "attempts": attempts,
        "generated_at": now_iso,
        "generated_at_source": "measured",
        "sampling": {
            "temperature": "default",
            "max_tokens": max_tokens,
            "top_p": "default",
        },
        "system_prompt": "none",
        "post_processing": post_processing,
        "runtime": None,
        "usage": {
            "estimated": False,
            "method": "api-usage",
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "note": note,
        },
        "cost": {
            # pricing_source=openrouter は actual_usd=null 固定（validate-runs.mjs の規約）。
            # usage.cost の実請求値は表示に使わないため run.json には載せず、stderr に出す。
            "estimated": False,
            "usd": usd,
            "actual_usd": None,
            "prompt_usd_per_mtok": pricing["prompt_usd_per_mtok"],
            "completion_usd_per_mtok": pricing["completion_usd_per_mtok"],
            "pricing_source": "openrouter",
            "pricing_model": pricing["pricing_model"],
            "pricing_fetched_at": pricing["pricing_fetched_at"],
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--theme", required=True)
    ap.add_argument("--model", required=True, help="model-map.json の slug")
    ap.add_argument(
        "--reasoning-effort",
        default="high",
        choices=["none", "low", "medium", "high"],
        help="OpenRouter reasoning.effort（既定 high）",
    )
    ap.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    ap.add_argument("--overwrite", action="store_true", help="既存の出力を上書きし attempts を +1")
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="API を叩かず、テーマ・モデル・API キー・単価の前提だけ検証する",
    )
    args = ap.parse_args()

    # theme / model はそのままパス構成要素になるため、`..` やスラッシュを弾く
    for label, value in (("--theme", args.theme), ("--model", args.model)):
        if not NAME_RE.match(value):
            print(
                f"[ERROR] {label} must match {NAME_RE.pattern} (got {value!r}). "
                "It is used as a directory name.",
                file=sys.stderr,
            )
            return 1

    theme_dir = PUBLIC / args.theme
    if not (theme_dir / "PROMPT.md").exists():
        print(f"[ERROR] theme not found: {theme_dir}/PROMPT.md", file=sys.stderr)
        return 1

    kind = detect_theme_kind(theme_dir)
    if kind == "json-levels":
        print(
            "[ERROR] json-ladder must use scripts/json-ladder-run.py; "
            "openrouter-run.py only supports one output per request.",
            file=sys.stderr,
        )
        return 1

    try:
        model_id = resolve_model_id(args.model)
        pricing = load_pricing(args.model)
        api_key = load_api_key()
        # 送信先の妥当性は preflight で確認する（dry-run でも検出できるように）
        resolve_api_url()
    except RuntimeError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    out_dir = theme_dir / args.model
    out_name = "output.json" if kind == "json" else "index.html"
    out_file = out_dir / out_name

    if out_file.exists() and not args.overwrite:
        print(f"[ERROR] already exists: {out_file} (pass --overwrite to regenerate)", file=sys.stderr)
        return 1

    try:
        prompt = build_prompt(theme_dir, kind)
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    print(
        f"=== {args.theme} / {args.model} ({model_id}) kind={kind} "
        f"effort={args.reasoning_effort} max_tokens={args.max_tokens} "
        f"prompt={len(prompt)} chars ===",
        file=sys.stderr,
    )

    if args.dry_run:
        print(
            f"[dry-run] preflight OK (api key present, pricing found: "
            f"${pricing['prompt_usd_per_mtok']}/${pricing['completion_usd_per_mtok']} per Mtok). "
            f"Would write {out_file}",
            file=sys.stderr,
        )
        return 0

    attempts = 1
    run_path = out_dir / "run.json"
    if args.overwrite and run_path.exists():
        previous = json.loads(run_path.read_text(encoding="utf-8"))
        attempts = int(previous.get("attempts") or 0) + 1

    try:
        body = call_openrouter(api_key, model_id, prompt, args.reasoning_effort, args.max_tokens)
    except OpenRouterError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    # max_tokens 打ち切りを先に弾く（壊れた成果物を保存しない）
    try:
        check_not_truncated(body, args.model)
    except TruncatedOutputError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    content = body["choices"][0]["message"].get("content") or ""
    if not content.strip():
        print("[ERROR] model returned empty content", file=sys.stderr)
        return 2

    post_processing = "none"
    if kind == "json":
        output_text = content.strip()
    else:
        output_text, extracted = extract_fenced_html(content)
        if extracted:
            post_processing = "extract-fenced-html"
        # finish_reason を返さないプロバイダ向けの二重チェック
        try:
            verify_html_complete(output_text, args.model)
        except TruncatedOutputError as exc:
            print(f"[ERROR] {exc}", file=sys.stderr)
            return 2

    try:
        prompt_tokens, completion_tokens, reasoning_tokens, actual_cost = read_usage(body, args.model)
    except UsageMissingError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 3

    # 書き込み直前に、出力先が public/ 配下に収まっていることを確認する
    # （NAME_RE の検証に加えた多層防御。symlink 経由の脱出も resolve() で潰す）
    resolved_dir = out_dir.resolve()
    if not resolved_dir.is_relative_to(PUBLIC.resolve()):
        print(
            f"[ERROR] refusing to write outside {PUBLIC}: {resolved_dir}",
            file=sys.stderr,
        )
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    out_file.write_text(output_text + ("\n" if not output_text.endswith("\n") else ""), encoding="utf-8")

    run = build_run_json(
        theme=args.theme,
        model_slug=args.model,
        model_id=model_id,
        reasoning_effort=args.reasoning_effort,
        max_tokens=args.max_tokens,
        attempts=attempts,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        reasoning_tokens=reasoning_tokens,
        pricing=pricing,
        post_processing=post_processing,
    )
    run_path.write_text(json.dumps(run, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        f"[ok] wrote {out_file} ({len(output_text)} chars, post_processing={post_processing})",
        file=sys.stderr,
    )
    print(
        f"[ok] usage prompt={prompt_tokens} completion={completion_tokens} "
        f"(reasoning={reasoning_tokens}) cost_from_pricing=${run['cost']['usd']}"
        + (f" openrouter_reported=${actual_cost}" if actual_cost is not None else ""),
        file=sys.stderr,
    )
    print(str(out_file))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
