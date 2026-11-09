"""AC-2: five stages, duplicate avoidance, neighbour page, not-found - on both sample PDFs."""
from __future__ import annotations

from functools import lru_cache

import pytest

from conftest import PDFS, load_pages
from pdf_redpen import ground
from pdf_redpen.grounding import ground_finding
from pdf_redpen.models import findings_from_json
from pdf_redpen.quads import line_rects

from conftest import FINDINGS_JSON

# (stage, page where found) per case in examples/findings.json order; same as the probe.
EXPECTED = [
    ("exact", 1),  # one line
    ("exact", 1),  # crosses a line break
    ("ws_collapse", 1),  # double space and newline in the quote
    ("no_space", 1),  # Korean spacing removed
    ("alnum_only", 1),  # punctuation changed
    ("prefix25", 1),  # tail paraphrased
    ("exact", 2),  # duplicate #1
    ("exact", 2),  # duplicate #2 -> next occurrence
    ("exact", 2),  # model said page 1, sentence is on page 2
    (None, None),  # not in the document
]


@lru_cache(maxsize=None)
def run_cases(kind: str):
    pages = load_pages(PDFS[kind])
    findings = findings_from_json(FINDINGS_JSON.read_text(encoding="utf-8"))
    used: dict[int, set[int]] = {}
    out = []
    for f in findings:
        res = ground_finding(lambda p: pages[p - 1], len(pages), f.page, f.quote, used)
        if res is None:
            out.append(None)
            continue
        page_no, m = res
        used[page_no].update(m.indices)
        out.append((page_no, m, line_rects(pages[page_no - 1].chars, m.indices)))
    return out


@pytest.mark.parametrize("kind", sorted(PDFS))
@pytest.mark.parametrize("case", range(10))
def test_probe_cases(kind, case):
    got = run_cases(kind)[case]
    stage, page = EXPECTED[case]
    if stage is None:
        assert got is None
    else:
        assert got is not None
        assert (got[1].stage, got[0]) == (stage, page)


@pytest.mark.parametrize("kind", sorted(PDFS))
def test_duplicates_land_on_different_lines(kind):
    first, second = run_cases(kind)[6], run_cases(kind)[7]
    assert first[2][0][1] != second[2][0][1]  # top of the first rect differs
    assert not set(first[1].indices) & set(second[1].indices)


def test_ground_respects_used_and_empty_quote():
    pages = load_pages(PDFS["plain"])
    page2 = pages[1]
    q = "결론 문장은 다시 한번 결론 문장으로 반복됩니다"
    a = ground(page2, q, set())
    b = ground(page2, q, set(a.indices))
    c = ground(page2, q, set(a.indices) | set(b.indices))
    assert a and b and c is None
    assert ground(page2, "   ", set()) is None


def test_prefix_is_only_a_last_resort():
    """A quote that alnum matching can place must not be painted by the loose prefix stage."""
    page1 = load_pages(PDFS["plain"])[0]
    m = ground(page1, "The quarterly revenue grew by fifteen-percent!", set())
    assert m.stage == "alnum_only"
