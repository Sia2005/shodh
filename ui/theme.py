from __future__ import annotations

import html

from ui.view_model import (
    STATUS_ACTIVE,
    STATUS_DONE,
    STATUS_FAILED,
    VERDICT_PENDING,
    VERDICT_SUPPORTED,
    VERDICT_UNSUPPORTED,
    VERDICT_WEAK,
    ClaimView,
    ContradictionView,
    SourceGroupView,
    SourceView,
    StageView,
    format_duration,
)

APP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
  --shodh-bg: #0e0f12;
  --shodh-surface: #15171b;
  --shodh-surface-raised: #1a1d22;
  --shodh-border: #25282e;
  --shodh-border-strong: #31353c;
  --shodh-text: #e6e7ea;
  --shodh-muted: #9a9ea8;
  --shodh-faint: #6c717b;
  --shodh-accent: #7c6cf2;
  --shodh-accent-hover: #8d7ff5;
  --shodh-accent-soft: rgba(124, 108, 242, 0.12);
  --shodh-green: #5fae84;
  --shodh-green-soft: rgba(95, 174, 132, 0.12);
  --shodh-amber: #c9a04f;
  --shodh-amber-soft: rgba(201, 160, 79, 0.12);
  --shodh-red: #cf6b64;
  --shodh-red-soft: rgba(207, 107, 100, 0.12);
  --shodh-radius: 12px;
  --shodh-shadow: 0 1px 2px rgba(0, 0, 0, 0.25);
}

