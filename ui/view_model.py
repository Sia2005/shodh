from __future__ import annotations

import html
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

PLANNING = "PLANNING"
SEARCHING = "SEARCHING"
SYNTHESIZING = "SYNTHESIZING"
CRITIQUING = "CRITIQUING"
DONE = "DONE"
FAILED = "FAILED"

STAGE_ORDER: tuple[str, ...] = (PLANNING, SEARCHING, SYNTHESIZING, CRITIQUING, DONE)
STAGE_LABELS: dict[str, str] = {
    PLANNING: "Planning",
    SEARCHING: "Searching",
    SYNTHESIZING: "Synthesizing",
    CRITIQUING: "Critiquing",
    DONE: "Complete",
}

STATUS_DONE = "done"
STATUS_ACTIVE = "active"
STATUS_PENDING = "pending"
STATUS_FAILED = "failed"

VERDICT_SUPPORTED = "supported"
VERDICT_WEAK = "weakly-supported"
VERDICT_UNSUPPORTED = "unsupported"
VERDICT_PENDING = "pending"

NOTE_PLANNING_COMPLETE = "planning complete"
NOTE_DRAFT_SYNTHESIZED = "draft synthesized"
NOTE_CRITIQUE_COMPLETE = "critique complete"
NOTE_RESEARCH_TRIGGERED = "re-search triggered"
NOTE_SEARCHED_PREFIX = "searched:"
NOTE_ERROR_PREFIX = "error:"

FAILURE_UNREACHABLE = "unreachable"
FAILURE_TRANSPORT = "transport"
FAILURE_BUDGET = "budget"
FAILURE_NO_CLAIMS = "no_claims"
FAILURE_ERROR = "error"
FAILURE_STREAM_ENDED = "stream_ended"

ACTIVE_STAGE_DESCRIPTIONS: dict[str, str] = {
    PLANNING: "Breaking the question into sub-questions",
    SEARCHING: "Searching the web for each sub-question",
    SYNTHESIZING: "Drafting a cited report from the evidence",
    CRITIQUING: "Grading each claim against its sources",
    DONE: "Finishing up",
}
PENDING_STAGE_DESCRIPTIONS: dict[str, str] = {
    PLANNING: "Not started",
    SEARCHING: "Waiting for a plan",
    SYNTHESIZING: "Waiting for evidence",
    CRITIQUING: "Waiting for a draft",
    DONE: "Waiting for the critic's approval",
}

SSE_DATA_PREFIX = "data: "
CITATION_PATTERN = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")
FAILED_TRANSITION_PATTERN = re.compile(r"\[(\w+) -> FAILED\]")


@dataclass
class RunRecord:
    question: str
    api_url: str
    started_at: float
    events: list[dict[str, Any]] = field(default_factory=list)
    arrival_times: list[float] = field(default_factory=list)
    stream_closed: bool = False
    connection_error: str | None = None
    transport_error: str | None = None

    def add_event(self, payload: dict[str, Any], arrived_at: float) -> None:
        self.events.append(payload)
        self.arrival_times.append(arrived_at)


@dataclass(frozen=True)
class StageView:
    key: str
    label: str
    status: str
    description: str
    duration_seconds: float | None


@dataclass(frozen=True)
class SourceView:
    number: int
    url: str
    title: str
    domain: str


@dataclass(frozen=True)
class SourceGroupView:
    url: str
    title: str
    domain: str
    numbers: tuple[int, ...]


@dataclass(frozen=True)
class ClaimView:
    position: int
    claim_id: str
    text: str
    verdict: str
    reason: str
    citations: tuple[SourceView | int, ...]


@dataclass(frozen=True)
class ContradictionView:
    claim: str
    note: str
    source_a: SourceView | None
    source_b: SourceView | None
    source_a_number: Any
    source_b_number: Any


@dataclass(frozen=True)
class VerificationSummary:
    supported: int
    weak: int
    unsupported: int

    @property
    def total(self) -> int:
        return self.supported + self.weak + self.unsupported


