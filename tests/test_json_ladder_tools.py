import copy
import importlib.util
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
THEME = ROOT / "public" / "json-ladder"
BUILD_SCRIPT = ROOT / "scripts" / "build-json-ladder-html.py"
VALIDATE_SCRIPT = ROOT / "scripts" / "validate-json-ladder.mjs"
ANSWER_KEY = THEME / "answer-key.json"
INPUT_MD = THEME / "input.md"
MODEL = "claude-opus-5"
OTHER_MODEL = "gemma-4-31b"

PATH_TOKEN_RE = re.compile(r"([^.\[\]]+)|\[(\d+)\]")


def load_python_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def answer_key() -> dict:
    return json.loads(ANSWER_KEY.read_text(encoding="utf-8"))


def parse_path(path: str) -> list[str | int]:
    tokens: list[str | int] = []
    for key, index in PATH_TOKEN_RE.findall(path):
        tokens.append(int(index) if index else key)
    return tokens


def assign(root: dict, path: str, value: object) -> None:
    """answer-key の path をたどって満点 JSON を組み立てる。"""
    tokens = parse_path(path)
    cur: object = root
    for i, token in enumerate(tokens):
        last = i == len(tokens) - 1
        nxt = None if last else tokens[i + 1]
        if isinstance(token, int):
            assert isinstance(cur, list)
            while len(cur) <= token:
                cur.append(None)
            if last:
                cur[token] = value
            else:
                if not isinstance(cur[token], (dict, list)):
                    cur[token] = [] if isinstance(nxt, int) else {}
                cur = cur[token]
        else:
            assert isinstance(cur, dict)
            if last:
                cur[token] = value
            else:
                if not isinstance(cur.get(token), (dict, list)):
                    cur[token] = [] if isinstance(nxt, int) else {}
                cur = cur[token]


def perfect_level_payload(level: dict) -> dict:
    """1 レベル分の満点 JSON を answer-key から機械合成する。"""
    root: dict = {}
    array_lengths = [f for f in level["fields"] if f["type"] == "array_length"]
    others = [f for f in level["fields"] if f["type"] != "array_length"]
    # 配列は要素代入で伸ばすので、まず空配列を作ってから要素を埋める
    for field in array_lengths:
        assign(root, field["path"], [])
    for field in others:
        assign(root, field["path"], field["expected"])
    for field in array_lengths:
        tokens = parse_path(field["path"])
        cur: Any = root
        for token in tokens:
            cur = cur[token]
        assert isinstance(cur, list)
        while len(cur) < field["expected"]:
            cur.append(None)
    return root


def perfect_output(fenced: bool = True) -> dict:
    levels = []
    for level in answer_key()["levels"]:
        payload = json.dumps(perfect_level_payload(level), ensure_ascii=False, indent=2)
        raw = f"```json\n{payload}\n```" if fenced else payload
        levels.append(
            {
                "level": level["level"],
                "raw": raw,
                "finish_reason": "stop",
                "usage": {"prompt_tokens": 0, "completion_tokens": 0},
            }
        )
    return {"schema_version": 1, "theme": "json-ladder", "levels": levels}


def level_payload(output: dict, level: int) -> dict:
    entry = next(item for item in output["levels"] if item["level"] == level)
    return json.loads(entry["raw"].removeprefix("```json\n").removesuffix("\n```"))


def set_level_payload(output: dict, level: int, payload: dict) -> None:
    entry = next(item for item in output["levels"] if item["level"] == level)
    entry["raw"] = "```json\n" + json.dumps(payload, ensure_ascii=False, indent=2) + "\n```"


def write_model(theme_dir: Path, model: str, output: dict) -> Path:
    model_dir = theme_dir / model
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "output.json").write_text(
        json.dumps(output, ensure_ascii=False), encoding="utf-8"
    )
    return model_dir


def run_validator(theme_dir: Path, model: str | None = None) -> subprocess.CompletedProcess:
    cmd = [
        "node",
        str(VALIDATE_SCRIPT),
        "--theme-dir",
        str(theme_dir),
        "--answer-key",
        str(ANSWER_KEY),
    ]
    if model:
        cmd += ["--model", model]
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)


