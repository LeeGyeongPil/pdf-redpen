"""Screen language: message table, language choice, translated output, error paths."""
from __future__ import annotations

import json
import os
import re
import string
import subprocess
import sys

import pytest
from pypdf import PdfWriter

from conftest import FINDINGS_JSON, PLAIN_PDF, RECORDED, annots_of
from pdf_redpen import annotate_pdf, i18n
from pdf_redpen.cli import main
from pdf_redpen.i18n import MESSAGES, CodedError, lang_from_argv, resolve_lang, t, t_plural
from pdf_redpen.models import Finding, InputError


def _fields(text: str) -> set[str]:
    return {name.split("!")[0] for _, name, _, _ in string.Formatter().parse(text) if name}


# ---- the message table ---------------------------------------------------------------------
def test_both_languages_have_the_same_keys():
    assert set(MESSAGES["en"]) == set(MESSAGES["ko"])


def test_placeholders_match_between_languages():
    for key, en in MESSAGES["en"].items():
        assert _fields(en) == _fields(MESSAGES["ko"][key]), key


def test_every_message_renders_in_both_languages():
    for lang in ("en", "ko"):
        for key, text in MESSAGES[lang].items():
            assert t(key, lang, **{f: "x" for f in _fields(text)})


def test_korean_values_are_really_korean():
    same = [k for k, v in MESSAGES["ko"].items() if v == MESSAGES["en"][k]]
    assert same == ["summary.sep"]  # only the list separator may be identical
    assert not re.search(r"[가-힣]", "".join(MESSAGES["en"].values()))


def test_plural_keys():
    assert t_plural("summary.memos", 1, "en") == "1 page memo"
    assert t_plural("summary.memos", 2, "en") == "2 page memos"
    assert t_plural("summary.memos", 1, "ko") == t_plural("summary.memos", 2, "ko").replace("2", "1")


# ---- choosing the language -----------------------------------------------------------------
@pytest.mark.parametrize("cli,env,want", [
    ("ko", {"PDF_REDPEN_LANG": "en", "LANG": "en_US.UTF-8"}, "ko"),            # --lang wins
    ("en", {"PDF_REDPEN_LANG": "ko", "LC_ALL": "ko_KR.UTF-8"}, "en"),
    (None, {"PDF_REDPEN_LANG": "ko", "LC_ALL": "en_US.UTF-8"}, "ko"),          # tool variable next
    (None, {"LC_ALL": "ko_KR.UTF-8", "LC_MESSAGES": "en_US.UTF-8", "LANG": "en"}, "ko"),
    (None, {"LC_MESSAGES": "ko_KR.UTF-8", "LANG": "en_US.UTF-8"}, "ko"),
    (None, {"LANG": "ko_KR.UTF-8"}, "ko"),
    (None, {"LANG": "ko"}, "ko"),
    (None, {"LANG": "C.UTF-8"}, "en"),
    (None, {"LANG": "fr_FR.UTF-8"}, "en"),
    (None, {"LANG": "!!garbage"}, "en"),
    (None, {"PDF_REDPEN_LANG": "klingon", "LANG": "ko_KR.UTF-8"}, "en"),        # bad value: English
    (None, {}, "en"),
    ("fr", {"LANG": "ko_KR.UTF-8"}, "ko"),                                      # bad --lang is ignored
])
def test_resolve_lang_priority(cli, env, want):
    assert resolve_lang(cli, env) == want


def test_lang_from_argv_ignores_the_review_prompt_option():
    assert lang_from_argv(["--lang", "ko", "demo"]) == "ko"
    assert lang_from_argv(["--lang=ko", "demo"]) == "ko"
    assert lang_from_argv(["review", "a.pdf", "--lang", "ko"]) is None  # prompt language, not screen
    assert lang_from_argv(["--lang"]) is None


def test_main_does_not_leak_the_language():
    assert i18n.get_lang() == "en"
    main(["--lang", "ko", "clear", "nope.pdf", "-o", "x.pdf"])
    assert i18n.get_lang() == "en"


# ---- translated output ---------------------------------------------------------------------
def test_help_in_korean_and_english(capsys):
    with pytest.raises(SystemExit):
        main(["--lang", "ko", "--help"])
    out = capsys.readouterr().out
    assert t("help.description", "ko") in out and t("help.review", "ko") in out
    assert "--lang" in out
    with pytest.raises(SystemExit):
        main(["--lang", "en", "review", "--help"])
    out = capsys.readouterr().out
    assert t("help.review_lang", "en") in out and "UI language" in out


