"""Shared fixtures: sample PDFs, helpers that build PDFs with pypdf, annotation readers."""
from __future__ import annotations

import json
from pathlib import Path

import pdfplumber
import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, FloatObject, NameObject, TextStringObject

from pdf_redpen.textlayer import PageText, page_text_from_plumber

ROOT = Path(__file__).resolve().parent.parent
PLAIN_PDF = ROOT / "src" / "pdf_redpen" / "data" / "sample_report.pdf"
EMBEDDED_PDF = ROOT / "examples" / "sample_embedded.pdf"
FINDINGS_JSON = ROOT / "examples" / "findings.json"
RECORDED = ROOT / "src" / "pdf_redpen" / "data" / "recorded"

PDFS = {"plain": PLAIN_PDF, "embedded": EMBEDDED_PDF}


@pytest.fixture(params=sorted(PDFS))
def sample_pdf(request) -> Path:
    return PDFS[request.param]


def load_pages(path: Path) -> list[PageText]:
    with pdfplumber.open(str(path)) as pdf:
        return [page_text_from_plumber(p, i + 1) for i, p in enumerate(pdf.pages)]


def annots_of(path: Path, page_index: int) -> list:
    reader = PdfReader(str(path))
    raw = reader.pages[page_index].get("/Annots") or []
    return [a.get_object() for a in raw]


def count_by_subtype(path: Path, page_index: int) -> dict[str, int]:
    out: dict[str, int] = {}
    for a in annots_of(path, page_index):
        out[a["/Subtype"]] = out.get(a["/Subtype"], 0) + 1
    return out


def make_blank_pdf(path: Path, pages: int = 2) -> Path:
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(width=420, height=595)
    with open(path, "wb") as fh:
        w.write(fh)
    return path


def add_human_annotation(src: Path, dst: Path, author: str = "Alice") -> Path:
    """Copy src and add one /Text annotation made by a person on page 1."""
    w = PdfWriter(clone_from=PdfReader(str(src)))
    w.add_annotation(
        0,
        {
            "/Type": "/Annot",
            "/Subtype": "/Text",
            "/Rect": ArrayObject(FloatObject(v) for v in (10, 10, 30, 30)),
            "/Contents": TextStringObject("human note"),
            "/T": TextStringObject(author),
        },
    )
    with open(dst, "wb") as fh:
        w.write(fh)
    return dst


@pytest.fixture
def findings_json() -> list[dict]:
    return json.loads(FINDINGS_JSON.read_text(encoding="utf-8"))