@dataclass(frozen=True)
class FailureView:
    kind: str
    title: str
    message: str
    technical_detail: str


@dataclass(frozen=True)
class ActivityLine:
    phase: str
    note: str


@dataclass(frozen=True)
class RunView:
    question: str
    has_events: bool
    is_running: bool
    is_done: bool
    failure: FailureView | None
    round_number: int
    stages: tuple[StageView, ...]
    sources_analysed: int
    searches_run: int
    claim_count: int
    verification: VerificationSummary | None
    rounds: int
    report: str | None
    linked_report_html: str | None
    claims: tuple[ClaimView, ...]
    sources: tuple[SourceView, ...]
    source_groups: tuple[SourceGroupView, ...]
    contradictions: tuple[ContradictionView, ...]
    activity: tuple[ActivityLine, ...]
    trace: tuple[str, ...]
    total_seconds: float | None

    @property
    def show_unverified_draft(self) -> bool:
        return self.failure is not None and bool(self.report)


def parse_sse_line(line: str) -> dict[str, Any] | None:
    if not line or not line.startswith(SSE_DATA_PREFIX):
        return None
    try:
        payload = json.loads(line[len(SSE_DATA_PREFIX):])
    except json.JSONDecodeError:
        logger.warning("Skipping malformed SSE line: %r", line[:200])
        return None
    if not isinstance(payload, dict):
        logger.warning("Skipping non-object SSE payload: %r", line[:200])
        return None
    return payload


def domain_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def note_of(payload: dict[str, Any]) -> str:
    return str(payload.get("note") or "")


def is_error_note(payload: dict[str, Any]) -> bool:
    return note_of(payload).startswith(NOTE_ERROR_PREFIX)


def is_failure_event(payload: dict[str, Any]) -> bool:
    return payload.get("phase") == FAILED or is_error_note(payload)


def count_searches(events: list[dict[str, Any]]) -> int:
    return sum(1 for payload in events if note_of(payload).startswith(NOTE_SEARCHED_PREFIX))


def round_number_for(payload: dict[str, Any]) -> int:
    iteration = int(payload.get("iteration") or 0)
    if note_of(payload) == NOTE_RESEARCH_TRIGGERED:
        return iteration + 1
    return max(iteration, 1)


def stage_for_failed_event(payload: dict[str, Any], previous_events: list[dict[str, Any]]) -> str:
    for trace_line in reversed(payload.get("trace") or []):
        match = FAILED_TRANSITION_PATTERN.search(str(trace_line))
        if match and match.group(1) in STAGE_ORDER:
            return match.group(1)
    for earlier in reversed(previous_events):
        phase = earlier.get("phase")
        if phase in STAGE_ORDER and phase != DONE:
            return str(phase)
    return PLANNING


def stage_for_event(payload: dict[str, Any], previous_events: list[dict[str, Any]]) -> str:
    if note_of(payload) == NOTE_PLANNING_COMPLETE:
        return PLANNING
    phase = payload.get("phase")
    if phase == FAILED:
        return stage_for_failed_event(payload, previous_events)
    if phase in STAGE_ORDER:
        return str(phase)
    return PLANNING


def stage_durations(record: RunRecord) -> dict[str, float]:
    durations: dict[str, float] = {stage: 0.0 for stage in STAGE_ORDER}
    previous_time = record.started_at
    for index, (payload, arrived_at) in enumerate(zip(record.events, record.arrival_times)):
        stage = stage_for_event(payload, record.events[:index])
        durations[stage] += max(arrived_at - previous_time, 0.0)
        previous_time = arrived_at
    return durations


def latest_index_with_note(events: list[dict[str, Any]], note: str) -> int:
    for index in range(len(events) - 1, -1, -1):
        if note_of(events[index]) == note:
            return index
    return -1


def verdicts_are_current(events: list[dict[str, Any]]) -> bool:
    critique_index = latest_index_with_note(events, NOTE_CRITIQUE_COMPLETE)
    return critique_index >= 0 and critique_index > latest_index_with_note(events, NOTE_DRAFT_SYNTHESIZED)


