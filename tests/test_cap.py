"""AC-6: findings above the per-page cap collapse into one page memo."""
from __future__ import annotations

import json

from conftest import FINDINGS_JSON, PLAIN_PDF, annots_of, count_by_subtype
from pdf_redpen.cli import main


def test_cap_three_via_cli(tmp_path, capsys):
    dst = tmp_path / "cap3.pdf"
    code = main(["apply", str(PLAIN_PDF), str(FINDINGS_JSON), "-o", str(dst), "--max-highlights-per-page", "3"])
    assert code == 0
    assert count_by_subtype(dst, 0) == {"/Highlight": 3, "/Text": 1}
    memo = [a for a in annots_of(dst, 0) if a["/Subtype"] == "/Text"][0]
    assert str(memo["/Contents"]).count("[상한 초과]") == 3
    report = json.loads(dst.with_suffix(".report.json").read_text(encoding="utf-8"))
    assert report["counts"]["memo_overflow"] == 3
    statuses = [f["status"] for f in report["findings"]]
    assert statuses.count("memo_overflow") == 3
    assert "1 page memo" not in capsys.readouterr().out  # 3 overflow + 1 not found = 4 memo findings


def test_cap_must_be_positive(tmp_path, capsys):
    code = main(["apply", str(PLAIN_PDF), str(FINDINGS_JSON), "-o", str(tmp_path / "o.pdf"),
                 "--max-highlights-per-page", "0"])
    assert code == 2 and "1 or more" in capsys.readouterr().err
