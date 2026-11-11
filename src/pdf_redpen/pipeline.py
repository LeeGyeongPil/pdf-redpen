"""The page loop: extract -> (review) -> ground -> annotate -> save, one page at a time.

A failure on one page is recorded for that page only; pages already finished
stay in the output file because the file is saved after every page.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional, Protocol

import pdfplumber

from .grounding import ground_finding
from .i18n import CodedError, t
from .llm import Client
from .models import (
    HIGHLIGHTED,
    MEMO_NOT_FOUND,
    MEMO_OVERFLOW,
    PAGE_ERROR,
    PAGE_SKIPPED,
    Finding,
    InputError,
    PageResult,
    Placement,
    Report,
)
from .quads import line_rects, quad_points
from .recall import PageReview, review_page
from .textlayer import PageText, page_text_from_plumber
from .writer import DEFAULT_AUTHOR, AnnotationWriter, open_source

QUOTE_PREVIEW = 40  # characters of the quote shown in memos


class Provider(Protocol):
    """Where the findings of a page come from."""

    skip_blank: bool

    def findings_for(self, page: PageText) -> tuple[list[Finding], Optional[PageReview]]: ...


class LLMProvider:
    """Ask a model (real or replayed) about each page. Pages without text are skipped."""

    skip_blank = True

    def __init__(self, client: Client, instructions: str, recall: bool = False, lang: str = "ko") -> None:
        self.client, self.instructions, self.recall, self.lang = client, instructions, recall, lang

    def findings_for(self, page: PageText):
        review = review_page(self.client, page, self.instructions, recall=self.recall, lang=self.lang)
        return review.findings, review


class JsonProvider:
    """Findings that already exist (apply mode); no model is called."""

    skip_blank = False

    def __init__(self, findings: Iterable[Finding]) -> None:
        self._by_page: dict[int, list[Finding]] = {}
        self._items: list[Finding] = list(findings)
        for f in self._items:
            self._by_page.setdefault(f.page, []).append(f)

    def check_pages(self, n_pages: int) -> None:
        """Reject findings that point past the last page instead of dropping them silently."""
        for i, f in enumerate(self._items):
            if f.page > n_pages:
                raise InputError("err.item_page", i=i, page=f.page, n_pages=n_pages)

    def findings_for(self, page: PageText):
        return self._by_page.get(page.number, []), None


def _short(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= QUOTE_PREVIEW else text[:QUOTE_PREVIEW] + "…"


def run_pipeline(
    src: Path,
    dst: Path,
    provider: Provider,
    *,
    mode: str,
    max_per_page: int = 20,
    pages: Optional[Iterable[int]] = None,
    author: str = DEFAULT_AUTHOR,
    recall: bool = False,
    on_page_done=None,
    lang: Optional[str] = None,
) -> Report:
    src, dst = Path(src), Path(dst)
    if max_per_page < 1:
        raise InputError("err.cap_min")
    reader = open_source(src)
    n_pages = len(reader.pages)
    selected = sorted(set(pages)) if pages else list(range(1, n_pages + 1))
    bad = [p for p in selected if not 1 <= p <= n_pages]
    if bad:
        raise InputError("err.pages_outside", pages=bad, n_pages=n_pages)
    if isinstance(provider, JsonProvider):
        provider.check_pages(n_pages)

    report = Report(str(src), str(dst), mode, max_per_page=max_per_page, recall_pass=recall)
    writer = AnnotationWriter(reader, dst, author)
    cache: dict[int, PageText] = {}
    used: dict[int, set[int]] = {}
    highlights: dict[int, int] = {}
    memo_lines: dict[int, list[str]] = {}

    def memo(page_no: int, line: str) -> None:
        memo_lines.setdefault(page_no, []).append(line)
        writer.set_memo(page_no - 1, "\n".join(memo_lines[page_no]))

    try:
        with pdfplumber.open(str(src)) as pdf:

            def get_page(p: int) -> PageText:
                if p not in cache:
                    cache[p] = page_text_from_plumber(pdf.pages[p - 1], p)
                return cache[p]

            def place(f: Finding) -> None:
                found = ground_finding(get_page, n_pages, f.page, f.quote, used)
                if found is None:
                    target = min(max(f.page, 1), n_pages)
                    memo(target, f"{t('tag.not_found', lang)} {_short(f.quote)} — {f.comment}")
                    report.placements.append(Placement(f, MEMO_NOT_FOUND, target))
                    return
                p, m = found
                if highlights.get(p, 0) >= max_per_page:
                    memo(p, f"{t('tag.overflow', lang)} {_short(f.quote)} — {f.comment}")
                    report.placements.append(Placement(f, MEMO_OVERFLOW, p, m.stage))
                    return
                page = get_page(p)
                used[p].update(m.indices)
                rects = line_rects(page.chars, m.indices)
                contents = f.comment if m.stage != "prefix25" else f"{t('tag.loose', lang)} {f.comment}"
                writer.add_highlight(p - 1, quad_points(rects, page.height), contents, f.severity)
                highlights[p] = highlights.get(p, 0) + 1
                report.placements.append(Placement(f, HIGHLIGHTED, p, m.stage, len(rects)))

            for p in selected:
                result = PageResult(p)
                try:
                    page = get_page(p)
                    _, result.truncated = page.prompt_text()
                    if provider.skip_blank and not page.has_text_layer:
                        result.status = PAGE_SKIPPED
                        cause = CodedError("detail.no_text_layer")
                        result.detail = str(cause)
                        result.cause = cause  # not a dataclass field: report.json keeps its keys
                    else:
                        findings, review = provider.findings_for(page)
                        if review is not None:
                            result.first_pass = len(review.first)
                            result.recall_added = len(review.added)
                            result.recall_deduped = review.deduped
                            result.broken_rows = review.broken_rows
                            result.no_table = review.no_table
                            result.prompts = review.prompts
                            result.responses_head = [r[:300] for r in review.responses]
                            result.detail = review.recall_error
                            result.cause = review.recall_cause
                        for f in findings:
                            place(f)
                except InputError:
                    raise
                except Exception as exc:  # isolate: only this page fails
                    result.status = PAGE_ERROR
                    result.detail = f"{type(exc).__name__}: {exc}"
                    result.cause, result.cause_prefix = exc, f"{type(exc).__name__}: "
                report.pages.append(result)
                writer.save()  # everything finished so far is safe on disk
                for key in [k for k in cache if k < p]:
                    del cache[key]
                if on_page_done:
                    on_page_done(result)
    finally:
        writer.close()
    return report