def summarize_verdicts(claim_verdicts: list[dict[str, Any]]) -> VerificationSummary:
    verdicts = [str(item.get("verdict")) for item in claim_verdicts]
    return VerificationSummary(
        supported=verdicts.count(VERDICT_SUPPORTED),
        weak=verdicts.count(VERDICT_WEAK),
        unsupported=verdicts.count(VERDICT_UNSUPPORTED),
    )


def build_sources(raw_sources: list[dict[str, Any]]) -> tuple[SourceView, ...]:
    sources: list[SourceView] = []
    for item in raw_sources:
        url = str(item.get("url") or "")
        number = item.get("n")
        if not url or not isinstance(number, int):
            continue
        sources.append(
            SourceView(
                number=number,
                url=url,
                title=str(item.get("title") or "").strip() or domain_from_url(url) or url,
                domain=domain_from_url(url),
            )
        )
    return tuple(sources)


def group_sources_by_url(sources: tuple[SourceView, ...]) -> tuple[SourceGroupView, ...]:
    groups: dict[str, list[SourceView]] = {}
    for source in sources:
        groups.setdefault(source.url, []).append(source)
    return tuple(
        SourceGroupView(
            url=url,
            title=members[0].title,
            domain=members[0].domain,
            numbers=tuple(member.number for member in members),
        )
        for url, members in groups.items()
    )


def resolve_citation(number: Any, sources_by_number: dict[int, SourceView]) -> SourceView | int | None:
    if isinstance(number, bool) or not isinstance(number, int):
        return None
    return sources_by_number.get(number, number)


def build_claims(
    raw_claims: list[dict[str, Any]],
    claim_verdicts: list[dict[str, Any]],
    verdicts_current: bool,
    sources_by_number: dict[int, SourceView],
) -> tuple[ClaimView, ...]:
    verdicts_by_id = {str(item.get("id")): item for item in claim_verdicts} if verdicts_current else {}
    claims: list[ClaimView] = []
    for position, raw_claim in enumerate(raw_claims, start=1):
        claim_id = str(raw_claim.get("id") or "")
        verdict = verdicts_by_id.get(claim_id, {})
        resolved = (resolve_citation(number, sources_by_number) for number in raw_claim.get("citations") or [])
        claims.append(
            ClaimView(
                position=position,
                claim_id=claim_id,
                text=str(raw_claim.get("text") or ""),
                verdict=str(verdict.get("verdict") or VERDICT_PENDING),
                reason=str(verdict.get("reason") or ""),
                citations=tuple(citation for citation in resolved if citation is not None),
            )
        )
    return tuple(claims)


def build_contradictions(
    raw_contradictions: list[dict[str, Any]], sources_by_number: dict[int, SourceView]
) -> tuple[ContradictionView, ...]:
    contradictions: list[ContradictionView] = []
    for item in raw_contradictions:
        side_a = resolve_citation(item.get("source_a"), sources_by_number)
        side_b = resolve_citation(item.get("source_b"), sources_by_number)
        contradictions.append(
            ContradictionView(
                claim=str(item.get("claim") or ""),
                note=str(item.get("note") or ""),
                source_a=side_a if isinstance(side_a, SourceView) else None,
                source_b=side_b if isinstance(side_b, SourceView) else None,
                source_a_number=item.get("source_a"),
                source_b_number=item.get("source_b"),
            )
        )
    return tuple(contradictions)


def citation_link_html(number: int, sources_by_number: dict[int, SourceView]) -> str:
    source = sources_by_number.get(number)
    if source is None:
        return f'<sup class="shodh-cite shodh-cite-missing">{number}</sup>'
    return (
        f'<sup class="shodh-cite"><a href="{html.escape(source.url, quote=True)}" target="_blank" '
        f'rel="noopener noreferrer" title="{html.escape(source.title, quote=True)}">{number}</a></sup>'
    )


