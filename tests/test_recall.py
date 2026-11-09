"""AC-5 (mock part): the recall turn adds only new findings."""
from conftest import PLAIN_PDF, RECORDED, load_pages
from pdf_redpen.llm import MockClient
from pdf_redpen.recall import quote_key, review_page


def test_recall_adds_only_new():
    page1 = load_pages(PLAIN_PDF)[0]
    client = MockClient(RECORDED)
    review = review_page(client, page1, "check", recall=True)
    assert len(review.first) == 4  # 5 rows, one broken
    assert review.broken_rows == 1
    assert len(review.added) == 1 and review.deduped == 1
    assert review.added[0].source == "recall"
    assert client.calls == [(1, 1), (1, 2)]
    assert "missed only" in review.prompts[1]
    assert review.first[0].quote in review.prompts[1]  # the model is shown its first findings


def test_without_recall_only_one_call():
    page1 = load_pages(PLAIN_PDF)[0]
    client = MockClient(RECORDED)
    review = review_page(client, page1, "check", recall=False)
    assert client.calls == [(1, 1)] and review.added == []


def test_answer_without_table_is_zero_findings_not_failure():
    page2 = load_pages(PLAIN_PDF)[1]
    review = review_page(MockClient(RECORDED), page2, "check", recall=True)
    assert len(review.first) == 4 and review.added == [] and review.deduped == 0


def test_quote_key_ignores_punctuation_and_case():
    assert quote_key("근거 표가 제시되지 않았습니다.") == quote_key('"근거표가 제시되지 않았습니다"')
    assert quote_key("A-b c!") == "abc"
