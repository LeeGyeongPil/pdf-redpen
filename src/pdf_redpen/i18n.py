"""Screen language (English / Korean): one message table, language choice, coded errors.

Only text that people read goes through here (CLI help, console lines, the Markdown
report, memo tags in the PDF). Machine output (report.json), prompts and data stay as they are.

Language order for the CLI: `--lang` > PDF_REDPEN_LANG > LC_ALL > LC_MESSAGES > LANG.
A value starting with "ko" means Korean; anything else (or a bad value) means English.
"""
from __future__ import annotations

from typing import Mapping, Optional

LANGS = ("en", "ko")
DEFAULT_LANG = "en"
ENV_VARS = ("PDF_REDPEN_LANG", "LC_ALL", "LC_MESSAGES", "LANG")

MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        # ---- command line: help ----
        "help.description": "Mark an LLM review on the original PDF: quotes become highlights with notes.",
        "help.lang_ui": "language of messages and reports: en or ko "
                        "(default: PDF_REDPEN_LANG, then the locale, else en)",
        "help.review": "review a PDF with a model (or replay a recording)",
        "help.apply": "mark findings from a JSON file (no model)",
        "help.clear": "remove annotations made by this tool",
        "help.demo": "run the bundled sample with recorded answers (no key needed)",
        "help.instructions": "file with your review instructions",
        "help.mock": "replay recorded answers from DIR (no model, no network)",
        "help.record": "save the model's answers to DIR for later --mock",
        "help.recall_pass": "ask once more for missed findings",
        "help.pages": "only these pages, e.g. 1-3,5",
        "help.review_lang": "prompt language (UI language: pdf-redpen --lang)",
        # ---- command line: output ----
        "progress.line": "  page {page}: {status}",
        "progress.line_detail": "  page {page}: {status} - {detail}",
        "out.wrote": "wrote {path}",
        "out.removed": "removed {n} annotation(s) by {author!r}; wrote {dst}",
        "err.prefix": "error: {message}",
        "err.all_failed": "error: every page failed; see the causes above (or the Pages table in the "
                          "report). Nothing was reviewed.",
        "warn.some_failed": "warning: {n} page(s) failed; the others are marked. "
                            "Re-run with --pages to retry them.",
        "err.interrupted": "interrupted; pages finished so far are saved in the output file",
        "err.unexpected": "unexpected error: {name}: {detail}",
        "err.os": "error: cannot access {path}: {reason}. Check that the path exists and that you "
                  "may read and write there.",
        "err.os_nopath": "error: file problem: {reason}. Check the paths and permissions.",
        # ---- input errors ----
        "err.pages_format": "--pages must look like 1-3,5 (got {spec!r}).",
        "err.pages_start": "--pages numbers start at 1.",
        "err.overwrite": "The output file would overwrite the input. Choose another -o path.",
        "err.mock_record": "Use either --mock (replay) or --record (save real answers), not both.",
        "err.instructions_missing": "Instructions file not found: {path}.",
        "err.findings_missing": "Findings file not found: {path}.",
        "err.cap_min": "--max-highlights-per-page must be 1 or more.",
        "err.pages_outside": "Page(s) {pages} are outside this PDF (it has {n_pages} pages).",
        "err.item_page": "item {i}: page {page} but the PDF has {n_pages} page(s). "
                         "Fix the page number in the findings file.",
        "err.pdf_not_found": "PDF not found: {path}. Check the path.",
        "err.pdf_encrypted": "{path} is password protected. Remove the password first "
                             "(for example with qpdf --decrypt) and run again.",
        "err.pdf_unreadable": "{path} could not be read as a PDF ({reason}). Is the file damaged?",
        "err.json_invalid": "{origin} is not valid JSON ({reason}). Expected a list of objects.",
        "err.json_not_list": "{origin} must be a JSON list of objects with page, quote and comment.",
        "err.json_not_object": "{origin}: item {i} is not an object.",
        "err.json_page": "{origin}: item {i} needs an integer 'page' >= 1 (got {page!r}).",
        "err.json_quote": "{origin}: item {i} needs a non-empty string 'quote'.",
        "err.json_comment": "{origin}: item {i}: 'comment' must be a string.",
        "err.json_severity": "{origin}: item {i}: unknown severity {severity!r}; use high, medium or low "
                             "(or omit 'severity').",
        # ---- model access ----
        "err.no_model": "No model configured for a real review. Set PDF_REDPEN_MODEL "
                        "(for example the name of a model you pulled in Ollama), or try "
                        "`pdf-redpen demo` / `--mock DIR` which need no model.",
        "err.base_url": "PDF_REDPEN_BASE_URL must be an http(s) URL, got {base_url!r}. "
                        "Example: http://localhost:11434/v1",
        "err.timeout_format": "PDF_REDPEN_TIMEOUT must be a number of seconds, got {raw!r}.",
        "err.http": "HTTP {code} from {url} (model {model!r}). Check the model name and the API key.",
        "err.unreachable": "Could not reach {url} ({reason}). Is the server running? "
                           "Local models can be slow; raise PDF_REDPEN_TIMEOUT (now {timeout}s).",
        "err.response_shape": "Unexpected response shape from {url}: {reason}",
        "err.record_dir": "Recording folder not found: {directory}. Create it with `review --record DIR` first.",
        "err.no_recording": "No recording for page {page} turn {turn}: expected {path}.",
        # ---- page details ----
        "detail.no_text_layer": "no usable text layer (blank, scanned or unmapped glyphs); "
                                "the model was not called",
        # ---- console summary ----
        "notice.mock": "Practice mock mode: the answers were replayed from recorded files written by hand, "
                       "not produced by a real model. Everything after the answer (table parsing, merging, "
                       "grounding, annotation) is the same code as in real mode.",
        "summary.highlighted": "{n} highlighted",
        "summary.memos.one": "{n} page memo",
        "summary.memos.other": "{n} page memos",
        "summary.skipped.one": "{n} page skipped (no text layer)",
        "summary.skipped.other": "{n} pages skipped (no text layer)",
        "summary.failed.one": "{n} page failed",
        "summary.failed.other": "{n} pages failed",
        "summary.line": "{total} findings: {parts}",
        "summary.sep": ", ",
        "summary.stages": "stages: {stages}",
        "summary.recall": "recall pass: first {first}, added {added}, duplicates dropped {dup}",
        # ---- Markdown report ----
        "md.title": "pdf-redpen report: {name}",
        "md.mode": "mode: {mode}",
        "mode.apply": "apply",
        "mode.review": "review",
        "mode.review_mock": "review (mock: practice replay)",
        "md.result": "result: **{summary}**",
        "md.broken_rows": "broken table rows skipped: {n}",
        "md.findings": "Findings",
        "md.findings_head": "| # | source | asked page | found page | stage | status | severity | quote | comment |",
        "md.prefix25_note": "Note: `prefix25` matches only the first 25 characters of the quote and paints "
                            "up to the quote's length, so it may cover text the model never quoted. "
                            "Check these highlights by eye.",
        "md.pages": "Pages",
        "md.pages_head": "| page | status | first | recall added | duplicates dropped | broken rows | note |",
        "md.no_table": "no table in answer",
        "md.truncated": "page text truncated before sending",
        "md.prompts": "Prompts sent",
        "md.prompt_head": "page {page}, turn {turn}",
        # ---- notes written into the PDF ----
        "tag.not_found": "[not found]",
        "tag.overflow": "[over cap]",
        "tag.loose": "(loose match)",
    },
    "ko": {
        "help.description": "LLM 검토 결과를 원본 PDF 위에 표시합니다. 인용문은 메모가 달린 형광펜이 됩니다.",
        "help.lang_ui": "메시지·보고서 언어: en 또는 ko (기본: PDF_REDPEN_LANG, 그다음 로캘, 없으면 en)",
        "help.review": "모델로 PDF를 검토합니다(또는 녹음된 답변을 재생)",
        "help.apply": "JSON 파일의 지적 사항을 표시합니다(모델 없음)",
        "help.clear": "이 도구가 만든 주석을 지웁니다",
        "help.demo": "녹음된 답변으로 내장 샘플을 실행합니다(키 불필요)",
        "help.instructions": "검토 지침이 든 파일",
        "help.mock": "DIR 의 녹음된 답변을 재생합니다(모델·네트워크 없음)",
        "help.record": "모델의 답변을 DIR 에 저장해 나중에 --mock 으로 씁니다",
        "help.recall_pass": "놓친 지적을 한 번 더 묻습니다",
        "help.pages": "이 쪽만 처리합니다. 예: 1-3,5",
        "help.review_lang": "프롬프트 언어(화면 언어는 pdf-redpen --lang)",
        "progress.line": "  {page}쪽: {status}",
        "progress.line_detail": "  {page}쪽: {status} - {detail}",
        "out.wrote": "저장함: {path}",
        "out.removed": "{author!r} 가 만든 주석 {n}개를 지웠습니다. 저장함: {dst}",
        "err.prefix": "오류: {message}",
        "err.all_failed": "오류: 모든 쪽이 실패했습니다. 위의 원인(또는 보고서의 쪽 표)을 확인하세요. "
                          "검토된 것이 없습니다.",
        "warn.some_failed": "경고: {n}개 쪽이 실패했습니다. 나머지는 표시되었습니다. "
                            "--pages 로 실패한 쪽만 다시 실행하세요.",
        "err.interrupted": "중단되었습니다. 지금까지 끝난 쪽은 출력 파일에 저장되어 있습니다",
        "err.unexpected": "예상하지 못한 오류: {name}: {detail}",
        "err.os": "오류: {path} 에 접근할 수 없습니다: {reason}. 경로가 있는지, 읽고 쓸 권한이 있는지 "
                  "확인하세요.",
        "err.os_nopath": "오류: 파일 문제: {reason}. 경로와 권한을 확인하세요.",
        "err.pages_format": "--pages 는 1-3,5 형식이어야 합니다(받은 값: {spec!r}).",
        "err.pages_start": "--pages 번호는 1부터 시작합니다.",
        "err.overwrite": "출력 파일이 입력 파일을 덮어쓰게 됩니다. 다른 -o 경로를 고르세요.",
        "err.mock_record": "--mock(재생)과 --record(실제 답변 저장) 중 하나만 쓰세요.",
        "err.instructions_missing": "지침 파일을 찾을 수 없습니다: {path}.",
        "err.findings_missing": "지적 사항 파일을 찾을 수 없습니다: {path}.",
        "err.cap_min": "--max-highlights-per-page 는 1 이상이어야 합니다.",
        "err.pages_outside": "{pages} 쪽은 이 PDF 범위 밖입니다(전체 {n_pages}쪽).",
        "err.item_page": "{i}번 항목: {page}쪽이지만 PDF는 {n_pages}쪽까지 있습니다. "
                         "지적 사항 파일의 쪽 번호를 고치세요.",
        "err.pdf_not_found": "PDF를 찾을 수 없습니다: {path}. 경로를 확인하세요.",
        "err.pdf_encrypted": "{path} 은(는) 암호로 보호되어 있습니다. 먼저 암호를 제거한 뒤"
                             "(예: qpdf --decrypt) 다시 실행하세요.",
        "err.pdf_unreadable": "{path} 을(를) PDF로 읽을 수 없습니다({reason}). 파일이 손상되지 않았는지 확인하세요.",
        "err.json_invalid": "{origin} 은(는) 올바른 JSON이 아닙니다({reason}). 객체 목록이어야 합니다.",
        "err.json_not_list": "{origin} 은(는) page, quote, comment 를 가진 객체의 JSON 목록이어야 합니다.",
        "err.json_not_object": "{origin}: {i}번 항목이 객체가 아닙니다.",
        "err.json_page": "{origin}: {i}번 항목에는 1 이상의 정수 'page' 가 필요합니다(받은 값: {page!r}).",
        "err.json_quote": "{origin}: {i}번 항목에는 비어 있지 않은 문자열 'quote' 가 필요합니다.",
        "err.json_comment": "{origin}: {i}번 항목: 'comment' 는 문자열이어야 합니다.",
        "err.json_severity": "{origin}: {i}번 항목: 알 수 없는 severity {severity!r}. "
                             "high, medium, low 중 하나를 쓰거나 'severity' 를 생략하세요.",
        "err.no_model": "실제 검토에 쓸 모델이 설정되지 않았습니다. PDF_REDPEN_MODEL 을 설정하거나"
                        "(예: Ollama 에서 받은 모델 이름), 모델이 필요 없는 `pdf-redpen demo` / "
                        "`--mock DIR` 을 써 보세요.",
        "err.base_url": "PDF_REDPEN_BASE_URL 은 http(s) 주소여야 합니다(받은 값: {base_url!r}). "
                        "예: http://localhost:11434/v1",
        "err.timeout_format": "PDF_REDPEN_TIMEOUT 은 초 단위 숫자여야 합니다(받은 값: {raw!r}).",
        "err.http": "{url} 가 HTTP {code} 를 반환했습니다(모델 {model!r}). 모델 이름과 API 키를 확인하세요.",
        "err.unreachable": "{url} 에 연결할 수 없습니다({reason}). 서버가 실행 중인가요? "
                           "로컬 모델은 느릴 수 있으니 PDF_REDPEN_TIMEOUT 을 늘려 보세요(현재 {timeout}초).",
        "err.response_shape": "{url} 의 응답 형태가 예상과 다릅니다: {reason}",
        "err.record_dir": "녹음 폴더를 찾을 수 없습니다: {directory}. 먼저 `review --record DIR` 로 만드세요.",
        "err.no_recording": "{page}쪽 {turn}번째 턴의 녹음이 없습니다. 필요한 파일: {path}.",
        "detail.no_text_layer": "쓸 수 있는 텍스트 층이 없습니다(빈 쪽, 스캔본 또는 매핑되지 않은 글리프). "
                                "모델을 호출하지 않았습니다",
        "notice.mock": "연습용 목(mock) 모드: 답변은 실제 모델이 아니라 손으로 쓴 녹음 파일에서 재생했습니다. "
                       "답변 이후 과정(표 해석·병합·위치 찾기·주석 쓰기)은 실제 모드와 같은 코드입니다.",
        "summary.highlighted": "강조 {n}개",
        "summary.memos.one": "페이지 메모 {n}개",
        "summary.memos.other": "페이지 메모 {n}개",
        "summary.skipped.one": "{n}쪽 건너뜀(텍스트 층 없음)",
        "summary.skipped.other": "{n}쪽 건너뜀(텍스트 층 없음)",
        "summary.failed.one": "{n}쪽 실패",
        "summary.failed.other": "{n}쪽 실패",
        "summary.line": "지적 {total}건: {parts}",
        "summary.sep": ", ",
        "summary.stages": "단계: {stages}",
        "summary.recall": "재확인 패스: 첫 번째 {first}, 추가 {added}, 중복 제외 {dup}",
        "md.title": "pdf-redpen 보고서: {name}",
        "md.mode": "모드: {mode}",
        "mode.apply": "적용(apply)",
        "mode.review": "검토(review)",
        "mode.review_mock": "검토(review, 목: 연습용 재생)",
        "md.result": "결과: **{summary}**",
        "md.broken_rows": "건너뛴 깨진 표 행: {n}",
        "md.findings": "지적 사항",
        "md.findings_head": "| # | 출처 | 요청 쪽 | 찾은 쪽 | 단계 | 상태 | 심각도 | 인용문 | 코멘트 |",
        "md.prefix25_note": "참고: `prefix25` 는 인용문의 앞 25자만 맞추고 인용문 길이만큼 칠하므로, "
                            "모델이 인용하지 않은 글까지 덮을 수 있습니다. 이 강조는 눈으로 확인하세요.",
        "md.pages": "쪽",
        "md.pages_head": "| 쪽 | 상태 | 첫 번째 | 재확인 추가 | 중복 제외 | 깨진 행 | 비고 |",
        "md.no_table": "답변에 표 없음",
        "md.truncated": "보내기 전에 쪽 텍스트를 잘랐음",
        "md.prompts": "보낸 프롬프트",
        "md.prompt_head": "{page}쪽, {turn}번째 턴",
        "tag.not_found": "[위치 못 찾음]",
        "tag.overflow": "[상한 초과]",
        "tag.loose": "(느슨 일치)",
    },
}

