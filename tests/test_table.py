"""AC-4: the table parser survives what models actually produce."""
from pdf_redpen.table import normalize_severity, parse_table


def quotes(t):
    return [r["quote"] for r in t.rows]


def test_header_variants_pick_columns():
    for header in ("| 원문 인용 | 지적 |", "| Quote | Comment |", "| excerpt | issue |", "| 문장 | 의견 |"):
        t = parse_table(f"{header}\n|---|---|\n| a sentence | a remark |\n")
        assert quotes(t) == ["a sentence"], header
        assert t.rows[0]["comment"] == "a remark", header


def test_column_order_changed_and_index_column():
    t = parse_table("| 심각도 | 지적 | 인용 | # |\n|--|--|--|--|\n| 높음 | bad | the quote | 1 |\n")
    r = t.rows[0]
    assert (r["quote"], r["comment"], r["severity"]) == ("the quote", "bad", "high")


def test_unknown_headers_fall_back_to_position_skipping_index():
    t = parse_table("| # | A | B |\n|---|---|---|\n| 1 | first | second |\n")
    assert t.rows[0]["quote"] == "first" and t.rows[0]["comment"] == "second"


def test_broken_rows_are_counted_not_fatal():
    md = "| 인용 | 지적 | 심각도 |\n|---|---|---|\n| ok | fine | 낮음 |\n| only two | cells |\n|  | empty quote | 높음 |\n"
    t = parse_table(md)
    assert quotes(t) == ["ok"] and t.skipped == 2


def test_no_table_gives_zero_rows():
    t = parse_table("추가로 놓친 지적은 없습니다.")
    assert t.rows == [] and not t.has_table and t.skipped == 0
    assert parse_table("").rows == []


def test_quotes_and_backticks_are_stripped():
    md = "| 인용 | 지적 |\n|---|---|\n| \"quoted\" | a |\n| `ticked` | b |\n| “curly” | c |\n"
    assert quotes(parse_table(md)) == ["quoted", "ticked", "curly"]


def test_two_tables_and_prose_between():
    md = "intro\n| quote | comment |\n|--|--|\n| a | x |\nmiddle text\n| 인용 | 지적 |\n|--|--|\n| b | y |\n"
    assert quotes(parse_table(md)) == ["a", "b"]


def test_escaped_pipe_inside_cell():
    t = parse_table("| quote | comment |\n|--|--|\n| a \\| b | c |\n")
    assert t.rows[0]["quote"] == "a | b"


def test_severity_words():
    assert normalize_severity("높음") == "high"
    assert normalize_severity("Medium") == "medium"
    assert normalize_severity("중간") == "medium"
    assert normalize_severity("낮음") == "low"
    assert normalize_severity("whatever") is None and normalize_severity("") is None