def link_citations(report: str, sources: tuple[SourceView, ...]) -> str:
    sources_by_number = {source.number: source for source in sources}
    safe_report = report.replace("<", "&lt;").replace("$", "\\$").replace("~", "\\~")

    def replace_group(match: re.Match[str]) -> str:
        numbers = [int(part) for part in re.split(r"\s*,\s*", match.group(1))]
        return "".join(citation_link_html(number, sources_by_number) for number in numbers)

    return CITATION_PATTERN.sub(replace_group, safe_report)


def plain_failure_message(kind: str, api_url: str) -> str:
    messages = {
        FAILURE_UNREACHABLE: (
            f"Shodh couldn't reach the research API at {api_url}. Start it with "
            "uvicorn api.main:app, or point SHODH_API_URL at the right address."
        ),
        FAILURE_TRANSPORT: "The connection to the research API broke while the agent was working.",
        FAILURE_BUDGET: "The agent hit its round or token limit before the critic approved the report.",
        FAILURE_NO_CLAIMS: "No verifiable claims could be extracted from the sources that were found.",
        FAILURE_ERROR: "Something went wrong inside the agent while it was working on this question.",
        FAILURE_STREAM_ENDED: "The research API closed the stream before the run finished.",
    }
    return messages[kind]


def classify_failure(record: RunRecord) -> FailureView | None:
    if record.connection_error is not None:
        kind, detail = FAILURE_UNREACHABLE, record.connection_error
    elif record.transport_error is not None:
        kind, detail = FAILURE_TRANSPORT, record.transport_error
    else:
        failure_event = next((payload for payload in record.events if is_failure_event(payload)), None)
        if failure_event is not None:
            detail = note_of(failure_event) or "Phase changed to FAILED."
            if is_error_note(failure_event):
                kind = FAILURE_ERROR
            elif detail.startswith("stopped:"):
                kind = FAILURE_BUDGET
            elif "no claims" in detail:
                kind = FAILURE_NO_CLAIMS
            else:
                kind = FAILURE_ERROR
        elif record.stream_closed and not any(payload.get("phase") == DONE for payload in record.events):
            kind, detail = FAILURE_STREAM_ENDED, "Stream closed without a DONE or FAILED event."
        else:
            return None
    return FailureView(
        kind=kind,
        title="Research couldn't be completed",
        message=plain_failure_message(kind, record.api_url),
        technical_detail=detail,
    )


def pluralize(count: int, singular: str, plural: str | None = None) -> str:
    return f"{count} {singular if count == 1 else (plural or singular + 's')}"


def describe_stage(
    stage: str,
    status: str,
    latest: dict[str, Any],
    searches_run: int,
    round_number: int,
    verification: VerificationSummary | None,
    total_seconds: float | None,
) -> str:
    description = describe_stage_from_data(stage, status, latest, searches_run, round_number, verification, total_seconds)
    if description:
        return description
    if status == STATUS_FAILED:
        return "Stopped here"
    if status == STATUS_ACTIVE:
        return ACTIVE_STAGE_DESCRIPTIONS[stage]
    return PENDING_STAGE_DESCRIPTIONS[stage]


def describe_stage_from_data(
    stage: str,
    status: str,
    latest: dict[str, Any],
    searches_run: int,
    round_number: int,
    verification: VerificationSummary | None,
    total_seconds: float | None,
) -> str | None:
    if stage == PLANNING:
        planned = len(latest.get("sub_questions") or [])
        return f"{pluralize(planned, 'sub-question')} planned" if planned else None
    if stage == SEARCHING:
        if status == STATUS_ACTIVE and round_number > 1:
            gap_count = len(latest.get("gaps") or [])
            return f"Round {round_number}: re-searching {pluralize(gap_count, 'weak or unsupported claim')}"
        if searches_run:
            rounds_suffix = f" over {round_number} rounds" if round_number > 1 else ""
            return f"searched {pluralize(searches_run, 'query', 'queries')}{rounds_suffix}"
        return None
    if stage == SYNTHESIZING:
        claim_count = int(latest.get("n_claims") or 0)
        return f"{pluralize(claim_count, 'claim')} drafted" if status == STATUS_DONE and claim_count else None
    if stage == CRITIQUING:
        if status == STATUS_DONE and verification is not None:
            return (
                f"{verification.supported} supported · {verification.weak} weak · "
                f"{verification.unsupported} unsupported"
            )
        return None
    if status == STATUS_DONE:
        return f"Critic approved the report in {format_duration(total_seconds)}" if total_seconds else "Critic approved the report"
    return None


