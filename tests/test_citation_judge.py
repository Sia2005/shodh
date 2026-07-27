"""
Pure-logic tests for evals.citation_judge.extract_cited_sentences -- the
regex-based splitter that pairs each citation-bearing sentence with the
citation numbers it references. No Gemini calls here; those are exercised
by the full eval run instead.
"""

from __future__ import annotations

from evals.citation_judge import extract_cited_sentences


def test_single_sentence_single_citation():
    report = "The market grew significantly [1]."
    assert extract_cited_sentences(report) == [("The market grew significantly [1].", [1])]


def test_multiple_sentences_split_correctly():
    report = "The market grew [1]. Adoption rose too [2]."
    result = extract_cited_sentences(report)
    assert result == [
        ("The market grew [1].", [1]),
        ("Adoption rose too [2].", [2]),
    ]


def test_multiple_citations_in_one_sentence_grouped_together():
    report = "Revenue and profit both grew [1][2]."
    assert extract_cited_sentences(report) == [("Revenue and profit both grew [1][2].", [1, 2])]


def test_comma_grouped_citation_bracket():
    # Observed in practice: the synthesizer sometimes emits "[2, 4]" instead
    # of "[2][4]" despite its prompt only showing the single-number form.
    report = "Norway won the most golds [2, 4]."
    assert extract_cited_sentences(report) == [("Norway won the most golds [2, 4].", [2, 4])]


def test_sentences_without_citations_are_dropped():
    report = "This is just context with no source. The market grew [1]."
    result = extract_cited_sentences(report)
    assert result == [("The market grew [1].", [1])]


def test_no_citations_anywhere_returns_empty():
    assert extract_cited_sentences("No citations in this report at all.") == []


def test_empty_report_returns_empty():
    assert extract_cited_sentences("") == []
