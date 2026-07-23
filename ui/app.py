"""
Streamlit demo: submits a question to the FastAPI /research SSE endpoint
and renders the live agent trace — plan, searches firing, critique
rewriting sections. This trace is the demo video.

Run locally (with the API already running on :8000):
    streamlit run ui/app.py
"""

import json
import os

import httpx
import streamlit as st

API_URL = os.environ.get("SHODH_API_URL", "http://localhost:8000")

st.set_page_config(page_title="Shodh — Research Agent", page_icon="🔎", layout="wide")
st.title("🔎 Shodh — Autonomous Research Agent")
st.caption("Plans multi-step search, cross-examines sources, self-critiques, cites everything.")

question = st.text_input("Research question", placeholder="e.g. How has India's UPI transaction volume changed since 2022?")
run = st.button("Run research", type="primary", disabled=not question)

trace_box = st.empty()
report_box = st.empty()

if run:
    trace_lines: list[str] = []
    with httpx.stream("POST", f"{API_URL}/research", json={"question": question}, timeout=None) as resp:
        for line in resp.iter_lines():
            if not line or not line.startswith("data: "):
                continue
            payload = json.loads(line[len("data: "):])

            phase = payload.get("phase", "?")
            note = payload.get("note", "")
            trace_lines.append(f"**[{phase}]** {note}")
            trace_box.markdown("\n\n".join(trace_lines[-15:]))

            if phase == "DONE":
                report_box.success("Research complete.")
