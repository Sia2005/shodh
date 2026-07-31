"""
Tests for agent.planner._validate -- the repair-or-reject callback handed
to json_utils.generate_json. Covers the deterministic [[...]] flatten
(observed in the eval run as q009) and the reject paths that hand off to
the single retry.
"""

from __future__ import annotations

import pytest

from agent.planner import _validate


def test_flat_list_passes_through():
    qs = ["Who won?", "Which party?"]
    assert _validate(qs) == qs


def test_flattens_one_level_of_nesting():
    # Observed: [['What is the projected population?']]
    assert _validate([["What is the projected population?"]]) == [
        "What is the projected population?"
    ]


def test_flattens_multiple_inner_lists_one_level():
    assert _validate([["a", "b"], ["c"]]) == ["a", "b", "c"]


def test_rejects_double_nesting_after_one_flatten():
    # Flattening one level of [[["a"]]] leaves [["a"]], still not a list of
    # strings -- must raise so generate_json's retry fires, not silently
    # return garbage.
    with pytest.raises(ValueError):
        _validate([[["a"]]])


def test_rejects_non_list():
    with pytest.raises(ValueError):
        _validate({"sub_questions": ["a"]})


def test_rejects_mixed_element_types():
    with pytest.raises(ValueError):
        _validate(["a", 2])
