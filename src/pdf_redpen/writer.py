"""Writing annotations with pypdf: Highlight, page memo (Text), /AP streams, clear.

Every annotation made here carries /T = author, which is how `clear` later
recognises its own work and leaves annotations made by people alone.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    FloatObject,
    NameObject,
    NumberObject,
    TextStringObject,
)

from .models import InputError

DEFAULT_AUTHOR = "pdf-redpen"

# Highlight colours by severity (RGB 0..1). Unknown severity -> yellow.
COLORS = {
    "high": (1.0, 0.45, 0.45),
    "medium": (1.0, 0.92, 0.2),
    "low": (0.55, 0.9, 0.55),
    None: (1.0, 0.92, 0.2),
}
MEMO_COLOR = (1.0, 0.85, 0.2)
MEMO_SIZE = 20.0

# pypdf warns about non-embedded CJK font names while cloning; extraction is
# done by pdfplumber so the warnings are noise for the user.
logging.getLogger("pypdf").setLevel(logging.ERROR)


def _num_array(values) -> ArrayObject:
    return ArrayObject(FloatObject(round(float(v), 4)) for v in values)


def open_source(path: Path) -> PdfReader:
    """Open a PDF for writing, with errors that say what to do."""
    if not path.is_file():
        raise InputError("err.pdf_not_found", path=path)
    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted and not reader.decrypt(""):
            raise InputError("err.pdf_encrypted", path=path)
        len(reader.pages)  # force a parse so broken files fail here
    except InputError:
        raise
    except Exception as exc:  # pypdf raises many types for broken files
        raise InputError("err.pdf_unreadable", path=path, reason=exc) from exc
    return reader


class AnnotationWriter:
    """Adds annotations page by page and saves the whole file after each page."""

    def __init__(self, reader: PdfReader, dst: Path, author: str = DEFAULT_AUTHOR) -> None:
        self._writer = PdfWriter(clone_from=reader)
        self._dst = dst
        self._part = dst.with_name(dst.name + ".part")
        self.author = author
        self._memos: dict[int, DictionaryObject] = {}  # page index -> memo annotation

    # ---- annotation creation ---------------------------------------------
    def _form_xobject(self, bbox, content: str, alpha: Optional[float] = None) -> object:
        stream = DecodedStreamObject()
        stream.set_data(content.encode("ascii"))
        stream.update(
            {
                NameObject("/Type"): NameObject("/XObject"),
                NameObject("/Subtype"): NameObject("/Form"),
                NameObject("/BBox"): _num_array(bbox),
            }
        )
        if alpha is not None:
            # Multiply blend keeps the text readable under the colour.
            gs = DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/ExtGState"),
                    NameObject("/BM"): NameObject("/Multiply"),
                    NameObject("/ca"): FloatObject(alpha),
                }
            )
            stream[NameObject("/Resources")] = DictionaryObject(
                {NameObject("/ExtGState"): DictionaryObject({NameObject("/GS"): gs})}
            )
        return self._writer._add_object(stream)  # noqa: SLF001 - pypdf has no public call

    def add_highlight(self, page_index: int, qp: list[float], contents: str, severity: Optional[str]) -> None:
        r, g, b = COLORS.get(severity, COLORS[None])
        xs, ys = qp[0::2], qp[1::2]
        rect = (min(xs), min(ys), max(xs), max(ys))
        ops = ["/GS gs", f"{r:.3f} {g:.3f} {b:.3f} rg"]
        for i in range(0, len(qp), 8):
            x0, yh, x1, _, _, yl, _, _ = qp[i : i + 8]
            ops.append(f"{x0:.3f} {yl:.3f} {x1 - x0:.3f} {yh - yl:.3f} re f")
        ap = self._form_xobject(rect, "\n".join(ops), alpha=1.0)
        annot = {
            "/Type": "/Annot",
            "/Subtype": "/Highlight",
            "/Rect": _num_array(rect),
            "/QuadPoints": _num_array(qp),
            "/C": _num_array((r, g, b)),
            "/F": NumberObject(4),  # print flag: visible in print and view
            "/T": TextStringObject(self.author),
            "/Contents": TextStringObject(contents),
            "/AP": DictionaryObject({NameObject("/N"): ap}),
        }
        self._writer.add_annotation(page_index, annot)

    def set_memo(self, page_index: int, text: str) -> None:
        """Create or update the single page memo (/Text annotation) of a page."""
        existing = self._memos.get(page_index)
        if existing is not None:
            existing[NameObject("/Contents")] = TextStringObject(text)
            return
        page = self._writer.pages[page_index]
        w, h = float(page.mediabox.width), float(page.mediabox.height)
        rect = (w - 30 - MEMO_SIZE, h - 10 - MEMO_SIZE, w - 30, h - 10)
        r, g, b = MEMO_COLOR
        ap = self._form_xobject(
            (0, 0, MEMO_SIZE, MEMO_SIZE),
            f"{r:.3f} {g:.3f} {b:.3f} rg 0 0 {MEMO_SIZE} {MEMO_SIZE} re f 0 0 0 RG 0.5 w "
            f"0.25 0.25 {MEMO_SIZE - 0.5} {MEMO_SIZE - 0.5} re S",
        )
        annot = {
            "/Type": "/Annot",
            "/Subtype": "/Text",
            "/Rect": _num_array(rect),
            "/Name": "/Comment",
            "/C": _num_array(MEMO_COLOR),
            "/F": NumberObject(4),
            "/Open": False,
            "/T": TextStringObject(self.author),
            "/Contents": TextStringObject(text),
            "/AP": DictionaryObject({NameObject("/N"): ap}),
        }
        self._memos[page_index] = self._writer.add_annotation(page_index, annot)

    # ---- saving ------------------------------------------------------------
    def save(self) -> None:
        """Write the full file to <dst>.part, then replace dst atomically.

        A full save per page is deliberate: repeated incremental saves lost
        earlier annotations in the probe, and a crash must never leave a
        half-written output.
        """
        self._dst.parent.mkdir(parents=True, exist_ok=True)
        with open(self._part, "wb") as fh:
            self._writer.write(fh)
        os.replace(self._part, self._dst)

    def close(self) -> None:
        """Always safe to call: removes a leftover .part file."""
        try:
            if self._part.exists():
                self._part.unlink()
        finally:
            self._writer.close()


def clear_annotations(src: Path, dst: Path, author: str = DEFAULT_AUTHOR) -> int:
    """Copy src to dst without annotations whose /T equals author. Returns removed count."""
    reader = open_source(src)
    writer = PdfWriter(clone_from=reader)
    removed = 0
    try:
        for page in writer.pages:
            annots = page.get("/Annots")
            if annots is None:
                continue
            annots = annots.get_object()
            keep = ArrayObject()
            for ref in annots:
                obj = ref.get_object()
                if obj.get("/T") == author:
                    removed += 1
                else:
                    keep.append(ref)
            page[NameObject("/Annots")] = keep
        if removed:
            try:
                writer.compress_identical_objects(remove_identicals=False, remove_orphans=True)
            except Exception:  # size optimisation only
                pass
        dst.parent.mkdir(parents=True, exist_ok=True)
        part = dst.with_name(dst.name + ".part")
        try:
            with open(part, "wb") as fh:
                writer.write(fh)
            os.replace(part, dst)
        finally:
            if part.exists():
                part.unlink()
    finally:
        writer.close()
    return removed