def validate_and_load_meta(theme_dir: Path, output: dict, model: str = MODEL) -> dict:
    model_dir = write_model(theme_dir, model, output)
    result = run_validator(theme_dir, model)
    assert (model_dir / "meta.json").exists(), result.stderr
    return json.loads((model_dir / "meta.json").read_text(encoding="utf-8"))


def meta_level(meta: dict, level: int) -> dict:
    return next(item for item in meta["levels"] if item["level"] == level)


def verdict_of(meta: dict, level: int, path: str) -> dict:
    return next(v for v in meta_level(meta, level)["verdicts"] if v["path"] == path)


# --- 1. answer-key と本文の静的整合ガード -------------------------------------


def test_answer_key_japanese_excerpts_exist_verbatim_in_input() -> None:
    """抜き出し系の期待値が input.md に一字一句あることを保証する（採点キーの誤りを防ぐ）。"""
    body = INPUT_MD.read_text(encoding="utf-8")
    missing = []
    for level in answer_key()["levels"]:
        for field in level["fields"]:
            if field["type"] != "string":
                continue
            expected = field["expected"]
            if not re.search(r"[ぁ-んァ-ン一-龥]", expected):
                continue
            for line in expected.split("\n"):
                if line and line not in body:
                    missing.append(f'L{level["level"]} {field["path"]}: {line}')
    assert missing == [], "input.md に存在しない期待値: " + " / ".join(missing)


# --- 2. 満点ケース ------------------------------------------------------------


def test_validator_scores_perfect_output(tmp_path: Path) -> None:
    meta = validate_and_load_meta(tmp_path / "json-ladder", perfect_output())

    assert meta["levels_total"] == 5
    assert meta["parse_pass_count"] == 5
    assert meta["score_pct"] == 100
    for level in meta["levels"]:
        assert level["valid_json"] is True
        assert level["schema_pass"] is True
        assert level["accuracy_pct"] == 100
        assert level["issues"] == []


def test_validator_accepts_unfenced_json(tmp_path: Path) -> None:
    meta = validate_and_load_meta(tmp_path / "json-ladder", perfect_output(fenced=False))

    assert meta["parse_pass_count"] == 5
    assert meta["score_pct"] == 100


# --- 3. パース失敗 ------------------------------------------------------------


def test_garbage_raw_fails_only_its_own_level(tmp_path: Path) -> None:
    output = perfect_output()
    next(item for item in output["levels"] if item["level"] == 3)["raw"] = "うまく出せませんでした"

    meta = validate_and_load_meta(tmp_path / "json-ladder", output)

    assert meta["parse_pass_count"] == 4
    level3 = meta_level(meta, 3)
    assert level3["valid_json"] is False
    assert level3["accuracy_pct"] == 0
    assert level3["verdicts"] == []
    assert "parse-failed" in level3["issues"]
    assert all(meta_level(meta, n)["accuracy_pct"] == 100 for n in (1, 2, 4, 5))
    assert meta["score_pct"] == 80


def test_broken_fence_does_not_fall_back_to_raw(tmp_path: Path) -> None:
    """フェンスがあるのに中身が壊れていたらパース失敗で確定させる（raw 再フォールバック禁止）。"""
    output = perfect_output()
    entry = next(item for item in output["levels"] if item["level"] == 1)
    valid_json = json.dumps({"title": "硝子の記憶"}, ensure_ascii=False)
    entry["raw"] = f'{valid_json}\n```json\n{{"title": "硝子の記憶",,}}\n```'

    meta = validate_and_load_meta(tmp_path / "json-ladder", output)

    level1 = meta_level(meta, 1)
    assert level1["valid_json"] is False
    assert level1["issues"] == ["parse-failed"]


def test_missing_level_is_recorded_as_invalid(tmp_path: Path) -> None:
    output = perfect_output()
    output["levels"] = [item for item in output["levels"] if item["level"] != 5]

    meta = validate_and_load_meta(tmp_path / "json-ladder", output)

    level5 = meta_level(meta, 5)
    assert level5["valid_json"] is False
    assert level5["issues"] == ["level 5 missing in output.json"]
    assert meta["parse_pass_count"] == 4


# --- 4. 採点の詳細 ------------------------------------------------------------


