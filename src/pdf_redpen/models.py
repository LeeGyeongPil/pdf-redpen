"""Plain data classes shared by every stage."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# Status values of a placed finding.
HIGHLIGHTED = "highlighted"
MEMO_NOT_FOUND = "memo_not_found"
MEMO_OVERFLOW = "memo_overflow"

# Status values of a page.
PAGE_OK = "ok"
PAGE_SKIPPED = "skipped_no_text_layer"
PAGE_ERROR = "error"

SEVERITIES = ("high", "medium", "low")


class InputError(Exception):
    """The user gave something unusable (bad file, bad JSON, missing model name).

    The message always says how to fix it. The CLI maps this to exit code 2.
    """


@dataclass
class Finding:
    """One review remark: a quoted sentence and a comment about it."""

    page: int  # 1-based page the model (or the JSON file) claims
    quote: str
    comment: str
    severity: Optional[str] = None  # "high" | "medium" | "low" | None
    source: str = "apply"  # "turn1" | "recall" | "apply"


@dataclass
class Match:
    """Where a quote was found: stage name plus indices into the page's Char list."""

    stage: str
    indices: list[int]


@dataclass
class Placement:
    """What happened to one finding."""

    finding: Finding
    status: str  # HIGHLIGHTED | MEMO_NOT_FOUND | MEMO_OVERFLOW
    page: int  # page that actually carries the mark (1-based)
    stage: Optional[str] = None  # grounding stage, None when not found
    lines: int = 0  # number of line quads of the highlight


@dataclass
class PageResult:
    page: int
    status: str = PAGE_OK
    detail: str = ""
    truncated: bool = False
    first_pass: int = 0  # findings from the first turn
    recall_added: int = 0
    recall_deduped: int = 0
    broken_rows: int = 0
    no_table: bool = False
    prompts: list[str] = field(default_factory=list)
    responses_head: list[str] = field(default_factory=list)


@dataclass
class Report:
    source: str
    output: str
    mode: str  # "review", "review (mock)", "apply"
    pages: list[PageResult] = field(default_factory=list)
    placements: list[Placement] = field(default_factory=list)
    max_per_page: int = 20
    recall_pass: bool = False

    # ---- derived counts -------------------------------------------------
    def count(self, status: str) -> int:
        return sum(1 for p in self.placements if p.status == status)

    @property
    def skipped_pages(self) -> int:
        return sum(1 for p in self.pages if p.status == PAGE_SKIPPED)

    @property
    def error_pages(self) -> int:
        return sum(1 for p in self.pages if p.status == PAGE_ERROR)

    def stage_counts(self) -> dict[str, int]:
        from .grounding import STAGE_ORDER

        counts = {s: 0 for s in STAGE_ORDER}
        for p in self.placements:
            if p.stage and p.status == HIGHLIGHTED:
                counts[p.stage] += 1
        return counts


def findings_from_json(text: str, origin: str = "findings JSON") -> list[Finding]:
    """Parse `[{"page": 1, "quote": "...", "comment": "...", "severity": "high"}]`.

    Raises InputError with the offending index so the file can be fixed.
    """
    import json

    try:
        data = json.loads(text)
    except ValueError as exc:
        raise InputError(f"{origin} is not valid JSON ({exc}). Expected a list of objects.") from exc
    if not isinstance(data, list):
        raise InputError(f"{origin} must be a JSON list of objects with page, quote and comment.")
    out: list[Finding] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise InputError(f"{origin}: item {i} is not an object.")
        page, quote, comment = item.get("page"), item.get("quote"), item.get("comment", "")
        if isinstance(page, bool) or not isinstance(page, int) or page < 1:
            raise InputError(f"{origin}: item {i} needs an integer 'page' >= 1 (got {page!r}).")
        if not isinstance(quote, str) or not quote.strip():
            raise InputError(f"{origin}: item {i} needs a non-empty string 'quote'.")
        if not isinstance(comment, str):
            raise InputError(f"{origin}: item {i}: 'comment' must be a string.")
        severity = item.get("severity")
        if severity is not None:
            from .table import normalize_severity

            normalized = normalize_severity(str(severity))
            if normalized is None:
                raise InputError(
                    f"{origin}: item {i}: unknown severity {severity!r}; use high, medium or low "
                    "(or omit 'severity')."
                )
            severity = normalized
        out.append(Finding(page, quote, comment, severity, "apply"))
    return out
