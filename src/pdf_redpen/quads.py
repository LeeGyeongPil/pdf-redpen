"""Matched characters -> one rectangle per text line -> PDF QuadPoints.

Extraction coordinates have their origin at the top-left (y grows downward);
PDF annotations use the bottom-left origin, hence `y_pdf = height - top`.
"""
from __future__ import annotations

from .textlayer import Char

Rect = tuple[float, float, float, float]  # (x0, top, x1, bottom) top-left origin


def line_rects(chars: list[Char], indices: list[int]) -> list[Rect]:
    """Merge the matched chars of each text line into a single rectangle."""
    by_line: dict[int, list] = {}
    for i in indices:
        c = chars[i]
        if c.text.isspace():
            continue
        by_line.setdefault(c.line, []).append(c.bbox)
    rects: list[Rect] = []
    for _, boxes in sorted(by_line.items()):
        rects.append(
            (
                min(b[0] for b in boxes),
                min(b[1] for b in boxes),
                max(b[2] for b in boxes),
                max(b[3] for b in boxes),
            )
        )
    return rects


def quad_points(rects: list[Rect], page_height: float) -> list[float]:
    """Flatten rects to PDF QuadPoints: 8 numbers per line, top-left first.

    Order per quad: top-left, top-right, bottom-left, bottom-right (what
    Acrobat and pdfium actually expect, despite the spec's counter-clockwise text).
    """
    qp: list[float] = []
    for x0, top, x1, bottom in rects:
        y_low, y_high = page_height - bottom, page_height - top
        qp += [x0, y_high, x1, y_high, x0, y_low, x1, y_low]
    return qp


def bounding_rect(qp: list[float]) -> tuple[float, float, float, float]:
    """PDF-space /Rect that encloses all quads."""
    xs, ys = qp[0::2], qp[1::2]
    return min(xs), min(ys), max(xs), max(ys)
