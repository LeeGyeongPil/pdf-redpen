"""Page text extraction: pdfplumber characters -> one flat string plus an index map.

The very same flat string is (a) sent to the model and (b) searched when
grounding a quote, so a quote copied from the page text can always be found.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

LINE_TOLERANCE = 2.0  # points; chars whose top differs less are on the same line
CID_RATIO_LIMIT = 0.3  # share of "(cid:N)" chars above which a page counts as broken
MAX_PAGE_CHARS = 12000  # text sent to the model per page is cut here


@dataclass
class Char:
    text: str
    bbox: tuple  # (x0, top, x1, bottom), origin top-left, PDF points
    line: int


@dataclass
class PageText:
    """Everything grounding needs for one page."""

    number: int  # 1-based
    width: float
    height: float
    chars: list[Char]
    flat: str = ""
    index_map: list = field(default_factory=list)  # flat position -> char index or None

    def __post_init__(self) -> None:
        if not self.flat:
            self.flat, self.index_map = build_flat(self.chars)

    @property
    def has_text_layer(self) -> bool:
        return text_layer_ok(self.chars)

    def prompt_text(self) -> tuple[str, bool]:
        """Flat text for the model; second value says whether it was truncated."""
        if len(self.flat) > MAX_PAGE_CHARS:
            return self.flat[:MAX_PAGE_CHARS], True
        return self.flat, False


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def _fold_char(ch: str) -> str:
    # Hangul compatibility jamo (U+3130..U+318F) are left alone: NFKC would turn
    # them into conjoining jamo that a per-Char flat string and a whole-quote
    # normalisation could then merge differently.
    if "㄰" <= ch <= "㆏":
        return ch
    return unicodedata.normalize("NFKC", ch)


def fold(text: str) -> str:
    """NFC, then compatibility-fold each character (ligatures such as fi/fl get spelled out).

    Used for both the page text and the quote, so the two always agree.
    """
    return "".join(_fold_char(ch) for ch in nfc(text))


def build_flat(chars: list[Char]) -> tuple[str, list]:
    """Join chars into one string; a synthetic space marks each line break.

    index_map[i] is the index of the Char that produced flat[i], or None for a
    synthetic space. Folding (NFC, then NFKC per char) may turn one char into several, all map to that Char.
    """
    out: list[str] = []
    idx: list = []
    prev_line = None
    for i, c in enumerate(chars):
        if prev_line is not None and c.line != prev_line:
            out.append(" ")
            idx.append(None)
        piece = fold(c.text)
        for ch in piece:
            out.append(ch)
            idx.append(i)
        prev_line = c.line
    return "".join(out), idx


def text_layer_ok(chars: list[Char]) -> bool:
    """False for pages with no real text (scans) or mostly "(cid:N)" glyph names."""
    visible = [c for c in chars if c.text.strip()]
    if not visible:
        return False
    broken = sum(1 for c in visible if c.text.startswith("(cid:"))
    return broken / len(visible) <= CID_RATIO_LIMIT


def chars_from_plumber(page) -> list[Char]:
    """Convert pdfplumber page.chars (content order) into Char objects with line numbers."""
    out: list[Char] = []
    line_no = -1
    last_top = None
    for c in page.chars:
        if last_top is None or abs(c["top"] - last_top) > LINE_TOLERANCE:
            line_no += 1
            last_top = c["top"]
        out.append(Char(c["text"], (c["x0"], c["top"], c["x1"], c["bottom"]), line_no))
    return out


def page_text_from_plumber(page, number: int) -> PageText:
    return PageText(number, float(page.width), float(page.height), chars_from_plumber(page))