def test_integer_as_string_is_type_error(tmp_path: Path) -> None:
    output = perfect_output()
    payload = level_payload(output, 1)
    payload["founded_year"] = "1961"
    set_level_payload(output, 1, payload)

    meta = validate_and_load_meta(tmp_path / "json-ladder", output)
    level1 = meta_level(meta, 1)

    assert verdict_of(meta, 1, "founded_year")["match"] == "miss"
    assert "type-error: founded_year" in level1["issues"]
    assert level1["schema_pass"] is False
    assert level1["valid_json"] is True


def test_string_null_is_miss(tmp_path: Path) -> None:
    output = perfect_output()
    payload = level_payload(output, 3)
    payload["workshop"]["closed_year"] = "null"
    set_level_payload(output, 3, payload)

    meta = validate_and_load_meta(tmp_path / "json-ladder", output)

    assert verdict_of(meta, 3, "workshop.closed_year")["match"] == "miss"
    assert "type-error: workshop.closed_year" in meta_level(meta, 3)["issues"]


def test_missing_path_is_recorded_as_missing_issue(tmp_path: Path) -> None:
    output = perfect_output()
    payload = level_payload(output, 1)
    del payload["city"]
    set_level_payload(output, 1, payload)

    meta = validate_and_load_meta(tmp_path / "json-ladder", output)
    verdict = verdict_of(meta, 1, "city")

    assert verdict["match"] == "miss"
    assert verdict["got"] is None
    assert "missing: city" in meta_level(meta, 1)["issues"]


def test_also_acceptable_scores_half(tmp_path: Path) -> None:
    output = perfect_output()
    payload = level_payload(output, 1)
    payload["author"] = "千鶴"
    set_level_payload(output, 1, payload)

    meta = validate_and_load_meta(tmp_path / "json-ladder", output)
    level1 = meta_level(meta, 1)

    assert verdict_of(meta, 1, "author")["match"] == "acceptable"
    assert level1["primary_match"] == 3
    assert level1["acceptable_match"] == 1
    assert level1["accuracy_pct"] == 88  # (3 + 0.5) / 4
    # 値の揺れだけでは構造は壊れていないので schema_pass は維持する
    assert level1["schema_pass"] is True


def test_array_length_mismatch_is_miss(tmp_path: Path) -> None:
    output = perfect_output()
    payload = level_payload(output, 2)
    payload["tools"] = payload["tools"][:2]
    set_level_payload(output, 2, payload)

    meta = validate_and_load_meta(tmp_path / "json-ladder", output)
    verdict = verdict_of(meta, 2, "tools")

    assert verdict["match"] == "miss"
    assert verdict["got"] == 2
    assert verdict["expected"] == 3
    # 要素そのものが消えた分は missing として記録される
    assert "missing: tools[2]" in meta_level(meta, 2)["issues"]


def test_array_length_type_error_when_not_array(tmp_path: Path) -> None:
    output = perfect_output()
    payload = level_payload(output, 2)
    payload["tools"] = "吹き竿、ポンテ竿、木箸"
    set_level_payload(output, 2, payload)

    meta = validate_and_load_meta(tmp_path / "json-ladder", output)

    assert verdict_of(meta, 2, "tools")["match"] == "miss"
    assert "type-error: tools" in meta_level(meta, 2)["issues"]


def test_japanese_key_path_is_resolved(tmp_path: Path) -> None:
    output = perfect_output()
    payload = level_payload(output, 5)
    payload["quotes_by_speaker"]["宗一郎"][1] = "ちがう言葉"
    set_level_payload(output, 5, payload)

    meta = validate_and_load_meta(tmp_path / "json-ladder", output)

    assert verdict_of(meta, 5, "quotes_by_speaker.宗一郎[0]")["match"] == "primary"
    assert verdict_of(meta, 5, "quotes_by_speaker.宗一郎[1]")["match"] == "miss"


def test_extra_top_level_key_fails_only_its_own_level(tmp_path: Path) -> None:
    """PROMPT.md が禁じるキー追加をスキーマ違反として検出する（accuracy は据え置き）。"""
    output = perfect_output()
    payload = level_payload(output, 1)
    payload["explanation"] = "タイトルは本文冒頭から取りました"
    set_level_payload(output, 1, payload)

    meta = validate_and_load_meta(tmp_path / "json-ladder", output)
    level1 = meta_level(meta, 1)

    assert level1["schema_pass"] is False
    assert "extra-key: explanation" in level1["issues"]
    # 採点対象フィールドは全一致のままなので accuracy は下がらない
    assert level1["accuracy_pct"] == 100
    assert all(meta_level(meta, n)["schema_pass"] is True for n in (2, 3, 4, 5))


