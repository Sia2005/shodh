from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

import httpx
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ui import theme
from ui.view_model import RunRecord, RunView, build_view, parse_sse_line

logger = logging.getLogger(__name__)

API_URL = os.environ.get("SHODH_API_URL", "http://localhost:8000")
CONNECT_TIMEOUT_SECONDS = 10.0
READ_TIMEOUT_SECONDS = 600.0
HISTORY_LABEL_MAX_CHARS = 48
SOURCE_GRID_COLUMNS = 3

QUESTION_KEY = "question_input"
RUNS_KEY = "runs"
SELECTED_RUN_KEY = "selected_run_index"
RETRY_QUESTION_KEY = "retry_question"
EXAMPLE_PILLS_KEY = "example_pills"

PLACEHOLDER_QUESTION = "e.g. How has India's UPI transaction volume changed since 2022?"
EXAMPLE_QUESTIONS: dict[str, str] = {
    "UPI growth since 2022": "How has India's UPI transaction volume changed since 2022?",
    "Four-day work week": "What does recent evidence say about four-day work weeks and productivity?",
    "Battery prices since 2015": "How have lithium-ion battery pack prices changed since 2015, and why?",
}


def init_session_state() -> None:
    st.session_state.setdefault(QUESTION_KEY, "")
    st.session_state.setdefault(RUNS_KEY, [])
    st.session_state.setdefault(SELECTED_RUN_KEY, None)


def start_new_research() -> None:
    st.session_state[QUESTION_KEY] = ""
    st.session_state[SELECTED_RUN_KEY] = None
    st.session_state.pop(RETRY_QUESTION_KEY, None)


def apply_example_pill() -> None:
    selected_label = st.session_state.get(EXAMPLE_PILLS_KEY)
    if selected_label in EXAMPLE_QUESTIONS:
        st.session_state[QUESTION_KEY] = EXAMPLE_QUESTIONS[selected_label]
    st.session_state[EXAMPLE_PILLS_KEY] = None


def select_run(run_index: int) -> None:
    st.session_state[SELECTED_RUN_KEY] = run_index
    st.session_state[QUESTION_KEY] = st.session_state[RUNS_KEY][run_index].question


def queue_retry(question: str) -> None:
    st.session_state[RETRY_QUESTION_KEY] = question
    st.session_state[QUESTION_KEY] = question


def selected_record() -> RunRecord | None:
    run_index = st.session_state[SELECTED_RUN_KEY]
    runs: list[RunRecord] = st.session_state[RUNS_KEY]
    if run_index is None or not 0 <= run_index < len(runs):
        return None
    return runs[run_index]


def history_label(record: RunRecord) -> str:
    view = build_view(record)
    status_icon = "✓" if view.is_done else "✕"
    question = record.question
    if len(question) > HISTORY_LABEL_MAX_CHARS:
        question = question[: HISTORY_LABEL_MAX_CHARS - 1].rstrip() + "…"
    return f"{status_icon}  {question}"


def render_sidebar() -> None:
    with st.sidebar:
        st.button("New research", key="sidebar_new_research", on_click=start_new_research)
        st.markdown(theme.section_label_html("This session"), unsafe_allow_html=True)
        st.caption("Only runs from this browser tab. Nothing is saved; refreshing the page clears this list.")
        runs: list[RunRecord] = st.session_state[RUNS_KEY]
        if not runs:
            st.caption("No research run yet.")
            return
        with st.container(key="history_list"):
            for run_index in range(len(runs) - 1, -1, -1):
                st.button(
                    history_label(runs[run_index]),
                    key=f"history_run_{run_index}",
                    on_click=select_run,
                    args=(run_index,),
                    type="primary" if run_index == st.session_state[SELECTED_RUN_KEY] else "secondary",
                )


def render_header() -> None:
    st.markdown(theme.header_html(), unsafe_allow_html=True)
    st.markdown(theme.tagline_html(), unsafe_allow_html=True)