def test_help_follows_the_environment(capsys, monkeypatch):
    monkeypatch.setenv("PDF_REDPEN_LANG", "ko")
    with pytest.raises(SystemExit):
        main(["--help"])
    assert t("help.description", "ko") in capsys.readouterr().out


def test_demo_in_korean(tmp_path, capsys):
    assert main(["--lang", "ko", "demo", "--out", str(tmp_path)]) == 0
    cap = capsys.readouterr()
    assert "지적 9건: 강조 8개, 페이지 메모 1개, 1쪽 건너뜀(텍스트 층 없음)" in cap.out
    assert "단계: exact=4" in cap.out and "연습용 목(mock) 모드" in cap.out
    assert "재확인 패스:" in cap.out
    assert cap.out.count("저장함:") == 3
    assert "1쪽: ok" in cap.err and "3쪽: skipped_no_text_layer" in cap.err
    md = (tmp_path / "reviewed.report.md").read_text(encoding="utf-8")
    assert md.startswith("# pdf-redpen 보고서: sample_report.pdf") and "## 지적 사항" in md
    assert "연습용 목(mock) 모드" in md and "prefix25" in md
    assert t("md.findings_head", "ko") in md and "텍스트 층이 없습니다" in md


def test_demo_markdown_in_english(tmp_path, capsys):
    assert main(["--lang", "en", "demo", "--out", str(tmp_path)]) == 0
    md = (tmp_path / "reviewed.report.md").read_text(encoding="utf-8")
    assert md.startswith("# pdf-redpen report: sample_report.pdf") and "## Findings" in md
    assert "prefix25" in md and "Practice mock mode" in md


def test_report_json_is_identical_in_both_languages(tmp_path, capsys):
    blobs = {}
    for lang in ("en", "ko"):
        out = tmp_path / lang
        assert main(["--lang", lang, "demo", "--out", str(out)]) == 0
        blobs[lang] = (out / "reviewed.report.json").read_bytes().replace(str(out).encode(), b"OUT")
    assert blobs["en"] == blobs["ko"]
    summary = json.loads(blobs["ko"])["summary"]
    assert summary == "9 findings: 8 highlighted, 1 page memo, 1 page skipped (no text layer)"


def test_clear_message_in_korean(tmp_path, capsys):
    marked = tmp_path / "m.pdf"
    assert main(["apply", str(PLAIN_PDF), str(FINDINGS_JSON), "-o", str(marked)]) == 0
    capsys.readouterr()
    assert main(["--lang", "ko", "clear", str(marked), "-o", str(tmp_path / "c.pdf")]) == 0
    assert "주석 10개를 지웠습니다" in capsys.readouterr().out


def test_memo_tags_follow_the_language(tmp_path):
    findings = [Finding(1, "no such sentence anywhere", "c1"),
                Finding(1, "Q4 revenue", "c2")]
    for lang, tags in (("en", ("[not found]",)), ("ko", ("[위치 못 찾음]",))):
        dst = tmp_path / f"{lang}.pdf"
        annotate_pdf(PLAIN_PDF, findings, dst, lang=lang)
        memos = [str(a["/Contents"]) for a in annots_of(dst, 0) if a["/Subtype"] == "/Text"]
        assert memos and all(m.startswith(tags[0]) for m in memos[:1])
    # default: the current screen language (English in tests)
    dst = tmp_path / "default.pdf"
    annotate_pdf(PLAIN_PDF, findings, dst)
    assert any("[not found]" in str(a["/Contents"]) for a in annots_of(dst, 0))


def test_cap_memo_and_loose_tags_in_korean(tmp_path, capsys):
    dst = tmp_path / "cap.pdf"
    assert main(["--lang", "ko", "apply", str(PLAIN_PDF), str(FINDINGS_JSON), "-o", str(dst),
                 "--max-highlights-per-page", "3"]) == 0
    memo = [a for a in annots_of(dst, 0) if a["/Subtype"] == "/Text"][0]
    assert str(memo["/Contents"]).count(t("tag.overflow", "ko")) == 3
    assert main(["--lang", "ko", "demo", "--out", str(tmp_path / "d")]) == 0
    loose = [str(a["/Contents"]) for pg in range(3) for a in annots_of(tmp_path / "d" / "reviewed.pdf", pg)
             if str(a.get("/Contents", "")).startswith(t("tag.loose", "ko"))]
    assert len(loose) == 1


def test_coded_error_str_stays_english():
    exc = InputError("err.pages_start")
    assert str(exc) == "--pages numbers start at 1."
    assert exc.render("ko") == "--pages 번호는 1부터 시작합니다."
    assert str(InputError("some literal text")) == "some literal text"  # unknown id: used as is
    assert isinstance(exc, CodedError)


