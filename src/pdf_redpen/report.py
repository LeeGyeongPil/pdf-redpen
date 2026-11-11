"""JSON and Markdown reports plus the one-line console summary."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from typing import Optional

from .i18n import CodedError, t, t_plural
from .models import HIGHLIGHTED, MEMO_NOT_FOUND, MEMO_OVERFLOW, PageResult, Report

def mock_notice(lang: Optional[str] = None) -> str:
    """The honest 'practice mock' label, in the chosen language."""
    return t("notice.mock", lang)


_MODE_KEYS = {"apply": "mode.apply", "review": "mode.review",
              "review (mock: practice replay)": "mode.review_mock"}


def mode_label(mode: str, lang: Optional[str] = None) -> str:
    """Screen label for report.json's mode value (the JSON itself stays untouched)."""
    key = _MODE_KEYS.get(mode)
    return t(key, lang) if key else mode


def summary_line(r: Report, lang: Optional[str] = None) -> str:
    memos = r.count(MEMO_NOT_FOUND) + r.count(MEMO_OVERFLOW)
    parts = [
        t("summary.highlighted", lang, n=r.count(HIGHLIGHTED)),
        t_plural("summary.memos", memos, lang),
        t_plural("summary.skipped", r.skipped_pages, lang),
    ]
    if r.error_pages:
        parts.append(t_plural("summary.failed", r.error_pages, lang))
    return t("summary.line", lang, total=len(r.placements), parts=t("summary.sep", lang).join(parts))


def stage_line(r: Report, lang: Optional[str] = None) -> str:
    return t("summary.stages", lang, stages=" ".join(f"{k}={v}" for k, v in r.stage_counts().items()))


def recall_line(r: Report, lang: Optional[str] = None) -> str:
    first = sum(p.first_pass for p in r.pages)
    added = sum(p.recall_added for p in r.pages)
    dup = sum(p.recall_deduped for p in r.pages)
    return t("summary.recall", lang, first=first, added=added, dup=dup)


def page_detail(p: PageResult, lang: Optional[str] = None) -> str:
    """The page's detail text in the chosen language (falls back to the stored English text)."""
    cause = getattr(p, "cause", None)
    if cause is None:
        return p.detail
    text = cause.render(lang) if isinstance(cause, CodedError) else str(cause)
    return getattr(p, "cause_prefix", "") + text


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
        "summary": summary_line(r, "en"),  # machine output: always English
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


def to_markdown(r: Report, lang: Optional[str] = None) -> str:
    c = _counts(r)
    lines = [
        f"# {t('md.title', lang, name=Path(r.source).name)}",
        "",
        f"- {t('md.mode', lang, mode=mode_label(r.mode, lang))}",
        f"- {t('md.result', lang, summary=summary_line(r, lang))}",
        f"- {stage_line(r, lang)}",
    ]
    if r.recall_pass:
        lines.append(f"- {recall_line(r, lang)}")
    if c["broken_rows"]:
        lines.append(f"- {t('md.broken_rows', lang, n=c['broken_rows'])}")
    if "mock" in r.mode:
        lines += ["", f"> {mock_notice(lang)}"]
    lines += [
        "",
        f"## {t('md.findings', lang)}",
        "",
        t("md.findings_head", lang),
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for i, p in enumerate(r.placements, 1):
        f = p.finding
        lines.append(
            f"| {i} | {f.source} | {f.page} | {p.page} | {p.stage or '-'} | {p.status} | "
            f"{f.severity or '-'} | {_cell(f.quote)} | {_cell(f.comment)} |"
        )
    if any(p.stage == "prefix25" for p in r.placements):
        lines += ["", t("md.prefix25_note", lang)]
    lines += ["", f"## {t('md.pages', lang)}", "", t("md.pages_head", lang),
              "|---|---|---|---|---|---|---|"]
    for p in r.pages:
        note = page_detail(p, lang) or (t("md.no_table", lang) if p.no_table else "")
        if p.truncated:
            note = (note + " " + t("md.truncated", lang)).strip()
        lines.append(f"| {p.page} | {p.status} | {p.first_pass} | {p.recall_added} | "
                     f"{p.recall_deduped} | {p.broken_rows} | {_cell(note)} |")
    prompted = [p for p in r.pages if p.prompts]
    if prompted:
        lines += ["", f"## {t('md.prompts', lang)}", ""]
        for p in prompted:
            for turn, text in enumerate(p.prompts, 1):
                head = text if turn > 1 else text[:400] + (" …" if len(text) > 400 else "")
                lines += [f"### {t('md.prompt_head', lang, page=p.page, turn=turn)}", "", "```text", head, "```", ""]
    return "\n".join(lines) + "\n"


def write_reports(r: Report, dst: Path, lang: Optional[str] = None) -> tuple[Path, Path]:
    """Write <out>.report.json (always English, for machines) and <out>.report.md (in `lang`)."""
    dst = Path(dst)
    json_path = dst.with_suffix(".report.json")
    md_path = dst.with_suffix(".report.md")
    json_path.write_text(json.dumps(to_dict(r), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(to_markdown(r, lang), encoding="utf-8")
    return json_path, md_path
