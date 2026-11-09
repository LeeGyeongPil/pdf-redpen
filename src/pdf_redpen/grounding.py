"""Five-stage quote locator.

Models rarely copy a sentence exactly: they change whitespace, drop Korean word
spacing, alter punctuation, paraphrase the tail, or name the wrong page. Each
stage below is looser than the one before; the first stage that finds a span of
characters that is not already used wins. Every stage searches a *projected*
string and keeps a map back to the original Char indices, so the highlight is
always drawn from real glyph boxes.
"""
from __future__ import annotations

import re
from typing import Callable, Optional

from .models import Match
from .textlayer import PageText, nfc

PREFIX_LEN = 25
ALNUM_MIN = 4
STAGE_ORDER = ("exact", "ws_collapse", "no_space", "alnum_only", "prefix25")


def _find_unused(hay: str, needle: str, mapping: list, used: set[int]) -> Optional[list[int]]:
    """First occurrence of needle whose chars are all still unused."""
    start = 0
    while needle:
        pos = hay.find(needle, start)
        if pos < 0:
            return None
        span = {mapping[k] for k in range(pos, pos + len(needle)) if mapping[k] is not None}
        if span and not (span & used):
            return sorted(span)
        start = pos + 1
    return None


def _project(flat: str, idx: list, keep: Callable[[str], bool]) -> tuple[str, list]:
    s, m = [], []
    for ch, i in zip(flat, idx):
        if keep(ch):
            s.append(ch)
            m.append(i)
    return "".join(s), m


def _collapse(flat: str, idx: list) -> tuple[str, list]:
    """Replace every whitespace run by a single space."""
    s, m = [], []
    for ch, i in zip(flat, idx):
        if ch.isspace():
            if s and s[-1] == " ":
                continue
            s.append(" ")
            m.append(i)
        else:
            s.append(ch)
            m.append(i)
    return "".join(s), m


def ground(page: PageText, quote: str, used: set[int]) -> Optional[Match]:
    """Find `quote` on one page, avoiding char indices in `used`. None if absent."""
    quote = nfc(quote).strip()
    if not quote:
        return None
    flat, idx = page.flat, page.index_map

    # 1. exact substring
    hit = _find_unused(flat, quote, idx, used)
    if hit:
        return Match("exact", hit)

    # 2. whitespace runs collapsed (double spaces, copied line breaks)
    cflat, cidx = _collapse(flat, idx)
    cq = re.sub(r"\s+", " ", quote)
    hit = _find_unused(cflat, cq, cidx, used)
    if hit:
        return Match("ws_collapse", hit)

    # 3. first 25 chars, extended to the quote's length (tail was paraphrased)
    prefix_match: Optional[Match] = None
    if len(cq) > PREFIX_LEN:
        pre = cq[:PREFIX_LEN]
        start = 0
        while True:
            pos = cflat.find(pre, start)
            if pos < 0:
                break
            end = min(len(cflat), pos + len(cq))
            span = {cidx[k] for k in range(pos, end) if cidx[k] is not None}
            if span and not (span & used):
                prefix_match = Match("prefix25", sorted(span))
                break
            start = pos + 1

    # 4. all whitespace removed (Korean spacing errors)
    sflat, sidx = _project(flat, idx, lambda ch: not ch.isspace())
    sq = re.sub(r"\s+", "", quote)
    hit = _find_unused(sflat, sq, sidx, used)
    if hit:
        return Match("no_space", hit)

    # 5. letters and digits only (punctuation changed)
    aflat, aidx = _project(flat, idx, lambda ch: ch.isalnum())
    aq = "".join(ch for ch in quote if ch.isalnum())
    if len(aq) >= ALNUM_MIN:
        hit = _find_unused(aflat, aq, aidx, used)
        if hit:
            return Match("alnum_only", hit)

    # The prefix match is the loosest guess (it may paint text the model never
    # quoted), so it is only used when the stricter stages 4 and 5 found nothing.
    return prefix_match


def ground_finding(
    get_page: Callable[[int], PageText],
    n_pages: int,
    page_no: int,
    quote: str,
    used: dict[int, set[int]],
) -> Optional[tuple[int, Match]]:
    """Search the claimed page first, then the previous and the next page.

    Returns (actual 1-based page, Match) or None. `used` holds the already
    painted char indices per 1-based page and is NOT modified here.
    """
    page_no = min(max(page_no, 1), n_pages)
    for p in (page_no, page_no - 1, page_no + 1):
        if not (1 <= p <= n_pages):
            continue
        m = ground(get_page(p), quote, used.setdefault(p, set()))
        if m:
            return p, m
    return None
