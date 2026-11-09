"""AC-9: clear removes only the annotations this tool made."""
from __future__ import annotations

from conftest import FINDINGS_JSON, PLAIN_PDF, add_human_annotation, annots_of
from pdf_redpen.cli import main


def test_clear_removes_only_own(tmp_path, capsys):
    human = add_human_annotation(PLAIN_PDF, tmp_path / "human.pdf")
    marked = tmp_path / "marked.pdf"
    assert main(["apply", str(human), str(FINDINGS_JSON), "-o", str(marked)]) == 0
    before = [len(annots_of(marked, i)) for i in range(3)]
    assert before[0] > 1  # human note + our highlights

    cleared = tmp_path / "clean.pdf"
    assert main(["clear", str(marked), "-o", str(cleared)]) == 0
    assert "removed 10 annotation(s)" in capsys.readouterr().out
    remaining = [a for i in range(3) for a in annots_of(cleared, i)]
    assert len(remaining) == 1
    assert str(remaining[0]["/Contents"]) == "human note" and remaining[0]["/T"] == "Alice"


def test_clear_with_nothing_to_remove(tmp_path):
    out = tmp_path / "same.pdf"
    assert main(["clear", str(PLAIN_PDF), "-o", str(out)]) == 0
    assert out.is_file()


def test_clear_custom_author(tmp_path):
    human = add_human_annotation(PLAIN_PDF, tmp_path / "h.pdf", author="Bob")
    out = tmp_path / "c.pdf"
    assert main(["clear", str(human), "-o", str(out), "--author", "Bob"]) == 0
    assert annots_of(out, 0) == []