def test_extra_key_in_nested_object_is_detected(tmp_path: Path) -> None:
    output = perfect_output()
    payload = level_payload(output, 3)
    payload["workshop"]["owner"] = "佐伯宗一郎"
    set_level_payload(output, 3, payload)

    meta = validate_and_load_meta(tmp_path / "json-ladder", output)

    assert "extra-key: workshop.owner" in meta_level(meta, 3)["issues"]
    assert meta_level(meta, 3)["schema_pass"] is False


def test_extra_key_in_array_element_is_detected(tmp_path: Path) -> None:
    output = perfect_output()
    payload = level_payload(output, 5)
    payload["characters"][0]["age"] = 80
    set_level_payload(output, 5, payload)

    meta = validate_and_load_meta(tmp_path / "json-ladder", output)

    assert "extra-key: characters[0].age" in meta_level(meta, 5)["issues"]
    assert meta_level(meta, 5)["schema_pass"] is False


def test_array_element_keys_are_allowed_across_all_indexes(tmp_path: Path) -> None:
    """要素ごとの許可キーは全インデックスの和集合で判定する（relations を持つのは末尾要素だけ）。"""
    output = perfect_output()
    payload = level_payload(output, 5)
    payload["characters"][0]["relations"] = []
    set_level_payload(output, 5, payload)

    meta = validate_and_load_meta(tmp_path / "json-ladder", output)

    assert meta_level(meta, 5)["schema_pass"] is True


def test_extra_array_element_is_length_miss_not_extra_key(tmp_path: Path) -> None:
    """配列の余剰要素は array_length 採点の領分で、extra-key として二重報告しない。"""
    output = perfect_output()
    payload = level_payload(output, 2)
    payload["tools"].append("金鋏")
    set_level_payload(output, 2, payload)

    meta = validate_and_load_meta(tmp_path / "json-ladder", output)
    level2 = meta_level(meta, 2)

    assert verdict_of(meta, 2, "tools")["match"] == "miss"
    assert verdict_of(meta, 2, "tools")["got"] == 4
    assert not any("extra-key" in issue for issue in level2["issues"])


def test_null_valued_allowed_key_is_not_extra_key(tmp_path: Path) -> None:
    """値が null でも許可キーなら違反にしない（存在するキーとして扱う）。"""
    output = perfect_output()
    payload = level_payload(output, 3)
    payload["workshop"]["closed_year"] = None
    set_level_payload(output, 3, payload)

    meta = validate_and_load_meta(tmp_path / "json-ladder", output)

    assert meta_level(meta, 3)["issues"] == []
    assert meta_level(meta, 3)["schema_pass"] is True


# --- 5. 正規化 ----------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "　硝子の記憶　",  # 前後の全角スペース
        "硝子​の記憶",  # ゼロ幅スペース混入
        " 硝子の記憶 ",  # 前後の半角スペース
    ],
)
def test_default_normalize_absorbs_whitespace_and_zero_width(tmp_path: Path, value: str) -> None:
    output = perfect_output()
    payload = level_payload(output, 1)
    payload["title"] = value
    set_level_payload(output, 1, payload)

    meta = validate_and_load_meta(tmp_path / "json-ladder", output)

    assert verdict_of(meta, 1, "title")["match"] == "primary"


def test_default_normalize_collapses_inner_whitespace_to_single_space(tmp_path: Path) -> None:
    """内部の連続空白は削除ではなく半角スペース1個に畳む（語間の有無は保存する）。"""
    output = perfect_output()
    payload = level_payload(output, 5)
    sentence = payload["timeline"][3]["sentence"]
    payload["timeline"][3]["sentence"] = sentence.replace("2001年", "2001　\n 年")
    set_level_payload(output, 5, payload)

    meta = validate_and_load_meta(tmp_path / "json-ladder", output)

    # 空白が1個残るため一致しない = 削除ではなく圧縮であることの証明
    assert verdict_of(meta, 5, "timeline[3].sentence")["match"] == "miss"


