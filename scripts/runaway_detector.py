#!/usr/bin/env python3
"""Detect repetition runaway in a local LLM generation while it is still streaming.

A runaway is a generation that stops making progress and instead re-emits what it
has already produced, running until max_tokens.  Two observed shapes motivate the
design: verbatim phrase loops (one sentence repeated hundreds of times) and
rewrite loops (the same component re-implemented with slightly different wording
each pass).  Verbatim loops are caught by line uniqueness; rewrite loops are not,
because every line differs textually.  Rewrite loops are caught by delta
compression against the text already generated, but that measure alone flags
healthy CSS-heavy output.  Requiring both signals at once separates the two
observed runaways from every healthy artifact in the benchmark corpus.

Requiring both signals also leaves a gap: a generation that restarts the whole
document each pass keeps every line textually distinct, so the line measure
stays high and the pair never fires.  One such output restarted a single-file
page 45 times and ran to max_tokens while scoring 0.809 -- comfortably healthy
by the paired measure.  Document restarts are therefore counted separately:
they are not a score, they are a structural fact about single-file artifacts.
"""
from __future__ import annotations

import re
import zlib
from dataclasses import dataclass

WINDOW_CHARS = 3000
STEP_CHARS = 1500
# Bounds how far back a rewrite loop can be recognised.  zlib's own dictionary
# is 32 KiB, so the effective reach is the smaller of this and that window: for
# CJK text at 3 bytes per character it is roughly 10,900 characters, for ASCII
# the full 40,000.  Comparing against a bounded context rather than the whole
# generation therefore changes the score, and does so toward earlier detection.
CONTEXT_CHARS = 40000
MIN_START_CHARS = 6000
# Separates every artifact in the benchmark corpus, but not by much: the worst
# healthy output scores 0.591 and the milder runaway scores 0.535.  A new model
# could land between them, so treat a single detection as a signal to inspect
# the output and retune with --runaway-threshold, not as settled ground truth.
THRESHOLD = 0.55
MIN_LINES = 15
# Themes whose deliverable is one self-contained file emit exactly one doctype.
# Two occurrences still happen in healthy output (a preamble that quotes the
# markup, a code sample inside the page), so only the third one is treated as
# a rewrite loop.  Measured: healthy artifacts in the corpus top out at 2,
# the observed loops reach 3 and 45.
RESTART_LIMIT = 3
_DOCTYPE_RE = re.compile(r"<!doctype\s+html", re.IGNORECASE)


@dataclass(frozen=True)
class RunawayVerdict:
    """Describe where a generation was judged to be repeating itself."""

    position: int
    delta_ratio: float
    unique_line_ratio: float
    score: float
    restarts: int = 0

    def describe(self) -> str:
        """Render a one-line reason suitable for an error message or run note."""
        if self.restarts:
            return (
                f"{self.position:,} 文字目で書き直しループを検知 "
                f"(doctype {self.restarts} 回目)"
            )
        return (
            f"{self.position:,} 文字目で繰り返し暴走を検知 "
            f"(score={self.score:.3f}, D={self.delta_ratio:.3f}, "
            f"A={self.unique_line_ratio:.3f})"
        )


def _delta_ratio(context: str, window: str) -> float:
    """Return how much new compressed data a window adds on top of its context.

    A window that merely restates the context compresses almost entirely into
    back-references, so the ratio approaches zero.  Genuinely new content
    compresses on its own terms and the ratio approaches one.
    """
    window_bytes = window.encode("utf-8")
    alone = len(zlib.compress(window_bytes, 6))
    if alone == 0:
        return 1.0
    context_bytes = context.encode("utf-8")
    base = len(zlib.compress(context_bytes, 6))
    combined = len(zlib.compress(context_bytes + window_bytes, 6))
    return (combined - base) / alone


def _unique_line_ratio(window: str) -> float:
    """Return the share of distinct non-blank lines inside one window.

    Windows with too few lines carry no evidence either way and score 1.0 so
    they cannot trigger a stop on their own.
    """
    lines = [line.strip() for line in window.splitlines() if line.strip()]
    if len(lines) < MIN_LINES:
        return 1.0
    return len(set(lines)) / len(lines)


class RunawayDetector:
    """Judge a growing generation for repetition.

    Feed decoded text as it arrives.  Every STEP_CHARS of new text the detector
    scores the most recent window against the text preceding it and returns a
    verdict once both repetition signals cross the threshold.  A verdict is
    returned exactly once; the caller is expected to abort the request.

    Only the trailing window plus its comparison context is retained, so memory
    stays bounded no matter how long a runaway is allowed to run.
    """

    def __init__(self, threshold: float = THRESHOLD) -> None:
        if not 0.0 < threshold < 1.0:
            raise ValueError("threshold must be between 0 and 1")
        self._threshold = threshold
        self._buffer = ""
        self._length = 0
        self._next_check = max(MIN_START_CHARS, WINDOW_CHARS)
        self._fired = False
        self._restarts = 0
        # A doctype can straddle a chunk boundary, so keep the tail that could
        # still complete one.  len("<!doctype html") - 1 is the longest prefix
        # that is not yet a match.
        self._restart_tail = ""

    @property
    def length(self) -> int:
        """Return the number of characters fed so far."""
        return self._length

    def feed(self, chunk: str) -> RunawayVerdict | None:
        """Accumulate one chunk and return a verdict when repetition is confirmed."""
        if not chunk:
            return None
        self._buffer = (self._buffer + chunk)[-(WINDOW_CHARS + CONTEXT_CHARS) :]
        self._length += len(chunk)
        if self._fired:
            return None
        restart = self._count_restarts(chunk)
        if restart is not None:
            return restart
        if self._length < self._next_check:
            return None
        self._next_check = self._length + STEP_CHARS
        return self._evaluate()

    def _count_restarts(self, chunk: str) -> RunawayVerdict | None:
        """Track document restarts and fire once the artifact is rewritten again.

        Counted on the raw stream rather than the trailing buffer so that a long
        rewrite loop cannot push earlier restarts out of the comparison window.
        """
        scan = self._restart_tail + chunk
        self._restarts += len(_DOCTYPE_RE.findall(scan))
        self._restart_tail = scan[-13:]
        if self._restarts < RESTART_LIMIT:
            return None
        self._fired = True
        return RunawayVerdict(
            position=self._length,
            delta_ratio=1.0,
            unique_line_ratio=1.0,
            score=1.0,
            restarts=self._restarts,
        )

    def _evaluate(self) -> RunawayVerdict | None:
        """Score the newest window against its context and record a firing verdict."""
        window = self._buffer[-WINDOW_CHARS:]
        context = self._buffer[:-WINDOW_CHARS]
        if not context:
            return None
        delta = _delta_ratio(context, window)
        unique = _unique_line_ratio(window)
        score = max(delta, unique)
        if score >= self._threshold:
            return None
        self._fired = True
        return RunawayVerdict(
            position=self._length,
            delta_ratio=delta,
            unique_line_ratio=unique,
            score=score,
        )


def scan_text(text: str, threshold: float = THRESHOLD) -> RunawayVerdict | None:
    """Replay a finished generation through the detector as if it had streamed.

    Used to check completed artifacts and to reproduce the streaming decision
    offline against the benchmark corpus.
    """
    detector = RunawayDetector(threshold)
    for start in range(0, len(text), STEP_CHARS):
        verdict = detector.feed(text[start : start + STEP_CHARS])
        if verdict is not None:
            return verdict
    return None