# ---- every error path, both languages ------------------------------------------------------
def _enc_pdf(tmp_path):
    w = PdfWriter()
    w.add_blank_page(width=100, height=100)
    w.encrypt("secret")
    p = tmp_path / "enc.pdf"
    with open(p, "wb") as fh:
        w.write(fh)
    return p


def _json(tmp_path, text):
    f = tmp_path / "f.json"
    f.write_text(text)
    return f


def _apply(tmp_path, text):
    return ["apply", str(PLAIN_PDF), str(_json(tmp_path, text)), "-o", str(tmp_path / "o.pdf")]


def _review(tmp_path, *extra):
    return ["review", str(PLAIN_PDF), "-o", str(tmp_path / "o.pdf"), *extra]


MOCK = ("--mock", str(RECORDED))

# (message id, argv builder, params of the message, exit code)
CASES = [
    ("err.pages_format", lambda tp: _review(tp, *MOCK, "--pages", "a"), lambda tp: {"spec": "a"}, 2),
    ("err.pages_start", lambda tp: _review(tp, *MOCK, "--pages", "0"), lambda tp: {}, 2),
    ("err.overwrite", lambda tp: ["clear", str(PLAIN_PDF), "-o", str(PLAIN_PDF)], lambda tp: {}, 2),
    ("err.mock_record", lambda tp: _review(tp, *MOCK, "--record", str(tp)), lambda tp: {}, 2),
    ("err.instructions_missing", lambda tp: _review(tp, *MOCK, "--instructions", str(tp / "no.md")),
     lambda tp: {"path": tp / "no.md"}, 2),
    ("err.findings_missing", lambda tp: ["apply", str(PLAIN_PDF), str(tp / "no.json"), "-o", str(tp / "o.pdf")],
     lambda tp: {"path": tp / "no.json"}, 2),
    ("err.cap_min", lambda tp: _apply(tp, "[]") + ["--max-highlights-per-page", "0"], lambda tp: {}, 2),
    ("err.pages_outside", lambda tp: _review(tp, *MOCK, "--pages", "9"), lambda tp: {"pages": [9], "n_pages": 3}, 2),
    ("err.item_page", lambda tp: _apply(tp, '[{"page": 99, "quote": "x", "comment": "y"}]'),
     lambda tp: {"i": 0, "page": 99, "n_pages": 3}, 2),
    ("err.pdf_not_found", lambda tp: ["clear", str(tp / "nope.pdf"), "-o", str(tp / "o.pdf")],
     lambda tp: {"path": tp / "nope.pdf"}, 2),
    ("err.pdf_encrypted", lambda tp: ["clear", str(_enc_pdf(tp)), "-o", str(tp / "o.pdf")],
     lambda tp: {"path": tp / "enc.pdf"}, 2),
    ("err.json_not_list", lambda tp: _apply(tp, '{"a": 1}'), lambda tp: {"origin": tp / "f.json"}, 2),
    ("err.json_not_object", lambda tp: _apply(tp, "[1]"), lambda tp: {"origin": tp / "f.json", "i": 0}, 2),
    ("err.json_page", lambda tp: _apply(tp, '[{"page": 0, "quote": "q"}]'),
     lambda tp: {"origin": tp / "f.json", "i": 0, "page": 0}, 2),
    ("err.json_quote", lambda tp: _apply(tp, '[{"page": 1, "quote": ""}]'),
     lambda tp: {"origin": tp / "f.json", "i": 0}, 2),
    ("err.json_comment", lambda tp: _apply(tp, '[{"page": 1, "quote": "q", "comment": 5}]'),
     lambda tp: {"origin": tp / "f.json", "i": 0}, 2),
    ("err.json_severity", lambda tp: _apply(tp, '[{"page": 1, "quote": "q", "severity": "zzz"}]'),
     lambda tp: {"origin": tp / "f.json", "i": 0, "severity": "zzz"}, 2),
    ("err.record_dir", lambda tp: _review(tp, "--mock", str(tp / "none")), lambda tp: {"directory": tp / "none"}, 2),
]

ENV_CASES = [
    ("err.no_model", {"PDF_REDPEN_MODEL": ""}, {}),
    ("err.base_url", {"PDF_REDPEN_MODEL": "m", "PDF_REDPEN_BASE_URL": "ftp://x"}, {"base_url": "ftp://x"}),
    ("err.timeout_format", {"PDF_REDPEN_MODEL": "m", "PDF_REDPEN_TIMEOUT": "soon"}, {"raw": "soon"}),
]