html, body, .stApp, [data-testid="stSidebar"], [data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] p,
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p,
button, button p, [data-baseweb="input"] input, [data-baseweb="tab"], .stApp li, .stApp label, .stApp textarea {
  font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif !important;
}
html, body, .stApp, [data-testid="stSidebar"], [data-testid="stMarkdownContainer"] p { font-size: 14px; }
.stApp { background: var(--shodh-bg); color: var(--shodh-text); }
[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p { font-size: 13px; color: var(--shodh-muted); }
button p, .stButton > button p { font-size: 14px; font-weight: 500; }

#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] { display: none !important; }
[data-testid="stHeader"] { background: transparent; height: 2.5rem; }
[data-testid="stMainBlockContainer"], .block-container {
  max-width: 1200px;
  padding: 1.5rem 1rem 4rem 1rem;
  margin: 0 auto;
}

.stApp h1, .stApp h2, .stApp h3, .stApp h4 { color: var(--shodh-text); letter-spacing: -0.01em; }
.stApp h1 { font-size: 26px; font-weight: 600; }
.stApp h2 { font-size: 21px; font-weight: 600; }
.stApp h3 { font-size: 18px; font-weight: 600; }
.stApp h4 { font-size: 16px; font-weight: 600; }
.stApp a { color: var(--shodh-accent-hover); text-decoration: none; }
.stApp a:hover { text-decoration: underline; }

[data-testid="stSidebar"] { background: var(--shodh-surface); border-right: 1px solid var(--shodh-border); }

.stButton > button {
  border-radius: var(--shodh-radius);
  font-weight: 500;
  transition: background-color 120ms ease, border-color 120ms ease, color 120ms ease;
}
[data-testid="stBaseButton-primary"]:not(:disabled) {
  background: var(--shodh-accent) !important;
  border: 1px solid var(--shodh-accent) !important;
  color: #ffffff !important;
}
[data-testid="stBaseButton-primary"]:not(:disabled) p { color: #ffffff !important; }
[data-testid="stBaseButton-primary"]:hover:not(:disabled) {
  background: var(--shodh-accent-hover) !important;
  border-color: var(--shodh-accent-hover) !important;
}
.st-key-input_card .stButton, .st-key-input_card .stButton > button,
.st-key-error_card .stButton, .st-key-error_card .stButton > button { width: auto !important; max-width: 100%; }
[data-testid="stBaseButton-primary"]:disabled {
  background: var(--shodh-surface-raised);
  border-color: var(--shodh-border);
  color: var(--shodh-faint);
}
[data-testid="stBaseButton-secondary"] {
  background: var(--shodh-surface);
  border: 1px solid var(--shodh-border);
  color: var(--shodh-text);
}
[data-testid="stBaseButton-secondary"]:hover {
  background: var(--shodh-surface-raised);
  border-color: var(--shodh-border-strong);
  color: var(--shodh-text);
}

[data-testid="stTextInput"] div[data-baseweb="input"] {
  border-radius: var(--shodh-radius);
  background: var(--shodh-bg);
  border: 1px solid var(--shodh-border-strong);
}
[data-testid="stTextInput"] div[data-baseweb="input"]:focus-within { border-color: var(--shodh-accent); }
[data-testid="stTextInput"] input { font-size: 14px; padding: 0.7rem 0.9rem; color: var(--shodh-text); }
[data-testid="stTextInput"] label p { font-size: 13px; font-weight: 600; color: var(--shodh-text); }

[data-testid="stExpander"] details {
  border-radius: var(--shodh-radius);
  border: 1px solid var(--shodh-border);
  background: var(--shodh-surface);
}
[data-testid="stExpander"] summary p { font-size: 13px; color: var(--shodh-muted); }

[data-baseweb="tab-list"] { gap: 0.25rem; }
[data-baseweb="tab"] { font-size: 14px; color: var(--shodh-muted); }
[data-baseweb="tab"][aria-selected="true"] { color: var(--shodh-text); }
[data-baseweb="tab-highlight"] { background-color: var(--shodh-accent); }
[data-baseweb="tab-border"] { background-color: var(--shodh-border); }

.st-key-input_card, [class*="st-key-report_body"], .st-key-error_card {
  box-sizing: border-box;
  width: 100% !important;
  max-width: 100%;
  background: var(--shodh-surface);
  border: 1px solid var(--shodh-border);
  border-radius: var(--shodh-radius);
  box-shadow: var(--shodh-shadow);
  padding: 1.1rem 1.25rem;
}
.st-key-input_card [data-testid="stElementContainer"],
[class*="st-key-report_body"] [data-testid="stElementContainer"],
.st-key-error_card [data-testid="stElementContainer"],
.st-key-input_card [data-testid="stMarkdown"],
[class*="st-key-report_body"] [data-testid="stMarkdown"],
.st-key-error_card [data-testid="stMarkdown"],
.st-key-input_card [data-testid="stTextInput"],
.st-key-input_card [data-baseweb="input"],
.st-key-input_card [data-baseweb="base-input"] {
  width: 100% !important;
  max-width: 100% !important;
  box-sizing: border-box;
}
.st-key-error_card { border-color: rgba(207, 107, 100, 0.35); }
[class*="st-key-report_body"] p, [class*="st-key-report_body"] li { font-size: 14px; line-height: 1.75; color: var(--shodh-text); }
[data-testid="stButtonGroup"] > div { display: flex; flex-wrap: nowrap; gap: 0.5rem; }
[data-testid="stBaseButton-pills"], [data-testid="stBaseButton-pillsActive"] {
  min-height: 0;
  padding: 0.3rem 0.8rem;
  border-radius: var(--shodh-radius);
  background: var(--shodh-surface);
  border: 1px solid var(--shodh-border);
  color: var(--shodh-muted);
  white-space: nowrap;
  transition: background-color 120ms ease, border-color 120ms ease, color 120ms ease;
}
[data-testid="stBaseButton-pills"] p, [data-testid="stBaseButton-pillsActive"] p { font-size: 13px !important; color: inherit; }
[data-testid="stBaseButton-pills"]:hover { border-color: var(--shodh-accent); color: var(--shodh-text); background: var(--shodh-surface-raised); }
@media (max-width: 640px) {
  [data-testid="stButtonGroup"] > div { flex-wrap: wrap; }
}
.st-key-history_list .stButton > button {
  width: 100%;
  justify-content: flex-start;
  text-align: left;
  font-size: 13px;
}

.shodh-header { display: flex; align-items: center; gap: 0.6rem; padding-top: 0.15rem; }
.shodh-logo {
  width: 30px; height: 30px; border-radius: 9px;
  background: var(--shodh-accent-soft); border: 1px solid rgba(124, 108, 242, 0.35);
  display: flex; align-items: center; justify-content: center;
}
.shodh-wordmark { font-size: 18px; font-weight: 700; color: var(--shodh-text); letter-spacing: -0.01em; }
.shodh-wordmark-sub { font-size: 13px; color: var(--shodh-faint); font-weight: 500; }
.shodh-tagline { font-size: 14px; color: var(--shodh-muted); margin: 0.35rem 0 1.1rem 0; }
.shodh-helper { font-size: 12.5px; color: var(--shodh-faint); margin-top: -0.35rem; }

.shodh-section-label {
  font-size: 11px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--shodh-faint); margin: 1.4rem 0 0.6rem 0;
}
.shodh-card {
  background: var(--shodh-surface);
  border: 1px solid var(--shodh-border);
  border-radius: var(--shodh-radius);
  box-shadow: var(--shodh-shadow);
  padding: 0.9rem 1rem;
  margin-bottom: 0.6rem;
  transition: border-color 120ms ease;
}
.shodh-card:hover { border-color: var(--shodh-border-strong); }

.shodh-capability-title { font-size: 14px; font-weight: 600; color: var(--shodh-text); margin-bottom: 0.25rem; }
.shodh-capability-body { font-size: 13px; color: var(--shodh-muted); line-height: 1.5; }

.shodh-stage { min-height: 6.4rem; }
.shodh-stage-head { display: flex; align-items: center; gap: 0.45rem; }
.shodh-stage-icon { font-size: 13px; width: 1rem; text-align: center; color: var(--shodh-faint); }
.shodh-stage-label { font-size: 14px; font-weight: 600; color: var(--shodh-muted); flex: 1; }
.shodh-stage-time { font-size: 12px; color: var(--shodh-faint); font-variant-numeric: tabular-nums; }
.shodh-stage-desc { font-size: 12.5px; color: var(--shodh-faint); line-height: 1.45; margin-top: 0.4rem; }
.shodh-stage-done .shodh-stage-icon { color: var(--shodh-green); }
.shodh-stage-done .shodh-stage-label { color: var(--shodh-text); }
.shodh-stage-done .shodh-stage-desc { color: var(--shodh-muted); }
.shodh-stage-active { border-color: rgba(124, 108, 242, 0.55); background: var(--shodh-accent-soft); }
.shodh-stage-active:hover { border-color: var(--shodh-accent); }
.shodh-stage-active .shodh-stage-icon, .shodh-stage-active .shodh-stage-label { color: var(--shodh-accent-hover); }
.shodh-stage-active .shodh-stage-desc { color: var(--shodh-text); }
.shodh-stage-failed { border-color: rgba(207, 107, 100, 0.45); }
.shodh-stage-failed .shodh-stage-icon, .shodh-stage-failed .shodh-stage-label { color: var(--shodh-red); }
.shodh-round { font-size: 12px; color: var(--shodh-accent-hover); background: var(--shodh-accent-soft);
  border-radius: var(--shodh-radius); padding: 0.1rem 0.5rem; margin-left: 0.5rem; letter-spacing: 0; text-transform: none; }

.shodh-metric-label { font-size: 12px; color: var(--shodh-faint); font-weight: 500; }
.shodh-metric-value { font-size: 20px; font-weight: 600; color: var(--shodh-text); margin-top: 0.2rem; font-variant-numeric: tabular-nums; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.shodh-question { font-size: 22px; font-weight: 600; color: var(--shodh-text); line-height: 1.35; margin: 0.4rem 0 0.6rem 0; }

.shodh-cite { font-size: 0.72em; line-height: 0; margin: 0 0.08em; }
.shodh-cite a, .shodh-chip {
  display: inline-block;
  border-radius: 6px;
  background: var(--shodh-accent-soft);
  color: var(--shodh-accent-hover) !important;
  padding: 0.1em 0.42em;
  font-weight: 600;
  text-decoration: none !important;
  transition: background-color 120ms ease;
}
.shodh-cite a:hover, a.shodh-chip:hover { background: rgba(124, 108, 242, 0.26); }
.shodh-cite-missing, .shodh-chip-missing { color: var(--shodh-faint) !important; background: var(--shodh-surface-raised); }
.shodh-chip { font-size: 12px; margin: 0.15rem 0.3rem 0 0; }

.shodh-claim-row { display: flex; gap: 0.9rem; align-items: flex-start; }
.shodh-claim-number { font-size: 13px; font-weight: 600; color: var(--shodh-faint); font-variant-numeric: tabular-nums; padding-top: 0.15rem; }
.shodh-claim-body { flex: 1; min-width: 0; }
.shodh-claim-text { font-size: 14.5px; color: var(--shodh-text); line-height: 1.55; }
.shodh-claim-reason { font-size: 13px; color: var(--shodh-muted); margin-top: 0.35rem; line-height: 1.5; }
.shodh-claim-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 0.3rem; margin-top: 0.5rem; }

.shodh-badge { display: inline-block; font-size: 11.5px; font-weight: 600; border-radius: 6px; padding: 0.15rem 0.5rem; margin-right: 0.3rem; }
.shodh-badge-supported { color: var(--shodh-green); background: var(--shodh-green-soft); }
.shodh-badge-weak { color: var(--shodh-amber); background: var(--shodh-amber-soft); }
.shodh-badge-unsupported { color: var(--shodh-red); background: var(--shodh-red-soft); }
.shodh-badge-pending { color: var(--shodh-faint); background: var(--shodh-surface-raised); }

.shodh-source-kicker { font-size: 11px; font-weight: 600; letter-spacing: 0.08em; color: var(--shodh-faint); }
.shodh-source-title { font-size: 14.5px; font-weight: 600; color: var(--shodh-text); margin: 0.3rem 0 0.15rem 0; overflow-wrap: anywhere; }
.shodh-source-domain { font-size: 12.5px; color: var(--shodh-muted); }
.shodh-source-link { font-size: 13px; font-weight: 500; display: inline-block; margin-top: 0.55rem; }

.shodh-side-label { font-size: 11px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--shodh-faint); }
.shodh-contradiction-sides { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 0.6rem; margin-top: 0.6rem; }
.shodh-contradiction-side { border: 1px solid var(--shodh-border); border-radius: var(--shodh-radius); padding: 0.6rem 0.75rem; background: var(--shodh-bg); }