def test_default_normalize_absorbs_nfkc_halfwidth_kana(tmp_path: Path) -> None:
    output = perfect_output()
    payload = level_payload(output, 2)
    payload["people"][4] = "ﾏﾙｺ"  # 半角カナ → NFKC で「マルコ」
    set_level_payload(output, 2, payload)

    meta = validate_and_load_meta(tmp_path / "json-ladder", output)

    assert verdict_of(meta, 2, "people[4]")["match"] == "primary"


def test_exact_field_rejects_dropped_newlines(tmp_path: Path) -> None:
    output = perfect_output()
    payload = level_payload(output, 4)
    payload["letter_excerpt"] = payload["letter_excerpt"].replace("\n", " ")
    set_level_payload(output, 4, payload)

    meta = validate_and_load_meta(tmp_path / "json-ladder", output)

    assert verdict_of(meta, 4, "letter_excerpt")["match"] == "miss"
    # 型は合っているので issue は出ず、値の不一致として扱う
    assert meta_level(meta, 4)["issues"] == []


def test_exact_field_allows_surrounding_whitespace_only(tmp_path: Path) -> None:
    output = perfect_output()
    payload = level_payload(output, 4)
    payload["letter_excerpt"] = f'\n{payload["letter_excerpt"]}  '
    set_level_payload(output, 4, payload)

    meta = validate_and_load_meta(tmp_path / "json-ladder", output)

    assert verdict_of(meta, 4, "letter_excerpt")["match"] == "primary"


# --- 6. CLI とビルダー --------------------------------------------------------


def test_validator_model_filter_exit_status(tmp_path: Path) -> None:
    theme_dir = tmp_path / "json-ladder"
    write_model(theme_dir, MODEL, perfect_output())
    broken = copy.deepcopy(perfect_output())
    next(item for item in broken["levels"] if item["level"] == 2)["raw"] = "not json"
    write_model(theme_dir, OTHER_MODEL, broken)

    passed = run_validator(theme_dir, MODEL)
    assert passed.returncode == 0, passed.stderr
    assert "PASS" in passed.stdout

    failed = run_validator(theme_dir, OTHER_MODEL)
    assert failed.returncode == 1
    assert "FAIL" in failed.stdout


def test_validator_skips_levels_directory(tmp_path: Path) -> None:
    theme_dir = tmp_path / "json-ladder"
    write_model(theme_dir, MODEL, perfect_output())
    (theme_dir / "levels").mkdir()
    (theme_dir / "levels" / "l1.md").write_text("設問", encoding="utf-8")

    result = run_validator(theme_dir)

    assert result.returncode == 0, result.stderr
    assert "levels" not in result.stdout
    assert not (theme_dir / "levels" / "meta.json").exists()


def test_build_html_renders_levels_and_filters_model(tmp_path: Path) -> None:
    theme_dir = tmp_path / "json-ladder"
    selected = write_model(theme_dir, MODEL, perfect_output())
    other = write_model(theme_dir, OTHER_MODEL, perfect_output())
    run_validator(theme_dir)
    module = load_python_script(BUILD_SCRIPT, "build_json_ladder_html")

    result = module.main(["--theme-dir", str(theme_dir), "--model", MODEL])

    assert result == 0
    output = (selected / "output.html").read_text(encoding="utf-8")
    assert "Claude Opus 5" in output
    assert "parse 5/5" in output
    assert "score 100%" in output
    assert "レベル 5" in output
    assert not (other / "output.html").exists()


def test_build_html_escapes_model_output(tmp_path: Path) -> None:
    theme_dir = tmp_path / "json-ladder"
    output = perfect_output()
    payload = level_payload(output, 1)
    payload["title"] = "<script>alert(1)</script>"
    set_level_payload(output, 1, payload)
    model_dir = write_model(theme_dir, MODEL, output)
    run_validator(theme_dir)
    module = load_python_script(BUILD_SCRIPT, "build_json_ladder_html_escape")

    assert module.main(["--theme-dir", str(theme_dir), "--model", MODEL]) == 0

    html_text = (model_dir / "output.html").read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in html_text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html_text