def _check(capsys, lang, message_id, params, code, got):
    assert got == code
    err = capsys.readouterr().err
    assert "Traceback" not in err
    want = t("err.prefix", lang, message=t(message_id, lang, **params))
    assert want in err, (want, err)
    assert ("오류:" in err) == (lang == "ko") and ("error:" in err) == (lang == "en")


@pytest.mark.parametrize("lang", ["en", "ko"])
@pytest.mark.parametrize("message_id,argv,params,code", CASES, ids=[c[0] for c in CASES])
def test_input_errors_in_both_languages(tmp_path, capsys, lang, message_id, argv, params, code):
    got = main(["--lang", lang, *argv(tmp_path)])
    _check(capsys, lang, message_id, params(tmp_path), code, got)


@pytest.mark.parametrize("lang", ["en", "ko"])
def test_invalid_json_and_unreadable_pdf(tmp_path, capsys, lang):
    got = main(["--lang", lang, *_apply(tmp_path, "{")])
    err = capsys.readouterr().err
    assert got == 2 and "Traceback" not in err
    assert ("올바른 JSON이 아닙니다" if lang == "ko" else "not valid JSON") in err
    bad = tmp_path / "x.pdf"
    bad.write_text("hello")
    got = main(["--lang", lang, "clear", str(bad), "-o", str(tmp_path / "o.pdf")])
    err = capsys.readouterr().err
    assert got == 2 and "Traceback" not in err
    assert ("PDF로 읽을 수 없습니다" if lang == "ko" else "could not be read") in err


@pytest.mark.parametrize("lang", ["en", "ko"])
@pytest.mark.parametrize("message_id,env,params", ENV_CASES, ids=[c[0] for c in ENV_CASES])
def test_configuration_errors_in_both_languages(tmp_path, capsys, monkeypatch, lang, message_id, env, params):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    got = main(["--lang", lang, *_review(tmp_path)])
    _check(capsys, lang, message_id, params, 2, got)


@pytest.mark.parametrize("lang", ["en", "ko"])
def test_model_failures_are_shown_per_page_in_the_language(tmp_path, capsys, lang):
    empty = tmp_path / "rec"
    empty.mkdir()  # exists but holds no recordings -> LLMError on every page
    got = main(["--lang", lang, *_review(tmp_path, "--mock", str(empty), "--pages", "1")])
    err = capsys.readouterr().err
    assert got == 1 and "Traceback" not in err
    page = t("err.no_recording", lang, page=1, turn=1, path=empty / "page1_turn1.md")
    assert f"LLMError: {page}" in err
    assert t("err.all_failed", lang) in err
    # the Markdown report is in the same language
    md = (tmp_path / "o.report.md").read_text(encoding="utf-8")
    assert f"LLMError: {page}" in md


def test_llm_error_messages_render_in_both_languages():
    from pdf_redpen.llm import LLMError

    samples = {
        "err.http": {"code": 500, "url": "http://h/v1", "model": "m"},
        "err.unreachable": {"url": "http://h/v1", "reason": "refused", "timeout": "120"},
        "err.response_shape": {"url": "http://h/v1", "reason": "KeyError('choices')"},
    }
    for message_id, params in samples.items():
        exc = LLMError(message_id, **params)
        assert str(exc) == exc.render("en") != exc.render("ko")
        assert "http://h/v1" in exc.render("ko")


def test_partial_failure_warning_in_korean(tmp_path, capsys, monkeypatch):
    from pdf_redpen import cli, llm

    class Flaky:
        def __init__(self, _directory):
            pass

        def complete(self, messages, *, page, turn):
            if page == 1:
                raise llm.LLMError("err.no_recording", page=1, turn=1, path="p")
            return "no table here"

    monkeypatch.setattr(cli, "MockClient", Flaky)
    assert cli.main(["--lang", "ko", *_review(tmp_path, *MOCK, "--pages", "1-2")]) == 0
    err = capsys.readouterr().err
    assert "경고: 1개 쪽이 실패했습니다" in err and "1쪽: error - LLMError:" in err


# ---- files that cannot be written (OSError) ------------------------------------------------
def _blocked_output(tmp_path):
    """A -o path whose parent is a file: every platform and user (even root) fails to write there."""
    parent = tmp_path / "afile"
    parent.write_text("x")
    return parent / "out.pdf"


