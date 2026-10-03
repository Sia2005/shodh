from __future__ import annotations

from typing import Any

from ui.view_model import (
    FAILURE_BUDGET,
    FAILURE_ERROR,
    FAILURE_STREAM_ENDED,
    FAILURE_UNREACHABLE,
    STATUS_ACTIVE,
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_PENDING,
    VERDICT_PENDING,
    RunRecord,
    SourceView,
    build_view,
    domain_from_url,
    link_citations,
    parse_sse_line,
)

SUB_QUESTIONS = ["What was UPI volume in 2022?", "What is UPI volume now?"]
SOURCES = [
    {"n": 1, "url": "https://www.npci.org.in/stats", "title": "NPCI statistics"},
    {"n": 2, "url": "https://rbi.org.in/report", "title": "RBI annual report"},
    {"n": 3, "url": "https://www.npci.org.in/stats", "title": "NPCI statistics"},
]
CLAIMS = [
    {"id": "c1", "text": "UPI volume grew sharply.", "citations": [1, 2], "sub_question": SUB_QUESTIONS[0]},
    {"id": "c2", "text": "UPI handles most retail payments.", "citations": [3], "sub_question": SUB_QUESTIONS[1]},
]
REPORT = "UPI grew sharply [1, 2]. It dominates retail payments [3]."


def payload(phase: str, note: str, **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "phase": phase,
        "note": note,
        "iteration": 1,
        "tokens_used": 0,
        "sub_questions": SUB_QUESTIONS,
        "n_evidence": 0,
        "n_claims": 0,
        "gaps": [],
        "report": None,
        "claim_verdicts": [],
        "trace": [],
        "sources": [],
        "claims": [],
        "contradictions": [],
    }
    base.update(overrides)
    return base


def drafted(phase: str, note: str, **overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "n_evidence": 6,
        "n_claims": 2,
        "report": REPORT,
        "sources": SOURCES,
        "claims": CLAIMS,
    }
    fields.update(overrides)
    return payload(phase, note, **fields)


def record_from(events: list[dict[str, Any]], closed: bool = True) -> RunRecord:
    record = RunRecord(question="How has UPI changed?", api_url="http://localhost:8000", started_at=100.0)
    for index, event in enumerate(events, start=1):
        record.add_event(event, 100.0 + index * 2.0)
    record.stream_closed = closed
    return record


def statuses(record: RunRecord) -> list[str]:
    return [stage.status for stage in build_view(record).stages]


def happy_path_events() -> list[dict[str, Any]]:
    supported = [
        {"id": "c1", "verdict": "supported", "reason": "NPCI data confirms it."},
        {"id": "c2", "verdict": "weakly-supported", "reason": "Only partially stated."},
    ]
    return [
        payload("SEARCHING", "planning complete", iteration=0),
        payload("SEARCHING", "searched: q1", n_evidence=3),
        payload("SEARCHING", "searched: q2", n_evidence=6),
        drafted("SYNTHESIZING", "draft synthesized"),
        drafted("CRITIQUING", "critique complete", claim_verdicts=supported),
        drafted("DONE", "done", claim_verdicts=supported),
    ]


def test_first_event_marks_planning_done_and_searching_active() -> None:
    record = record_from([payload("SEARCHING", "planning complete", iteration=0)], closed=False)
    view = build_view(record)
    assert statuses(record) == [STATUS_DONE, STATUS_ACTIVE, STATUS_PENDING, STATUS_PENDING, STATUS_PENDING]
    assert view.stages[0].description == "2 sub-questions planned"
    assert view.stages[0].duration_seconds == 2.0
    assert view.is_running


def test_happy_path() -> None:
    view = build_view(record_from(happy_path_events()))
    assert view.is_done and view.failure is None and not view.is_running
    assert [stage.status for stage in view.stages] == [STATUS_DONE] * 5
    assert view.stages[1].description == "searched 2 queries"
    assert view.stages[1].duration_seconds == 4.0
    assert view.stages[2].description == "2 claims drafted"
    assert view.stages[3].description == "1 supported · 1 weak · 0 unsupported"
    assert view.searches_run == 2
    assert view.sources_analysed == 6
    assert view.verification is not None and view.verification.supported == 1 and view.verification.total == 2
    assert view.total_seconds == 12.0
    assert [claim.verdict for claim in view.claims] == ["supported", "weakly-supported"]
    assert [group.numbers for group in view.source_groups] == [(1, 3), (2,)]
    assert view.source_groups[0].domain == "npci.org.in"


def test_report_citations_link_to_matching_source_numbers() -> None:
    view = build_view(record_from(happy_path_events()))
    assert view.linked_report_html is not None
    assert 'href="https://www.npci.org.in/stats"' in view.linked_report_html
    assert view.linked_report_html.count('class="shodh-cite"') == 3
    assert view.linked_report_html.index("rbi.org.in") < view.linked_report_html.index(">3</a>")
    claim_one_citations = view.claims[0].citations
    assert [citation.number for citation in claim_one_citations if isinstance(citation, SourceView)] == [1, 2]


