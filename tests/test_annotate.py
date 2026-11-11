"""AC-3: annotations re-read by two independent readers; text under each quad is the quote."""
from __future__ import annotations

import pdfplumber
from pypdf import PdfReader

from conftest import FINDINGS_JSON, PLAIN_PDF
from pdf_redpen import annotate_pdf
from pdf_redpen.i18n import t
from pdf_redpen.models import HIGHLIGHTED, findings_from_json
from pdf_redpen.recall import quote_key


def test_reread_two_readers(tmp_path, sample_pdf):
    dst = tmp_path / "out.pdf"
    findings = findings_from_json(FINDINGS_JSON.read_text(encoding="utf-8"))
    report = annotate_pdf(sample_pdf, findings, dst)
    by_comment = {p.finding.comment: p for p in report.placements}

    reader = PdfReader(str(dst))
    with pdfplumber.open(str(dst)) as pdf:
        checked = 0
        for pno, plumber_page in enumerate(pdf.pages):
            raw = [a.get_object() for a in (reader.pages[pno].get("/Annots") or [])]
            assert len(raw) == len(plumber_page.annots)  # both readers see the same number
            height = float(plumber_page.height)
            for a in raw:
                if a["/Subtype"] != "/Highlight":
                    continue
                assert a["/T"] == "pdf-redpen"
                assert len(a["/C"]) == 3
                assert "/N" in a["/AP"]
                qp = [float(v) for v in a["/QuadPoints"]]
                assert len(qp) % 8 == 0 and qp
                under = []
                for i in range(0, len(qp), 8):
                    xs, ys = qp[i:i + 8:2], qp[i + 1:i + 8:2]
                    x0, x1 = min(xs), max(xs)
                    top, bottom = height - max(ys), height - min(ys)  # back to top-left origin
                    for c in plumber_page.chars:
                        cx, cy = (c["x0"] + c["x1"]) / 2, (c["top"] + c["bottom"]) / 2
                        if x0 <= cx <= x1 and top <= cy <= bottom:
                            under.append(c["text"])
                placement = by_comment[str(a["/Contents"]).removeprefix(t("tag.loose", "en") + " ")]
                assert placement.status == HIGHLIGHTED
                if placement.stage == "prefix25":
                    continue  # loose match: painted text is longer than the quote on purpose
                assert quote_key(placement.finding.quote) in quote_key("".join(under))
                checked += 1
    assert checked == 8


def test_annotate_pdf_keeps_source_unchanged(tmp_path):
    before = PLAIN_PDF.read_bytes()
    annotate_pdf(PLAIN_PDF, [], tmp_path / "o.pdf")
    assert PLAIN_PDF.read_bytes() == before
