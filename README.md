# Shodh (शोध) — Autonomous Research Agent

An autonomous research agent that plans multi-step search strategies, retrieves
and cross-examines web sources, detects contradictions, and produces
citation-grounded reports — with a self-critique loop and a quantified
evaluation benchmark, built from scratch without agent frameworks.

## Architecture

```
question
   │
   ▼
┌─────────────┐
│  PLANNING   │  planner.py — decompose into 2-5 sub-questions
└──────┬──────┘
       ▼
┌─────────────┐
│  SEARCHING  │◄─────────────────┐  executor.py — search, fetch, chunk, embed
└──────┬──────┘                  │
       ▼                         │
┌─────────────┐                  │
│SYNTHESIZING │  synthesizer.py — evidence → cited report + contradictions
└──────┬──────┘                  │
       ▼                         │
┌─────────────┐   weak claims /  │
│ CRITIQUING  │───gaps found─────┘  critic.py — grade claim-by-claim
└──────┬──────┘
       │ passes
       ▼
┌─────────────┐
│    DONE     │
└─────────────┘
```

Every phase transition is enforced by an explicit state machine
(`agent/state.py`) with hard ceilings on iteration count and token spend —
the agent cannot loop or spend forever, and fails loudly (`Phase.FAILED`)
when it hits a guard instead of silently running away.

## Why no agent framework

The planner → executor → synthesizer → critic loop, the state machine, and
the context-budget accounting are all hand-rolled. No LangChain, LlamaIndex,
or CrewAI. This was a deliberate choice: frameworks hide exactly the control
flow that's most worth understanding and being able to explain — how the
loop terminates, how retries are scoped, how budget is enforced. Every line
of orchestration here is one I can walk through on a whiteboard.

## How context budget works

`AgentState` tracks `tokens_used` and `iteration_count` against configurable
ceilings (`max_tokens`, `max_iterations`). `spend()` is called after every
fetch with a rough token estimate; `tick()` is called once per
search→synthesize→critique cycle. Either ceiling being crossed raises
`BudgetExceeded`, forces the state machine into `FAILED`, and the API layer
catches it and streams a clean stop event rather than crashing.

## Stack

| Layer | Choice | Why |
|---|---|---|
| Agent core | Python 3.12 + FastAPI | Industry default for AI systems work |
| LLM | Gemini API | Single provider, kept simple |
| Search | Tavily (free tier) | Purpose-built for LLM agent search |
| Fetch/clean | httpx + trafilatura | Boilerplate-free article extraction |
| Vector store | Chroma (embedded) | Zero infra, good enough for one-shot runs |
| Demo UI | Streamlit + SSE | Streams the live agent trace |
| Evals | pytest + custom harness | Quantifies agent vs. baseline |

## Setup

```bash
# from WSL
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# then fill in GEMINI_API_KEY and TAVILY_API_KEY in .env
```

### Run the API

```bash
uvicorn api.main:app --reload --port 8000
```

### Run the demo UI (in a second terminal)

```bash
streamlit run ui/app.py
```

### Run tests

```bash
pytest
```

### Run evals

```bash
python -m evals.run_evals --limit 5   # quick smoke test
python -m evals.run_evals             # full 30-question benchmark
```

## Benchmark results

> `evals/benchmark.jsonl` currently ships with 3 sample questions to prove
> the harness works end-to-end. Expand to 30 objectively-checkable questions
> (dates, figures, named entities, spanning multiple sources) before citing
> numbers on a resume.

| Metric | Baseline (single-pass RAG) | Shodh (agent) | Δ |
|---|---|---|---|
| Citation accuracy | — | — | — |
| Factual precision | — | — | — |

Run `python -m evals.run_evals` and paste the printed table here.

## Scope (deliberately out)

Multi-agent setups, auth/users, multiple model providers, PDF ingestion,
chat history. Single question → single report. Depth over surface.

## Project layout

```
shodh/
├── agent/
│   ├── planner.py        # question → research plan (sub-questions)
│   ├── executor.py       # tool loop: search, fetch, extract
│   ├── state.py           # agent state machine + context budget
│   ├── tools.py           # search / fetch / extract tool definitions
│   ├── synthesizer.py     # claims → cited report
│   └── critic.py          # self-critique + targeted re-retrieval
├── retrieval/
│   ├── store.py            # Chroma wrapper, chunking
│   └── ranker.py            # dedupe + rerank fetched evidence
├── evals/
│   ├── benchmark.jsonl      # questions w/ verifiable answers
│   ├── run_evals.py          # agent vs single-pass RAG baseline
│   └── metrics.py             # citation accuracy, factual precision
├── api/main.py                 # FastAPI endpoints (SSE streaming)
├── ui/app.py                    # Streamlit demo
├── tests/
└── README.md
```
