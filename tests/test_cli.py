"""Input errors map to exit code 2 with a message that says how to fix them."""
from __future__ import annotations

from conftest import PLAIN_PDF, RECORDED
from pdf_redpen.cli import main, parse_pages
import pytest
from pdf_redpen.models import InputError


def test_missing_pdf(tmp_path, capsys):
    assert main(["clear", str(tmp_path / "nope.pdf"), "-o", str(tmp_path / "o.pdf")]) == 2
    assert "not found" in capsys.readouterr().err


def test_not_a_pdf(tmp_path, capsys):
    bad = tmp_path / "x.pdf"
    bad.write_text("hello")
    assert main(["clear", str(bad), "-o", str(tmp_path / "o.pdf")]) == 2
    assert "could not be read" in capsys.readouterr().err


def test_bad_findings_json(tmp_path, capsys):
    f = tmp_path / "f.json"
    for text, needle in (("{", "not valid JSON"), ('{"a": 1}', "list"), ('[{"page": 0, "quote": "q"}]', "page"),
                         ('[{"page": 1, "quote": ""}]', "quote"), ("[1]", "not an object")):
        f.write_text(text)
        assert main(["apply", str(PLAIN_PDF), str(f), "-o", str(tmp_path / "o.pdf")]) == 2
        assert needle in capsys.readouterr().err


def test_review_without_model_is_exit_2(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("PDF_REDPEN_MODEL", raising=False)
    assert main(["review", str(PLAIN_PDF), "-o", str(tmp_path / "o.pdf")]) == 2
    assert "PDF_REDPEN_MODEL" in capsys.readouterr().err


def test_output_must_differ_from_input(tmp_path, capsys):
    assert main(["clear", str(PLAIN_PDF), "-o", str(PLAIN_PDF)]) == 2
    f = tmp_path / "f.json"
    f.write_text("[]")
    assert main(["apply", str(PLAIN_PDF), str(f), "-o", str(PLAIN_PDF)]) == 2


def test_review_mock_with_pages_and_record_conflict(tmp_path, capsys):
    out = tmp_path / "o.pdf"
    assert main(["review", str(PLAIN_PDF), "-o", str(out), "--mock", str(RECORDED), "--pages", "1", "--recall-pass"]) == 0
    first_line = capsys.readouterr().out.split("\n")[0]
    assert first_line == "5 findings: 5 highlighted, 0 page memos, 0 pages skipped (no text layer)"
    assert main(["review", str(PLAIN_PDF), "--mock", str(RECORDED), "--record", str(tmp_path)]) == 2


def test_parse_pages():
    assert parse_pages("1-3,5") == [1, 2, 3, 5]
    assert parse_pages(None) is None
    for bad in ("a", "3-1", "0"):
        with pytest.raises(InputError):
            parse_pages(bad)


def test_apply_page_beyond_pdf_is_exit_2(tmp_path, capsys):
    f = tmp_path / "f.json"
    f.write_text('[{"page": 1, "quote": "x", "comment": "y"}, {"page": 99, "quote": "x", "comment": "y"}]')
    out = tmp_path / "o.pdf"
    assert main(["apply", str(PLAIN_PDF), str(f), "-o", str(out)]) == 2
    err = capsys.readouterr().err
    assert "item 1" in err and "page 99" in err and "3 page" in err
    assert not out.exists()


def test_apply_unknown_severity_is_exit_2(tmp_path, capsys):
    f = tmp_path / "f.json"
    f.write_text('[{"page": 1, "quote": "x", "comment": "y", "severity": "urgnt"}]')
    assert main(["apply", str(PLAIN_PDF), str(f), "-o", str(tmp_path / "o.pdf")]) == 2
    err = capsys.readouterr().err
    assert "item 0" in err and "urgnt" in err and "high, medium or low" in err
    f.write_text('[{"page": 1, "quote": "x", "comment": "y", "severity": "높음"}]')
    assert main(["apply", str(PLAIN_PDF), str(f), "-o", str(tmp_path / "o.pdf")]) == 0


def test_review_unreachable_endpoint_shows_cause_and_exits_1(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("PDF_REDPEN_MODEL", "m")
    monkeypatch.setenv("PDF_REDPEN_BASE_URL", "http://127.0.0.1:9/v1")
    monkeypatch.setenv("PDF_REDPEN_TIMEOUT", "2")
    assert main(["review", str(PLAIN_PDF), "-o", str(tmp_path / "o.pdf"), "--pages", "1"]) == 1
    err = capsys.readouterr().err
    assert "page 1: error - " in err and "LLMError" in err
    assert "every page failed" in err


def test_review_partial_failure_warns_but_exits_0(tmp_path, capsys, monkeypatch):
    from pdf_redpen import cli, llm

    class Flaky:
        def __init__(self, _directory):
            self.calls = 0

        def complete(self, messages, *, page, turn):
            if page == 1:
                raise llm.LLMError("boom")
            return "no table here"

    monkeypatch.setattr(cli, "MockClient", Flaky)
    assert cli.main(["review", str(PLAIN_PDF), "-o", str(tmp_path / "o.pdf"), "--mock", str(RECORDED),
                     "--pages", "1-2"]) == 0
    err = capsys.readouterr().err
    assert "page 1: error - LLMError: boom" in err and "1 page(s) failed" in err