.shodh-notice { border-radius: var(--shodh-radius); padding: 0.75rem 1rem; font-size: 13.5px; line-height: 1.5; margin-bottom: 0.8rem; border: 1px solid; }
.shodh-notice strong { font-weight: 600; }
.shodh-notice-warning { color: var(--shodh-amber); background: var(--shodh-amber-soft); border-color: rgba(201, 160, 79, 0.3); }
.shodh-notice-info { color: var(--shodh-muted); background: var(--shodh-surface); border-color: var(--shodh-border); }

.shodh-error-title { font-size: 17px; font-weight: 600; color: var(--shodh-text); }
.shodh-error-body { font-size: 14px; color: var(--shodh-muted); margin-top: 0.3rem; line-height: 1.55; }

.shodh-activity-line { font-size: 12.5px; color: var(--shodh-muted); font-family: ui-monospace, 'SFMono-Regular', Menlo, monospace; line-height: 1.7; overflow-wrap: anywhere; }
.shodh-activity-phase { color: var(--shodh-faint); margin-right: 0.5rem; }
.shodh-muted-text { font-size: 13px; color: var(--shodh-faint); }
</style>
"""

LOGO_SVG = (
    '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<circle cx="7" cy="7" r="4.25" stroke="#8d7ff5" stroke-width="1.6"/>'
    '<path d="M10.2 10.2L13.5 13.5" stroke="#8d7ff5" stroke-width="1.6" stroke-linecap="round"/>'
    '<circle cx="7" cy="7" r="1.4" fill="#8d7ff5"/>'
    "</svg>"
)

STAGE_ICONS: dict[str, str] = {
    STATUS_DONE: "✓",
    STATUS_ACTIVE: "●",
    STATUS_FAILED: "✕",
}
PENDING_ICON = "○"

VERDICT_BADGES: dict[str, tuple[str, str]] = {
    VERDICT_SUPPORTED: ("Supported", "shodh-badge-supported"),
    VERDICT_WEAK: ("Weakly supported", "shodh-badge-weak"),
    VERDICT_UNSUPPORTED: ("Unsupported", "shodh-badge-unsupported"),
    VERDICT_PENDING: ("Not yet verified", "shodh-badge-pending"),
}

CAPABILITIES: tuple[tuple[str, str], ...] = (
    ("Plans", "Breaks your question into focused sub-questions before touching the web."),
    ("Searches", "Runs a web search per sub-question and pulls the full text of the top sources."),
    ("Cross-checks", "A critic grades every claim against its cited evidence and re-searches weak ones."),
    ("Synthesizes", "Writes a report where every sentence carries a numbered, clickable citation."),
)


def escape_text(text: str) -> str:
    return html.escape(text.replace("\n", " "), quote=True)


def header_html() -> str:
    return (
        '<div class="shodh-header">'
        f'<div class="shodh-logo">{LOGO_SVG}</div>'
        '<div><div class="shodh-wordmark">Shodh</div><div class="shodh-wordmark-sub">Autonomous Research</div></div>'
        "</div>"
    )


def tagline_html() -> str:
    return (
        '<div class="shodh-tagline">An autonomous research workspace that plans, searches, '
        "cross-checks and synthesizes evidence.</div>"
    )


def helper_text_html(text: str) -> str:
    return f'<div class="shodh-helper">{escape_text(text)}</div>'


def section_label_html(text: str, round_number: int | None = None) -> str:
    round_badge = f'<span class="shodh-round">Round {round_number}</span>' if round_number else ""
    return f'<div class="shodh-section-label">{escape_text(text)}{round_badge}</div>'


def capability_card_html(title: str, body: str) -> str:
    return (
        '<div class="shodh-card">'
        f'<div class="shodh-capability-title">{escape_text(title)}</div>'
        f'<div class="shodh-capability-body">{escape_text(body)}</div>'
        "</div>"
    )


def stage_card_html(stage: StageView) -> str:
    icon = STAGE_ICONS.get(stage.status, PENDING_ICON)
    duration = format_duration(stage.duration_seconds) if stage.duration_seconds is not None else ""
    return (
        f'<div class="shodh-card shodh-stage shodh-stage-{stage.status}">'
        '<div class="shodh-stage-head">'
        f'<span class="shodh-stage-icon">{icon}</span>'
        f'<span class="shodh-stage-label">{escape_text(stage.label)}</span>'
        f'<span class="shodh-stage-time">{escape_text(duration)}</span>'
        "</div>"
        f'<div class="shodh-stage-desc">{escape_text(stage.description)}</div>'
        "</div>"
    )


def metric_card_html(label: str, value: str) -> str:
    return (
        '<div class="shodh-card">'
        f'<div class="shodh-metric-label">{escape_text(label)}</div>'
        f'<div class="shodh-metric-value">{escape_text(value)}</div>'
        "</div>"
    )


def question_heading_html(question: str) -> str:
    return f'<div class="shodh-question">{escape_text(question)}</div>'


def notice_html(tone: str, title: str, body: str) -> str:
    return (
        f'<div class="shodh-notice shodh-notice-{tone}">'
        f"<strong>{escape_text(title)}</strong> {escape_text(body)}"
        "</div>"
    )


def verdict_badge_html(verdict: str) -> str:
    label, css_class = VERDICT_BADGES.get(verdict, (verdict, "shodh-badge-pending"))
    return f'<span class="shodh-badge {css_class}">{escape_text(label)}</span>'


def citation_chip_html(citation: SourceView | int) -> str:
    if isinstance(citation, SourceView):
        return (
            f'<a class="shodh-chip" href="{escape_text(citation.url)}" target="_blank" '
            f'rel="noopener noreferrer" title="{escape_text(citation.title)}">[{citation.number}] '
            f"{escape_text(citation.domain)}</a>"
        )
    return f'<span class="shodh-chip shodh-chip-missing">[{citation}]</span>'


def claim_card_html(claim: ClaimView) -> str:
    reason = f'<div class="shodh-claim-reason">{escape_text(claim.reason)}</div>' if claim.reason else ""
    chips = "".join(citation_chip_html(citation) for citation in claim.citations)
    return (
        '<div class="shodh-card"><div class="shodh-claim-row">'
        f'<div class="shodh-claim-number">{claim.position:02d}</div>'
        '<div class="shodh-claim-body">'
        f'<div class="shodh-claim-text">{escape_text(claim.text)}</div>'
        f"{reason}"
        f'<div class="shodh-claim-meta">{verdict_badge_html(claim.verdict)}{chips}</div>'
        "</div></div></div>"
    )


def source_card_html(position: int, group: SourceGroupView) -> str:
    cited_as = " ".join(f"[{number}]" for number in group.numbers)
    return (
        '<div class="shodh-card">'
        f'<div class="shodh-source-kicker">SOURCE {position:02d} · CITED AS {escape_text(cited_as)}</div>'
        f'<div class="shodh-source-title">{escape_text(group.title)}</div>'
        f'<div class="shodh-source-domain">{escape_text(group.domain)}</div>'
        f'<a class="shodh-source-link" href="{escape_text(group.url)}" target="_blank" '
        'rel="noopener noreferrer">Open source ↗</a>'
        "</div>"
    )


def contradiction_side_html(label: str, source: SourceView | None, raw_number: object) -> str:
    if source is not None:
        body = citation_chip_html(source) + f'<div class="shodh-source-title">{escape_text(source.title)}</div>'
    else:
        body = f'<div class="shodh-muted-text">Source {escape_text(str(raw_number))} is not in the evidence list.</div>'
    return (
        '<div class="shodh-contradiction-side">'
        f'<div class="shodh-side-label">{escape_text(label)}</div>{body}'
        "</div>"
    )


def contradiction_card_html(contradiction: ContradictionView) -> str:
    note = f'<div class="shodh-claim-reason">{escape_text(contradiction.note)}</div>' if contradiction.note else ""
    return (
        '<div class="shodh-card">'
        f'<div class="shodh-claim-text">{escape_text(contradiction.claim)}</div>'
        f"{note}"
        '<div class="shodh-contradiction-sides">'
        f"{contradiction_side_html('Side A', contradiction.source_a, contradiction.source_a_number)}"
        f"{contradiction_side_html('Side B', contradiction.source_b, contradiction.source_b_number)}"
        "</div></div>"
    )


def error_heading_html(title: str, message: str) -> str:
    return (
        f'<div class="shodh-error-title">{escape_text(title)}</div>'
        f'<div class="shodh-error-body">{escape_text(message)}</div>'
    )


def activity_line_html(phase: str, note: str) -> str:
    return (
        '<div class="shodh-activity-line">'
        f'<span class="shodh-activity-phase">{escape_text(phase)}</span>{escape_text(note)}'
        "</div>"
    )
