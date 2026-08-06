#!/usr/bin/env python3
"""Exercise repetition-runaway detection against both observed runaway shapes."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from runaway_detector import RunawayDetector, RunawayVerdict, scan_text  # noqa: E402


def healthy_html(blocks: int = 40) -> str:
    """Build markup that keeps introducing new content, as a finished artifact does."""
    parts = ["<!doctype html>\n<html>\n<head><style>\n"]
    for i in range(blocks):
        parts.append(
            f".card-{i} {{\n"
            f"  display: flex;\n"
            f"  padding: {i % 7 + 1}rem;\n"
            f"  color: #{i:03x}{i:03x};\n"
            f"}}\n"
            f".card-{i}:hover {{ transform: translateY(-{i % 5 + 1}px); }}\n"
        )
    parts.append("</style></head>\n<body>\n")
    for i in range(blocks):
        parts.append(
            f'<section class="card-{i}">\n'
            f"  <h2>見出し {i} 番目の独自トピック</h2>\n"
            f"  <p>この段落は {i} 番目の説明で、他の段落とは違う内容を述べている。</p>\n"
            f"</section>\n"
        )
    parts.append("</body>\n</html>\n")
    return "".join(parts)


def phrase_loop(repeats: int = 400) -> str:
    """Reproduce the verbatim phrase loop seen in the hasami-shogi runaway."""
    return "".join(
        "**好的，让我写完整代码。**\n让我把代码写完。\n让我也考虑一下、在移动后的处理。\n"
        for _ in range(repeats)
    )


def rewrite_loop(repeats: int = 120) -> str:
    """Reproduce the rewrite loop seen in the suminagashi runaway.

    Each pass restates the same component, varying some identifiers while
    boilerplate lines recur verbatim, which is what the real runaway looked
    like: neither signal alone is decisive, and only their conjunction is.
    """
    parts = []
    for i in range(repeats):
        parts.append(
            f"では、実装をもう一度整理して書き直してみます。バージョン {i} です。\n"
            f"```javascript\n"
            f"const canvas = document.getElementById('c{i}');\n"
            f"const ctx = canvas.getContext('2d');\n"
            f"canvas.width = window.innerWidth;\n"
            f"canvas.height = window.innerHeight;\n"
            f"function draw{i}() {{\n"
            f"  ctx.fillStyle = 'rgba(0,0,0,0.02)';\n"
            f"  ctx.fillRect(0, 0, canvas.width, canvas.height);\n"
            f"  requestAnimationFrame(draw{i});\n"
            f"}}\n"
            f"draw{i}();\n"
            f"```\n"
            f"いや、これだと墨の広がりが表現できていません。書き直します。\n"
        )
    return "".join(parts)


def feed_all(
    text: str, threshold: float | None = None, chunk: int = 200
) -> RunawayVerdict | None:
    """Stream text through a detector in small chunks and return the first verdict."""
    detector = RunawayDetector() if threshold is None else RunawayDetector(threshold)
    for start in range(0, len(text), chunk):
        verdict = detector.feed(text[start : start + chunk])
        if verdict is not None:
            return verdict
    return None


def test_verbatim_phrase_loop_is_stopped() -> None:
    """A generation repeating one sentence is aborted while streaming."""
    verdict = feed_all(healthy_html(10) + phrase_loop())

    assert verdict is not None
    assert verdict.unique_line_ratio < 0.55
    assert verdict.delta_ratio < 0.55


def test_rewrite_loop_is_stopped() -> None:
    """A generation re-implementing the same component is aborted while streaming."""
    verdict = feed_all(healthy_html(10) + rewrite_loop())

    assert verdict is not None


def test_healthy_generation_is_never_stopped() -> None:
    """Repetitive-looking but progressing markup streams to completion untouched."""
    assert feed_all(healthy_html(200)) is None


def test_short_generation_is_never_stopped() -> None:
    """Output below the warmup length yields no verdict even when fully repetitive."""
    assert feed_all("同じ行\n" * 200) is None


def test_stop_happens_early_in_the_loop() -> None:
    """Detection fires soon after repetition starts, not after the whole budget."""
    prefix = healthy_html(10)
    text = prefix + phrase_loop(2000)
    verdict = feed_all(text)

    assert verdict is not None
    assert verdict.position < len(prefix) + 12000
    assert verdict.position < len(text) // 4


def test_detection_can_be_tuned_and_disabled_per_run() -> None:
    """A stricter threshold detects less, matching the CLI escape hatch."""
    text = healthy_html(10) + rewrite_loop()

    assert feed_all(text, threshold=0.55) is not None
    assert feed_all(text, threshold=0.05) is None


def test_verdict_reports_where_and_why_it_fired() -> None:
    """The verdict carries the position and both signals for the error message."""
    verdict = feed_all(healthy_html(10) + phrase_loop())

    assert verdict is not None
    assert str(verdict.position) in verdict.describe().replace(",", "")
    assert "score=" in verdict.describe()


def test_verdict_fires_only_once_per_generation() -> None:
    """After firing, further chunks produce no second verdict."""
    detector = RunawayDetector()
    text = healthy_html(10) + phrase_loop()
    verdicts = [
        v
        for start in range(0, len(text), 200)
        if (v := detector.feed(text[start : start + 200])) is not None
    ]

    assert len(verdicts) == 1


@pytest.mark.parametrize("chunk", [1, 7, 200, 5000])
def test_verdict_is_independent_of_chunk_boundaries(chunk: int) -> None:
    """Streaming granularity does not change whether a runaway is caught."""
    assert feed_all(healthy_html(10) + phrase_loop(), chunk=chunk) is not None


def test_scan_text_matches_streaming_for_finished_output() -> None:
    """Replaying a finished artifact reaches the same conclusion as streaming did."""
    text = healthy_html(10) + phrase_loop()

    assert scan_text(text) is not None
    assert scan_text(healthy_html(200)) is None
