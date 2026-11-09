"""Regenerate the bundled sample PDFs (development only; needs `pip install pymupdf`).

pdf-redpen itself never imports pymupdf. The committed PDFs are the product of
this script, so normal users and CI do not need it.

  python scripts/make_sample_pdf.py            # writes both files below
"""
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
PLAIN = ROOT / "src" / "pdf_redpen" / "data" / "sample_report.pdf"  # non-embedded CJK font reference
EMBEDDED = ROOT / "examples" / "sample_embedded.pdf"  # subset-embedded Droid Sans Fallback

# Invented text: no real company, person or figure.
P1 = (
    "검토 대상 문서의 첫 번째 쪽입니다. 이 보고서는 2025년 매출이 전년 대비 15% 증가했다고 "
    "주장하지만 근거 표가 제시되지 않았습니다. 또한 신규 고객 수는 1,200명으로 집계되었다고 "
    "적혀 있으나 다른 절에서는 1,300명이라고 적혀 있어 서로 맞지 않습니다. "
    "The quarterly revenue grew by fifteen percent, but the supporting table is missing. "
    "This sentence intentionally wraps across several lines so that a quoted passage "
    "will not match the extracted text exactly."
)
P2 = (
    "두 번째 쪽입니다. 결론에서는 모든 위험이 해소되었다고 단정하지만, 앞 절의 위험 목록 중 "
    "세 항목은 여전히 진행 중입니다. 결론 문장은 다시 한번 결론 문장으로 반복됩니다. "
    "결론 문장은 다시 한번 결론 문장으로 반복됩니다. "
    "Risks are declared resolved although three items remain open."
)


def build(dst: Path, embedded: bool) -> None:
    doc = pymupdf.open()
    for text in (P1, P2):
        page = doc.new_page(width=420, height=595)
        if embedded:
            page.insert_font(fontname="F0", fontbuffer=pymupdf.Font("cjk").buffer)
            font = "F0"
        else:
            font = "korea"
        rc = page.insert_textbox(pymupdf.Rect(40, 50, 380, 560), text, fontname=font,
                                 fontsize=11, lineheight=1.5)
        assert rc >= 0, f"text overflow {rc}"
    doc.new_page(width=420, height=595)  # page 3: no text layer at all
    if embedded:
        doc.subset_fonts()
    dst.parent.mkdir(parents=True, exist_ok=True)
    doc.save(dst, garbage=3, deflate=True)
    doc.close()
    print("wrote", dst)


if __name__ == "__main__":
    build(PLAIN, embedded=False)
    build(EMBEDDED, embedded=True)