_current = DEFAULT_LANG


def set_lang(lang: str) -> str:
    """Set the language used when a call does not name one. Returns the previous one."""
    global _current
    previous = _current
    _current = lang if lang in LANGS else DEFAULT_LANG
    return previous


def get_lang() -> str:
    return _current


def t(message_id: str, lang: Optional[str] = None, **params: object) -> str:
    """Look up a message and fill its {placeholders}."""
    table = MESSAGES.get(lang or _current, MESSAGES[DEFAULT_LANG])
    return table[message_id].format(**params)


def t_plural(message_id: str, n: int, lang: Optional[str] = None, **params: object) -> str:
    """Like t(), choosing `<id>.one` for n == 1 and `<id>.other` otherwise."""
    return t(f"{message_id}.{'one' if n == 1 else 'other'}", lang, n=n, **params)


def _from_value(value: str) -> str:
    return "ko" if value.strip().lower().startswith("ko") else "en"


def resolve_lang(cli_value: Optional[str] = None, env: Optional[Mapping[str, str]] = None) -> str:
    """`--lang` > PDF_REDPEN_LANG > LC_ALL > LC_MESSAGES > LANG; Korean only if it starts with "ko"."""
    if cli_value in LANGS:
        return str(cli_value)
    if env is None:
        import os

        env = os.environ
    for name in ENV_VARS:
        value = env.get(name, "")
        if value.strip():
            return _from_value(value)
    return DEFAULT_LANG


def lang_from_argv(argv: list[str]) -> Optional[str]:
    """Find a global `--lang X` before the sub-command (so help and parse errors use it too).

    The sub-command's own `review --lang` is the prompt language and is not looked at.
    """
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--lang":
            return argv[i + 1] if i + 1 < len(argv) else None
        if arg.startswith("--lang="):
            return arg.split("=", 1)[1]
        if not arg.startswith("-"):
            return None  # first word is the sub-command
        i += 1
    return None


class CodedError(Exception):
    """An error with a message id and parameters, rendered in the reader's language.

    `str(exc)` is always the English text, so library users see stable messages. If the
    id is not in the table it is used as the literal message.
    """

    def __init__(self, message_id: str, **params: object) -> None:
        self.message_id = message_id
        self.params = params
        super().__init__(self.render("en"))

    def render(self, lang: Optional[str] = None) -> str:
        if self.message_id in MESSAGES["en"]:
            return t(self.message_id, lang, **self.params)
        return self.message_id
