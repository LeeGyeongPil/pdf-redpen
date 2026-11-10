"""Ligature glyphs (U+FB01 'fi' ...) in the text layer must not hide quotes written as 'fi'."""
from __future__ import annotations

import pdfplumber
from pypdf import PdfWriter
from pypdf.generic import (
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
)

from pdf_redpen import ground
from pdf_redpen.textlayer import Char, build_flat, fold, page_text_from_plumber

TO_UNICODE = b"""/CIDInit /ProcSet findresource begin
12 dict begin
begincmap
/CMapName /Adobe-Identity-UCS def
/CMapType 2 def
1 begincodespacerange
<00> <FF>
endcodespacerange
1 beginbfchar
<01> <FB01>
endbfchar
1 beginbfrange
<20> <7E> <0020>
endbfrange
endcmap
CMapName currentdict /CMap defineresource pop
end
end
"""


def make_ligature_pdf(path):
    """One page: Helvetica, byte 0x01 mapped to U+FB01 by a ToUnicode CMap. No fixture file."""
    w = PdfWriter()
    page = w.add_blank_page(width=612, height=792)
    cmap = DecodedStreamObject()
    cmap.set_data(TO_UNICODE)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
            NameObject("/ToUnicode"): w._add_object(cmap),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): w._add_object(font)})}
    )
    content = DecodedStreamObject()
    content.set_data(b"BT /F1 12 Tf 72 720 Td (The \x01nal report has no \x01gures in section two.) Tj ET")
    page[NameObject("/Contents")] = w._add_object(content)
    with open(path, "wb") as fh:
        w.write(fh)
    return path


def _page(tmp_path):
    pdf = make_ligature_pdf(tmp_path / "lig.pdf")
    with pdfplumber.open(pdf) as doc:
        return page_text_from_plumber(doc.pages[0], 1)


def test_pdf_really_holds_ligature_glyphs(tmp_path):
    pdf = make_ligature_pdf(tmp_path / "lig.pdf")
    with pdfplumber.open(pdf) as doc:
        assert "ﬁ" in [c["text"] for c in doc.pages[0].chars]


def test_long_quote_with_fi_is_found(tmp_path):
    page = _page(tmp_path)
    hit = ground(page, "The final report has no figures in section two.", set())
    assert hit is not None and hit.stage == "exact"


def test_short_quote_without_ligature_letters_in_pdf_is_found(tmp_path):
    page = _page(tmp_path)
    hit = ground(page, "has no figures", set())
    assert hit is not None and hit.stage == "exact"


def test_quote_copied_with_ligature_glyph_is_also_found(tmp_path):
    page = _page(tmp_path)
    hit = ground(page, "The ﬁnal report", set())
    assert hit is not None and hit.stage == "exact"


def test_build_flat_spells_out_ligature_onto_one_char():
    flat, index_map = build_flat([Char("ﬁ", (0, 0, 5, 5), 0)])
    assert flat == "fi"
    assert index_map == [0, 0]


def test_all_ligature_block_is_spelled_out():
    assert [fold(c) for c in "ﬀﬁﬂﬃﬄﬅﬆ"] == [
        "ff", "fi", "fl", "ffi", "ffl", "st", "st",
    ]


def test_hangul_compat_jamo_stay_as_they_are():
    # NFKC would merge/convert these; they must stay identical on flat and quote side
    jamo = "ㄱㅏ"  # compatibility jamo g + a
    assert fold(jamo) == jamo
    flat, _ = build_flat([Char("ㄱ", (0, 0, 1, 1), 0), Char("ㅏ", (1, 0, 2, 1), 0)])
    assert flat == jamo == fold(jamo)


def test_nfd_hangul_quote_still_composes():
    assert fold("가") == "가"
