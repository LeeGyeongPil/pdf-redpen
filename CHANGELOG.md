# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
uses [Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-11-12

### Added
- Screen language: English and Korean. Pick it with the global option `pdf-redpen --lang en|ko <command>`, the `PDF_REDPEN_LANG` environment variable, or the locale (`LC_ALL`, `LC_MESSAGES`, `LANG`; a value starting with `ko` means Korean, anything else English). It covers `--help`, progress and summary lines, error messages and the Markdown report.
- File problems (read-only output folder, permission denied, disk full) now print a clear `error: cannot access <path>: <reason>` message with exit code 2 instead of `unexpected error: PermissionError`.
- `annotate_pdf(..., lang=)` and `pdf_redpen.i18n` (message table, `set_lang`).

### Changed
- The notes written into the PDF follow the screen language: `[not found]` / `[over cap]` / `(loose match)` in English, `[위치 못 찾음]` / `[상한 초과]` / `(느슨 일치)` in Korean. Before, they were always Korean, so English users now see English tags.
- `review --lang` is unchanged: it is still the prompt language (default `ko`), not the screen language. Its help text says so.
- `InputError` and `LLMError` carry a message id and parameters; `str(exc)` is still the English text.

### Unchanged
- `report.json` (always English), exit codes, environment variable names, prompts and the bundled data.

## [0.1.4] - 2026-11-10

### Fixed
- Find quotes written as `fi`/`fl` on PDFs whose text layer stores ligatures (U+FB00..U+FB06, common in LaTeX papers). Page text and quotes now share one compatibility normalisation; Hangul compatibility jamo are left as they are.

## [0.1.3] - 2026-11-10

### Changed
- Docs: replace the tool comparison table with a short when-to-use section.

## [0.1.2] - 2026-11-09

### Changed
- Docs: list Pillow in the license section and NOTICE, explain `clear --author`, note that `apply` also writes report files.

## [0.1.1] - 2026-11-09

### Security
- Require `pillow>=13.0.0` (transitive via pdfplumber); fixes all open Pillow advisories, whose first patched version is 13.0.0.

### Changed
- Minimum Python is now 3.11 (Pillow 13 requires it).

## [0.1.0] - 2026-11-09

### Added
- `review`: OpenAI-compatible chat client (urllib), `--mock DIR` replay, `--record DIR`, `--recall-pass`.
- `apply`: mark findings from a JSON file without any model.
- `clear`: remove only annotations whose author is `pdf-redpen`.
- `demo`: bundled 3-page sample with recorded (practice mock) answers.
- Five-stage quote grounding with duplicate avoidance and neighbour-page search.
- Standard `/Highlight` and `/Text` annotations with `/AP` appearance streams.
- Per-page highlight cap with a page memo, progressive save (`.part` + atomic replace).
- JSON and Markdown reports.