@pytest.mark.parametrize("lang", ["en", "ko"])
def test_unwritable_output_gives_a_message_not_a_traceback(tmp_path, capsys, lang):
    out = _blocked_output(tmp_path)
    got = main(["--lang", lang, "apply", str(PLAIN_PDF), str(FINDINGS_JSON), "-o", str(out)])
    err = capsys.readouterr().err
    assert got == 2 and "Traceback" not in err and "unexpected" not in err.lower().replace("예상하지", "")
    assert str(out.parent) in err
    assert ("접근할 수 없습니다" if lang == "ko" else "cannot access") in err


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root ignores permissions")
@pytest.mark.parametrize("lang", ["en", "ko"])
def test_read_only_folder_in_a_fresh_process(tmp_path, lang):
    ro = tmp_path / "ro"
    ro.mkdir()
    ro.chmod(0o500)
    try:
        env = {**os.environ, "PDF_REDPEN_LANG": lang}
        done = subprocess.run(
            [sys.executable, "-m", "pdf_redpen", "apply", str(PLAIN_PDF), str(FINDINGS_JSON),
             "-o", str(ro / "x.pdf")], capture_output=True, text=True, timeout=120, env=env)
    finally:
        ro.chmod(0o700)
    assert done.returncode == 2
    assert "Traceback" not in done.stderr and "PermissionError" not in done.stderr
    assert ("오류: " if lang == "ko" else "error: cannot access") in done.stderr
    assert str(ro / "x.pdf") in done.stderr and ".part" not in done.stderr  # Q-3: the user's path


@pytest.mark.parametrize("lang", ["en", "ko"])
def test_demo_into_unwritable_folder_in_a_fresh_process(tmp_path, lang):
    out = _blocked_output(tmp_path).parent  # --out is a file, not a folder
    env = {**os.environ, "PDF_REDPEN_LANG": lang}
    done = subprocess.run([sys.executable, "-m", "pdf_redpen", "demo", "--out", str(out)],
                          capture_output=True, text=True, timeout=120, env=env)
    assert done.returncode == 2
    assert "Traceback" not in done.stderr
    assert ("접근할 수 없습니다" if lang == "ko" else "cannot access") in done.stderr


# ---- review-round fixes: temp-file name, mock notice on input errors, mode label -------------
@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root ignores permissions")
@pytest.mark.parametrize("lang", ["en", "ko"])
def test_write_error_names_the_users_path_not_the_part_file(tmp_path, capsys, lang):
    ro = tmp_path / "ro"
    ro.mkdir()
    ro.chmod(0o500)
    try:
        got = main(["--lang", lang, "apply", str(PLAIN_PDF), str(FINDINGS_JSON), "-o", str(ro / "x.pdf")])
    finally:
        ro.chmod(0o700)
    err = capsys.readouterr().err
    assert got == 2 and "Traceback" not in err
    assert str(ro / "x.pdf") in err and ".part" not in err


@pytest.mark.parametrize("lang", ["en", "ko"])
def test_mock_notice_not_printed_when_nothing_was_replayed(tmp_path, capsys, lang):
    got = main(["--lang", lang, *_review(tmp_path, *MOCK, "--pages", "abc")])
    cap = capsys.readouterr()
    assert got == 2 and "Traceback" not in cap.err
    assert ("오류: " if lang == "ko" else "error: ") in cap.err
    assert t("notice.mock", lang) not in cap.err + cap.out
    # demo into an unusable folder: error only, no notice on stdout either
    bad = _blocked_output(tmp_path).parent
    got = main(["--lang", lang, "demo", "--out", str(bad)])
    cap = capsys.readouterr()
    assert got == 2 and t("notice.mock", lang) not in cap.err + cap.out


@pytest.mark.parametrize("lang", ["en", "ko"])
def test_mock_notice_still_printed_after_a_real_replay(tmp_path, capsys, lang):
    assert main(["--lang", lang, *_review(tmp_path, *MOCK, "--pages", "1")]) == 0
    assert t("notice.mock", lang) in capsys.readouterr().err


def test_markdown_mode_label_is_translated_but_json_is_not(tmp_path):
    outs = {}
    for lang in ("en", "ko"):
        d = tmp_path / lang
        assert main(["--lang", lang, "demo", "--out", str(d)]) == 0
        outs[lang] = ((d / "reviewed.report.md").read_text(encoding="utf-8"),
                      (d / "reviewed.report.json").read_text(encoding="utf-8"))
    assert "- mode: review (mock: practice replay)" in outs["en"][0]
    assert "- 모드: 검토(review, 목: 연습용 재생)" in outs["ko"][0]
    modes = {json.loads(j)["mode"] for _, j in outs.values()}
    assert modes == {"review (mock: practice replay)"}  # machine output stays English
