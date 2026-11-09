"""Prompts for the first review turn and the recall (missed-only) turn.

The table format is spelled out with an example because that is what keeps the
model's answer parseable; the parser still tolerates deviations.
"""
from __future__ import annotations

from .models import Finding

DEFAULT_INSTRUCTIONS = {
    "ko": "사실 관계, 숫자 불일치, 근거 없는 주장, 모호한 표현을 찾아 지적하세요.",
    "en": "Find factual problems, inconsistent numbers, unsupported claims and vague wording.",
}

_SYSTEM = {
    "ko": (
        "당신은 문서 검토자입니다. 주어진 한 쪽의 텍스트에서 문제가 있는 문장을 찾아 "
        "마크다운 표 하나로만 답하세요. 열: | 원문 인용 | 지적 | 심각도 |. "
        "원문 인용은 본문에서 그대로 복사한 한 문장이며, 심각도는 높음/중간/낮음 중 하나입니다. "
        "표 밖의 설명은 짧게 쓰세요."
    ),
    "en": (
        "You are a document reviewer. Read one page of text and answer with a single "
        "markdown table only. Columns: | Quote | Comment | Severity |. The quote is one "
        "sentence copied verbatim from the page; severity is high, medium or low."
    ),
}

_EXAMPLE = {
    "ko": "예:\n| 원문 인용 | 지적 | 심각도 |\n|---|---|---|\n| (본문에서 복사한 문장) | (무엇이 문제인지) | 높음 |",
    "en": "Example:\n| Quote | Comment | Severity |\n|---|---|---|\n| (sentence copied from the page) | (what is wrong) | high |",
}

_RECALL = {
    "ko": (
        "방금 지적한 목록은 다음과 같습니다.\n{listing}\n\n"
        "같은 쪽을 다시 읽고 위 목록에 없는, 놓친 것만 같은 형식의 표로 추가하세요(missed only). "
        "새로 지적할 것이 없으면 표 없이 '추가로 놓친 지적은 없습니다.'라고만 답하세요."
    ),
    "en": (
        "You already reported the following:\n{listing}\n\n"
        "Read the same page again and add only what you missed (missed only), in the same "
        "table format. If there is nothing new, answer without a table."
    ),
}


def system_prompt(lang: str = "ko") -> str:
    return _SYSTEM[lang] + "\n" + _EXAMPLE[lang]


def first_turn(page_no: int, page_text: str, instructions: str, lang: str = "ko") -> list[dict]:
    header = f"[Page {page_no}]" if lang == "en" else f"[{page_no}쪽]"
    return [
        {"role": "system", "content": system_prompt(lang)},
        {"role": "user", "content": f"{instructions.strip()}\n\n{header}\n{page_text}"},
    ]


def recall_turn(first_answer: str, findings: list[Finding], lang: str = "ko") -> list[dict]:
    """Messages to append after the first answer: show what was found, ask for the rest."""
    listing = "\n".join(f"{i}. {f.quote}" for i, f in enumerate(findings, 1)) or "(none)"
    return [
        {"role": "assistant", "content": first_answer},
        {"role": "user", "content": _RECALL[lang].format(listing=listing)},
    ]
