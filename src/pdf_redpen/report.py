"""JSON and Markdown reports plus the one-line console summary."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .models import HIGHLIGHTED, MEMO_NOT_FOUND, MEMO_OVERFLOW, Report

MOCK_NOTICE = (
    "Practice mock mode: the answers were replayed from recorded files written by hand, "
    "not produced by a real model. Everything after the answer (table parsing, merging, "
    "grounding, annotation) is the same code as in real mode."
)


def summary_line(r: Report) -> str:
    memos = r.count(MEMO_NOT_FOUND) + r.count(MEMO_OVERFLOW)
    skipped = r.skipped_pages
    parts = [
        f"{r.count(HIGHLIGHTED)} highlighted",
        f"{memos} page memo{'' if memos == 1 else 's'}",
        f"{skipped} page{'' if skipped == 1 else 's'} skipped (no text layer)",
    ]
    if r.error_pages:
        parts.append(f"{r.error_pages} page{'' if r.error_pages == 1 else 's'} failed")
    return f"{len(r.placements)} findings: " + ", ".join(parts)


def stage_line(r: Report) -> str:
    return "stages: " + " ".join(f"{k}={v}" for k, v in r.stage_counts().items())


def recall_line(r: Report) -> str:
    first = sum(p.first_pass for p in r.pages)
    added = sum(p.recall_added for p in r.pages)
    dup = sum(p.recall_deduped for p in r.pages)
    return f"recall pass: first {first}, added {added}, duplicates dropped {dup}"


def _counts(r: Report) -> dict:
    return {
        "findings": len(r.placements),
        "highlighted": r.count(HIGHLIGHTED),
        "memo_not_found": r.count(MEMO_NOT_FOUND),
        "memo_overflow": r.count(MEMO_OVERFLOW),
        "pages_skipped": r.skipped_pages,
        "pages_failed": r.error_pages,
        "first_pass": sum(p.first_pass for p in r.pages),
        "recall_added": sum(p.recall_added for p in r.pages),
        "recall_deduped": sum(p.recall_deduped for p in r.pages),
        "broken_rows": sum(p.broken_rows for p in r.pages),
    }


def to_dict(r: Report) -> dict:
    return {
        "source": r.source,
        "output": r.output,
        "mode": r.mode,
        "max_highlights_per_page": r.max_per_page,
        "recall_pass": r.recall_pass,
        "summary": summary_line(r),
        "counts": _counts(r),
        "stage_counts": r.stage_counts(),
        "pages": [asdict(p) for p in r.pages],
        "findings": [
            {
                "source": p.finding.source,
                "requested_page": p.finding.page,
                "page": p.page,
                "stage": p.stage,
                "status": p.status,
                "severity": p.finding.severity,
                "quote": p.finding.quote,
                "comment": p.finding.comment,
                "lines": p.lines,
            }
            for p in r.placements
        ],
    }


def _cell(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def to_markdown(r: Report) -> str:
    c = _counts(r)
    lines = [
        f"# pdf-redpen report: {Path(r.source).name}",
        "",
        f"- mode: {r.mode}",
        f"- result: **{summary_line(r)}**",
        f"- {stage_line(r)}",
    ]
    if r.recall_pass:
        lines.append(f"- {recall_line(r)}")
    if c["broken_rows"]:
        lines.append(f"- broken table rows skipped: {c['broken_rows']}")
    if "mock" in r.mode:
        lines += ["", f"> {MOCK_NOTICE}"]
    lines += [
        "",
        "## Findings",
        "",
        "| # | source | asked page | found page | stage | status | severity | quote | comment |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for i, p in enumerate(r.placements, 1):
        f = p.finding
        lines.append(
            f"| {i} | {f.source} | {f.page} | {p.page} | {p.stage or '-'} | {p.status} | "
            f"{f.severity or '-'} | {_cell(f.quote)} | {_cell(f.comment)} |"
        )
    if any(p.stage == "prefix25" for p in r.placements):
        lines += ["", "Note: `prefix25` matches only the first 25 characters of the quote and paints "
                      "up to the quote's length, so it may cover text the model never quoted. "
                      "Check these highlights by eye."]
    lines += ["", "## Pages", "", "| page | status | first | recall added | duplicates dropped | broken rows | note |",
              "|---|---|---|---|---|---|---|"]
    for p in r.pages:
        note = p.detail or ("no table in answer" if p.no_table else "")
        if p.truncated:
            note = (note + " page text truncated before sending").strip()
        lines.append(f"| {p.page} | {p.status} | {p.first_pass} | {p.recall_added} | "
                     f"{p.recall_deduped} | {p.broken_rows} | {_cell(note)} |")
    prompted = [p for p in r.pages if p.prompts]
    if prompted:
        lines += ["", "## Prompts sent", ""]
        for p in prompted:
            for turn, text in enumerate(p.prompts, 1):
                head = text if turn > 1 else text[:400] + (" …" if len(text) > 400 else "")
                lines += [f"### page {p.page}, turn {turn}", "", "```text", head, "```", ""]
    return "\n".join(lines) + "\n"


def write_reports(r: Report, dst: Path) -> tuple[Path, Path]:
    """Write <out>.report.json and <out>.report.md next to the output PDF."""
    dst = Path(dst)
    json_path = dst.with_suffix(".report.json")
    md_path = dst.with_suffix(".report.md")
    json_path.write_text(json.dumps(to_dict(r), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(to_markdown(r), encoding="utf-8")
    return json_path, md_path
