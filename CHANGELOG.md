# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