def stage_statuses(record: RunRecord, failure: FailureView | None) -> dict[str, str]:
    if not record.events:
        first_status = STATUS_FAILED if failure else STATUS_ACTIVE
        return {stage: (first_status if stage == PLANNING else STATUS_PENDING) for stage in STAGE_ORDER}
    latest = record.events[-1]
    if latest.get("phase") == DONE and failure is None:
        return {stage: STATUS_DONE for stage in STAGE_ORDER}
    current_stage = stage_for_event(latest, record.events[:-1])
    if note_of(latest) == NOTE_PLANNING_COMPLETE:
        current_stage = SEARCHING
    current_index = STAGE_ORDER.index(current_stage)
    current_status = STATUS_FAILED if failure else STATUS_ACTIVE
    statuses: dict[str, str] = {}
    for index, stage in enumerate(STAGE_ORDER):
        if index < current_index:
            statuses[stage] = STATUS_DONE
        elif index == current_index:
            statuses[stage] = current_status
        else:
            statuses[stage] = STATUS_PENDING
    return statuses


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return ""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, remainder = divmod(int(round(seconds)), 60)
    return f"{minutes}m {remainder:02d}s"


def build_view(record: RunRecord) -> RunView:
    latest: dict[str, Any] = record.events[-1] if record.events else {}
    failure = classify_failure(record)
    is_done = latest.get("phase") == DONE and failure is None
    durations = stage_durations(record)
    total_seconds = record.arrival_times[-1] - record.started_at if record.arrival_times else None
    verdicts_current = verdicts_are_current(record.events)
    claim_verdicts = list(latest.get("claim_verdicts") or [])
    verification = summarize_verdicts(claim_verdicts) if verdicts_current and claim_verdicts else None
    searches_run = count_searches(record.events)
    round_number = round_number_for(latest) if latest else 1
    statuses = stage_statuses(record, failure)

    stages = tuple(
        StageView(
            key=stage,
            label=STAGE_LABELS[stage],
            status=statuses[stage],
            description=describe_stage(
                stage, statuses[stage], latest, searches_run, round_number, verification, total_seconds
            ),
            duration_seconds=(
                durations[stage]
                if statuses[stage] in (STATUS_DONE, STATUS_FAILED) and stage != DONE and record.events
                else None
            ),
        )
        for stage in STAGE_ORDER
    )

    sources = build_sources(list(latest.get("sources") or []))
    sources_by_number = {source.number: source for source in sources}
    report = latest.get("report") or None

    return RunView(
        question=record.question,
        has_events=bool(record.events),
        is_running=not record.stream_closed and failure is None and not is_done,
        is_done=is_done,
        failure=failure,
        round_number=round_number,
        stages=stages,
        sources_analysed=int(latest.get("n_evidence") or 0),
        searches_run=searches_run,
        claim_count=int(latest.get("n_claims") or 0),
        verification=verification,
        rounds=int(latest.get("iteration") or 0),
        report=report,
        linked_report_html=link_citations(report, sources) if report else None,
        claims=build_claims(list(latest.get("claims") or []), claim_verdicts, verdicts_current, sources_by_number),
        sources=sources,
        source_groups=group_sources_by_url(sources),
        contradictions=build_contradictions(list(latest.get("contradictions") or []), sources_by_number),
        activity=tuple(ActivityLine(phase=str(payload.get("phase") or ""), note=note_of(payload)) for payload in record.events),
        trace=tuple(str(line) for line in latest.get("trace") or []),
        total_seconds=total_seconds,
    )
