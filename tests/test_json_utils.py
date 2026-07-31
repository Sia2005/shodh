"""
Tests for agent.json_utils.strip_to_json -- the deterministic half of the
malformed-JSON fix. The retry half needs a live model, so it isn't
covered here.

Cases marked "observed" are verbatim from the 30-question eval run that
motivated the fix (see evals/results.md pipeline-errors table).
"""

from __future__ import annotations

import json

from agent.json_utils import strip_to_json


def test_plain_json_passes_through():
    assert strip_to_json('["a", "b"]') == '["a", "b"]'


def test_strips_markdown_fences():
    assert strip_to_json('```json\n["a", "b"]\n```') == '["a", "b"]'


def test_strips_stray_equals_after_opening_bracket():
    # Observed: '[="What are the results of the 2026 Tamil Nadu..."]'
    assert strip_to_json('[="a", "b"]') == '["a", "b"]'


def test_strips_prose_before_and_after_payload():
    raw = 'Here is the JSON:\n["a", "b"]\nLet me know if you need more.'
    assert strip_to_json(raw) == '["a", "b"]'


def test_handles_object_payload():
    assert strip_to_json('Sure!\n{"claims": []}') == '{"claims": []}'


def test_stripped_output_is_parseable():
    for raw in ('```json\n["a"]\n```', '[="a"]', 'Here:\n{"k": 1}'):
        json.loads(strip_to_json(raw))


def test_leaves_unrepairable_junk_alone():
    # Unquoted elements can't be fixed without guessing at intent -- these
    # are what the one retry exists for, so strip_to_json must not mangle
    # them into something that parses as the wrong thing.
    raw = "[Who won the 2026 West Bengal election?, Which party won?]"
    assert strip_to_json(raw) == raw