def render_input_card() -> tuple[str, bool]:
    with st.container(key="input_card"):
        question = st.text_input("Research question", key=QUESTION_KEY, placeholder=PLACEHOLDER_QUESTION)
        st.markdown(
            theme.helper_text_html("Ask a question that needs multiple sources or a deeper investigation."),
            unsafe_allow_html=True,
        )
        run_clicked = st.button("Run research →", key="run_research", type="primary", disabled=not question.strip())
    return question.strip(), run_clicked


def render_empty_state() -> None:
    st.markdown(theme.section_label_html("What Shodh does"), unsafe_allow_html=True)
    for column, (title, body) in zip(st.columns(len(theme.CAPABILITIES)), theme.CAPABILITIES):
        with column:
            st.markdown(theme.capability_card_html(title, body), unsafe_allow_html=True)
    st.markdown(theme.section_label_html("Try an example"), unsafe_allow_html=True)
    st.pills(
        "Example questions",
        options=list(EXAMPLE_QUESTIONS),
        selection_mode="single",
        key=EXAMPLE_PILLS_KEY,
        on_change=apply_example_pill,
        label_visibility="collapsed",
    )


def render_stepper(view: RunView) -> None:
    round_number = view.round_number if view.round_number > 1 else None
    st.markdown(theme.section_label_html("Progress", round_number), unsafe_allow_html=True)
    for column, stage in zip(st.columns(len(view.stages)), view.stages):
        with column:
            st.markdown(theme.stage_card_html(stage), unsafe_allow_html=True)
    with st.expander("View activity", expanded=False):
        activity_html = "".join(theme.activity_line_html(line.phase, line.note) for line in view.activity)
        st.markdown(activity_html or theme.helper_text_html("No events yet."), unsafe_allow_html=True)
        if view.trace:
            st.code("\n".join(view.trace), language=None)


def verification_value(view: RunView) -> str:
    if view.verification is None or view.verification.total == 0:
        return "—"
    return f"{view.verification.supported}/{view.verification.total} supported"


def render_metrics(view: RunView) -> None:
    metrics = (
        ("Sources analysed", str(view.sources_analysed)),
        ("Searches run", str(view.searches_run)),
        ("Claims", str(view.claim_count)),
        ("Verification", verification_value(view)),
        ("Rounds", str(view.rounds)),
    )
    for column, (label, value) in zip(st.columns(len(metrics)), metrics):
        with column:
            st.markdown(theme.metric_card_html(label, value), unsafe_allow_html=True)


def render_failure_card(view: RunView, record: RunRecord) -> None:
    if view.failure is None:
        return
    with st.container(key="error_card"):
        st.markdown(theme.error_heading_html(view.failure.title, view.failure.message), unsafe_allow_html=True)
        st.button("Try again", key="retry_research", type="primary", on_click=queue_retry, args=(record.question,))
        with st.expander("Technical details", expanded=False):
            st.code(view.failure.technical_detail, language=None)


def render_report_tab(view: RunView, render_token: str) -> None:
    with st.container(key=f"report_body_{render_token}"):
        st.markdown(view.linked_report_html or "", unsafe_allow_html=True)


def render_claims_tab(view: RunView) -> None:
    if not view.claims:
        st.markdown(theme.helper_text_html("No claims extracted yet."), unsafe_allow_html=True)
        return
    st.markdown("".join(theme.claim_card_html(claim) for claim in view.claims), unsafe_allow_html=True)


def render_sources_tab(view: RunView) -> None:
    if not view.source_groups:
        st.markdown(theme.helper_text_html("No sources yet."), unsafe_allow_html=True)
        return
    groups = list(enumerate(view.source_groups, start=1))
    for row_start in range(0, len(groups), SOURCE_GRID_COLUMNS):
        row = groups[row_start : row_start + SOURCE_GRID_COLUMNS]
        for column, (position, group) in zip(st.columns(SOURCE_GRID_COLUMNS), row):
            with column:
                st.markdown(theme.source_card_html(position, group), unsafe_allow_html=True)


