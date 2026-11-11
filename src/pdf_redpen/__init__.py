"""pdf-redpen: ground LLM review quotes to PDF coordinates and mark them up.

Small public API (everything else is internal):

    Finding, ground, annotate_pdf, InputError, __version__
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .grounding import ground
from .models import Finding, InputError, Match, Report
from .writer import DEFAULT_AUTHOR

__version__ = "0.2.0"
__all__ = ["Finding", "Match", "Report", "InputError", "ground", "annotate_pdf", "__version__"]


def annotate_pdf(
    src: "str | Path",
    findings: Iterable[Finding],
    dst: "str | Path",
    *,
    max_per_page: int = 20,
    author: str = DEFAULT_AUTHOR,
    lang: "str | None" = None,
) -> Report:
    """Highlight each finding's quote in `src` and save the result to `dst`.

    No model is called. Quotes that cannot be found become one memo per page. The memo tags
    ("[not found]", "[over cap]", "(loose match)") follow `lang` ("en" or "ko"); by default the
    language set with `pdf_redpen.i18n.set_lang` (English unless changed).
    """
    from .pipeline import JsonProvider, run_pipeline

    return run_pipeline(
        Path(src), Path(dst), JsonProvider(findings), mode="apply",
        max_per_page=max_per_page, author=author, lang=lang,
    )
