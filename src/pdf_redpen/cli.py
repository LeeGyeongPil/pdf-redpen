"""Command line: review, apply, clear, demo. Exit codes: 0 ok, 2 bad input, 1 unexpected."""
from __future__ import annotations

import argparse
import sys
from importlib import resources
from pathlib import Path
from typing import Optional, Sequence

from . import __version__, prompts
from .llm import Client, MockClient, OpenAIChatClient, RecordingClient
from .models import PAGE_SKIPPED, InputError, findings_from_json
from .pipeline import JsonProvider, LLMProvider, run_pipeline
from .report import MOCK_NOTICE, recall_line, stage_line, summary_line, write_reports
from .writer import DEFAULT_AUTHOR, clear_annotations


def parse_pages(spec: Optional[str]) -> Optional[list[int]]:
    """'1-3,5' -> [1, 2, 3, 5]."""
    if not spec:
        return None
    pages: list[int] = []
    try:
        for part in spec.split(","):
            if "-" in part:
                a, b = part.split("-", 1)
                lo, hi = int(a), int(b)
                if lo > hi:
                    raise ValueError
                pages += range(lo, hi + 1)
            else:
                pages.append(int(part))
    except ValueError:
        raise InputError(f"--pages must look like 1-3,5 (got {spec!r}).") from None
    if any(p < 1 for p in pages):
        raise InputError("--pages numbers start at 1.")
    return pages


def _progress(result) -> None:
    """One stderr line per page; failures (and a failed recall turn) show their cause."""
    line = f"  page {result.page}: {result.status}"
    if result.detail and result.status != "skipped_no_text_layer":
        line += f" - {result.detail}"
    print(line, file=sys.stderr)


def _finish(report, dst: Path) -> int:
    """Print the summary; return 1 when every page that was sent to the model failed."""
    json_path, md_path = write_reports(report, dst)
    print(summary_line(report))
    print(stage_line(report))
    if report.recall_pass:
        print(recall_line(report))
    print(f"wrote {dst}")
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    attempted = [p for p in report.pages if p.status != PAGE_SKIPPED]
    if report.error_pages:
        if attempted and report.error_pages == len(attempted):
            print("error: every page failed; see the causes above (or the Pages table in the "
                  "report). Nothing was reviewed.", file=sys.stderr)
            return 1
        print(f"warning: {report.error_pages} page(s) failed; the others are marked. "
              "Re-run with --pages to retry them.", file=sys.stderr)
    return 0


def _default_out(src: Path, suffix: str) -> Path:
    return src.with_name(f"{src.stem}.{suffix}.pdf")


def _check_out(src: Path, dst: Path) -> None:
    if src.resolve() == dst.resolve():
        raise InputError("The output file would overwrite the input. Choose another -o path.")


def cmd_review(a: argparse.Namespace) -> int:
    src = Path(a.input)
    dst = Path(a.output) if a.output else _default_out(src, "reviewed")
    _check_out(src, dst)
    if a.mock and a.record:
        raise InputError("Use either --mock (replay) or --record (save real answers), not both.")
    instructions = prompts.DEFAULT_INSTRUCTIONS[a.lang]
    if a.instructions:
        ipath = Path(a.instructions)
        if not ipath.is_file():
            raise InputError(f"Instructions file not found: {ipath}.")
        instructions = ipath.read_text(encoding="utf-8")
    client: Client
    if a.mock:
        client, mode = MockClient(Path(a.mock)), "review (mock: practice replay)"
        print(MOCK_NOTICE, file=sys.stderr)
    else:
        client, mode = OpenAIChatClient.from_env(), "review"
        if a.record:
            client = RecordingClient(client, Path(a.record))
    provider = LLMProvider(client, instructions, a.recall_pass, a.lang)
    report = run_pipeline(src, dst, provider, mode=mode, max_per_page=a.max_highlights_per_page,
                          pages=parse_pages(a.pages), author=a.author, recall=a.recall_pass,
                          on_page_done=_progress)
    return _finish(report, dst)


def cmd_apply(a: argparse.Namespace) -> int:
    src, fpath = Path(a.input), Path(a.findings)
    dst = Path(a.output)
    _check_out(src, dst)
    if not fpath.is_file():
        raise InputError(f"Findings file not found: {fpath}.")
    findings = findings_from_json(fpath.read_text(encoding="utf-8"), str(fpath))
    report = run_pipeline(src, dst, JsonProvider(findings), mode="apply",
                          max_per_page=a.max_highlights_per_page, author=DEFAULT_AUTHOR)
    return _finish(report, dst)


def cmd_clear(a: argparse.Namespace) -> int:
    src, dst = Path(a.input), Path(a.output)
    _check_out(src, dst)
    removed = clear_annotations(src, dst, a.author)
    print(f"removed {removed} annotation(s) by {a.author!r}; wrote {dst}")
    return 0


def cmd_demo(a: argparse.Namespace) -> int:
    out = Path(a.out)
    data = resources.files("pdf_redpen") / "data"
    print(MOCK_NOTICE)
    with resources.as_file(data / "sample_report.pdf") as sample, \
            resources.as_file(data / "recorded") as recorded, \
            resources.as_file(data / "review.md") as instr:
        dst = out / "reviewed.pdf"
        provider = LLMProvider(MockClient(recorded), Path(instr).read_text(encoding="utf-8"),
                               recall=True)
        report = run_pipeline(sample, dst, provider, mode="review (mock: practice replay)",
                              max_per_page=a.max_highlights_per_page, recall=True,
                              on_page_done=_progress)
    return _finish(report, dst)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pdf-redpen",
        description="Mark an LLM review on the original PDF: quotes become highlights with notes.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    cap = ["--max-highlights-per-page"]
    r = sub.add_parser("review", help="review a PDF with a model (or replay a recording)")
    r.add_argument("input")
    r.add_argument("-o", "--output")
    r.add_argument("--instructions", help="file with your review instructions")
    r.add_argument("--mock", metavar="DIR", help="replay recorded answers from DIR (no model, no network)")
    r.add_argument("--record", metavar="DIR", help="save the model's answers to DIR for later --mock")
    r.add_argument("--recall-pass", action="store_true", help="ask once more for missed findings")
    r.add_argument(*cap, type=int, default=20)
    r.add_argument("--pages", help="only these pages, e.g. 1-3,5")
    r.add_argument("--author", default=DEFAULT_AUTHOR)
    r.add_argument("--lang", choices=("ko", "en"), default="ko", help="prompt language")
    r.set_defaults(func=cmd_review)

    ap = sub.add_parser("apply", help="mark findings from a JSON file (no model)")
    ap.add_argument("input")
    ap.add_argument("findings")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument(*cap, type=int, default=20)
    ap.set_defaults(func=cmd_apply)

    cl = sub.add_parser("clear", help="remove annotations made by this tool")
    cl.add_argument("input")
    cl.add_argument("-o", "--output", required=True)
    cl.add_argument("--author", default=DEFAULT_AUTHOR)
    cl.set_defaults(func=cmd_clear)

    d = sub.add_parser("demo", help="run the bundled sample with recorded answers (no key needed)")
    d.add_argument("--out", default="out")
    d.add_argument(*cap, type=int, default=20)
    d.set_defaults(func=cmd_demo)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("interrupted; pages finished so far are saved in the output file", file=sys.stderr)
        return 1
    except Exception as exc:  # last resort: no traceback for users
        print(f"unexpected error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
