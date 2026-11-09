"""Tolerant parser for the markdown table a model answers with.

Models change header names, reorder columns, break rows, wrap quotes in
quotation marks or backticks, or forget the table. None of that may stop a run.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

QUOTE_KEYS = ("인용", "원문", "quote", "excerpt", "sentence", "문장")
COMMENT_KEYS = ("지적", "의견", "문제", "comment", "issue", "suggest", "수정", "feedback")
SEVERITY_KEYS = ("심각", "severity", "중요", "level", "priority")
INDEX_HEADERS = {"#", "no", "no.", "번호", "순번", "idx", "id"}
QUOTE_CHARS = "\"'`“”‘’「」『』 "

_SEVERITY_WORDS = {
    "high": ("높음", "심각", "high", "critical", "major", "severe", "상"),
    "medium": ("중간", "보통", "medium", "moderate", "mid", "중"),
    "low": ("낮음", "경미", "low", "minor", "info", "하"),
}


@dataclass
class ParsedTable:
    rows: list[dict] = field(default_factory=list)  # {"quote", "comment", "severity"}
    skipped: int = 0  # broken or empty-quote rows
    has_table: bool = False
    headers: Optional[list[str]] = None


def split_row(line: str) -> Optional[list[str]]:
    """Cells of a `| a | b |` line, or None when the line is not a table row."""
    line = line.strip()
    if not line.startswith("|"):
        return None
    body = line[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", body)]


def _is_separator(cells: list[str]) -> bool:
    nonempty = [c for c in cells if c]
    return bool(nonempty) and all(re.fullmatch(r":?-{2,}:?", c) for c in nonempty)


def _pick(headers: list[str], keys: tuple, exclude: set[int]) -> Optional[int]:
    for i, h in enumerate(headers):
        if i not in exclude and any(k in h.lower() for k in keys):
            return i
    return None


def normalize_severity(raw: str) -> Optional[str]:
    """Map a severity cell (Korean or English) to high/medium/low, else None."""
    text = raw.strip().lower()
    if not text:
        return None
    for name, words in _SEVERITY_WORDS.items():
        # one-character words must be the whole cell, longer ones may be contained
        if any(text == w or (len(w) > 1 and w in text) for w in words):
            return name
    return None


def _choose_columns(headers: list[str]) -> tuple[int, int, Optional[int]]:
    lowered = [h.strip().lower() for h in headers]
    used = {i for i, h in enumerate(lowered) if h in INDEX_HEADERS}
    qi = _pick(headers, QUOTE_KEYS, used)
    if qi is not None:
        used.add(qi)
    ci = _pick(headers, COMMENT_KEYS, used)
    if ci is not None:
        used.add(ci)
    free = [i for i in range(len(headers)) if i not in used]
    if qi is None:
        qi = free.pop(0) if free else 0
    if ci is None:
        ci = free.pop(0) if free else min(qi + 1, len(headers) - 1)
    si = _pick(headers, SEVERITY_KEYS, {qi, ci})
    return qi, ci, si


def parse_table(markdown: str) -> ParsedTable:
    """Parse every pipe-table block of `markdown`; never raises."""
    result = ParsedTable()
    block: list[list[str]] = []

    def flush() -> None:
        if len(block) < 1:
            return
        headers = block[0]
        result.has_table = True
        if result.headers is None:
            result.headers = headers
        qi, ci, si = _choose_columns(headers)
        for cells in block[1:]:
            if _is_separator(cells):
                continue
            if len(cells) != len(headers):
                result.skipped += 1
                continue
            quote = cells[qi].strip(QUOTE_CHARS)
            if not quote:
                result.skipped += 1
                continue
            result.rows.append(
                {
                    "quote": quote,
                    "comment": cells[ci],
                    "severity": normalize_severity(cells[si]) if si is not None else None,
                }
            )

    for line in markdown.splitlines():
        cells = split_row(line)
        if cells is None:
            flush()
            block = []
        else:
            block.append(cells)
    flush()
    return result
