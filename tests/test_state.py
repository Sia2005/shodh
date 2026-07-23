import pytest

from agent.state import AgentState, BudgetExceeded, Phase


def test_legal_transition():
    state = AgentState(question="test")
    state.advance(Phase.SEARCHING)
    assert state.phase == Phase.SEARCHING


def test_illegal_transition_rejected():
    state = AgentState(question="test")
    with pytest.raises(ValueError):
        state.advance(Phase.DONE)  # can't skip straight from PLANNING to DONE


def test_token_budget_enforced():
    state = AgentState(question="test", max_tokens=100)
    state.spend(50)
    assert state.tokens_used == 50
    with pytest.raises(BudgetExceeded):
        state.spend(100)
    assert state.phase == Phase.FAILED


def test_iteration_budget_enforced():
    state = AgentState(question="test", max_iterations=2)
    state.tick()
    state.tick()
    with pytest.raises(BudgetExceeded):
        state.tick()
    assert state.phase == Phase.FAILED


def test_critiquing_can_loop_back_to_searching():
    state = AgentState(question="test")
    state.advance(Phase.SEARCHING)
    state.advance(Phase.SYNTHESIZING)
    state.advance(Phase.CRITIQUING)
    state.advance(Phase.SEARCHING, "gap found, re-searching")
    assert state.phase == Phase.SEARCHING
