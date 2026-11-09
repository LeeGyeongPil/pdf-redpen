"""Render one PDF page to PNG with pypdfium2 (installed together with pdfplumber).

  python scripts/render_page.py out/reviewed.pdf 1 [out.png]

Also prints how many strongly coloured pixels were drawn, a quick proof that the
/AP appearance streams render in a second PDF engine (pdfium).
"""
import sys

import pypdfium2 as pdfium


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    src, page_no = sys.argv[1], int(sys.argv[2])
    dst = sys.argv[3] if len(sys.argv) > 3 else f"page{page_no}.png"
    pdf = pdfium.PdfDocument(src)
    # may_draw_annots defaults to True: pdfium paints the annotation appearance streams
    image = pdf[page_no - 1].render(scale=2).to_pil().convert("RGB")
    image.save(dst)
    colored = sum(1 for r, g, b in image.getdata() if max(r, g, b) - min(r, g, b) > 60)
    print(f"wrote {dst}; colored pixels: {colored}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
