"""Review of one page: first turn, optional recall turn, merge without duplicates.

A single model answer misses things and varies from run to run. The recall turn
shows the model its own first findings in the same conversation and asks for the
missed ones only; rows whose quote duplicates an earlier one are dropped.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from . import prompts
from .llm import Client, LLMError
from .models import Finding
from .table import parse_table
from .textlayer import PageText


def quote_key(quote: str) -> str:
    """Letters and digits only, lower-cased: the identity of a quote for de-duplication."""
    return re.sub(r"[\W_]+", "", unicodedata.normalize("NFC", quote)).lower()


@dataclass
class PageReview:
    first: list[Finding] = field(default_factory=list)
    added: list[Finding] = field(default_factory=list)
    deduped: int = 0
    broken_rows: int = 0
    no_table: bool = False
    prompts: list[str] = field(default_factory=list)
    responses: list[str] = field(default_factory=list)
    recall_error: str = ""

    @property
    def findings(self) -> list[Finding]:
        return self.first + self.added


def _to_findings(rows: list[dict], page_no: int, source: str) -> list[Finding]:
    return [Finding(page_no, r["quote"], r["comment"], r["severity"], source) for r in rows]


def review_page(client: Client, page: PageText, instructions: str, *, recall: bool,
                lang: str = "ko") -> PageReview:
    out = PageReview()
    text, _ = page.prompt_text()
    messages = prompts.first_turn(page.number, text, instructions, lang)
    out.prompts.append(messages[-1]["content"])
    answer1 = client.complete(messages, page=page.number, turn=1)  # LLMError -> caller marks page
    out.responses.append(answer1)
    parsed = parse_table(answer1)
    out.broken_rows += parsed.skipped
    out.no_table = not parsed.has_table
    out.first = _to_findings(parsed.rows, page.number, "turn1")

    if not recall:
        return out

    follow = prompts.recall_turn(answer1, out.first, lang)
    messages = messages + follow
    out.prompts.append(follow[-1]["content"])
    try:
        answer2 = client.complete(messages, page=page.number, turn=2)
    except LLMError as exc:  # keep the first-turn findings
        out.recall_error = str(exc)
        return out
    out.responses.append(answer2)
    parsed2 = parse_table(answer2)
    out.broken_rows += parsed2.skipped
    seen = {quote_key(f.quote) for f in out.first}
    for f in _to_findings(parsed2.rows, page.number, "recall"):
        key = quote_key(f.quote)
        if key in seen:
            out.deduped += 1
        else:
            seen.add(key)
            out.added.append(f)
    return out