def render_contradictions_tab(view: RunView) -> None:
    st.markdown(
        "".join(theme.contradiction_card_html(contradiction) for contradiction in view.contradictions),
        unsafe_allow_html=True,
    )


def render_report_section(view: RunView, live: bool, render_token: str) -> None:
    if not view.report:
        if live and view.has_events:
            st.markdown(
                theme.notice_html("info", "Working.", "The report appears here once the first draft is synthesized."),
                unsafe_allow_html=True,
            )
        return
    st.markdown(theme.section_label_html("Report"), unsafe_allow_html=True)
    st.markdown(theme.question_heading_html(view.question), unsafe_allow_html=True)
    if view.show_unverified_draft:
        st.markdown(
            theme.notice_html(
                "warning",
                "Unverified draft.",
                "The run stopped before the critic approved this report. Check each claim against its sources before relying on it.",
            ),
            unsafe_allow_html=True,
        )
    elif view.is_running:
        st.markdown(
            theme.notice_html("info", "Draft in progress.", "Verification is still running, so this report may change."),
            unsafe_allow_html=True,
        )

    tab_names = ["Report", f"Claims ({len(view.claims)})", f"Sources ({len(view.source_groups)})"]
    if view.contradictions:
        tab_names.append(f"Contradictions ({len(view.contradictions)})")
    tabs = st.tabs(tab_names)
    with tabs[0]:
        render_report_tab(view, render_token)
    with tabs[1]:
        render_claims_tab(view)
    with tabs[2]:
        render_sources_tab(view)
    if view.contradictions:
        with tabs[3]:
            render_contradictions_tab(view)


def render_run(record: RunRecord, live: bool, render_token: str) -> None:
    view = build_view(record)
    if view.has_events or live:
        render_stepper(view)
        render_metrics(view)
    if not live:
        render_failure_card(view, record)
    render_report_section(view, live, render_token)


def render_live(live_area: DeltaGenerator, record: RunRecord) -> None:
    with live_area.container():
        render_run(record, live=True, render_token=f"live_{len(record.events)}")


def stream_research(question: str, live_area: DeltaGenerator) -> RunRecord:
    record = RunRecord(question=question, api_url=API_URL, started_at=time.monotonic())
    render_live(live_area, record)
    timeout = httpx.Timeout(READ_TIMEOUT_SECONDS, connect=CONNECT_TIMEOUT_SECONDS)
    try:
        with httpx.stream("POST", f"{API_URL}/research", json={"question": question}, timeout=timeout) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                payload = parse_sse_line(line)
                if payload is None:
                    continue
                record.add_event(payload, time.monotonic())
                render_live(live_area, record)
    except (httpx.ConnectError, httpx.ConnectTimeout) as error:
        logger.warning("Shodh API unreachable at %s: %s", API_URL, error)
        record.connection_error = f"{type(error).__name__}: {error}"
    except httpx.HTTPError as error:
        logger.warning("Shodh API stream failed: %s", error)
        record.transport_error = f"{type(error).__name__}: {error}"
    record.stream_closed = True
    return record


def main() -> None:
    st.set_page_config(page_title="Shodh", page_icon="🔎", layout="wide")
    st.markdown(theme.APP_CSS, unsafe_allow_html=True)
    init_session_state()
    render_sidebar()
    render_header()
    question, run_clicked = render_input_card()
    body = st.empty()

    question_to_run = question if run_clicked else st.session_state.pop(RETRY_QUESTION_KEY, None)
    if question_to_run:
        record = stream_research(question_to_run, body)
        st.session_state[RUNS_KEY].append(record)
        st.session_state[SELECTED_RUN_KEY] = len(st.session_state[RUNS_KEY]) - 1
        st.rerun()

    record = selected_record()
    with body.container():
        if record is None:
            render_empty_state()
        else:
            render_run(record, live=False, render_token="final")


main()
