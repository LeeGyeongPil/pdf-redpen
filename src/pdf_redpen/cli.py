"""Command line: review, apply, clear, demo. Exit codes: 0 ok, 2 bad input, 1 unexpected."""
from __future__ import annotations

import argparse
import sys
from importlib import resources
from pathlib import Path
from typing import Optional, Sequence

from . import __version__, prompts
from .i18n import LANGS, CodedError, lang_from_argv, resolve_lang, set_lang, t
from .llm import Client, MockClient, OpenAIChatClient, RecordingClient
from .models import PAGE_SKIPPED, InputError, findings_from_json
from .pipeline import JsonProvider, LLMProvider, run_pipeline
from .report import mock_notice, page_detail, recall_line, stage_line, summary_line, write_reports
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
        raise InputError("err.pages_format", spec=spec) from None
    if any(p < 1 for p in pages):
        raise InputError("err.pages_start")
    return pages


def _progress(result) -> None:
    """One stderr line per page; failures (and a failed recall turn) show their cause."""
    if result.detail and result.status != "skipped_no_text_layer":
        line = t("progress.line_detail", page=result.page, status=result.status,
                 detail=page_detail(result))
    else:
        line = t("progress.line", page=result.page, status=result.status)
    print(line, file=sys.stderr)


def _finish(report, dst: Path, notice_to=None) -> int:
    """Print the summary; return 1 when every page that was sent to the model failed.

    The mock notice is printed here (only once a run really replayed answers), to `notice_to`.
    """
    if "mock" in report.mode:
        print(mock_notice(), file=notice_to or sys.stderr)
    json_path, md_path = write_reports(report, dst)
    print(summary_line(report))
    print(stage_line(report))
    if report.recall_pass:
        print(recall_line(report))
    for path in (dst, json_path, md_path):
        print(t("out.wrote", path=path))
    attempted = [p for p in report.pages if p.status != PAGE_SKIPPED]
    if report.error_pages:
        if attempted and report.error_pages == len(attempted):
            print(t("err.all_failed"), file=sys.stderr)
            return 1
        print(t("warn.some_failed", n=report.error_pages), file=sys.stderr)
    return 0


def _default_out(src: Path, suffix: str) -> Path:
    return src.with_name(f"{src.stem}.{suffix}.pdf")


def _check_out(src: Path, dst: Path) -> None:
    if src.resolve() == dst.resolve():
        raise InputError("err.overwrite")


def cmd_review(a: argparse.Namespace) -> int:
    src = Path(a.input)
    dst = Path(a.output) if a.output else _default_out(src, "reviewed")
    _check_out(src, dst)
    if a.mock and a.record:
        raise InputError("err.mock_record")
    instructions = prompts.DEFAULT_INSTRUCTIONS[a.lang]
    if a.instructions:
        ipath = Path(a.instructions)
        if not ipath.is_file():
            raise InputError("err.instructions_missing", path=ipath)
        instructions = ipath.read_text(encoding="utf-8")
    client: Client
    if a.mock:
        client, mode = MockClient(Path(a.mock)), "review (mock: practice replay)"
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
        raise InputError("err.findings_missing", path=fpath)
    findings = findings_from_json(fpath.read_text(encoding="utf-8"), str(fpath))
    report = run_pipeline(src, dst, JsonProvider(findings), mode="apply",
                          max_per_page=a.max_highlights_per_page, author=DEFAULT_AUTHOR)
    return _finish(report, dst)


def cmd_clear(a: argparse.Namespace) -> int:
    src, dst = Path(a.input), Path(a.output)
    _check_out(src, dst)
    removed = clear_annotations(src, dst, a.author)
    print(t("out.removed", n=removed, author=a.author, dst=dst))
    return 0


def cmd_demo(a: argparse.Namespace) -> int:
    out = Path(a.out)
    data = resources.files("pdf_redpen") / "data"
    with resources.as_file(data / "sample_report.pdf") as sample, \
            resources.as_file(data / "recorded") as recorded, \
            resources.as_file(data / "review.md") as instr:
        dst = out / "reviewed.pdf"
        provider = LLMProvider(MockClient(recorded), Path(instr).read_text(encoding="utf-8"),
                               recall=True)
        report = run_pipeline(sample, dst, provider, mode="review (mock: practice replay)",
                              max_per_page=a.max_highlights_per_page, recall=True,
                              on_page_done=_progress)
    return _finish(report, dst, notice_to=sys.stdout)


def build_parser() -> argparse.ArgumentParser:
    """Build the parser; help texts come from the current screen language (see i18n)."""
    p = argparse.ArgumentParser(prog="pdf-redpen", description=t("help.description"))
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    # Screen language (messages, reports). Not the same as `review --lang` (prompt language).
    p.add_argument("--lang", dest="ui_lang", choices=LANGS, default=None, help=t("help.lang_ui"))
    sub = p.add_subparsers(dest="command", required=True)

    cap = ["--max-highlights-per-page"]
    r = sub.add_parser("review", help=t("help.review"))
    r.add_argument("input")
    r.add_argument("-o", "--output")
    r.add_argument("--instructions", help=t("help.instructions"))
    r.add_argument("--mock", metavar="DIR", help=t("help.mock"))
    r.add_argument("--record", metavar="DIR", help=t("help.record"))
    r.add_argument("--recall-pass", action="store_true", help=t("help.recall_pass"))
    r.add_argument(*cap, type=int, default=20)
    r.add_argument("--pages", help=t("help.pages"))
    r.add_argument("--author", default=DEFAULT_AUTHOR)
    r.add_argument("--lang", choices=("ko", "en"), default="ko", help=t("help.review_lang"))
    r.set_defaults(func=cmd_review)

    ap = sub.add_parser("apply", help=t("help.apply"))
    ap.add_argument("input")
    ap.add_argument("findings")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument(*cap, type=int, default=20)
    ap.set_defaults(func=cmd_apply)

    cl = sub.add_parser("clear", help=t("help.clear"))
    cl.add_argument("input")
    cl.add_argument("-o", "--output", required=True)
    cl.add_argument("--author", default=DEFAULT_AUTHOR)
    cl.set_defaults(func=cmd_clear)

    d = sub.add_parser("demo", help=t("help.demo"))
    d.add_argument("--out", default="out")
    d.add_argument(*cap, type=int, default=20)
    d.set_defaults(func=cmd_demo)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    # Pick the screen language before parsing so --help and parse errors use it too.
    previous = set_lang(resolve_lang(lang_from_argv(args_list)))
    try:
        return _run(args_list)
    finally:
        set_lang(previous)  # do not leak the language into the caller (tests, library use)


def _run(args_list: list[str]) -> int:
    args = build_parser().parse_args(args_list)
    try:
        return args.func(args)
    except CodedError as exc:  # InputError, LLMError: message id + params, shown in our language
        print(t("err.prefix", message=exc.render()), file=sys.stderr)
        return 2 if isinstance(exc, InputError) else 1
    except OSError as exc:  # unreadable/unwritable paths, full disk, ...
        reason = exc.strerror or str(exc)
        if exc.filename:
            path = str(exc.filename)
            if path.endswith(".part"):  # internal temp file: show the path the user gave
                path = path[: -len(".part")]
            print(t("err.os", path=path, reason=reason), file=sys.stderr)
        else:
            print(t("err.os_nopath", reason=reason), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print(t("err.interrupted"), file=sys.stderr)
        return 1
    except Exception as exc:  # last resort: no traceback for users
        print(t("err.unexpected", name=type(exc).__name__, detail=exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