def test_one_research_round_is_shown_as_round_not_reset() -> None:
    weak = [
        {"id": "c1", "verdict": "supported", "reason": "ok"},
        {"id": "c2", "verdict": "unsupported", "reason": "Citation does not mention retail share."},
    ]
    gaps = [{"claim": "UPI handles most retail payments.", "sub_question": SUB_QUESTIONS[1]}]
    events = happy_path_events()[:4] + [
        drafted("CRITIQUING", "critique complete", claim_verdicts=weak),
        drafted("SEARCHING", "re-search triggered", claim_verdicts=weak, gaps=gaps),
    ]
    view = build_view(record_from(events, closed=False))
    assert view.round_number == 2
    assert view.stages[0].status == STATUS_DONE
    assert view.stages[1].status == STATUS_ACTIVE
    assert view.stages[1].description == "Round 2: re-searching 1 weak or unsupported claim"
    assert view.failure is None and view.is_running

    events.append(drafted("SEARCHING", "searched: UPI handles most retail payments.", iteration=2, claim_verdicts=weak, gaps=gaps))
    view = build_view(record_from(events, closed=False))
    assert view.round_number == 2
    assert view.searches_run == 3
    assert view.stages[1].description.startswith("Round 2")

    events.append(drafted("SYNTHESIZING", "draft synthesized", iteration=2, claim_verdicts=weak, gaps=gaps))
    view = build_view(record_from(events, closed=False))
    assert view.verification is None
    assert all(claim.verdict == VERDICT_PENDING for claim in view.claims)

    approved = [{"id": "c1", "verdict": "supported", "reason": "ok"}, {"id": "c2", "verdict": "supported", "reason": "ok"}]
    events.append(drafted("CRITIQUING", "critique complete", iteration=2, claim_verdicts=approved, gaps=gaps))
    events.append(drafted("DONE", "done", iteration=2, claim_verdicts=approved, gaps=gaps))
    view = build_view(record_from(events))
    assert view.is_done and view.rounds == 2
    assert view.stages[1].description == "searched 3 queries over 2 rounds"
    assert view.stages[3].description == "2 supported · 0 weak · 0 unsupported"


def test_failed_with_draft_shows_unverified_draft() -> None:
    weak = [{"id": "c1", "verdict": "unsupported", "reason": "no"}, {"id": "c2", "verdict": "unsupported", "reason": "no"}]
    events = happy_path_events()[:4] + [
        drafted("CRITIQUING", "critique complete", claim_verdicts=weak),
        drafted("SEARCHING", "re-search triggered", claim_verdicts=weak),
        drafted(
            "FAILED",
            "stopped: iteration_count=4 > max_iterations=3",
            iteration=4,
            claim_verdicts=weak,
            trace=["[CRITIQUING -> SEARCHING] re-searching 2 gaps", "[SEARCHING -> FAILED] max iterations exceeded"],
        ),
    ]
    view = build_view(record_from(events))
    assert view.failure is not None and view.failure.kind == FAILURE_BUDGET
    assert view.show_unverified_draft
    assert view.report == REPORT
    assert not view.is_done and not view.is_running
    assert statuses(record_from(events)) == [STATUS_DONE, STATUS_FAILED, STATUS_PENDING, STATUS_PENDING, STATUS_PENDING]


def test_error_note_without_failed_phase_is_a_failure() -> None:
    events = [
        payload("SEARCHING", "planning complete", iteration=0),
        payload("SEARCHING", "error: Tavily request timed out", trace=["[ERROR] Tavily request timed out"]),
    ]
    view = build_view(record_from(events))
    assert view.failure is not None
    assert view.failure.kind == FAILURE_ERROR
    assert view.failure.technical_detail == "error: Tavily request timed out"
    assert not view.show_unverified_draft
    assert [stage.status for stage in view.stages][:2] == [STATUS_DONE, STATUS_FAILED]


def test_unreachable_api_and_truncated_stream() -> None:
    unreachable = RunRecord(question="q", api_url="http://localhost:9999", started_at=0.0, stream_closed=True)
    unreachable.connection_error = "All connection attempts failed"
    view = build_view(unreachable)
    assert view.failure is not None and view.failure.kind == FAILURE_UNREACHABLE
    assert "http://localhost:9999" in view.failure.message and "SHODH_API_URL" in view.failure.message

    truncated = build_view(record_from(happy_path_events()[:3]))
    assert truncated.failure is not None and truncated.failure.kind == FAILURE_STREAM_ENDED


def test_parse_sse_line_and_helpers() -> None:
    assert parse_sse_line('data: {"phase": "DONE"}') == {"phase": "DONE"}
    assert parse_sse_line("") is None
    assert parse_sse_line("data: {not json") is None
    assert domain_from_url("https://www.example.com/a") == "example.com"
    linked = link_citations("Costs $5 <b>bold</b> [9]", ())
    assert "\\$5" in linked and "&lt;b>" in linked and "shodh-cite-missing" in linked
