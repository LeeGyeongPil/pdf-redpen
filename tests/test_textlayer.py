"""AC-8: pages without a usable text layer never reach the model."""
from __future__ import annotations

from conftest import PLAIN_PDF, RECORDED, make_blank_pdf
from pdf_redpen import pipeline
from pdf_redpen.llm import MockClient
from pdf_redpen.pipeline import LLMProvider, run_pipeline
from pdf_redpen.textlayer import Char, PageText, page_text_from_plumber, text_layer_ok


def test_blank_and_cid_pages_skipped(tmp_path, monkeypatch):
    # blank page: a generated PDF with two empty pages
    blank = make_blank_pdf(tmp_path / "blank.pdf", pages=2)
    client = MockClient(RECORDED)
    report = run_pipeline(blank, tmp_path / "o1.pdf", LLMProvider(client, "x"), mode="review")
    assert [p.status for p in report.pages] == ["skipped_no_text_layer"] * 2
    assert client.calls == []

    # cid page: sample page 2 whose glyphs all came out as "(cid:N)"
    real = page_text_from_plumber

    def fake(page, number):
        pt = real(page, number)
        if number == 2:
            cid_chars = [Char(f"(cid:{i})", (10 + i, 10, 20 + i, 20), 0) for i in range(30)]
            return PageText(number, pt.width, pt.height, cid_chars)
        return pt

    monkeypatch.setattr(pipeline, "page_text_from_plumber", fake)
    client = MockClient(RECORDED)
    report = run_pipeline(PLAIN_PDF, tmp_path / "o2.pdf", LLMProvider(client, "x"), mode="review")
    assert [p.status for p in report.pages] == ["ok", "skipped_no_text_layer", "skipped_no_text_layer"]
    assert all(page != 2 and page != 3 for page, _ in client.calls)
    assert client.calls == [(1, 1)]


def test_text_layer_ok_thresholds():
    assert not text_layer_ok([])
    assert not text_layer_ok([Char(" ", (0, 0, 1, 1), 0)])
    good = [Char("a", (0, 0, 1, 1), 0)] * 9
    assert text_layer_ok(good + [Char("(cid:1)", (0, 0, 1, 1), 0)])  # 10% broken is tolerated
    assert not text_layer_ok(good[:3] + [Char("(cid:1)", (0, 0, 1, 1), 0)] * 7)


def test_truncation_is_flagged():
    chars = [Char("a", (i, 0, i + 1, 1), 0) for i in range(13000)]
    text, truncated = PageText(1, 100, 100, chars).prompt_text()
    assert truncated and len(text) == 12000
