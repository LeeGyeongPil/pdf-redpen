# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
uses [Semantic Versioning](https://semver.org/).

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
