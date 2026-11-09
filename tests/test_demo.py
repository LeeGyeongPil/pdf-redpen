"""AC-1: the demo runs offline from one command and produces the expected result."""
from __future__ import annotations

import json
import subprocess
import sys

from pdf_redpen.cli import main

SUMMARY = "9 findings: 8 highlighted, 1 page memo, 1 page skipped (no text layer)"
STAGES = "exact=4 ws_collapse=1 no_space=1 alnum_only=1 prefix25=1"


def test_demo_runs_offline(tmp_path, capsys):
    assert main(["demo", "--out", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert SUMMARY in out and STAGES in out
    assert "Practice mock mode" in out  # honest label
    for name in ("reviewed.pdf", "reviewed.report.json", "reviewed.report.md"):
        assert (tmp_path / name).is_file()
    report = json.loads((tmp_path / "reviewed.report.json").read_text(encoding="utf-8"))
    assert report["summary"] == SUMMARY
    assert report["stage_counts"] == {"exact": 4, "ws_collapse": 1, "no_space": 1, "alnum_only": 1, "prefix25": 1}
    c = report["counts"]
    assert (c["first_pass"], c["recall_added"], c["recall_deduped"], c["broken_rows"]) == (8, 1, 1, 1)
    # neighbour page: the page-2 finding about 2025 sales is placed on page 1
    moved = [f for f in report["findings"] if f["requested_page"] != f["page"]]
    assert len(moved) == 1 and moved[0]["page"] == 1
    md = (tmp_path / "reviewed.report.md").read_text(encoding="utf-8")
    assert "Practice mock mode" in md and "prefix25" in md


def test_demo_as_module_in_a_fresh_process(tmp_path):
    done = subprocess.run([sys.executable, "-m", "pdf_redpen", "demo", "--out", str(tmp_path)],
                          capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    assert SUMMARY in done.stdout
