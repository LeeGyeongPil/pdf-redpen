"""AC-7: a failure on page 2 keeps page 1's annotations; no .part file is left."""
from __future__ import annotations

import json

import pytest

from conftest import PLAIN_PDF, RECORDED, count_by_subtype
from pdf_redpen.llm import MockClient
from pdf_redpen.pipeline import LLMProvider, run_pipeline
from pdf_redpen.report import write_reports


class FailsOnPage2(MockClient):
    def complete(self, messages, *, page, turn):
        if page == 2:
            raise RuntimeError("boom on page 2")
        return super().complete(messages, page=page, turn=turn)


def test_failure_on_page2_keeps_page1(tmp_path):
    dst = tmp_path / "out.pdf"
    provider = LLMProvider(FailsOnPage2(RECORDED), "check", recall=True)
    report = run_pipeline(PLAIN_PDF, dst, provider, mode="review (mock: practice replay)", recall=True)

    assert dst.is_file()
    assert count_by_subtype(dst, 0).get("/Highlight", 0) == 5  # page 1 survived (5 of its findings)
    assert list(tmp_path.glob("*.part")) == []
    assert [p.status for p in report.pages] == ["ok", "error", "skipped_no_text_layer"]
    assert "boom on page 2" in report.pages[1].detail

    _, md = write_reports(report, dst)
    assert "error" in md.read_text(encoding="utf-8")


def test_unexpected_crash_leaves_finished_pages_and_no_part(tmp_path, monkeypatch):
    """Even if the writer itself dies, the file saved after page 1 stays valid."""
    from pdf_redpen import pipeline

    dst = tmp_path / "out.pdf"
    real_place_calls = {"n": 0}
    original = pipeline.line_rects

    def exploding(*a, **k):
        real_place_calls["n"] += 1
        if real_place_calls["n"] > 5:  # first 5 placements are page 1
            raise KeyboardInterrupt  # not an Exception: escapes the per-page guard
        return original(*a, **k)

    monkeypatch.setattr(pipeline, "line_rects", exploding)
    with pytest.raises(KeyboardInterrupt):
        run_pipeline(PLAIN_PDF, dst, LLMProvider(MockClient(RECORDED), "check", recall=True), mode="review")
    assert count_by_subtype(dst, 0).get("/Highlight", 0) == 5
    assert list(tmp_path.glob("*.part")) == []
